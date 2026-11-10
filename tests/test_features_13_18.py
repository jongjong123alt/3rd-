import io
import json
import unittest
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import app as project
from services.plan_service import validate_plan, PlanError


class Features13To17Tests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.db_patch = patch.object(project, "DB_PATH", Path(self.temp.name) / "data.db")
        self.db_patch.start()
        self.client = project.create_app({"TESTING": True, "SECRET_KEY": "tests"}).test_client()
        self.client.get("/")
        with self.client.session_transaction() as session:
            self.token = session["csrf_token"]

    def tearDown(self):
        self.db_patch.stop()
        self.temp.cleanup()

    def post(self, url, **data):
        return self.client.post(url, data={"csrf_token": self.token, **data})

    def create(self, title, due_date=None, course=""):
        response = self.post("/assignments/new", title=title, course=course,
                             due_date=due_date or "", description="과제 설명",
                             status="todo", priority="medium")
        self.assertEqual(response.status_code, 302)
        with project.connect_db() as db:
            return db.execute("SELECT id FROM assignments WHERE title=?", (title,)).fetchone()["id"]

    def test_f13_deadline_alerts_and_today_tasks(self):
        today = date.today().isoformat()
        soon = (date.today() + timedelta(days=2)).isoformat()
        a = self.create("오늘 제출", due_date=today)
        self.create("이틀 후 제출", due_date=soon)
        self.post(f"/assignments/{a}/checklist", content="오늘 조사")
        body = self.client.get("/").get_data(as_text=True)
        self.assertIn("마감 알림", body)
        self.assertIn("오늘 제출", body)
        self.assertIn("이틀 후 제출", body)
        self.assertIn("오늘 조사", body)

    def test_f15_same_day_conflicts(self):
        due = (date.today() + timedelta(days=5)).isoformat()
        self.create("발표 과제", due_date=due)
        self.create("보고서 과제", due_date=due)
        body = self.client.get("/schedule").get_data(as_text=True)
        self.assertIn("일정 충돌 확인", body)
        self.assertIn("발표 과제", body)
        self.assertIn("보고서 과제", body)
        self.assertIn("추천 작업 시작일", body)

    def test_f14_plan_generation_edit_and_delete(self):
        due = (date.today() + timedelta(days=4)).isoformat()
        a = self.create("AI 일정", due_date=due)
        entry = {"date": date.today().isoformat(), "task": "자료 조사"}
        with patch("features.planning.generate_study_plan", return_value=[entry]) as generator:
            self.assertEqual(self.post(f"/assignments/{a}/plan").status_code, 302)
            generator.assert_called_once()
        with project.connect_db() as db:
            row = db.execute("SELECT * FROM study_plan WHERE assignment_id=?", (a,)).fetchone()
        self.assertEqual(row["content"], "자료 조사")
        self.assertIn("자료 조사", self.client.get(f"/assignments/{a}").get_data(as_text=True))
        self.assertEqual(self.post(f"/assignments/{a}/plan/{row['id']}/edit",
                                   date=due, content="최종 검토").status_code, 302)
        self.assertIn("최종 검토", self.client.get(f"/assignments/{a}").get_data(as_text=True))
        self.assertEqual(self.post(f"/assignments/{a}/plan/{row['id']}/delete").status_code, 302)
        with project.connect_db() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM study_plan").fetchone()[0], 0)

    def test_f14_ai_plan_schema_validation(self):
        today = date.today()
        with self.assertRaises(PlanError):
            validate_plan({"entries": [{"date": (today - timedelta(days=1)).isoformat(), "task": "잘못된 일정"}]},
                          today, today + timedelta(days=2))
        valid = validate_plan({"entries": [{"date": today.isoformat(), "task": "계획 작성"}]}, today, today)
        self.assertEqual(valid[0]["task"], "계획 작성")

    def test_f16_restore_merge_and_invalid_backup(self):
        a = self.create("원본 과제")
        self.post(f"/assignments/{a}/checklist", content="할 일")
        self.post(f"/assignments/{a}/notes", kind="note", content="참고 메모")
        original = self.client.get("/export/backup.json").get_data()
        response = self.client.post("/backup/restore", data={
            "csrf_token": self.token, "confirm": "yes",
            "backup": (io.BytesIO(original), "backup.json")
        }, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 302)
        with project.connect_db() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM assignments").fetchone()[0], 2)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM checklist_items").fetchone()[0], 2)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM assignment_notes").fetchone()[0], 2)
        malformed = json.dumps({"format_version": 1, "assignments": [
            {"id": 1, "title": "x", "status": "invalid"}],
            "checklist_items": [], "assignment_notes": []}).encode()
        self.client.post("/backup/restore", data={
            "csrf_token": self.token, "confirm": "yes",
            "backup": (io.BytesIO(malformed), "bad.json")
        }, content_type="multipart/form-data")
        with project.connect_db() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM assignments").fetchone()[0], 2)

    def test_f17_attachment_upload_download_delete_and_validation(self):
        a = self.create("첨부 과제")
        data = b"%PDF-1.4\nhello test"
        response = self.client.post(f"/assignments/{a}/attachments", data={
            "csrf_token": self.token,
            "attachment": (io.BytesIO(data), "paper.pdf")
        }, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 302)
        with project.connect_db() as db:
            item = db.execute("SELECT * FROM attachments").fetchone()
        self.assertEqual(item["original_name"], "paper.pdf")
        download = self.client.get(f"/assignments/{a}/attachments/{item['id']}")
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download.data, data)
        self.assertIn("attachment", download.headers["Content-Disposition"])
        self.assertEqual(self.post(f"/assignments/{a}/attachments/{item['id']}/delete").status_code, 302)
        self.assertEqual(self.client.get(f"/assignments/{a}/attachments/{item['id']}").status_code, 404)
        bad = self.client.post(f"/assignments/{a}/attachments", data={
            "csrf_token": self.token,
            "attachment": (io.BytesIO(b"not pdf"), "bad.pdf")
        }, content_type="multipart/form-data")
        self.assertEqual(bad.status_code, 400)


class AuthIsolationTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.db_patch = patch.object(project, "DB_PATH", Path(self.temp.name) / "data.db")
        self.db_patch.start()
        self.client = project.create_app({
            "TESTING": True, "AUTH_REQUIRED": True, "SECRET_KEY": "auth-test"
        }).test_client()
        self.client.get("/auth/register")
        with self.client.session_transaction() as session:
            self.token = session["csrf_token"]

    def tearDown(self):
        self.db_patch.stop()
        self.temp.cleanup()

    def post(self, url, **data):
        return self.client.post(url, data={"csrf_token": self.token, **data})

    def update_token(self):
        with self.client.session_transaction() as session:
            self.token = session["csrf_token"]

    def test_f18_login_owner_isolation_and_legacy_adoption(self):
        with project.connect_db() as db:
            db.execute("INSERT INTO assignments(title) VALUES ('이전 과제')")
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertIn("전체 기능 보기", self.client.get("/").get_data(as_text=True))
        self.assertEqual(self.post("/auth/register", username="first_user",
                                   password="long-password-123").status_code, 302)
        self.update_token()
        first = self.client.get("/").get_data(as_text=True)
        self.assertIn("이전 과제", first)
        self.assertEqual(self.post("/assignments/new", title="첫 사용자 과제").status_code, 302)
        with project.connect_db() as db:
            first_id = db.execute("SELECT id FROM assignments WHERE title='첫 사용자 과제'").fetchone()[0]
            user = db.execute("SELECT password_hash FROM users WHERE username='first_user'").fetchone()[0]
            self.assertNotEqual(user, "long-password-123")
        self.assertEqual(self.post("/auth/logout").status_code, 302)
        self.client.get("/auth/register")
        self.update_token()
        self.assertEqual(self.post("/auth/register", username="second_user",
                                   password="second-password-123").status_code, 302)
        self.update_token()
        self.assertNotIn("이전 과제", self.client.get("/").get_data(as_text=True))
        self.assertEqual(self.client.get(f"/assignments/{first_id}").status_code, 404)
        self.assertEqual(self.client.get("/export/backup.json").json["assignments"], [])
        self.assertEqual(self.post("/auth/logout").status_code, 302)
        self.client.get("/auth/login")
        self.update_token()
        self.assertEqual(self.post("/auth/login", username="first_user",
                                   password="wrong-password").status_code, 401)
        self.assertEqual(self.post("/auth/login", username="first_user",
                                   password="long-password-123").status_code, 302)
        self.assertIn("이전 과제", self.client.get("/").get_data(as_text=True))

    def test_f18_csrf_and_remote_first_user_registration(self):
        self.assertEqual(self.client.post("/auth/register", data={
            "username": "tester", "password": "long-password-123"
        }).status_code, 400)
        self.assertEqual(self.client.post("/auth/register", data={
            "csrf_token": self.token, "username": "tester", "password": "long-password-123"
        }, environ_overrides={"REMOTE_ADDR": "198.51.100.12"}).status_code, 403)


if __name__ == "__main__":
    unittest.main()
