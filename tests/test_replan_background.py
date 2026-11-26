"""F-21 auto replan runs in the background so edits return immediately."""
import threading
import time
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
import app as project
from features import planning


class BackgroundReplanTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.db_patch = patch.object(project, 'DB_PATH', Path(self.temp.name) / 'test.db')
        self.db_patch.start()
        self.app = project.create_app({'TESTING': True, 'AUTH_REQUIRED': True, 'SECRET_KEY': 'tests-only',
                                       'AUTO_REPLAN_WAIT': False})
        self.client = self.app.test_client()
        self.due = (date.today() + timedelta(days=5)).isoformat()
        with project.connect_db() as db:
            db.execute('INSERT INTO users(username,password_hash) VALUES (?,?)', ('one', 'hash'))
            self.a = db.execute('INSERT INTO assignments(owner_id,title,due_date,auto_replan_enabled) VALUES (1,?,?,1)',
                                ('BG', self.due)).lastrowid
        with self.client.session_transaction() as s:
            s['user_id'] = 1
        self.client.get('/')
        with self.client.session_transaction() as s:
            self.token = s['csrf_token']

    def tearDown(self):
        self.wait_idle()
        self.db_patch.stop()
        self.temp.cleanup()

    def post(self, path, **data):
        return self.client.post(path, data={'csrf_token': self.token, **data})

    def pending(self):
        with project.connect_db() as db:
            return db.execute('SELECT replan_pending FROM assignments WHERE id=?', (self.a,)).fetchone()[0]

    def wait_idle(self, timeout=5):
        end = time.time() + timeout
        while time.time() < end:
            with planning._replan_lock:
                if self.a not in planning._replan_state:
                    return
            time.sleep(0.02)
        self.fail('replan worker did not finish')

    def test_edit_returns_before_gemini_finishes_then_plan_lands(self):
        release = threading.Event()
        calls = []

        def slow(snapshot, tasks, today):
            calls.append(list(tasks))
            release.wait(5)
            return [{'date': self.due, 'task': 'BG_PLAN'}]

        with patch('features.planning.generate_study_plan', side_effect=slow):
            started = time.time()
            response = self.post(f'/assignments/{self.a}/checklist', content='TASK_ONE')
            self.assertEqual(response.status_code, 302)
            self.assertLess(time.time() - started, 2)           # did not wait for Gemini
            self.assertEqual(self.pending(), 2)                   # shown as running
            page = self.client.get(f'/assignments/{self.a}').get_data(as_text=True)
            self.assertIn('다시 계획하고 있어요', page)
            with project.connect_db() as db:                      # edit already saved
                self.assertEqual(db.execute('SELECT COUNT(*) FROM checklist_items WHERE content=?',
                                            ('TASK_ONE',)).fetchone()[0], 1)
            release.set()
            self.wait_idle()
        self.assertEqual(self.pending(), 0)
        with project.connect_db() as db:
            self.assertEqual([r[0] for r in db.execute('SELECT content FROM study_plan WHERE assignment_id=?', (self.a,))],
                             ['BG_PLAN'])

    def test_rapid_edits_coalesce_and_last_state_wins(self):
        release = threading.Event()
        calls = []

        def slow(snapshot, tasks, today):
            calls.append(list(tasks))
            release.wait(5)
            return [{'date': self.due, 'task': 'PLAN_' + str(len(tasks))}]

        with patch('features.planning.generate_study_plan', side_effect=slow):
            for name in ('T1', 'T2', 'T3'):
                self.assertEqual(self.post(f'/assignments/{self.a}/checklist', content=name).status_code, 302)
            release.set()
            self.wait_idle()
        self.assertLessEqual(len(calls), 2)                       # not one call per edit
        self.assertEqual(calls[-1], ['T1', 'T2', 'T3'])           # final run saw every edit
        with project.connect_db() as db:
            self.assertEqual([r[0] for r in db.execute('SELECT content FROM study_plan WHERE assignment_id=?', (self.a,))],
                             ['PLAN_3'])

    def test_background_failure_keeps_plan_and_marks_retry(self):
        with project.connect_db() as db:
            db.execute('INSERT INTO study_plan(assignment_id,plan_date,content,is_manual) VALUES (?,?,?,0)',
                       (self.a, self.due, 'KEEP_ME'))
        with patch('features.planning.generate_study_plan', side_effect=planning.PlanError('모의 실패')):
            self.post(f'/assignments/{self.a}/checklist', content='X')
            self.wait_idle()
        self.assertEqual(self.pending(), 1)
        with project.connect_db() as db:
            self.assertEqual([r[0] for r in db.execute('SELECT content FROM study_plan WHERE assignment_id=?', (self.a,))],
                             ['KEEP_ME'])
        self.assertIn('AI 재계획 다시 시도', self.client.get(f'/assignments/{self.a}').get_data(as_text=True))

    def test_running_state_resets_on_restart(self):
        with project.connect_db() as db:
            db.execute('UPDATE assignments SET replan_pending=2 WHERE id=?', (self.a,))
        project.create_app({'TESTING': True, 'SECRET_KEY': 'tests-only'})
        self.assertEqual(self.pending(), 1)
