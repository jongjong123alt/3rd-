"""Guest feature previews must never expose private data or run Gemini."""
import io
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import app as project


class PublicPreviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.db_patch = patch.object(project, "DB_PATH", Path(self.temp.name) / "data.db")
        self.db_patch.start()
        self.client = project.create_app({
            "TESTING": True, "AUTH_REQUIRED": True, "SECRET_KEY": "guest-tests"
        }).test_client()
        self.client.get("/")
        with self.client.session_transaction() as session:
            self.token = session["csrf_token"]

    def tearDown(self):
        self.db_patch.stop()
        self.temp.cleanup()

    def test_guest_landing_catalog_and_previews_are_public(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        text = response.get_data(as_text=True)
        self.assertIn("로그인하고 시작하기", text)
        self.assertIn("전체 기능 보기 (21개)", text)
        self.assertIn("서비스 미리보기", text)
        catalog = self.client.get("/features")
        self.assertEqual(catalog.status_code, 200)
        body = catalog.get_data(as_text=True)
        for number in range(1, 22):
            self.assertIn(f"F-{number:02d}", body)
        for slug in ("dashboard", "assignments", "checklist", "ai",
                     "calendar", "schedule", "insights", "files", "alerts"):
            with self.subTest(slug=slug):
                preview = self.client.get("/preview/" + slug)
                self.assertEqual(preview.status_code, 200)
                self.assertIn("예시", preview.get_data(as_text=True))
        self.assertEqual(self.client.get("/preview/unknown").status_code, 404)

    def test_guest_previews_do_not_leak_private_assignments(self):
        private_title = "비공개-과제-절대-노출-금지"
        with project.connect_db() as db:
            db.execute("INSERT INTO users(username,password_hash) VALUES (?,?)",
                       ("secretuser", "unused"))
            db.execute("INSERT INTO assignments(title,owner_id) VALUES (?,?)",
                       (private_title, 1))
        for path in ("/", "/features", "/preview/dashboard", "/preview/calendar",
                     "/preview/ai", "/preview/schedule"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertNotIn(private_title, response.get_data(as_text=True))

    def test_guest_private_get_redirects_to_login(self):
        for path in ("/assignments/new", "/assignments/1", "/calendar",
                     "/schedule", "/ai/analyze", "/export/backup.json",
                     "/export/assignments.csv", "/backup/restore"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 302)
                self.assertIn("/auth/login", response.headers["Location"])

    def test_guest_private_post_is_denied_before_ai_or_database(self):
        with patch("app.analyze_notice") as analyze, patch("app.analyze_document") as document:
            cases = [
                ("/assignments/new", {"title": "몰래 등록"}),
                ("/ai/analyze", {"notice": "공지"}),
                ("/ai/analyze-file", {"document": (io.BytesIO(b"%PDF-1.4"), "x.pdf")}),
                ("/ai/save", {"title": "몰래 저장"}),
                ("/assignments/1/plan", {}),
                ("/assignments/1/auto-replan", {"enabled": "yes"}),
                ("/assignments/1/checklist", {"content": "몰래 추가"}),
                ("/backup/restore", {"confirm": "yes"}),
            ]
            for path, form in cases:
                with self.subTest(path=path):
                    response = self.client.post(path, data={"csrf_token": self.token, **form})
                    self.assertEqual(response.status_code, 401)
            analyze.assert_not_called()
            document.assert_not_called()
        with project.connect_db() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM assignments").fetchone()[0], 0)

    def test_guest_can_login_and_access_workspace(self):
        response = self.client.post("/auth/register", data={
            "csrf_token": self.token, "username": "preview_user",
            "password": "secure-password-123"
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertIn("내 과제 대시보드", self.client.get("/").get_data(as_text=True))
        self.assertEqual(self.client.get("/assignments/new").status_code, 200)
        self.assertEqual(self.client.get("/ai/analyze").status_code, 200)
        with self.client.session_transaction() as session:
            self.token = session["csrf_token"]
        self.assertEqual(self.client.post("/auth/logout", data={"csrf_token": self.token}).status_code, 302)
        self.assertIn("로그인하고 시작하기", self.client.get("/").get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
