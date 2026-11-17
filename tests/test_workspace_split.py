"""Overview and management are distinct, owner-scoped workflows."""
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from html.parser import HTMLParser
import app as project


class NavParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.current = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'a' and attrs.get('aria-current') == 'page':
            self.current.append(attrs.get('href'))


class WorkspaceSplitTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.db_patch = patch.object(project, 'DB_PATH', Path(self.temp.name)/'test.db')
        self.db_patch.start()
        self.client = project.create_app({'TESTING':True, 'AUTH_REQUIRED':True, 'SECRET_KEY':'tests-only'}).test_client()
        with project.connect_db() as db:
            for name in ('owner', 'other'):
                db.execute('INSERT INTO users(username,password_hash) VALUES (?,?)',(name,'unused'))
            for i in range(6):
                db.execute('INSERT INTO assignments(title,owner_id,due_date,status) VALUES (?,?,?,?)',
                           (f'MY_TASK_{i}',1,(date.today()+timedelta(days=i+1)).isoformat(),'todo'))
            db.execute('INSERT INTO assignments(title,owner_id,due_date) VALUES (?,?,?)',
                       ('OTHER_PRIVATE',2,date.today().isoformat()))
        with self.client.session_transaction() as session:
            session['user_id']=1

    def tearDown(self):
        self.db_patch.stop()
        self.temp.cleanup()

    def test_overview_is_bounded_without_management_filters(self):
        body=self.client.get('/').get_data(as_text=True)
        self.assertIn('오늘 할 일',body)
        self.assertIn('MY_TASK_3',body)
        self.assertNotIn('MY_TASK_4',body)
        self.assertNotIn('dashboard-query',body)
        self.assertNotIn('OTHER_PRIVATE',body)

    def test_management_contains_full_list_and_not_overview_widgets(self):
        response=self.client.get('/assignments')
        self.assertEqual(response.status_code,200)
        body=response.get_data(as_text=True)
        self.assertIn('MY_TASK_5',body)
        self.assertIn('dashboard-query',body)
        self.assertNotIn('notification-toggle',body)
        self.assertNotIn('overview-stats',body)
        self.assertNotIn('OTHER_PRIVATE',body)

    def test_old_query_link_redirects_to_management(self):
        response=self.client.get('/',query_string={'q':'MY_TASK_5'})
        self.assertEqual(response.status_code,302)
        self.assertIn('/assignments?q=MY_TASK_5',response.headers['Location'])
        body=self.client.get(response.headers['Location']).get_data(as_text=True)
        self.assertIn('검색 결과 1개 / 전체 6개',body)
        self.assertNotIn('MY_TASK_0',body)

    def test_each_tab_has_one_selected_navigation_item(self):
        for path,expected in [('/','/'),('/assignments','/assignments'),('/assignments/1','/assignments')]:
            with self.subTest(path=path):
                parser=NavParser()
                parser.feed(self.client.get(path).get_data(as_text=True))
                self.assertEqual(parser.current,[expected])

    def test_create_and_delete_return_to_management(self):
        self.client.get('/assignments')
        with self.client.session_transaction() as session:
            token=session['csrf_token']
        response=self.client.post('/assignments/new',data={'csrf_token':token,'title':'NEW_TASK'})
        self.assertEqual(response.headers['Location'],'/assignments')
        with project.connect_db() as db:
            task=db.execute('SELECT id FROM assignments WHERE title=?',('NEW_TASK',)).fetchone()['id']
        response=self.client.post(f'/assignments/{task}/delete',data={'csrf_token':token})
        self.assertEqual(response.headers['Location'],'/assignments')

    def test_other_owner_gets_their_own_list_and_overview(self):
        with self.client.session_transaction() as session:
            session['user_id']=2
        for path in ('/','/assignments'):
            body=self.client.get(path).get_data(as_text=True)
            self.assertIn('OTHER_PRIVATE',body)
            self.assertNotIn('MY_TASK_',body)
