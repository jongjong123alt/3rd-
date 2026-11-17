"""Disposable browser-test server. Never writes test records into the project DB."""
import sys,tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app as project
from datetime import date,timedelta
from werkzeug.security import generate_password_hash
state=tempfile.TemporaryDirectory(prefix='campus-ui-')
project.DB_PATH=Path(state.name)/'ui.sqlite3'
app=project.create_app({'SECRET_KEY':'browser-tests-only','TESTING':False})
with project.connect_db() as db:
    uid=db.execute('INSERT INTO users(username,password_hash) VALUES (?,?)',('campus_test',generate_password_hash('browser-test-password'))).lastrowid
    for i,(title,course) in enumerate([('트리 구현 및 분석','자료구조'),('중간 프로젝트 보고서','데이터베이스'),('프로세스 동기화','운영체제')]):
        aid=db.execute('INSERT INTO assignments(title,course,due_date,status,priority,owner_id) VALUES (?,?,?,?,?,?)',(title,course,(date.today()+timedelta(days=i+1)).isoformat(),'doing' if i<2 else 'todo','medium',uid)).lastrowid
        db.execute('INSERT INTO checklist_items(assignment_id,content) VALUES (?,?)',(aid,'자료 조사와 요구사항 정리'))
app.run(host='0.0.0.0',port=5001,debug=False,use_reloader=False)
