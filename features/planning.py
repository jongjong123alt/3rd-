"""F-13/14/15: in-app alerts, AI plans and deadline conflict view."""
from collections import defaultdict
from datetime import date, timedelta
from flask import abort, flash, redirect, render_template, request, url_for
from services.plan_service import generate_study_plan, PlanError


def init_planning_db(connect_db):
    with connect_db() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS study_plan (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assignment_id INTEGER NOT NULL,
            plan_date TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(assignment_id) REFERENCES assignments(id) ON DELETE CASCADE
        )""")
        columns = {r["name"] for r in db.execute("PRAGMA table_info(study_plan)")}
        if "is_manual" not in columns:
            db.execute("ALTER TABLE study_plan ADD COLUMN is_manual INTEGER NOT NULL DEFAULT 0")


def maybe_auto_replan(connect_db, assignment_id, owner_id):
    """F-21: replan after relevant edits, only when explicitly enabled.

    Keep the existing AI plan if the Gemini call fails, and always preserve
    entries the user has manually edited. The POST waits for Gemini to finish.
    """
    with connect_db() as db:
        assignment = db.execute(
            "SELECT * FROM assignments WHERE id=? AND owner_id IS ?",
            (assignment_id, owner_id)).fetchone()
        if assignment is None or not assignment["auto_replan_enabled"]:
            return False
        db.execute("UPDATE assignments SET replan_pending=1 WHERE id=?", (assignment_id,))
        if assignment["status"] == "done" or not assignment["due_date"]:
            flash("자동 재계획 대기: 미완료 과제에 제출기한을 지정해 주세요.", "error")
            return False
        today = date.today()
        due = date.fromisoformat(assignment["due_date"])
        if due < today:
            flash("자동 재계획 대기: 이미 마감된 과제입니다.", "error")
            return False
        tasks = [r["content"] for r in db.execute(
            "SELECT content FROM checklist_items WHERE assignment_id=? AND is_done=0 ORDER BY id",
            (assignment_id,))]
        snapshot = dict(assignment)
    try:
        entries = generate_study_plan(snapshot, tasks, today)
    except PlanError as exc:
        flash("자동 재계획 실패: " + str(exc) + " 기존 일정은 유지됩니다.", "error")
        return False
    with connect_db() as db:
        current = db.execute(
            "SELECT due_date, status, auto_replan_enabled FROM assignments "
            "WHERE id=? AND owner_id IS ?", (assignment_id, owner_id)).fetchone()
        if (current is None or not current["auto_replan_enabled"] or
                current["due_date"] != snapshot["due_date"] or current["status"] != snapshot["status"]):
            return False
        db.execute("DELETE FROM study_plan WHERE assignment_id=? AND is_manual=0", (assignment_id,))
        db.executemany(
            "INSERT INTO study_plan (assignment_id, plan_date, content, is_manual) VALUES (?,?,?,0)",
            [(assignment_id, entry["date"], entry["task"]) for entry in entries],
        )
        db.execute("UPDATE assignments SET replan_pending=0 WHERE id=?", (assignment_id,))
    flash("Gemini가 변경된 과제에 맞춰 AI 일정을 자동 갱신했습니다. 직접 수정한 일정은 유지됩니다.", "success")
    return True


def dashboard_planning(connect_db, owner_id):
    today = date.today()
    last = (today + timedelta(days=3)).isoformat()
    with connect_db() as db:
        due = [dict(r) for r in db.execute(
            "SELECT id, title, due_date, priority FROM assignments "
            "WHERE owner_id IS ? AND status!='done' AND due_date IS NOT NULL "
            "AND due_date<=? ORDER BY due_date, id LIMIT 30",
            (owner_id, last))]
        tasks = [dict(r) for r in db.execute(
            "SELECT c.id, c.content, a.id AS assignment_id, a.title FROM checklist_items c "
            "JOIN assignments a ON a.id=c.assignment_id "
            "WHERE a.owner_id IS ? AND a.status!='done' AND c.is_done=0 "
            "AND (a.due_date=? OR a.due_date IS NULL) ORDER BY a.id, c.id LIMIT 15",
            (owner_id, today.isoformat()))]
        plans = [dict(r) for r in db.execute(
            "SELECT p.content, p.assignment_id, a.title FROM study_plan p "
            "JOIN assignments a ON a.id=p.assignment_id "
            "WHERE a.owner_id IS ? AND a.status!='done' AND p.plan_date=? ORDER BY p.id LIMIT 15",
            (owner_id, today.isoformat()))]
    for item in due:
        item["days"] = (date.fromisoformat(item["due_date"]) - today).days
    return {"alerts": due, "today_tasks": tasks, "today_plans": plans}


def schedule_conflicts(connect_db, owner_id):
    today = date.today()
    with connect_db() as db:
        rows = [dict(r) for r in db.execute(
            "SELECT a.id, a.title, a.due_date, a.priority, COUNT(c.id) AS remaining "
            "FROM assignments a LEFT JOIN checklist_items c "
            "ON c.assignment_id=a.id AND c.is_done=0 "
            "WHERE a.owner_id IS ? AND a.status!='done' AND a.due_date IS NOT NULL "
            "GROUP BY a.id ORDER BY a.due_date, a.id",
            (owner_id,))]
    by_day = defaultdict(list)
    for row in rows:
        by_day[row["due_date"]].append(row)
    conflicts = []
    for day, group in by_day.items():
        if len(group) >= 2:
            due = date.fromisoformat(day)
            # A conservative, rule-based suggestion; not an AI-generated claim.
            lead = min(7, max(1, sum(max(1, x["remaining"]) for x in group)))
            start = max(today, due - timedelta(days=lead))
            conflicts.append({"date": day, "assignments": group,
                              "start": start.isoformat(), "overdue": due < today})
    return conflicts


def register_planning(app, connect_db, get_assignment, current_owner_id):
    init_planning_db(connect_db)

    @app.post("/assignments/<int:assignment_id>/auto-replan")
    def toggle_auto_replan(assignment_id):
        assignment = get_assignment(assignment_id)
        enable = request.form.get("enabled") == "yes"
        with connect_db() as db:
            db.execute(
                "UPDATE assignments SET auto_replan_enabled=?, replan_pending=0 WHERE id=?",
                (int(enable), assignment_id))
        flash("변경 시 AI 자동 재계획을 켰습니다. 다음 과제/체크리스트 변경부터 실행됩니다." if enable
              else "AI 자동 재계획을 껐습니다.", "success")
        return redirect(url_for("assignment_detail", assignment_id=assignment_id) + "#study-plan")

    @app.post("/assignments/<int:assignment_id>/replan")
    def retry_auto_replan(assignment_id):
        assignment = get_assignment(assignment_id)
        if not assignment["auto_replan_enabled"]:
            flash("먼저 AI 자동 재계획을 켜 주세요.", "error")
        else:
            maybe_auto_replan(connect_db, assignment_id, current_owner_id())
        return redirect(url_for("assignment_detail", assignment_id=assignment_id) + "#study-plan")

    @app.get("/schedule")
    def schedule_view():
        return render_template("schedule.html",
                               conflicts=schedule_conflicts(connect_db, current_owner_id()))

    @app.post("/assignments/<int:assignment_id>/plan")
    def make_study_plan(assignment_id):
        assignment = get_assignment(assignment_id)
        if assignment["status"] == "done" or not assignment["due_date"]:
            flash("완료된 과제 또는 마감일이 없는 과제는 일정 생성 대상이 아닙니다.", "error")
            return redirect(url_for("assignment_detail", assignment_id=assignment_id))
        today = date.today()
        due = date.fromisoformat(assignment["due_date"])
        if due < today:
            flash("마감일이 지난 과제는 일정을 생성할 수 없습니다.", "error")
            return redirect(url_for("assignment_detail", assignment_id=assignment_id))
        with connect_db() as db:
            tasks = [r["content"] for r in db.execute(
                "SELECT content FROM checklist_items WHERE assignment_id=? AND is_done=0 ORDER BY id",
                (assignment_id,))]
        try:
            entries = generate_study_plan(dict(assignment), tasks, today)
        except PlanError as exc:
            flash(str(exc), "error")
            return redirect(url_for("assignment_detail", assignment_id=assignment_id))
        with connect_db() as db:
            db.execute("DELETE FROM study_plan WHERE assignment_id=?", (assignment_id,))
            db.executemany(
                "INSERT INTO study_plan (assignment_id, plan_date, content) VALUES (?,?,?)",
                [(assignment_id, entry["date"], entry["task"]) for entry in entries],
            )
        flash("Gemini 추천 일정을 저장했습니다. 내용을 확인하고 필요하면 직접 수정하세요.", "success")
        return redirect(url_for("assignment_detail", assignment_id=assignment_id) + "#study-plan")

    @app.post("/assignments/<int:assignment_id>/plan/<int:entry_id>/edit")
    def edit_study_plan(assignment_id, entry_id):
        get_assignment(assignment_id)
        content = request.form.get("content", "").strip()
        day = request.form.get("date", "")
        try:
            date.fromisoformat(day)
        except ValueError:
            day = ""
        if not content or len(content) > 300 or not day:
            flash("날짜와 1~300자 작업 내용을 입력해 주세요.", "error")
        else:
            with connect_db() as db:
                changed = db.execute(
                    "UPDATE study_plan SET plan_date=?, content=?, is_manual=1 WHERE id=? AND assignment_id=?",
                    (day, content, entry_id, assignment_id))
                if not changed.rowcount:
                    abort(404)
            flash("일정이 수정되었습니다.", "success")
        return redirect(url_for("assignment_detail", assignment_id=assignment_id) + "#study-plan")

    @app.post("/assignments/<int:assignment_id>/plan/<int:entry_id>/delete")
    def delete_study_plan(assignment_id, entry_id):
        get_assignment(assignment_id)
        with connect_db() as db:
            changed = db.execute("DELETE FROM study_plan WHERE id=? AND assignment_id=?",
                                 (entry_id, assignment_id))
            if not changed.rowcount:
                abort(404)
        flash("일정이 삭제되었습니다.", "success")
        return redirect(url_for("assignment_detail", assignment_id=assignment_id) + "#study-plan")
