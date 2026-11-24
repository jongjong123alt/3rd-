"""Verify production configuration in isolated processes and temporary storage."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DeploymentTests(unittest.TestCase):
    def run_isolated(self, code, secret="test-production-secret"):
        with tempfile.TemporaryDirectory() as directory:
            env = dict(os.environ, APP_ENV="production", APP_DATA_DIR=directory,
                       FLASK_SECRET_KEY=secret)
            return subprocess.run([__import__('sys').executable, '-c', code], cwd=ROOT,
                                  env=env, capture_output=True, text=True)

    def test_missing_production_secret_fails(self):
        result = self.run_isolated('import app', secret='')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Production requires FLASK_SECRET_KEY', result.stderr)

    def test_account_and_persistent_storage(self):
        result = self.run_isolated('''
import os
from pathlib import Path
import app
from werkzeug.security import check_password_hash
assert app.DB_PATH.parent == Path(os.environ['APP_DATA_DIR'])
assert app.app.config['SESSION_COOKIE_SECURE'] is True
client = app.app.test_client()
assert client.get('/auth/register', environ_overrides={'REMOTE_ADDR':'127.0.0.1'}).status_code == 200
runner = app.app.test_cli_runner()
result = runner.invoke(args=['create-user', '--username', 'demo'], input='safe-test-password\\nsafe-test-password\\n')
assert result.exit_code == 0, result.output
with app.connect_db() as db:
    user = db.execute('SELECT * FROM users WHERE username=?', ('demo',)).fetchone()
    assert check_password_hash(user['password_hash'], 'safe-test-password')
result = runner.invoke(args=['create-user', '--username', 'demo'], input='safe-test-password\\nsafe-test-password\\n')
assert result.exit_code != 0
app.create_app()
with app.connect_db() as db:
    assert db.execute('SELECT COUNT(*) FROM users').fetchone()[0] == 1
assert client.get('/health').status_code == 200
''')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_production_public_signup_does_not_adopt_legacy(self):
        result = self.run_isolated('''
import app
from flask import session
with app.connect_db() as db:
    legacy = db.execute("INSERT INTO assignments(title) VALUES ('legacy private')").lastrowid
client = app.app.test_client()
assert client.get('/auth/register', base_url='https://example.test').status_code == 200
with client.session_transaction(base_url='https://example.test') as state:
    token = state['csrf_token']
response = client.post('/auth/register', base_url='https://example.test', data={
    'csrf_token': token, 'username': 'online_user', 'password': 'long-test-password'
}, environ_overrides={'REMOTE_ADDR': '198.51.100.20'})
assert response.status_code == 302, response.status_code
assert client.get('/', base_url='https://example.test').status_code == 200
assert client.get(f'/assignments/{legacy}', base_url='https://example.test').status_code == 404
with app.connect_db() as db:
    assert db.execute('SELECT owner_id FROM assignments WHERE id=?', (legacy,)).fetchone()[0] is None
    assert db.execute('SELECT COUNT(*) FROM users').fetchone()[0] == 1
''')
        self.assertEqual(result.returncode, 0, result.stderr)
