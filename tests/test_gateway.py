import json
import tempfile
import unittest
from pathlib import Path

import match_gateway


class MatchGatewayTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_job_dir = match_gateway.JOB_DIR
        self.original_result_dir = match_gateway.RESULT_DIR
        self.original_preview_job_dir = match_gateway.PREVIEW_JOB_DIR
        self.original_preview_result_dir = match_gateway.PREVIEW_RESULT_DIR
        match_gateway.JOB_DIR = Path(self.temp_dir.name) / "match_jobs"
        match_gateway.RESULT_DIR = Path(self.temp_dir.name) / "match_results"
        match_gateway.PREVIEW_JOB_DIR = Path(self.temp_dir.name) / "preview_jobs"
        match_gateway.PREVIEW_RESULT_DIR = Path(self.temp_dir.name) / "preview_results"

    def tearDown(self):
        match_gateway.JOB_DIR = self.original_job_dir
        match_gateway.RESULT_DIR = self.original_result_dir
        match_gateway.PREVIEW_JOB_DIR = self.original_preview_job_dir
        match_gateway.PREVIEW_RESULT_DIR = self.original_preview_result_dir
        self.temp_dir.cleanup()

    def test_worker_result_is_saved_with_authenticated_worker_id(self):
        request_id = "a" * 32
        match_gateway.JOB_DIR.mkdir(parents=True)
        (match_gateway.JOB_DIR / f"{request_id}.json").write_text("{}", encoding="utf-8")
        match_gateway.save_match_result(
            {
                "type": "match_result",
                "requestId": request_id,
                "workerId": "untrusted-id",
                "ok": True,
                "matched": True,
                "matches": [{"imageIndex": 1, "similarity": 0.9}],
            },
            "trusted-worker",
        )

        result = json.loads(
            (match_gateway.RESULT_DIR / f"{request_id}.json").read_text(encoding="utf-8")
        )
        self.assertEqual(result["workerId"], "trusted-worker")
        self.assertIn("receivedAt", result)

    def test_invalid_request_id_is_rejected(self):
        with self.assertRaises(ValueError):
            match_gateway.save_match_result(
                {"type": "match_result", "requestId": "../invalid", "ok": True},
                "trusted-worker",
            )

    def test_unknown_request_id_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown requestId"):
            match_gateway.save_match_result(
                {"type": "match_result", "requestId": "b" * 32, "ok": True},
                "trusted-worker",
            )

    def test_preview_result_is_saved_for_existing_job(self):
        request_id = "c" * 32
        match_gateway.PREVIEW_JOB_DIR.mkdir(parents=True)
        (match_gateway.PREVIEW_JOB_DIR / f"{request_id}.json").write_text(
            "{}", encoding="utf-8"
        )
        match_gateway.save_preview_result(
            {
                "type": "preview_result",
                "requestId": request_id,
                "success": True,
                "imageUrls": ["https://example.com/look.png"],
            },
            "preview-worker-01",
        )

        result = json.loads(
            (match_gateway.PREVIEW_RESULT_DIR / f"{request_id}.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(result["workerId"], "preview-worker-01")
        self.assertTrue(result["success"])

    def test_single_worker_channel_handles_both_result_types(self):
        channel = match_gateway.worker_channel("/ws/matcher")

        self.assertIsNotNone(channel)
        self.assertEqual(channel["token"], match_gateway.MATCHER_TOKEN)
        self.assertEqual(
            set(channel["resultHandlers"]),
            {"match_result", "preview_result"},
        )
        self.assertIsNone(match_gateway.worker_channel("/ws/preview"))


if __name__ == "__main__":
    unittest.main()
