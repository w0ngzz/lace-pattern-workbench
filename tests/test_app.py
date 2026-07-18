import io
import json
import tempfile
import time
import unittest
from pathlib import Path

from PIL import Image

import app as lace_app


class LaceWebsiteTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.top10_dir = root / "pattern" / "top10"
        self.library_dir = root / "pattern" / "library"
        self.library_original_dir = self.library_dir / "pic" / "originals"
        self.library_thumbnail_dir = self.library_dir / "pic" / "thumbnails"
        self.library_data_dir = self.library_dir / "data"
        self.top10_dir.mkdir(parents=True)
        self.library_original_dir.mkdir(parents=True)
        self.library_thumbnail_dir.mkdir(parents=True)
        self.library_data_dir.mkdir(parents=True)
        self.upload_dir = root / "uploads"
        self.data_dir = root / "data"
        self.thumbnail_dir = root / "thumbnails"
        self.work_orders_file = self.data_dir / "design_work_orders.jsonl"
        self.material_upload_db = self.data_dir / "material_catalog.db"
        self.material_upload_original_dir = self.data_dir / "material_library" / "originals"
        self.material_upload_thumbnail_dir = self.data_dir / "material_library" / "thumbnails"
        self.matcher_state_file = root / "runtime" / "matcher_status.json"
        self.matcher_request_dir = root / "runtime" / "match_requests"
        self.matcher_state_file.parent.mkdir()
        self.matcher_state_file.write_text(
            json.dumps({"online": True, "workerId": "test-worker", "updatedAt": time.time()}),
            encoding="utf-8",
        )

        for index in range(1, 12):
            Image.new("RGB", (40, 40), (index * 10, 80, 100)).save(self.top10_dir / f"{index}.png")
        Image.new("RGB", (40, 40), (10, 80, 100)).save(self.library_original_dir / "1.png")
        Image.new("RGB", (24, 24), (10, 80, 100)).save(self.library_thumbnail_dir / "1_thumb.jpg")
        (self.library_data_dir / "styles.csv").write_text(
            "编号ID,款式名称,花纹类型,季度,上市状态,销量(米),销售额(元),订单数,环比增长,期末库存(米)\n"
            "1,LACE-001,巴洛克纹,2026Q1,在售,68,3740,1,0.10,4490\n"
            "1,LACE-001,巴洛克纹,2026Q2,在售,118,6490,2,0.20,4372\n",
            encoding="utf-8-sig",
        )

        self.original_paths = (
            lace_app.TOP10_DIR,
            lace_app.MATERIAL_LIBRARY_DIR,
            lace_app.MATERIAL_ORIGINAL_DIR,
            lace_app.MATERIAL_THUMBNAIL_DIR,
            lace_app.MATERIAL_DATA_DIR,
            lace_app.MATERIAL_UPLOAD_DB,
            lace_app.MATERIAL_UPLOAD_ORIGINAL_DIR,
            lace_app.MATERIAL_UPLOAD_THUMBNAIL_DIR,
            lace_app.UPLOAD_DIR,
            lace_app.DATA_DIR,
            lace_app.THUMBNAIL_DIR,
            lace_app.WORK_ORDERS_FILE,
            lace_app.MATCHER_STATE_FILE,
            lace_app.MATCHER_REQUEST_DIR,
        )
        lace_app.TOP10_DIR = self.top10_dir
        lace_app.MATERIAL_LIBRARY_DIR = self.library_dir
        lace_app.MATERIAL_ORIGINAL_DIR = self.library_original_dir
        lace_app.MATERIAL_THUMBNAIL_DIR = self.library_thumbnail_dir
        lace_app.MATERIAL_DATA_DIR = self.library_data_dir
        lace_app.MATERIAL_UPLOAD_DB = self.material_upload_db
        lace_app.MATERIAL_UPLOAD_ORIGINAL_DIR = self.material_upload_original_dir
        lace_app.MATERIAL_UPLOAD_THUMBNAIL_DIR = self.material_upload_thumbnail_dir
        lace_app.UPLOAD_DIR = self.upload_dir
        lace_app.DATA_DIR = self.data_dir
        lace_app.THUMBNAIL_DIR = self.thumbnail_dir
        lace_app.WORK_ORDERS_FILE = self.work_orders_file
        lace_app.MATCHER_STATE_FILE = self.matcher_state_file
        lace_app.MATCHER_REQUEST_DIR = self.matcher_request_dir
        self.original_material_upload_token = lace_app.app.config.get("MATERIAL_UPLOAD_TOKEN")
        lace_app.app.config.update(TESTING=True, MATERIAL_UPLOAD_TOKEN="test-material-token")
        self.client = lace_app.app.test_client()

    def tearDown(self):
        (
            lace_app.TOP10_DIR,
            lace_app.MATERIAL_LIBRARY_DIR,
            lace_app.MATERIAL_ORIGINAL_DIR,
            lace_app.MATERIAL_THUMBNAIL_DIR,
            lace_app.MATERIAL_DATA_DIR,
            lace_app.MATERIAL_UPLOAD_DB,
            lace_app.MATERIAL_UPLOAD_ORIGINAL_DIR,
            lace_app.MATERIAL_UPLOAD_THUMBNAIL_DIR,
            lace_app.UPLOAD_DIR,
            lace_app.DATA_DIR,
            lace_app.THUMBNAIL_DIR,
            lace_app.WORK_ORDERS_FILE,
            lace_app.MATCHER_STATE_FILE,
            lace_app.MATCHER_REQUEST_DIR,
        ) = self.original_paths
        lace_app.app.config["MATERIAL_UPLOAD_TOKEN"] = self.original_material_upload_token
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
        self.assertIn("蕾智创库", body)
        self.assertIn("images/logo.svg", body)
        self.assertIn("images/favicon.svg", body)
        self.assertNotIn('id="matcherStatus"', body)
        self.assertIn("本月精选", body)
        self.assertIn("Top 10", body)
        self.assertIn("浏览本店素材库", body)
        self.assertIn('href="/library"', body)
        self.assertIn("客户图案智能匹配", body)
        self.assertIn('id="matchSteps"', body)
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
        requests = list(self.matcher_request_dir.glob("*.json"))
        self.assertEqual(len(requests), 2)
        self.assertTrue(all(json.loads(path.read_text(encoding="utf-8"))["type"] == "match_request" for path in requests))

    def test_matching_is_rejected_when_worker_is_offline(self):
        self.matcher_state_file.write_text(
            json.dumps({"online": False, "workerId": None, "updatedAt": time.time()}),
            encoding="utf-8",
        )
        response = self.upload("1.png")
        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.get_json()["ok"])
        self.assertIn("不在线", response.get_json()["message"])
        self.assertFalse(self.upload_dir.exists())

    def test_thumbnail_route_returns_webp(self):
        response = self.client.get("/pattern-images/1.png")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "image/webp")
        response.close()

    def test_material_library_page_uses_private_catalog_data(self):
        response = self.client.get("/library")
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("本店素材库", body)
        self.assertIn("LACE-001", body)
        self.assertIn("巴洛克纹", body)
        self.assertIn('id="libraryGrid"', body)
        self.assertIn('id="categoryFilter"', body)
        self.assertIn('id="widthFilter"', body)
        self.assertIn('id="materialFilter"', body)
        self.assertIn('id="usageFilter"', body)
        self.assertIn('id="colorFilter"', body)
        self.assertIn('id="libraryPagination"', body)
        self.assertIn('data-sales="186.0"', body)
        self.assertIn("/library-thumbnails/1_thumb.jpg", body)

    def test_material_library_thumbnail_route(self):
        response = self.client.get("/library-thumbnails/1_thumb.jpg")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "image/jpeg")
        response.close()

    def test_material_upload_requires_bearer_token(self):
        response = self.client.post("/api/library/materials", json={"styleId": 81})
        self.assertEqual(response.status_code, 401)
        self.assertFalse(response.get_json()["ok"])

    def test_material_upload_persists_metadata_and_image(self):
        image = io.BytesIO()
        Image.new("RGB", (60, 40), (180, 90, 70)).save(image, "PNG")
        image.seek(0)
        response = self.client.post(
            "/api/library/materials",
            headers={"Authorization": "Bearer test-material-token"},
            data={
                "styleId": "81",
                "code": "LACE-081",
                "category": "植物花卉纹",
                "width": "150cm",
                "material": "锦纶混纺",
                "usage": "礼服",
                "color": "象牙白",
                "description": "适合轻礼服罩层。",
                "image": (image, "sample.png"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.get_json()["ok"])
        self.assertTrue(self.material_upload_db.is_file())
        self.assertTrue((self.material_upload_original_dir / "81.png").is_file())
        self.assertTrue((self.material_upload_thumbnail_dir / "81_thumb.webp").is_file())

        library_response = self.client.get("/library")
        body = library_response.get_data(as_text=True)
        self.assertIn("LACE-081", body)
        self.assertIn('data-width="150cm"', body)
        self.assertIn('data-material="锦纶混纺"', body)
        self.assertIn("/uploaded-library-thumbnails/81_thumb.webp", body)

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
