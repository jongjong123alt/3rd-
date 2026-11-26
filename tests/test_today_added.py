"""Checklist items added today show up in the dashboard's today list automatically."""
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
import app as project


class TodayAddedTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.db_patch = patch.object(project, 'DB_PATH', Path(self.temp.name) / 'test.db')
        self.db_patch.start()
        self.client = project.create_app({'TESTING': True, 'AUTH_REQUIRED': True, 'SECRET_KEY': 'tests-only'}).test_client()
        far = (date.today() + timedelta(days=20)).isoformat()
        with project.connect_db() as db:
            for name in ('one', 'two'):
                db.execute('INSERT INTO users(username,password_hash) VALUES (?,?)', (name, 'hash'))
            db.execute('INSERT INTO assignments(owner_id,title,due_date) VALUES (1,?,?)', ('MINE', far))
            db.execute('INSERT INTO assignments(owner_id,title,due_date) VALUES (2,?,?)', ('THEIRS', far))
            # added on an earlier day / before this feature (created_on NULL)
            db.execute('INSERT INTO checklist_items(assignment_id,content,created_on) VALUES (1,?,?)',
                       ('OLD_ITEM', (date.today() - timedelta(days=1)).isoformat()))
            db.execute('INSERT INTO checklist_items(assignment_id,content) VALUES (1,?)', ('LEGACY_ITEM',))
            db.execute('INSERT INTO checklist_items(assignment_id,content,created_on) VALUES (2,?,?)',
                       ('FOREIGN_TODAY', date.today().isoformat()))
        with self.client.session_transaction() as s:
            s['user_id'] = 1
        self.client.get('/')
        with self.client.session_transaction() as s:
            self.token = s['csrf_token']

    def tearDown(self):
        self.db_patch.stop()
        self.temp.cleanup()

    def post(self, path, **data):
        return self.client.post(path, data={'csrf_token': self.token, **data})

    def today_list(self):
        html = self.client.get('/').get_data(as_text=True)
        start = html.index('id="today-heading"')
        return html[start:html.index('id="progress-heading"')]

    def item_id(self, content):
        with project.connect_db() as db:
            return db.execute('SELECT id FROM checklist_items WHERE content=?', (content,)).fetchone()['id']

    def test_added_item_appears_then_leaves_when_done_or_deleted(self):
        self.assertEqual(self.post('/assignments/1/checklist', content='NEW_TODAY').status_code, 302)
        self.post('/assignments/1/checklist', content='SECOND_TODAY')
        section = self.today_list()
        self.assertIn('NEW_TODAY', section)
        self.assertIn('오늘 추가', section)
        self.assertNotIn('OLD_ITEM', section)
        self.assertNotIn('LEGACY_ITEM', section)
        self.assertNotIn('FOREIGN_TODAY', section)
        self.post(f'/assignments/1/checklist/{self.item_id("NEW_TODAY")}/toggle')
        self.assertNotIn('NEW_TODAY', self.today_list())
        self.post(f'/assignments/1/checklist/{self.item_id("SECOND_TODAY")}/delete')
        self.assertNotIn('SECOND_TODAY', self.today_list())

    def test_reopened_item_returns(self):
        self.post('/assignments/1/checklist', content='TOGGLE_ME')
        item = self.item_id('TOGGLE_ME')
        self.post(f'/assignments/1/checklist/{item}/toggle')
        self.post(f'/assignments/1/checklist/{item}/toggle')
        self.assertIn('TOGGLE_ME', self.today_list())

    def test_done_assignment_hides_items(self):
        self.post('/assignments/1/checklist', content='DONE_PARENT')
        with project.connect_db() as db:
            db.execute("UPDATE assignments SET status='done' WHERE id=1")
        self.assertNotIn('DONE_PARENT', self.today_list())

    def test_ai_saved_tasks_count_as_added_today(self):
        response = self.post('/ai/save', title='AI_TASK_PARENT', course='', due_date='', summary='',
                             deliverables='', tasks='AI_TASK_ONE\nAI_TASK_TWO')
        self.assertEqual(response.status_code, 302)
        section = self.today_list()
        self.assertIn('AI_TASK_ONE', section)
        self.assertIn('AI_TASK_TWO', section)
