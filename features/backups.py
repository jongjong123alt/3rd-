"""Account-scoped ZIP backup and additive, validated restore; no account credentials."""
import io
import json
import zipfile
from datetime import date
from pathlib import Path
from uuid import uuid4
from flask import abort, flash, redirect, render_template, request, send_file, url_for

MAX_ZIP = 50 * 1024 * 1024
MAX_TOTAL = 100 * 1024 * 1024
TABLES = ('assignments','checklist_items','assignment_notes','study_plan','attachments')


def _text(row, name, limit, default='', required=False):
    value = row.get(name, default)
    if not isinstance(value, str) or len(value) > limit or (required and not value.strip()):
        raise ValueError(f'{name} 값이 올바르지 않습니다.')
    return value


def _date(value):
    if value in (None, ''):
        return None
    if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
        raise ValueError('날짜 형식이 올바르지 않습니다.')
    return value


def _identifier(row, key='id'):
    value = row.get(key)
    if type(value) is not int or value < 1:
        raise ValueError('항목 ID가 올바르지 않습니다.')
    return value


def _bit(row, name):
    value = row.get(name, 0)
    if type(value) is not int or value not in (0,1):
        raise ValueError('상태 값이 올바르지 않습니다.')
    return value


def make_backup(connect_db, owner_id, db_path):
    with connect_db() as db:
        db.execute('BEGIN')
        data = {'version':1}
        data['assignments'] = [dict(r) for r in db.execute('SELECT * FROM assignments WHERE owner_id IS ?', (owner_id,))]
        for row in data['assignments']:
            row.pop('owner_id', None)
        for table in TABLES[1:]:
            data[table] = [dict(r) for r in db.execute(f'SELECT t.* FROM {table} t JOIN assignments a ON a.id=t.assignment_id WHERE a.owner_id IS ?', (owner_id,))]
    if any(len(data[t]) > 5000 for t in TABLES):
        raise ValueError('백업은 표별 5,000개 항목까지 지원합니다.')
    encoded = json.dumps(data, ensure_ascii=False).encode('utf-8')
    if len(encoded) > 2 * 1024 * 1024:
        raise ValueError('백업 데이터가 2MB를 초과합니다.')
    buffer = io.BytesIO()
    total = len(encoded)
    root = db_path.parent / 'uploads'
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('data.json', encoded)
        for row in data['attachments']:
            path = root / row['stored_name']
            if path.is_symlink() or path.resolve().parent != root.resolve() or not path.is_file():
                raise ValueError('누락되었거나 사용할 수 없는 첨부파일이 있습니다. 과제의 첨부파일을 확인하세요.')
            size = path.stat().st_size
            total += size
            if size > 5*1024*1024 or total > MAX_TOTAL:
                raise ValueError('백업 파일 크기 한도를 초과합니다.')
            archive.write(path, f'attachments/{row["id"]}')
    if buffer.tell() > MAX_ZIP:
        raise ValueError('ZIP이 50MB를 초과합니다. 파일을 별도로 보관해 주세요.')
    buffer.seek(0)
    return buffer


def restore_backup(raw, connect_db, owner_id, db_path):
    if len(raw) > MAX_ZIP:
        raise ValueError('복원 ZIP은 50MB 이하여야 합니다.')
    files = []
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            infos = archive.infolist()
            names = [i.filename for i in infos]
            if len(names) != len(set(names)) or len(names)>5001 or sum(i.file_size for i in infos)>MAX_TOTAL:
                raise ValueError('중복되거나 크기가 너무 큰 ZIP입니다.')
            if 'data.json' not in names or archive.getinfo('data.json').file_size > 2*1024*1024:
                raise ValueError('백업 데이터 파일을 확인해 주세요.')
            data = json.loads(archive.read('data.json'))
            if not isinstance(data,dict) or type(data.get('version')) is not int or data.get('version') != 1:
                raise ValueError('지원하지 않는 백업 버전입니다.')
            for table in TABLES:
                rows = data.get(table)
                if not isinstance(rows,list) or len(rows)>5000 or any(not isinstance(r,dict) for r in rows):
                    raise ValueError('백업 항목 형식이 올바르지 않습니다.')
                ids = [_identifier(r) for r in rows]
                if len(ids) != len(set(ids)):
                    raise ValueError('중복된 항목 ID입니다.')
            aids = {_identifier(r) for r in data['assignments']}
            for table in TABLES[1:]:
                if any(_identifier(r,'assignment_id') not in aids for r in data[table]):
                    raise ValueError('과제 연결 정보가 올바르지 않습니다.')
            expected = {'data.json'} | {f'attachments/{_identifier(r)}' for r in data['attachments']}
            if set(names) != expected:
                raise ValueError('누락되었거나 예상하지 못한 ZIP 항목이 있습니다.')
            for row in data['attachments']:
                filename = _text(row,'original_name',180,required=True)
                if any(ord(ch) < 32 for ch in filename) or '/' in filename or '\\' in filename or Path(filename).suffix.lower() not in ('.pdf','.png','.jpg','.jpeg','.txt','.docx'):
                    raise ValueError('첨부파일 이름이 올바르지 않습니다.')
                info = archive.getinfo(f'attachments/{row["id"]}')
                if not 0 < info.file_size <= 5*1024*1024:
                    raise ValueError('첨부파일은 5MB 이하여야 합니다.')
                content = archive.read(info)
                files.append((row, content))
        root = db_path.parent / 'uploads'
        written = []
        try:
            with connect_db() as db:
                mapping = {}
                for row in data['assignments']:
                    status = row.get('status','todo'); priority = row.get('priority','medium')
                    if status not in ('todo','doing','done') or priority not in ('low','medium','high'):
                        raise ValueError('과제 상태가 올바르지 않습니다.')
                    cursor = db.execute('INSERT INTO assignments(title,course,description,due_date,status,priority,owner_id,auto_replan_enabled,replan_pending,created_at) VALUES (?,?,?,?,?,?,?,?,0,COALESCE(?,CURRENT_TIMESTAMP))',
                        (_text(row,'title',120,required=True),_text(row,'course',100),_text(row,'description',5000),_date(row.get('due_date')),status,priority,owner_id,_bit(row,'auto_replan_enabled'),_text(row,'created_at',40) or None))
                    mapping[row['id']] = cursor.lastrowid
                for row in data['checklist_items']:
                    db.execute('INSERT INTO checklist_items(assignment_id,content,is_done,focus_date) VALUES (?,?,?,?)',
                        (mapping[row['assignment_id']],_text(row,'content',300,required=True),_bit(row,'is_done'),_date(row.get('focus_date'))))
                for row in data['assignment_notes']:
                    kind = row.get('kind','note')
                    if kind not in ('note','progress'): raise ValueError('메모 종류가 올바르지 않습니다.')
                    db.execute('INSERT INTO assignment_notes(assignment_id,kind,content,created_at) VALUES (?,?,?,COALESCE(?,CURRENT_TIMESTAMP))',
                        (mapping[row['assignment_id']],kind,_text(row,'content',2000,required=True),_text(row,'created_at',40) or None))
                for row in data['study_plan']:
                    day = _date(row.get('plan_date'))
                    if not day: raise ValueError('학습 일정 날짜가 없습니다.')
                    db.execute('INSERT INTO study_plan(assignment_id,plan_date,content,is_manual,created_at) VALUES (?,?,?,?,COALESCE(?,CURRENT_TIMESTAMP))',
                        (mapping[row['assignment_id']],day,_text(row,'content',300,required=True),_bit(row,'is_manual'),_text(row,'created_at',40) or None))
                if files: root.mkdir(parents=True, exist_ok=True)
                for row, content in files:
                    stored = uuid4().hex
                    path = root/stored
                    written.append(path)
                    path.write_bytes(content)
                    db.execute('INSERT INTO attachments(assignment_id,stored_name,original_name,byte_size,created_at) VALUES (?,?,?,?,COALESCE(?,CURRENT_TIMESTAMP))',
                        (mapping[row['assignment_id']],stored,row['original_name'],len(content),_text(row,'created_at',40) or None))
        except Exception:
            for path in written: path.unlink(missing_ok=True)
            raise
        return len(mapping)
    except (zipfile.BadZipFile, json.JSONDecodeError, UnicodeError, KeyError, TypeError, OverflowError, RuntimeError, NotImplementedError, RecursionError) as exc:
        raise ValueError('올바른 과제 노트 백업 ZIP인지 확인해 주세요.') from exc


def register_backups(app, connect_db, owner_id, db_path):
    @app.get('/backup')
    def backup_settings():
        return render_template('backup.html')

    @app.post('/backup/download')
    def backup_download():
        try:
            buffer = make_backup(connect_db, owner_id(), db_path())
        except (ValueError, OSError) as exc:
            flash(str(exc) if isinstance(exc, ValueError) else '백업 파일을 읽거나 저장하지 못했습니다. 저장 공간과 파일 권한을 확인하세요.', 'error')
            return redirect(url_for('backup_settings'))
        response = send_file(buffer, as_attachment=True, download_name=f'assignment-backup-{date.today().isoformat()}.zip', mimetype='application/zip')
        response.headers['Cache-Control'] = 'no-store'
        return response

    @app.post('/backup/import')
    def backup_restore():
        if request.form.get('confirm') != 'yes':
            abort(400, description='기존 데이터에 새 항목으로 추가하는 복원 방식에 동의해 주세요.')
        upload = request.files.get('backup')
        if upload is None or not upload.filename:
            abort(400, description='백업 ZIP을 선택하세요.')
        try:
            count = restore_backup(upload.stream.read(MAX_ZIP+1), connect_db, owner_id(), db_path())
        except (ValueError, OSError) as exc:
            flash(str(exc) if isinstance(exc, ValueError) else '백업 파일을 읽거나 저장하지 못했습니다. 저장 공간과 파일 권한을 확인하세요.', 'error')
            return redirect(url_for('backup_settings'))
        flash(f'{count}개 과제와 관련 데이터를 새 항목으로 복원했습니다.', 'success')
        return redirect(url_for('assignment_list', view='all'))
