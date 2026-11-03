import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import app as project


class CalendarTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.db_patch = patch.object(project, "DB_PATH", Path(self.temp_dir.name) / "test.db")
        self.db_patch.start()
        self.client = project.create_app({"TESTING": True, "SECRET_KEY": "test-secret"}).test_client()
        with project.connect_db() as db:
            db.executemany(
                "INSERT INTO assignments (title, course, due_date, status) VALUES (?, ?, ?, ?)",
                [
                    ("운영체제 보고서", "운영체제", "2026-11-12", "todo"),
                    ("발표 준비", "자료구조", "2026-11-12", "doing"),
                    ("완료 과제", "AI", "2026-11-20", "done"),
                    ("다음달 과제", "AI", "2026-12-01", "todo"),
                    ("기한 미정", "", None, "todo"),
                ],
            )

    def tearDown(self):
        self.db_patch.stop()
        self.temp_dir.cleanup()

    def test_calendar_displays_current_month_assignments_only(self):
        response = self.client.get("/calendar?month=2026-11")
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("2026년 11월", body)
        self.assertIn("이번 달 마감 과제 3개", body)
        self.assertIn("운영체제 보고서", body)
        self.assertIn("발표 준비", body)
        self.assertIn("완료 과제", body)
        self.assertNotIn("다음달 과제", body)
        self.assertNotIn("기한 미정", body)
        self.assertIn("status-doing", body)
        self.assertIn("status-done", body)
        self.assertIn("/assignments/", body)

    def test_month_navigation_and_invalid_month(self):
        body = self.client.get("/calendar?month=2026-11").get_data(as_text=True)
        self.assertIn("month=2026-10", body)
        self.assertIn("month=2026-12", body)
        for month in ("2026-00", "2026-13", "2026-02-01", "bad", "0000-01"):
            with self.subTest(month=month):
                self.assertEqual(self.client.get("/calendar?month=" + month).status_code, 400)

    def test_calendar_defaults_to_current_month(self):
        response = self.client.get("/calendar")
        self.assertEqual(response.status_code, 200)
        now = date.today()
        self.assertIn(f"{now.year}년 {now.month}월", response.get_data(as_text=True))

    def test_month_with_no_assignments(self):
        response = self.client.get("/calendar?month=2027-01")
        self.assertEqual(response.status_code, 200)
        self.assertIn("이번 달 마감 과제 0개", response.get_data(as_text=True))

    def test_boundary_months(self):
        self.assertEqual(self.client.get("/calendar?month=0001-01").status_code, 200)
        self.assertEqual(self.client.get("/calendar?month=9999-12").status_code, 200)


if __name__ == "__main__":
    unittest.main()
