"""Public registration must create isolated accounts without adopting legacy data."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import app as project
from werkzeug.security import check_password_hash


class PublicSignupTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.db_patch = patch.object(project, 'DB_PATH', Path(self.temp.name) / 'test.db')
        self.db_patch.start()
        self.app = project.create_app({'TESTING': True, 'AUTH_REQUIRED': True,
                                      'LEGACY_LOCAL_ADOPTION_ENABLED': False})
        self.client = self.app.test_client()

    def tearDown(self):
        self.db_patch.stop()
        self.temp.cleanup()

    def signup(self, client, username, password='test-password-123'):
        self.assertEqual(client.get('/auth/register').status_code, 200)
        with client.session_transaction() as session:
            token = session['csrf_token']
        return client.post('/auth/register', data={'csrf_token': token,
                           'username': username, 'password': password},
                           environ_overrides={'REMOTE_ADDR': '198.51.100.42'})

    def test_public_signup_isolation_and_login(self):
        with project.connect_db() as db:
            legacy = db.execute("INSERT INTO assignments(title) VALUES ('private legacy')").lastrowid
        self.assertEqual(self.signup(self.client, 'new_student').status_code, 302)
        self.assertNotIn('private legacy', self.client.get('/assignments').get_data(as_text=True))
        self.assertEqual(self.client.get(f'/assignments/{legacy}').status_code, 404)
        with project.connect_db() as db:
            user = db.execute('SELECT * FROM users WHERE username=?', ('new_student',)).fetchone()
            self.assertTrue(check_password_hash(user['password_hash'], 'test-password-123'))
            self.assertIsNone(db.execute('SELECT owner_id FROM assignments WHERE id=?', (legacy,)).fetchone()[0])
            own = db.execute('INSERT INTO assignments(title,owner_id) VALUES (?,?)',
                             ('first student only', user['id'])).lastrowid
        second = self.app.test_client()
        self.assertEqual(self.signup(second, 'second_student').status_code, 302)
        self.assertEqual(second.get(f'/assignments/{own}').status_code, 404)
        with self.client.session_transaction() as session:
            token = session['csrf_token']
        self.client.post('/auth/logout', data={'csrf_token': token})
        self.client.get('/auth/login')
        with self.client.session_transaction() as session:
            token = session['csrf_token']
        self.assertEqual(self.client.post('/auth/login', data={'csrf_token': token,
                         'username': 'new_student', 'password': 'test-password-123'}).status_code, 302)
        self.assertEqual(self.client.get(f'/assignments/{own}').status_code, 200)

    def test_duplicate_validation_and_csrf(self):
        self.assertEqual(self.signup(self.client, 'existing').status_code, 302)
        self.assertEqual(self.signup(self.app.test_client(), 'existing').status_code, 400)
        self.assertEqual(self.signup(self.app.test_client(), 'invalid name').status_code, 400)
        self.assertEqual(self.signup(self.app.test_client(), 'valid_name', 'short').status_code, 400)
        self.assertEqual(self.client.post('/auth/register', data={'username': 'no_csrf',
                         'password': 'test-password-123'}).status_code, 400)
        with project.connect_db() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM users').fetchone()[0], 1)

    def test_signup_can_be_disabled(self):
        self.app.config['WEB_SIGNUP_ENABLED'] = False
        self.assertEqual(self.client.get('/auth/register').status_code, 403)
        self.assertNotIn('새 계정 만들기', self.client.get('/auth/login').get_data(as_text=True))
