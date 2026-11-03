import json
import unittest
from unittest.mock import Mock, patch

from services.gemini_service import GeminiAnalysisError, _normalize, _parse_response, analyze_notice
import app as project


class GeminiTests(unittest.TestCase):
    def test_normalize_unknown_date(self):
        data = {"title": "과제", "course": "", "due_date": "10월 24일",
                "summary": "설명", "deliverables": ["PDF"], "tasks": ["보고서 작성"]}
        self.assertEqual(_normalize(data)["due_date"], "")

    def test_missing_key(self):
        with patch.dict("os.environ", {"GEMINI_API_KEY": ""}):
            with self.assertRaises(GeminiAnalysisError):
                analyze_notice("공지")

    def test_sdk_generate_content_and_json_parsing(self):
        data = {"title": "운영체제 과제", "course": "운영체제",
                "due_date": "2026-11-20", "summary": "보고서 작성",
                "deliverables": ["PDF"], "tasks": ["자료 조사"]}
        fake_model = Mock()
        fake_model.generate_content.return_value.text = json.dumps(data, ensure_ascii=False)
        with patch.dict("os.environ", {"GEMINI_API_KEY": "test-key", "GEMINI_MODEL": "gemini-2.5-flash"}):
            with patch("services.gemini_service.genai.configure") as configure:
                with patch("services.gemini_service.genai.GenerativeModel", return_value=fake_model):
                    result = analyze_notice("과제 공지")
        configure.assert_called_once_with(api_key="test-key")
        self.assertIn("과제 공지", fake_model.generate_content.call_args.args[0])
        self.assertEqual(result["title"], "운영체제 과제")

    def test_invalid_json(self):
        with self.assertRaises(GeminiAnalysisError):
            _parse_response("잘못된 응답")

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
