import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import app as project


class AssignmentTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.db_patch = patch.object(project, "DB_PATH", Path(self.temp_dir.name) / "test.db")
        self.db_patch.start()
        self.app = project.create_app({"TESTING": True, "SECRET_KEY": "test-only-secret"})
        self.client = self.app.test_client()

    def tearDown(self):
        self.db_patch.stop()
        self.temp_dir.cleanup()

    def csrf(self):
        self.client.get("/")
        with self.client.session_transaction() as session:
            return session["csrf_token"]

    def test_create_update_delete_and_persist(self):
        token = self.csrf()
        response = self.client.post("/assignments/new", data={
            "csrf_token": token, "title": "자료구조 과제", "course": "자료구조",
            "due_date": "2026-12-10", "status": "todo", "description": "보고서 작성"
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("자료구조 과제", response.get_data(as_text=True))
        with project.connect_db() as db:
            item = db.execute("SELECT * FROM assignments").fetchone()
            self.assertEqual(item["title"], "자료구조 과제")
            assignment_id = item["id"]
        response = self.client.post(f"/assignments/{assignment_id}/edit", data={
            "csrf_token": token, "title": "수정된 과제", "course": "자료구조",
            "due_date": "2026-12-11", "status": "doing", "description": "수정"
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("수정된 과제", response.get_data(as_text=True))
        self.assertEqual(self.client.get(f"/assignments/{assignment_id}/delete").status_code, 405)
        response = self.client.post(f"/assignments/{assignment_id}/delete",
                                    data={"csrf_token": token}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        with project.connect_db() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM assignments").fetchone()[0], 0)

    def test_validation_and_csrf(self):
        token = self.csrf()
        self.assertEqual(self.client.post("/assignments/new", data={"title": "no token"}).status_code, 400)
        response = self.client.post("/assignments/new", data={
            "csrf_token": token, "title": "", "status": "todo"
        })
        self.assertEqual(response.status_code, 400)
        response = self.client.post("/assignments/new", data={
            "csrf_token": token, "title": "테스트", "due_date": "2026-02-31", "status": "todo"
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.get("/assignments/99999").status_code, 404)


if __name__ == "__main__":
    unittest.main()
