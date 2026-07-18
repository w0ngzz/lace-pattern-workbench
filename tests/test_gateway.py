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
        match_gateway.JOB_DIR = Path(self.temp_dir.name) / "match_jobs"
        match_gateway.RESULT_DIR = Path(self.temp_dir.name) / "match_results"

    def tearDown(self):
        match_gateway.JOB_DIR = self.original_job_dir
        match_gateway.RESULT_DIR = self.original_result_dir
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


if __name__ == "__main__":
    unittest.main()
