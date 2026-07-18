import io
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

import app as lace_app


class LaceWebsiteTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.pattern_dir = root / "pattern"
        self.pattern_dir.mkdir()
        self.upload_dir = root / "uploads"
        self.data_dir = root / "data"
        self.thumbnail_dir = root / "thumbnails"
        self.work_orders_file = self.data_dir / "design_work_orders.jsonl"

        for index in range(1, 12):
            Image.new("RGB", (40, 40), (index * 10, 80, 100)).save(self.pattern_dir / f"{index}.png")

        self.original_paths = (
            lace_app.PATTERN_DIR,
            lace_app.UPLOAD_DIR,
            lace_app.DATA_DIR,
            lace_app.THUMBNAIL_DIR,
            lace_app.WORK_ORDERS_FILE,
        )
        lace_app.PATTERN_DIR = self.pattern_dir
        lace_app.UPLOAD_DIR = self.upload_dir
        lace_app.DATA_DIR = self.data_dir
        lace_app.THUMBNAIL_DIR = self.thumbnail_dir
        lace_app.WORK_ORDERS_FILE = self.work_orders_file
        lace_app.app.config.update(TESTING=True)
        self.client = lace_app.app.test_client()

    def tearDown(self):
        (
            lace_app.PATTERN_DIR,
            lace_app.UPLOAD_DIR,
            lace_app.DATA_DIR,
            lace_app.THUMBNAIL_DIR,
            lace_app.WORK_ORDERS_FILE,
        ) = self.original_paths
        self.temp_dir.cleanup()

    def upload(self, filename):
        return self.client.post(
            "/api/match",
            data={"pattern": (io.BytesIO(b"test image payload"), filename)},
            content_type="multipart/form-data",
        )

    def test_home_displays_only_top_ten(self):
        response = self.client.get("/")
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("本月精选", body)
        self.assertIn("Top 10", body)
        self.assertIn('class="design-workbench"', body)
        self.assertLess(body.index('id="collection"'), body.index('id="recognition"'))
        self.assertEqual(body.count('class="pattern-image pattern-detail-trigger"'), 10)
        self.assertIn('id="patternModal"', body)
        self.assertIn("推荐理由", body)
        self.assertIn("适用方向", body)
        self.assertIn("创建设计工单", body)
        self.assertIn("登记客户信息", body)
        self.assertIn("10.png", body)
        self.assertNotIn("11.png", body)

    def test_matching_uses_filename(self):
        matched = self.upload("1.png")
        missing = self.upload("unknown.png")
        self.assertTrue(matched.get_json()["matched"])
        self.assertEqual(matched.get_json()["message"], "匹配成功")
        self.assertFalse(missing.get_json()["matched"])
        self.assertEqual(missing.get_json()["message"], "暂未找到您想要的款式")

    def test_thumbnail_route_returns_webp(self):
        response = self.client.get("/pattern-images/1.png")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "image/webp")
        response.close()

    def test_design_work_order_is_created(self):
        response = self.client.post(
            "/api/work-orders",
            json={
                "customerName": "测试客户",
                "customerContact": "13800000000",
                "uploadFileName": "custom.png",
                "matchStatus": "not_matched",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertRegex(response.get_json()["workOrderNo"], r"^LS-\d{8}-[A-F0-9]{8}$")
        record = json.loads(self.work_orders_file.read_text(encoding="utf-8"))
        self.assertEqual(record["customerName"], "测试客户")
        self.assertEqual(record["uploadFileName"], "custom.png")
        self.assertEqual(record["matchStatus"], "not_matched")
        self.assertEqual(record["status"], "pending")

    def test_matched_pattern_cannot_create_work_order(self):
        response = self.client.post(
            "/api/work-orders",
            json={
                "customerName": "测试客户",
                "customerContact": "13800000000",
                "uploadFileName": "1.png",
                "matchStatus": "matched",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.get_json()["ok"])

    def test_preview_placeholder(self):
        response = self.client.get("/preview?pattern=1.png")
        self.assertEqual(response.status_code, 200)
        self.assertIn("成衣效果，正在打版", response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
