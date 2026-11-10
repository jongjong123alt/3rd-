"""F-19~F-21 regression tests: no real Gemini calls or browser permissions."""
import io
import json
import os
import unittest
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import app as project
from services.gemini_service import GeminiAnalysisError, analyze_document
from services.plan_service import PlanError


class NewFeaturesTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.db_patch = patch.object(project, "DB_PATH", Path(self.temp.name) / "data.db")
        self.db_patch.start()
        self.client = project.create_app({"TESTING": True, "SECRET_KEY": "test"}).test_client()
        self.client.get("/")
        with self.client.session_transaction() as sess:
            self.token = sess["csrf_token"]

    def tearDown(self):
        self.db_patch.stop()
        self.temp.cleanup()

    def post(self, path, **data):
        return self.client.post(path, data={"csrf_token": self.token, **data})

    def create(self, title="테스트 과제", due=None):
        response = self.post("/assignments/new", title=title, course="운영체제",
                             description="자료 조사", due_date=due or "",
                             status="todo", priority="medium")
        self.assertEqual(response.status_code, 302)
        with project.connect_db() as db:
            return db.execute("SELECT id FROM assignments WHERE title=?", (title,)).fetchone()[0]

    def test_f19_pdf_png_jpeg_multimodal_route_and_preview(self):
        answer = {"title": "과제 공지", "course": "자료구조", "due_date": "",
                  "summary": "공지 요약", "deliverables": ["보고서"], "tasks": ["조사"]}
        files = [
            ("notice.pdf", b"%PDF-1.4\ncontent", "application/pdf"),
            ("notice.png", b"\x89PNG\r\n\x1a\ncontent", "image/png"),
            ("notice.jpg", b"\xff\xd8\xffcontent", "image/jpeg"),
        ]
        for name, contents, mime in files:
            with self.subTest(name=name):
                with patch("app.analyze_document", return_value=answer) as analyze:
                    response = self.client.post("/ai/analyze-file", data={
                        "csrf_token": self.token,
                        "document": (io.BytesIO(contents), name),
                    }, content_type="multipart/form-data")
                self.assertEqual(response.status_code, 200)
                self.assertIn("과제 공지", response.get_data(as_text=True))
                self.assertIn("ai-save-form", response.get_data(as_text=True))
                analyze.assert_called_once_with(contents, mime)
        with project.connect_db() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM assignments").fetchone()[0], 0)

    def test_f19_rejects_bad_extension_magic_oversize_and_missing_csrf(self):
        cases = [("test.svg", b"<svg/>"), ("test.pdf", b"not-a-pdf"),
                 ("test.png", b"not-a-png"), ("test.jpg", b"not-a-jpeg"),
                 ("huge.pdf", b"%PDF-" + b"x" * (5 * 1024 * 1024))]
        for name, data in cases:
            with self.subTest(name=name):
                with patch("app.analyze_document") as analyze:
                    response = self.client.post("/ai/analyze-file", data={
                        "csrf_token": self.token, "document": (io.BytesIO(data), name),
                    }, content_type="multipart/form-data")
                self.assertEqual(response.status_code, 400)
                analyze.assert_not_called()
        no_csrf = self.client.post("/ai/analyze-file", data={
            "document": (io.BytesIO(b"%PDF-1.4"), "notice.pdf")
        }, content_type="multipart/form-data")
        self.assertEqual(no_csrf.status_code, 400)

    def test_f19_service_parses_mocked_gemini_response(self):
        payload = {"title": "AI 과제", "course": "", "due_date": "",
                   "summary": "요약", "deliverables": [], "tasks": ["준비"]}
        fake_client = MagicMock()
        fake_client.__enter__.return_value.models.generate_content.return_value.text = json.dumps(payload)
        with patch.dict(os.environ, {"GEMINI_API_KEY": "fake-test-key"}):
            with patch("services.gemini_service.genai.Client", return_value=fake_client):
                result = analyze_document(b"%PDF-1.4", "application/pdf")
        self.assertEqual(result["title"], "AI 과제")
        self.assertTrue(fake_client.__enter__.return_value.models.generate_content.called)
        with self.assertRaises(GeminiAnalysisError):
            analyze_document(b"data", "text/html")

    def test_f20_dashboard_contains_owner_scoped_notification_payload(self):
        due = (date.today() + timedelta(days=1)).isoformat()
        self.create("알림 테스트", due)
        body = self.client.get("/").get_data(as_text=True)
        self.assertIn('id="notification-toggle"', body)
        self.assertIn('id="notification-data"', body)
        self.assertIn("알림 테스트", body)
        js = (Path(project.__file__).resolve().parent / "static/js/deadline_notifications.js").read_text(encoding="utf-8")
        self.assertIn("Notification.requestPermission()", js)
        self.assertIn("localStorage", js)
        self.assertIn("Notification.permission", js)

    def test_f21_opt_in_replan_and_preserve_manual_edits(self):
        due = (date.today() + timedelta(days=5)).isoformat()
        a = self.create("재계획 과제", due)
        self.assertEqual(self.post(f"/assignments/{a}/auto-replan", enabled="yes").status_code, 302)
        with patch("features.planning.generate_study_plan", return_value=[
            {"date": date.today().isoformat(), "task": "초기 AI 작업"}
        ]) as generator:
            self.assertEqual(self.post(f"/assignments/{a}/checklist", content="첫 작업").status_code, 302)
            generator.assert_called_once()
        with project.connect_db() as db:
            first = db.execute("SELECT * FROM study_plan WHERE assignment_id=?", (a,)).fetchone()
            self.assertEqual(first["is_manual"], 0)
        self.assertEqual(self.post(f"/assignments/{a}/plan/{first['id']}/edit",
                                   date=due, content="직접 수정 작업").status_code, 302)
        with patch("features.planning.generate_study_plan", return_value=[
            {"date": due, "task": "변경된 AI 작업"}
        ]) as generator:
            self.assertEqual(self.post(f"/assignments/{a}/checklist", content="두 번째 작업").status_code, 302)
            generator.assert_called_once()
        with project.connect_db() as db:
            rows = db.execute("SELECT content, is_manual FROM study_plan WHERE assignment_id=?",
                              (a,)).fetchall()
            assignment = db.execute("SELECT * FROM assignments WHERE id=?", (a,)).fetchone()
        self.assertEqual({(row["content"], row["is_manual"]) for row in rows},
                         {("직접 수정 작업", 1), ("변경된 AI 작업", 0)})
        self.assertEqual(assignment["replan_pending"], 0)

    def test_f21_failure_keeps_plan_and_retry(self):
        due = (date.today() + timedelta(days=3)).isoformat()
        a = self.create("실패 복구", due)
        self.post(f"/assignments/{a}/auto-replan", enabled="yes")
        with project.connect_db() as db:
            db.execute("INSERT INTO study_plan(assignment_id,plan_date,content) VALUES (?,?,?)",
                       (a, due, "기존 계획"))
        with patch("features.planning.generate_study_plan", side_effect=PlanError("API 오류")):
            self.assertEqual(self.post(f"/assignments/{a}/checklist", content="변경 사항").status_code, 302)
        with project.connect_db() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM study_plan WHERE content='기존 계획'").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT replan_pending FROM assignments WHERE id=?", (a,)).fetchone()[0], 1)
        with patch("features.planning.generate_study_plan", return_value=[
            {"date": due, "task": "복구된 계획"}
        ]):
            self.assertEqual(self.post(f"/assignments/{a}/replan").status_code, 302)
        with project.connect_db() as db:
            self.assertEqual(db.execute("SELECT content FROM study_plan").fetchone()[0], "복구된 계획")
            self.assertEqual(db.execute("SELECT replan_pending FROM assignments WHERE id=?", (a,)).fetchone()[0], 0)

    def test_f21_due_date_change_triggers_replan_only_when_enabled(self):
        a = self.create("기한 수정", (date.today() + timedelta(days=4)).isoformat())
        updated_due = (date.today() + timedelta(days=6)).isoformat()
        with patch("features.planning.generate_study_plan") as generator:
            self.post(f"/assignments/{a}/edit", title="기한 수정", course="운영체제",
                      description="자료 조사", due_date=updated_due, status="todo", priority="medium")
            generator.assert_not_called()
        self.post(f"/assignments/{a}/auto-replan", enabled="yes")
        with patch("features.planning.generate_study_plan", return_value=[
            {"date": updated_due, "task": "새 기한 준비"}
        ]) as generator:
            self.post(f"/assignments/{a}/edit", title="기한 수정", course="운영체제",
                      description="자료 조사", due_date=updated_due, status="todo", priority="high")
            generator.assert_called_once()
        self.assertIn("새 기한 준비", self.client.get(f"/assignments/{a}").get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
