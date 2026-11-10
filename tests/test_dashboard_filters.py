import unittest
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import app as project

class DashboardFilterTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.db_patch = patch.object(project, "DB_PATH", Path(self.temp.name) / "test.db")
        self.db_patch.start()
        self.client = project.create_app({"TESTING": True, "SECRET_KEY": "test-secret"}).test_client()
        today = date.today()
        self.titles = ("자료구조 보고서", "AI 프로젝트", "오래된 운영체제", "완료된 과제", "기한 미정")
        with project.connect_db() as db:
            db.executemany(
                "INSERT INTO assignments (title, course, description, due_date, status) VALUES (?, ?, ?, ?, ?)",
                [
                    (self.titles[0], "자료구조", "정렬 알고리즘", (today + timedelta(days=2)).isoformat(), "todo"),
                    (self.titles[1], "AI입문", "보고서 작성", (today + timedelta(days=20)).isoformat(), "doing"),
                    (self.titles[2], "운영체제", "프로세스", (today - timedelta(days=1)).isoformat(), "doing"),
                    (self.titles[3], "자료구조", "보고서 제출", (today - timedelta(days=3)).isoformat(), "done"),
                    (self.titles[4], "", "일정 미정", None, "todo"),
                ],
            )

    def tearDown(self):
        self.db_patch.stop()
        self.temp.cleanup()

    def test_search_title_course_description(self):
        for query, expected in (
            ("프로젝트", ("AI 프로젝트",)),
            ("운영체제", ("오래된 운영체제",)),
            ("정렬 알고리즘", ("자료구조 보고서",)),
            ("자료구조", ("자료구조 보고서", "완료된 과제")),
        ):
            with self.subTest(query=query):
                body = self.client.get("/", query_string={"q": query}).get_data(as_text=True)
                for title in self.titles:
                    if title in expected:
                        self.assertIn(title, body)
                    else:
                        self.assertNotIn(title, body)

    def test_status_deadline_filters(self):
        cases = (
            ({"status": "doing"}, ("AI 프로젝트", "오래된 운영체제")),
            ({"deadline": "overdue"}, ("오래된 운영체제",)),
            ({"deadline": "week"}, ("자료구조 보고서",)),
            ({"deadline": "no_due"}, ("기한 미정",)),
            ({"status": "done", "deadline": "overdue"}, ()),
        )
        for params, expected in cases:
            with self.subTest(params=params):
                body = self.client.get("/", query_string=params).get_data(as_text=True)
                for title in self.titles:
                    if title in expected:
                        self.assertIn(title, body)
                    else:
                        self.assertNotIn(title, body)

    def test_combined_filters_counts(self):
        body = self.client.get("/", query_string={"q": "보고서", "status": "todo"}).get_data(as_text=True)
        self.assertIn("검색 결과 1개 / 전체 5개", body)
        self.assertIn("자료구조 보고서", body)
        self.assertNotIn("완료된 과제", body)

    def test_invalid_filters(self):
        body = self.client.get("/", query_string={"status": "bad", "deadline": "bad"}).get_data(as_text=True)
        self.assertIn("자료구조 보고서", body)
        self.assertIn("기한 미정", body)
        self.assertNotIn("검색 결과", body)

    def test_empty_and_escaped_search(self):
        body = self.client.get("/", query_string={"q": "<script>alert(1)</script>"}).get_data(as_text=True)
        self.assertIn("조건에 맞는 과제가 없어요", body)
        self.assertNotIn("<script>alert(1)</script>", body)
        self.assertIn("&lt;script&gt;", body)

if __name__ == "__main__":
    unittest.main()
