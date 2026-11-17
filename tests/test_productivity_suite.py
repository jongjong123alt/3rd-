"""Daily focus, archive, courses, private backups and measurable AI request checks."""
import io
import json
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import date, timedelta
from unittest import TestCase
from unittest.mock import patch
import app as project
from services.requirement_checks import inspect_requirements
from features.backups import restore_backup


class ProductivityTests(TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory()
        self.db_patch=patch.object(project,'DB_PATH',Path(self.temp.name)/'test.db')
        self.db_patch.start()
        self.client=project.create_app({'TESTING':True,'AUTH_REQUIRED':True,'SECRET_KEY':'tests-only'}).test_client()
        with project.connect_db() as db:
            for name in ('one','two'):
                db.execute('INSERT INTO users(username,password_hash) VALUES (?,?)',(name,'private-password-hash'))
            for owner,title,course in [(1,'MY_A','과목 A'),(1,'MY_B','과목 B'),(2,'FOREIGN','다른 과목')]:
                db.execute('INSERT INTO assignments(owner_id,title,course,due_date) VALUES (?,?,?,?)',
                           (owner,title,course,(date.today()+timedelta(days=20)).isoformat()))
            db.execute('INSERT INTO checklist_items(assignment_id,content) VALUES (1,?)',('PIN_ME',))
            db.execute('INSERT INTO checklist_items(assignment_id,content) VALUES (3,?)',('FOREIGN_TASK',))
            db.execute("INSERT INTO assignment_notes(assignment_id,content,created_at) VALUES (1,'MEMO','2025-01-02 03:04:05')")
            db.execute('INSERT INTO study_plan(assignment_id,content,plan_date,is_manual) VALUES (1,?,?,1)',
                       ('PLAN',(date.today()+timedelta(days=2)).isoformat()))
        with self.client.session_transaction() as session: session['user_id']=1
        self.client.get('/')
        with self.client.session_transaction() as session: self.token=session['csrf_token']

    def tearDown(self):
        self.db_patch.stop();self.temp.cleanup()

    def post(self,path,**data):
        return self.client.post(path,data={'csrf_token':self.token,**data})

    def backup(self):
        self.post('/assignments/1/attachments',attachment=(io.BytesIO(b'hello backup'),'note.txt'))
        response=self.post('/backup/download')
        self.assertEqual(response.status_code,200)
        return response.data

    def test_pin_and_unpin_future_work(self):
        self.assertNotIn('PIN_ME',self.client.get('/').get_data(as_text=True))
        self.assertEqual(self.post('/assignments/1/checklist/1/focus').status_code,302)
        self.assertIn('PIN_ME',self.client.get('/').get_data(as_text=True))
        self.post('/assignments/1/checklist/1/focus')
        self.assertNotIn('PIN_ME',self.client.get('/').get_data(as_text=True))

    def test_undated_work_requires_explicit_today_selection(self):
        with project.connect_db() as db: db.execute('UPDATE assignments SET due_date=NULL WHERE id=1')
        self.assertNotIn('PIN_ME',self.client.get('/').get_data(as_text=True))
        self.post('/assignments/1/checklist/1/focus')
        self.assertIn('PIN_ME',self.client.get('/').get_data(as_text=True))
        self.post('/assignments/1/checklist/1/focus')
        self.assertNotIn('PIN_ME',self.client.get('/').get_data(as_text=True))

    def test_complete_pinned_work_from_dashboard(self):
        self.post('/assignments/1/checklist/1/focus')
        response=self.post('/assignments/1/checklist/1/toggle',return_to='dashboard')
        self.assertEqual(response.headers['Location'],'/')
        self.assertNotIn('PIN_ME',self.client.get('/').get_data(as_text=True))

    def test_quick_status_archive_and_reopen(self):
        self.post('/assignments/1/checklist/1/focus')
        response=self.post('/assignments/1/status',status='done')
        self.assertEqual(response.status_code,302)
        self.assertNotIn('MY_A',self.client.get('/assignments').get_data(as_text=True))
        self.assertIn('MY_A',self.client.get('/assignments?view=completed').get_data(as_text=True))
        with project.connect_db() as db:
            self.assertIsNone(db.execute('SELECT focus_date FROM checklist_items WHERE id=1').fetchone()[0])
        self.post('/assignments/1/status',status='doing',view='completed')
        self.assertIn('MY_A',self.client.get('/assignments').get_data(as_text=True))
        self.assertNotIn('MY_A',self.client.get('/assignments?view=completed').get_data(as_text=True))

    def test_status_and_focus_owner_validation(self):
        self.assertEqual(self.post('/assignments/3/status',status='done').status_code,404)
        self.assertEqual(self.post('/assignments/1/status',status='invalid').status_code,400)
        self.assertEqual(self.post('/assignments/3/checklist/2/focus').status_code,404)
        self.assertEqual(self.post('/assignments/1/checklist/2/focus').status_code,404)

    def test_quick_status_preserves_filters_and_uses_internal_redirect(self):
        response=self.post('/assignments/1/status', status='doing', view='active', course='과목 A', q='MY_A',
                           filter_status='all', return_to='https://outside.invalid')
        self.assertTrue(response.headers['Location'].startswith('/assignments?'))
        self.assertIn('q=MY_A',response.headers['Location'])
        self.assertNotIn('outside.invalid',response.headers['Location'])

    def test_course_groups_and_filter(self):
        body=self.client.get('/courses').get_data(as_text=True)
        self.assertIn('과목 A',body);self.assertNotIn('다른 과목',body)
        body=self.client.get('/assignments?course=과목 A').get_data(as_text=True)
        self.assertIn('MY_A',body);self.assertNotIn('MY_B',body);self.assertNotIn('FOREIGN',body)

    def test_backup_contains_only_current_account_and_file_bytes(self):
        raw=self.backup()
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            data=z.read('data.json').decode()
            self.assertIn('MY_A',data);self.assertNotIn('FOREIGN',data)
            self.assertNotIn('private-password-hash',data)
            self.assertNotIn('owner_id',data)
            payload=json.loads(data)
            attachment=payload['attachments'][0]
            self.assertEqual(z.read(f'attachments/{attachment["id"]}'),b'hello backup')

    def test_restore_remaps_owners_and_preserves_existing_records_and_dates(self):
        raw=self.backup()
        with self.client.session_transaction() as session:session['user_id']=2
        response=self.post('/backup/import',confirm='yes',backup=(io.BytesIO(raw),'backup.zip'))
        self.assertEqual(response.status_code,302)
        with project.connect_db() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM assignments WHERE owner_id=2').fetchone()[0],3)
            restored=db.execute("SELECT id FROM assignments WHERE owner_id=2 AND title='MY_A'").fetchone()[0]
            self.assertNotEqual(restored,1)
            note=db.execute('SELECT * FROM assignment_notes WHERE assignment_id=?',(restored,)).fetchone()
            self.assertEqual(note['created_at'],'2025-01-02 03:04:05')
            self.assertEqual(db.execute('SELECT is_manual FROM study_plan WHERE assignment_id=?',(restored,)).fetchone()[0],1)
            file=db.execute('SELECT * FROM attachments WHERE assignment_id=?',(restored,)).fetchone()
            self.assertEqual((project.DB_PATH.parent/'uploads'/file['stored_name']).read_bytes(),b'hello backup')
            self.assertEqual(db.execute('SELECT COUNT(*) FROM assignments WHERE owner_id=1').fetchone()[0],2)

    def test_restore_bad_zip_or_missing_confirmation_does_not_change_data(self):
        self.assertEqual(self.post('/backup/import',backup=(io.BytesIO(b'bad'),'bad.zip')).status_code,400)
        self.assertEqual(self.post('/backup/import',confirm='yes',backup=(io.BytesIO(b'bad'),'bad.zip')).status_code,302)
        with project.connect_db() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM assignments').fetchone()[0],3)

    def test_ai_recheck_does_not_call_gemini_or_save(self):
        with patch('app.analyze_notice') as ai:
            response=self.post('/ai/check-requirements',requirements='5줄로 요약',summary='one\ntwo',tasks='할 일')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json['checks'][0]['status'],'unmet')
        ai.assert_not_called()
        with project.connect_db() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM assignments').fetchone()[0],3)
        self.assertEqual(self.post('/ai/check-requirements',summary='가'*2001).status_code,400)

    def test_extra_zip_paths_rejected(self):
        raw=self.backup();buf=io.BytesIO(raw)
        with zipfile.ZipFile(buf,'a') as z:z.writestr('../outside.txt','bad')
        with self.assertRaises(ValueError):restore_backup(buf.getvalue(),project.connect_db,1,project.DB_PATH)
        self.assertFalse((project.DB_PATH.parent.parent/'outside.txt').exists())

    def test_restore_validation_is_atomic(self):
        raw=self.backup();buf=io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(raw)) as src,zipfile.ZipFile(buf,'w') as dst:
            for name in src.namelist():
                content=src.read(name)
                if name=='data.json':
                    data=json.loads(content);data['assignments'][1]['title']='';content=json.dumps(data).encode()
                dst.writestr(name,content)
        with self.assertRaises(ValueError):restore_backup(buf.getvalue(),project.connect_db,1,project.DB_PATH)
        with project.connect_db() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM assignments').fetchone()[0],3)

    def test_restore_partial_disk_failure_rolls_back_rows_and_new_files(self):
        self.post('/assignments/1/attachments',attachment=(io.BytesIO(b'first'),'first.txt'))
        raw=self.backup()
        root=project.DB_PATH.parent/'uploads'
        before={p.name for p in root.iterdir()}
        real_write=Path.write_bytes
        calls=[]
        def fail_second(path, content):
            calls.append(path)
            if len(calls)==2: raise OSError('test disk failure')
            return real_write(path, content)
        with patch.object(Path,'write_bytes',fail_second):
            with self.assertRaises(OSError):restore_backup(raw,project.connect_db,1,project.DB_PATH)
        self.assertEqual({p.name for p in root.iterdir()},before)
        with project.connect_db() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM assignments').fetchone()[0],3)

    def test_new_routes_require_login_and_csrf(self):
        self.assertEqual(self.client.post('/backup/download').status_code,400)
        with self.client.session_transaction() as session:session.pop('user_id',None)
        for path in ('/backup','/courses'):
            self.assertEqual(self.client.get(path).status_code,302)
        self.assertEqual(self.post('/backup/download').status_code,401)
        self.assertEqual(self.post('/assignments/1/status',status='done').status_code,401)


class RequirementInspectionTests(TestCase):
    def test_lines_characters_and_task_counts(self):
        result={'summary':'a\nb\nc','tasks':['one','two'],'deliverables':['PDF']}
        checks=inspect_requirements('3줄, 10자 이내, 할 일 2개, 제출물 1개',result)
        self.assertEqual([c['status'] for c in checks],['passed']*4+['manual'])

    def test_failed_conditions_and_semantic_requests_are_distinct(self):
        checks=inspect_requirements('20줄로 쉽게 영어로',{'summary':'one','tasks':[]})
        self.assertEqual(checks[0]['status'],'unmet')
        self.assertEqual(checks[-1]['status'],'manual')
        self.assertEqual(inspect_requirements('영어로 쉽게',{'summary':'한국어'})[0]['status'],'manual')

    def test_korean_numbers_and_ambiguous_sentence_count(self):
        self.assertEqual(inspect_requirements('세 줄로',{'summary':'a\nb\nc'})[0]['status'],'passed')
        self.assertEqual(inspect_requirements('세 문장으로',{'summary':'a. b. c.'})[0]['status'],'manual')

    def test_upper_and_lower_bounds(self):
        result={'summary':'a\nb','tasks':['one','two']}
        for request in ('최대 5줄', '최소 2줄', '10자 이하', '할 일 최대 3개', '할 일 3개 이내'):
            with self.subTest(request=request):
                self.assertEqual(inspect_requirements(request,result)[0]['status'],'passed')
        self.assertEqual(inspect_requirements('최대 5줄 이상', result)[0]['status'],'manual')

    def test_no_request_has_no_checks(self):
        self.assertEqual(inspect_requirements('',{'summary':'text'}),[])
