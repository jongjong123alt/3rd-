import json
import unittest
from unittest.mock import MagicMock, patch

from google.genai import errors

from services import gemini_models
from services.gemini_service import GeminiAnalysisError, analyze_notice


def _payload():
    return json.dumps({"title": "보고서", "course": "운영체제", "due_date": "", "summary": "요약",
                       "deliverables": [], "tasks": []}, ensure_ascii=False)


class ModelFallbackTests(unittest.TestCase):
    def test_candidates_start_with_configured_model_and_dedupe(self):
        with patch.dict("os.environ", {"GEMINI_MODEL": "gemini-3.5-flash-lite"}, clear=False):
            models = gemini_models.candidate_models()
        self.assertEqual(models[0], "gemini-3.5-flash-lite")
        self.assertEqual(len(models), len(set(models)))

    def test_invalid_model_name_rejected(self):
        with patch.dict("os.environ", {"GEMINI_API_KEY": "k", "GEMINI_MODEL": "bad model!"}):
            with self.assertRaises(GeminiAnalysisError):
                analyze_notice("공지")

    def test_retired_model_404_falls_back_once(self):
        client = MagicMock()
        ok = MagicMock(text=_payload(), candidates=[])
        client.models.generate_content.side_effect = [errors.APIError(404, {}), ok]
        sdk = MagicMock(); sdk.__enter__.return_value = client
        env = {"GEMINI_API_KEY": "k", "GEMINI_MODEL": "gemini-2.5-flash", "GEMINI_FALLBACK_MODELS": "gemini-3.5-flash-lite"}
        with patch.dict("os.environ", env), patch("services.gemini_service.genai.Client", return_value=sdk):
            result = analyze_notice("운영체제 보고서 공지")
        self.assertEqual(result["title"], "보고서")
        used = [c.kwargs["model"] for c in client.models.generate_content.call_args_list]
        self.assertEqual(used, ["gemini-2.5-flash", "gemini-3.5-flash-lite"])

    def test_other_errors_do_not_switch_models(self):
        client = MagicMock()
        client.models.generate_content.side_effect = errors.ServerError(503, {})
        sdk = MagicMock(); sdk.__enter__.return_value = client
        env = {"GEMINI_API_KEY": "k", "GEMINI_MODEL": "gemini-3.5-flash-lite", "GEMINI_FALLBACK_MODELS": "gemini-3.8-flash"}
        with patch.dict("os.environ", env), patch("services.gemini_service.genai.Client", return_value=sdk):
            with self.assertRaises(GeminiAnalysisError):
                analyze_notice("공지")
        self.assertEqual(client.models.generate_content.call_count, 1)

    def test_all_models_retired_reports_clear_message(self):
        client = MagicMock()
        client.models.generate_content.side_effect = errors.APIError(404, {})
        sdk = MagicMock(); sdk.__enter__.return_value = client
        env = {"GEMINI_API_KEY": "k", "GEMINI_MODEL": "gemini-2.5-flash", "GEMINI_FALLBACK_MODELS": "gemini-old-x"}
        with patch.dict("os.environ", env), patch("services.gemini_service.genai.Client", return_value=sdk):
            with self.assertRaises(GeminiAnalysisError) as ctx:
                analyze_notice("공지")
        self.assertIn("404", str(ctx.exception))
        self.assertEqual(client.models.generate_content.call_count, 2)


if __name__ == "__main__":
    unittest.main()
