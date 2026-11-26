"""Owner-scoped daily focus, quick status and course summaries."""
from datetime import date
from flask import abort, flash, redirect, render_template, request, url_for


def register_productivity(app, connect_db, get_assignment, owner_id, replan):
    with connect_db() as db:
        columns = {r['name'] for r in db.execute('PRAGMA table_info(checklist_items)')}
        if 'focus_date' not in columns:
            db.execute('ALTER TABLE checklist_items ADD COLUMN focus_date TEXT')
        if 'created_on' not in columns:
            # Day the item was added (server date). Existing rows stay NULL.
            db.execute('ALTER TABLE checklist_items ADD COLUMN created_on TEXT')

    @app.post('/assignments/<int:assignment_id>/checklist/<int:item_id>/focus')
    def focus_task(assignment_id, item_id):
        assignment = get_assignment(assignment_id)
        if assignment['status'] == 'done':
            abort(400, description='완료된 과제는 진행 상태를 바꾼 후 오늘 할 일에 추가하세요.')
        with connect_db() as db:
            item = db.execute('SELECT * FROM checklist_items WHERE id=? AND assignment_id=?',
                              (item_id, assignment_id)).fetchone()
            if item is None:
                abort(404)
            if item['is_done']:
                abort(400, description='완료된 할 일은 오늘 할 일로 지정할 수 없습니다.')
            selected = item['focus_date'] == date.today().isoformat()
            db.execute('UPDATE checklist_items SET focus_date=? WHERE id=?',
                       (None if selected else date.today().isoformat(), item_id))
        flash('직접 지정을 해제했습니다. 오늘 추가했거나 오늘 마감인 작업은 계속 표시됩니다.' if selected else '오늘 할 일에 추가했습니다.', 'success')
        return redirect(url_for('dashboard') if request.form.get('return_to') == 'dashboard' else
                        url_for('assignment_detail', assignment_id=assignment_id)+'#checklist-title')

    @app.post('/assignments/<int:assignment_id>/status')
    def quick_status(assignment_id):
        assignment = get_assignment(assignment_id)
        status = request.form.get('status', '')
        if status not in ('todo', 'doing', 'done'):
            abort(400, description='올바른 진행 상태를 선택하세요.')
        with connect_db() as db:
            db.execute('UPDATE assignments SET status=? WHERE id=? AND owner_id IS ?',
                       (status, assignment_id, owner_id()))
            if status == 'done':
                db.execute('UPDATE checklist_items SET focus_date=NULL WHERE assignment_id=?', (assignment_id,))
                db.execute('UPDATE assignments SET replan_pending=0 WHERE id=?', (assignment_id,))
        if status != 'done' and status != assignment['status']:
            replan(connect_db, assignment_id, owner_id())
        flash('완료 보관함으로 이동했습니다.' if status == 'done' else '진행 상태를 변경했습니다.', 'success')
        allowed = ('course','q','priority','deadline','sort','unassigned')
        params = {key: request.form.get(key, '')[:120] for key in allowed if request.form.get(key)}
        view = request.form.get('view', 'active')
        params['view'] = view if view in ('active','completed','all') else 'active'
        if request.form.get('filter_status') in ('all','todo','doing','done'):
            params['status'] = request.form['filter_status']
        return redirect(url_for('assignment_list', **params))

    @app.get('/courses')
    def courses():
        with connect_db() as db:
            rows = db.execute('SELECT course, COUNT(*) AS total, '
                              "SUM(status='done') AS done FROM assignments WHERE owner_id IS ? "
                              'GROUP BY course ORDER BY course', (owner_id(),)).fetchall()
        return render_template('courses.html', courses=rows)
