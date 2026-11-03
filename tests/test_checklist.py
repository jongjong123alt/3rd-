import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import app as project


class ChecklistTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.patch_db = patch.object(project, "DB_PATH", Path(self.temp.name) / "test.db")
        self.patch_db.start()
        self.client = project.create_app({"TESTING": True, "SECRET_KEY": "test-secret"}).test_client()
        self.client.get("/")
        with self.client.session_transaction() as s:
            self.token = s["csrf_token"]
        with project.connect_db() as db:
            self.a = db.execute("INSERT INTO assignments(title) VALUES ('과제 A')").lastrowid
            self.b = db.execute("INSERT INTO assignments(title) VALUES ('과제 B')").lastrowid

    def tearDown(self):
        self.patch_db.stop()
        self.temp.cleanup()

    def post(self, path, **data):
        return self.client.post(path, data={"csrf_token": self.token, **data}, follow_redirects=True)

    def test_lifecycle(self):
        base = f"/assignments/{self.a}/checklist"
        self.assertEqual(self.post(base, content="자료 조사").status_code, 200)
        with project.connect_db() as db:
            item = db.execute("SELECT * FROM checklist_items WHERE assignment_id=?", (self.a,)).fetchone()
            self.assertEqual(item["content"], "자료 조사")
            item_id = item["id"]
        self.assertIn("자료 조사", self.client.get(f"/assignments/{self.a}").get_data(as_text=True))
        self.assertEqual(self.post(f"{base}/{item_id}/toggle").status_code, 200)
        with project.connect_db() as db:
            self.assertEqual(db.execute("SELECT is_done FROM checklist_items WHERE id=?", (item_id,)).fetchone()[0], 1)
        self.assertEqual(self.post(f"{base}/{item_id}/edit", content="보고서 작성").status_code, 200)
        self.assertEqual(self.post(f"/assignments/{self.b}/checklist/{item_id}/delete").status_code, 404)
        self.assertEqual(self.post(f"{base}/{item_id}/delete").status_code, 200)
        with project.connect_db() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM checklist_items").fetchone()[0], 0)

    def test_validation_and_cascade(self):
        base = f"/assignments/{self.a}/checklist"
        self.post(base, content=" ")
        self.post(base, content="x" * 301)
        with project.connect_db() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM checklist_items").fetchone()[0], 0)
        self.assertEqual(self.client.post(base, data={"content": "토큰 없음"}).status_code, 400)
        self.post(base, content="함께 삭제할 항목")
        self.post(f"/assignments/{self.a}/delete")
        with project.connect_db() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM checklist_items").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
