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
        fake_client = Mock()
        fake_client.models.generate_content.return_value.text = json.dumps(data, ensure_ascii=False)
        context = Mock()
        context.__enter__ = Mock(return_value=fake_client)
        context.__exit__ = Mock(return_value=False)
        with patch.dict("os.environ", {"GEMINI_API_KEY": "test-key", "GEMINI_MODEL": "gemini-2.5-flash"}):
            with patch("services.gemini_service.genai.Client", return_value=context) as client_factory:
                result = analyze_notice("과제 공지")
        options = client_factory.call_args.kwargs["http_options"]
        self.assertEqual(options.timeout, 20000)
        self.assertEqual(options.retry_options.attempts, 2)
        self.assertEqual(fake_client.models.generate_content.call_args.kwargs["model"], "gemini-2.5-flash")
        self.assertIn("과제 공지", fake_client.models.generate_content.call_args.kwargs["contents"])
        config = fake_client.models.generate_content.call_args.kwargs["config"]
        self.assertEqual(config.max_output_tokens, 4096)
        self.assertEqual(config.response_mime_type, "application/json")
        self.assertEqual(config.response_json_schema["type"], "object")
        self.assertEqual(result["title"], "운영체제 과제")

    def test_server_overload_message(self):
        from google.genai import errors
        for code, expected in ((503, "503"), (504, "504"), (429, "429")):
            with self.subTest(code=code):
                context = Mock()
                context.__enter__ = Mock(side_effect=errors.ServerError(code, {"error": {"message": "temporary"}}))
                context.__exit__ = Mock(return_value=False)
                with patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}):
                    with patch("services.gemini_service.genai.Client", return_value=context):
                        with self.assertRaises(GeminiAnalysisError) as caught:
                            analyze_notice("과제 공지")
                self.assertIn(expected, str(caught.exception))

    def test_truncated_response_message(self):
        response = Mock()
        response.text = '{"title":"미완성'
        response.candidates = [Mock(finish_reason="MAX_TOKENS")]
        fake_client = Mock()
        fake_client.models.generate_content.return_value = response
        context = Mock()
        context.__enter__ = Mock(return_value=fake_client)
        context.__exit__ = Mock(return_value=False)
        with patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}):
            with patch("services.gemini_service.genai.Client", return_value=context):
                with self.assertRaises(GeminiAnalysisError) as caught:
                    analyze_notice("과제 공지")
        self.assertIn("길이 제한", str(caught.exception))

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
