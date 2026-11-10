import csv
import io
import json
import sqlite3
import unittest
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import app as project


class ExtendedFeatureTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.patch_db = patch.object(project, "DB_PATH", Path(self.temp.name) / "test.db")
        self.patch_db.start()
        self.client = project.create_app({"TESTING": True, "SECRET_KEY": "test-secret"}).test_client()
        self.client.get("/")
        with self.client.session_transaction() as session:
            self.token = session["csrf_token"]

    def tearDown(self):
        self.patch_db.stop()
        self.temp.cleanup()

    def post(self, path, **fields):
        return self.client.post(path, data={"csrf_token": self.token, **fields})

    def create(self, title, priority="medium", due_date="", status="todo", course=""):
        response = self.post("/assignments/new", title=title, priority=priority,
                             due_date=due_date, status=status, course=course, description="")
        self.assertEqual(response.status_code, 302)
        with project.connect_db() as db:
            return db.execute("SELECT id FROM assignments WHERE title=?", (title,)).fetchone()[0]

    def test_f08_deadline_badges(self):
        today = date.today()
        self.assertEqual(project.deadline_badge(today.isoformat(), "todo")["label"], "D-DAY")
        self.assertEqual(project.deadline_badge((today + timedelta(days=2)).isoformat(), "doing")["label"], "D-2")
        self.assertEqual(project.deadline_badge((today - timedelta(days=3)).isoformat(), "todo")["label"], "D+3")
        self.assertIsNone(project.deadline_badge(today.isoformat(), "done"))
        self.assertIsNone(project.deadline_badge(None, "todo"))
        self.create("오늘 과제", due_date=today.isoformat())
        self.assertIn("D-DAY", self.client.get("/").get_data(as_text=True))

    def test_f09_priority_create_edit_sort_and_filter(self):
        high = self.create("높은 과제", priority="high")
        self.create("낮은 과제", priority="low")
        self.create("보통 과제")
        with project.connect_db() as db:
            self.assertEqual(db.execute("SELECT priority FROM assignments WHERE id=?", (high,)).fetchone()[0], "high")
        body = self.client.get("/", query_string={"sort": "priority"}).get_data(as_text=True)
        self.assertLess(body.index("높은 과제"), body.index("보통 과제"))
        self.assertLess(body.index("보통 과제"), body.index("낮은 과제"))
        body = self.client.get("/", query_string={"priority": "high"}).get_data(as_text=True)
        self.assertIn("높은 과제", body)
        self.assertNotIn("낮은 과제", body)
        response = self.post(f"/assignments/{high}/edit", title="높은 과제",
                             priority="low", status="doing", course="", description="", due_date="")
        self.assertEqual(response.status_code, 302)
        with project.connect_db() as db:
            self.assertEqual(db.execute("SELECT priority FROM assignments WHERE id=?", (high,)).fetchone()[0], "low")
        self.assertEqual(self.post("/assignments/new", title="거부", priority="invalid").status_code, 400)

    def test_f10_json_backup_and_csv_formula_safety(self):
        assignment_id = self.create("=HYPERLINK(1)", course="자료구조")
        self.post(f"/assignments/{assignment_id}/checklist", content="자료 조사")
        self.post(f"/assignments/{assignment_id}/notes", kind="progress", content="1차 작업 완료")
        response = self.client.get("/export/backup.json")
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response.headers["Content-Disposition"])
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        data = json.loads(response.get_data(as_text=True))
        self.assertEqual(data["format_version"], 1)
        self.assertEqual(data["assignments"][0]["title"], "=HYPERLINK(1)")
        self.assertEqual(data["checklist_items"][0]["content"], "자료 조사")
        self.assertEqual(data["assignment_notes"][0]["content"], "1차 작업 완료")
        response = self.client.get("/export/assignments.csv")
        self.assertEqual(response.status_code, 200)
        rows = list(csv.DictReader(io.StringIO(response.get_data(as_text=True).lstrip("\ufeff"))))
        self.assertEqual(rows[0]["title"], "'=HYPERLINK(1)")
        self.assertEqual(rows[0]["priority"], "medium")

    def test_f11_notes_lifecycle_isolation_and_cascade(self):
        first = self.create("과제 A")
        second = self.create("과제 B")
        self.assertEqual(self.post(f"/assignments/{first}/notes", kind="note", content="개인 메모").status_code, 302)
        self.assertEqual(self.post(f"/assignments/{first}/notes", kind="progress", content="진행 상황").status_code, 302)
        self.post(f"/assignments/{first}/notes", kind="invalid", content="거부")
        self.post(f"/assignments/{first}/notes", kind="note", content="x" * 2001)
        with project.connect_db() as db:
            notes = db.execute("SELECT * FROM assignment_notes ORDER BY id").fetchall()
        self.assertEqual(len(notes), 2)
        note_id = notes[0]["id"]
        self.assertEqual(self.post(f"/assignments/{second}/notes/{note_id}/delete").status_code, 404)
        self.assertEqual(self.post(f"/assignments/{first}/notes/{note_id}/edit",
                                   kind="progress", content="수정 완료").status_code, 302)
        self.assertIn("수정 완료", self.client.get(f"/assignments/{first}").get_data(as_text=True))
        self.assertEqual(self.post(f"/assignments/{first}/notes/{note_id}/delete").status_code, 302)
        self.post(f"/assignments/{first}/delete")
        with project.connect_db() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM assignment_notes").fetchone()[0], 0)

    def test_f12_stats_and_filtered_list_independent(self):
        a = self.create("보고서 A", priority="high", course="운영체제")
        self.create("보고서 B", priority="low", status="done", course="운영체제")
        self.post(f"/assignments/{a}/checklist", content="할 일 1")
        self.post(f"/assignments/{a}/checklist", content="할 일 2")
        with project.connect_db() as db:
            item = db.execute("SELECT id FROM checklist_items ORDER BY id LIMIT 1").fetchone()[0]
        self.post(f"/assignments/{a}/checklist/{item}/toggle")
        body = self.client.get("/", query_string={"priority": "high"}).get_data(as_text=True)
        self.assertIn("검색 결과 1개 / 전체 2개", body)
        self.assertIn("체크리스트 진행률", body)
        self.assertIn("1 / 2 완료", body)
        self.assertIn("50%", body)
        self.assertIn("운영체제", body)
        self.assertIn("과제 현황 분석", body)

    def test_csrf_protects_notes_and_exports_do_not_mutate(self):
        assignment_id = self.create("검증 과제")
        self.assertEqual(self.client.post(f"/assignments/{assignment_id}/notes",
                                          data={"content": "위조"}).status_code, 400)
        self.client.get("/export/backup.json")
        self.client.get("/export/assignments.csv")
        with project.connect_db() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM assignment_notes").fetchone()[0], 0)


class LegacyMigrationTests(unittest.TestCase):
    def test_priority_and_notes_are_added_to_existing_database(self):
        with TemporaryDirectory() as directory:
            db_path = Path(directory) / "legacy.db"
            with sqlite3.connect(db_path) as db:
                db.execute("""CREATE TABLE assignments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
                    course TEXT NOT NULL DEFAULT '', description TEXT NOT NULL DEFAULT '',
                    due_date TEXT, status TEXT NOT NULL DEFAULT 'todo',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
                db.execute("INSERT INTO assignments(title) VALUES ('기존 과제')")
            with patch.object(project, "DB_PATH", db_path):
                app = project.create_app({"TESTING": True, "SECRET_KEY": "test"})
                client = app.test_client()
                self.assertEqual(client.get("/").status_code, 200)
                with project.connect_db() as db:
                    row = db.execute("SELECT title, priority FROM assignments").fetchone()
                    self.assertEqual(row["title"], "기존 과제")
                    self.assertEqual(row["priority"], "medium")
                    self.assertIn("assignment_notes", [r[0] for r in db.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'")])


if __name__ == "__main__":
    unittest.main()
