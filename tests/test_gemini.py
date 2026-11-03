import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from services.gemini_service import GeminiAnalysisError, _normalize, analyze_notice
import app as project


class FakeResponse:
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, *args):
        return b""


class GeminiTests(unittest.TestCase):
    def test_normalize_unknown_date(self):
        data = {"title": "과제", "course": "", "due_date": "10월 24일",
                "summary": "설명", "deliverables": ["PDF"], "tasks": ["보고서 작성"]}
        self.assertEqual(_normalize(data)["due_date"], "")

    def test_missing_key(self):
        with patch.dict("os.environ", {"GEMINI_API_KEY": ""}):
            with self.assertRaises(GeminiAnalysisError):
                analyze_notice("공지")

    def test_success_with_mocked_api(self):
        data = {"title": "운영체제 과제", "course": "운영체제",
                "due_date": "2026-11-20", "summary": "보고서 작성",
                "deliverables": ["PDF"], "tasks": ["자료 조사"]}
        payload = {"candidates": [{"content": {"parts": [{"text": json.dumps(data)}]}}]}
        class MockResponse:
            def __enter__(self): return self
            def __exit__(self, *args): return False
        with patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}):
            with patch("services.gemini_service.urlopen") as mock_open:
                mock_open.return_value.__enter__.return_value = MockResponse()
                with patch("services.gemini_service.json.load", return_value=payload):
                    result = analyze_notice("과제 공지")
        self.assertEqual(result["title"], "운영체제 과제")

    def test_web_route_without_key(self):
        client = project.create_app({"TESTING": True, "SECRET_KEY": "test-secret"}).test_client()
        client.get("/ai/analyze")
        with client.session_transaction() as session:
            token = session["csrf_token"]
        with patch.dict("os.environ", {"GEMINI_API_KEY": ""}):
            response = client.post("/ai/analyze", data={"csrf_token": token, "notice": "과제 공지"})
        self.assertEqual(response.status_code, 502)
        self.assertIn("API 키", response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
