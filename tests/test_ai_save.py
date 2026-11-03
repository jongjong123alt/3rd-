import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import app as project


class AISaveTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.db_patch = patch.object(project, "DB_PATH", Path(self.temp.name) / "test.db")
        self.db_patch.start()
        self.client = project.create_app({"TESTING": True, "SECRET_KEY": "test-secret"}).test_client()
        self.client.get("/ai/analyze")
        with self.client.session_transaction() as session:
            self.csrf = session["csrf_token"]

    def tearDown(self):
        self.db_patch.stop()
        self.temp.cleanup()

    def test_save_creates_assignment_and_tasks(self):
        response = self.client.post("/ai/save", data={
            "csrf_token": self.csrf, "title": "수정된 과제",
            "course": "운영체제", "due_date": "2026-12-10",
            "summary": "검토된 요약", "deliverables": "보고서 PDF\n발표 자료",
            "tasks": "자료 조사\n보고서 작성",
        })
        self.assertEqual(response.status_code, 302)
        with project.connect_db() as db:
            assignment = db.execute("SELECT * FROM assignments").fetchone()
            tasks = db.execute("SELECT content FROM checklist_items ORDER BY id").fetchall()
        self.assertEqual(assignment["title"], "수정된 과제")
        self.assertEqual(assignment["due_date"], "2026-12-10")
        self.assertIn("보고서 PDF", assignment["description"])
        self.assertEqual([x["content"] for x in tasks], ["자료 조사", "보고서 작성"])

    def test_invalid_does_not_write(self):
        for changes in ({"due_date": "2026-02-31"}, {"title": ""}, {"tasks": "x" * 301}):
            form = {"csrf_token": self.csrf, "title": "과제", "due_date": "",
                    "tasks": "해야 할 일", **changes}
            response = self.client.post("/ai/save", data=form)
            self.assertEqual(response.status_code, 400)
        with project.connect_db() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM assignments").fetchone()[0], 0)

    def test_csrf_and_get_rejected(self):
        self.assertEqual(self.client.get("/ai/save").status_code, 405)
        self.assertEqual(self.client.post("/ai/save", data={"title": "과제"}).status_code, 400)

    def test_empty_date_and_tasks_allowed(self):
        response = self.client.post("/ai/save", data={
            "csrf_token": self.csrf, "title": "기한 미정 과제",
        })
        self.assertEqual(response.status_code, 302)
        with project.connect_db() as db:
            self.assertIsNone(db.execute("SELECT due_date FROM assignments").fetchone()[0])
            self.assertEqual(db.execute("SELECT COUNT(*) FROM checklist_items").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
