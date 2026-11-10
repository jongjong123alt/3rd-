from datetime import date, timedelta, datetime, timezone
import csv
import io
import json
import calendar
from pathlib import Path
import os
import secrets
import sqlite3

from flask import Flask, Response, abort, flash, jsonify, redirect, render_template, request, session, url_for
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / '.env')
from services.gemini_service import analyze_notice, GeminiAnalysisError
from features.auth import register_auth
from features.planning import register_planning, dashboard_planning
from features.backup import register_backup
from features.attachments import register_attachments, cleanup_assignment_files

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "instance" / "assignments.db"
STATUSES = {"todo": "시작 전", "doing": "진행 중", "done": "완료"}
PRIORITIES = {"high": "높음", "medium": "보통", "low": "낮음"}

def deadline_badge(due_date, status):
    if not due_date or status == "done":
        return None
    try:
        days = (date.fromisoformat(due_date) - date.today()).days
    except ValueError:
        return None
    if days < 0:
        return {"label": f"D+{-days}", "kind": "overdue"}
    if days == 0:
        return {"label": "D-DAY", "kind": "today"}
    return {"label": f"D-{days}", "kind": "soon" if days <= 3 else "normal"}



def connect_db():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect_db() as connection:
        connection.execute("""CREATE TABLE IF NOT EXISTS assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            course TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            due_date TEXT,
            status TEXT NOT NULL DEFAULT 'todo' CHECK(status IN ('todo','doing','done')),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""")
        connection.execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""")
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(assignments)")}
        if "priority" not in columns:
            connection.execute("ALTER TABLE assignments ADD COLUMN priority TEXT NOT NULL DEFAULT 'medium'")
        if "owner_id" not in columns:
            connection.execute("ALTER TABLE assignments ADD COLUMN owner_id INTEGER")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_assignments_owner ON assignments(owner_id)")
        connection.execute("""CREATE TABLE IF NOT EXISTS checklist_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assignment_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            is_done INTEGER NOT NULL DEFAULT 0 CHECK(is_done IN (0,1)),
            FOREIGN KEY (assignment_id) REFERENCES assignments(id) ON DELETE CASCADE
        )""")
        connection.execute("""CREATE TABLE IF NOT EXISTS assignment_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assignment_id INTEGER NOT NULL,
            kind TEXT NOT NULL DEFAULT 'note' CHECK(kind IN ('note','progress')),
            content TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (assignment_id) REFERENCES assignments(id) ON DELETE CASCADE
        )""")


def current_owner_id():
    return session.get("user_id")


def get_assignment(assignment_id):
    with connect_db() as connection:
        assignment = connection.execute(
            "SELECT * FROM assignments WHERE id = ? AND owner_id IS ?",
            (assignment_id, current_owner_id())
        ).fetchone()
    if assignment is None:
        abort(404)
    return assignment


def validate_form(form):
    values = {
        "title": form.get("title", "").strip(),
        "course": form.get("course", "").strip(),
        "description": form.get("description", "").strip(),
        "due_date": form.get("due_date", "").strip(),
        "status": form.get("status", "todo").strip(),
        "priority": form.get("priority", "medium").strip(),
    }
    errors = []
    if not values["title"] or len(values["title"]) > 120:
        errors.append("과제명은 1~120자로 입력해 주세요.")
    if len(values["course"]) > 100:
        errors.append("과목명은 100자 이내로 입력해 주세요.")
    if len(values["description"]) > 5000:
        errors.append("설명은 5,000자 이내로 입력해 주세요.")
    if values["status"] not in STATUSES:
        errors.append("진행 상태를 다시 선택해 주세요.")
    if values["priority"] not in PRIORITIES:
        errors.append("우선순위를 다시 선택해 주세요.")
    if values["due_date"]:
        try:
            parsed = date.fromisoformat(values["due_date"])
            if parsed.isoformat() != values["due_date"]:
                raise ValueError
        except ValueError:
            errors.append("제출기한은 올바른 날짜로 입력해 주세요.")
    return values, errors


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.update(SECRET_KEY=os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32),
                      MAX_CONTENT_LENGTH=6 * 1024 * 1024,
                      SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")
    if test_config:
        app.config.update(test_config)
    init_db()
    register_auth(app, connect_db)
    register_planning(app, connect_db, get_assignment, current_owner_id)
    register_backup(app, connect_db, current_owner_id, validate_form)
    register_attachments(app, connect_db, get_assignment, lambda: DB_PATH)

    @app.before_request
    def csrf_protect():
        if request.method == "POST":
            token = session.get("csrf_token")
            submitted = request.form.get("csrf_token", "")
            if not token or not secrets.compare_digest(token, submitted):
                abort(400, description="유효하지 않은 요청입니다. 페이지를 새로고침해 주세요.")

    @app.context_processor
    def inject_globals():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_urlsafe(32)
        return {"csrf_token": session["csrf_token"], "statuses": STATUSES,
                "priorities": PRIORITIES, "deadline_badge": deadline_badge}

    @app.get("/")
    def dashboard():
        with connect_db() as connection:
            assignments = connection.execute(
                "SELECT * FROM assignments WHERE owner_id IS ? ORDER BY CASE WHEN due_date IS NULL OR due_date = '' THEN 1 ELSE 0 END, due_date ASC, id DESC",
                (current_owner_id(),)
            ).fetchall()
        today = date.today().isoformat()
        counts = {
            "total": len(assignments),
            "doing": sum(a["status"] == "doing" for a in assignments),
            "upcoming": sum(bool(a["due_date"]) and a["due_date"] >= today and a["status"] != "done" for a in assignments),
        }
        # F-12: statistics are based on all assignments, regardless of active filters.
        status_counts = {key: sum(a["status"] == key for a in assignments) for key in STATUSES}
        status_chart = [
            {"key": key, "label": label, "count": status_counts[key],
             "percent": round(status_counts[key] * 100 / len(assignments)) if assignments else 0}
            for key, label in STATUSES.items()
        ]
        course_counts = {}
        for assignment in assignments:
            course = assignment["course"] or "과목 미지정"
            course_counts[course] = course_counts.get(course, 0) + 1
        popular_courses = sorted(course_counts.items(), key=lambda pair: (-pair[1], pair[0]))[:5]
        course_max = max((count for _, count in popular_courses), default=0)
        course_chart = [
            {"name": course, "count": count, "percent": round(count * 100 / course_max)}
            for course, count in popular_courses
        ]
        with connect_db() as connection:
            checklist_stats = connection.execute(
                "SELECT COUNT(*) AS total, COALESCE(SUM(is_done), 0) AS done FROM checklist_items "
                "WHERE assignment_id IN (SELECT id FROM assignments WHERE owner_id IS ?)",
                (current_owner_id(),)
            ).fetchone()
        checklist_total = checklist_stats["total"]
        checklist_done = checklist_stats["done"]
        insights = {
            "overdue": sum(bool(a["due_date"]) and a["due_date"] < today and a["status"] != "done" for a in assignments),
            "done": status_counts["done"],
            "checklist_done": checklist_done,
            "checklist_total": checklist_total,
            "checklist_percent": round(checklist_done * 100 / checklist_total) if checklist_total else 0,
        }
        # F-07: keep summary counts global; filter only the displayed list.
        query = request.args.get("q", "").strip()[:120]
        status_filter = request.args.get("status", "all")
        deadline_filter = request.args.get("deadline", "all")
        priority_filter = request.args.get("priority", "all")
        sort_by = request.args.get("sort", "due")
        if priority_filter not in ("all", "high", "medium", "low"):
            priority_filter = "all"
        if sort_by not in ("due", "priority", "recent"):
            sort_by = "due"
        if status_filter not in ("all", "todo", "doing", "done"):
            status_filter = "all"
        if deadline_filter not in ("all", "overdue", "week", "no_due"):
            deadline_filter = "all"
        visible = assignments
        if query:
            needle = query.casefold()
            visible = [a for a in visible if any(
                needle in (a[field] or "").casefold()
                for field in ("title", "course", "description")
            )]
        if status_filter != "all":
            visible = [a for a in visible if a["status"] == status_filter]
        if priority_filter != "all":
            visible = [a for a in visible if a["priority"] == priority_filter]
        if deadline_filter == "overdue":
            visible = [a for a in visible if a["due_date"] and a["due_date"] < today and a["status"] != "done"]
        elif deadline_filter == "week":
            end = (date.today() + timedelta(days=7)).isoformat()
            visible = [a for a in visible if a["due_date"] and today <= a["due_date"] <= end and a["status"] != "done"]
        elif deadline_filter == "no_due":
            visible = [a for a in visible if not a["due_date"]]
        if sort_by == "priority":
            rank = {"high": 0, "medium": 1, "low": 2}
            visible = sorted(visible, key=lambda a: (rank.get(a["priority"], 1), a["due_date"] or "9999-12-31", -a["id"]))
        elif sort_by == "recent":
            visible = sorted(visible, key=lambda a: -a["id"])
        return render_template(
            "dashboard.html", assignments=visible, counts=counts,
            status_chart=status_chart, course_chart=course_chart, insights=insights,
            planning=dashboard_planning(connect_db, current_owner_id()),
            filters={"q": query, "status": status_filter, "deadline": deadline_filter,
                     "priority": priority_filter, "sort": sort_by},
            filtered_count=len(visible),
            filters_active=bool(query or status_filter != "all" or deadline_filter != "all" or priority_filter != "all"),
        )

    @app.get("/calendar")
    def calendar_view():
        today = date.today()
        month_value = request.args.get("month", "")
        if month_value:
            try:
                if len(month_value) != 7 or month_value[4] != "-" or not (month_value[:4] + month_value[5:]).isdigit():
                    raise ValueError
                year, month = int(month_value[:4]), int(month_value[5:])
                selected = date(year, month, 1)
            except ValueError:
                abort(400, description="올바른 연도와 월을 선택해 주세요.")
        else:
            selected = today.replace(day=1)

        first = selected.isoformat()
        if selected.year == 9999 and selected.month == 12:
            next_month = None
            after_last = None
        else:
            next_year = selected.year + (selected.month == 12)
            next_number = selected.month % 12 + 1
            next_month = date(next_year, next_number, 1)
            after_last = next_month.isoformat()
        if selected.year == 1 and selected.month == 1:
            prev_month = None
        else:
            prev_year = selected.year - (selected.month == 1)
            prev_number = 12 if selected.month == 1 else selected.month - 1
            prev_month = date(prev_year, prev_number, 1)

        with connect_db() as connection:
            if after_last:
                assignments = connection.execute(
                    "SELECT id, title, course, due_date, status FROM assignments "
                    "WHERE owner_id IS ? AND due_date >= ? AND due_date < ? ORDER BY due_date, id",
                    (current_owner_id(), first, after_last),
                ).fetchall()
            else:
                assignments = connection.execute(
                    "SELECT id, title, course, due_date, status FROM assignments "
                    "WHERE owner_id IS ? AND due_date >= ? AND due_date <= ? ORDER BY due_date, id",
                    (current_owner_id(), first, "9999-12-31"),
                ).fetchall()

        by_day = {}
        for assignment in assignments:
            by_day.setdefault(assignment["due_date"], []).append(assignment)

        weeks = []
        for week in calendar.Calendar(firstweekday=6).monthdayscalendar(selected.year, selected.month):
            cells = []
            for day_number in week:
                in_month = day_number != 0
                day = date(selected.year, selected.month, day_number) if in_month else None
                key = day.isoformat() if day else ""
                cells.append({
                    "day": day_number, "in_month": in_month,
                    "date": key, "is_today": day == today if day else False,
                    "assignments": by_day.get(key, []) if in_month else [],
                })
            weeks.append(cells)
        return render_template(
            "calendar.html", selected=selected, weeks=weeks,
            prev_month=prev_month, next_month=next_month,
            assignment_count=len(assignments),
        )

    @app.route("/assignments/new", methods=["GET", "POST"])
    def new_assignment():
        if request.method == "POST":
            values, errors = validate_form(request.form)
            if not errors:
                with connect_db() as connection:
                    connection.execute(
                        "INSERT INTO assignments (title, course, description, due_date, status, priority, owner_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (values["title"], values["course"], values["description"], values["due_date"] or None, values["status"], values["priority"], current_owner_id()),
                    )
                flash("과제가 등록되었습니다.", "success")
                return redirect(url_for("dashboard"))
            return render_template("assignment_form.html", values=values, errors=errors, editing=False), 400
        return render_template("assignment_form.html", values={}, errors=[], editing=False)

    @app.get("/assignments/<int:assignment_id>")
    def assignment_detail(assignment_id):
        assignment = get_assignment(assignment_id)
        with connect_db() as connection:
            items = connection.execute(
                "SELECT * FROM checklist_items WHERE assignment_id = ? ORDER BY id",
                (assignment_id,)
            ).fetchall()
        with connect_db() as connection:
            notes = connection.execute(
                "SELECT * FROM assignment_notes WHERE assignment_id=? ORDER BY id DESC",
                (assignment_id,),
            ).fetchall()
        with connect_db() as connection:
            study_plan = connection.execute(
                "SELECT * FROM study_plan WHERE assignment_id=? ORDER BY plan_date, id",
                (assignment_id,)).fetchall()
        with connect_db() as connection:
            attachments = connection.execute(
                "SELECT * FROM attachments WHERE assignment_id=? ORDER BY id DESC",
                (assignment_id,)).fetchall()
        done_count = sum(item["is_done"] for item in items)
        return render_template(
            "assignment_detail.html", assignment=assignment,
            checklist_items=items, done_count=done_count, notes=notes, study_plan=study_plan,
            attachments=attachments
        )

    @app.route("/assignments/<int:assignment_id>/edit", methods=["GET", "POST"])
    def edit_assignment(assignment_id):
        assignment = get_assignment(assignment_id)
        if request.method == "POST":
            values, errors = validate_form(request.form)
            if not errors:
                with connect_db() as connection:
                    connection.execute(
                        "UPDATE assignments SET title=?, course=?, description=?, due_date=?, status=?, priority=? WHERE id=? AND owner_id IS ?",
                        (values["title"], values["course"], values["description"], values["due_date"] or None, values["status"], values["priority"], assignment_id, current_owner_id()),
                    )
                flash("과제가 수정되었습니다.", "success")
                return redirect(url_for("assignment_detail", assignment_id=assignment_id))
            return render_template("assignment_form.html", values=values, errors=errors, editing=True, assignment=assignment), 400
        return render_template("assignment_form.html", values=dict(assignment), errors=[], editing=True, assignment=assignment)

    @app.post("/assignments/<int:assignment_id>/delete")
    def delete_assignment(assignment_id):
        get_assignment(assignment_id)
        cleanup_assignment_files(connect_db, DB_PATH, assignment_id)
        with connect_db() as connection:
            connection.execute("DELETE FROM assignments WHERE id=? AND owner_id IS ?", (assignment_id, current_owner_id()))
        flash("과제가 삭제되었습니다.", "success")
        return redirect(url_for("dashboard"))

    @app.post("/assignments/<int:assignment_id>/checklist")
    def add_checklist_item(assignment_id):
        get_assignment(assignment_id)
        content = request.form.get("content", "").strip()
        if not content or len(content) > 300:
            flash("할 일은 1~300자로 입력해 주세요.", "error")
        else:
            with connect_db() as connection:
                connection.execute(
                    "INSERT INTO checklist_items (assignment_id, content) VALUES (?, ?)",
                    (assignment_id, content),
                )
            flash("할 일이 추가되었습니다.", "success")
        return redirect(url_for("assignment_detail", assignment_id=assignment_id))

    @app.post("/assignments/<int:assignment_id>/checklist/<int:item_id>/toggle")
    def toggle_checklist_item(assignment_id, item_id):
        get_assignment(assignment_id)
        with connect_db() as connection:
            cursor = connection.execute(
                "UPDATE checklist_items SET is_done = CASE WHEN is_done = 0 THEN 1 ELSE 0 END "
                "WHERE id = ? AND assignment_id = ?", (item_id, assignment_id)
            )
            if cursor.rowcount == 0:
                abort(404)
        return redirect(url_for("assignment_detail", assignment_id=assignment_id))

    @app.post("/assignments/<int:assignment_id>/checklist/<int:item_id>/edit")
    def edit_checklist_item(assignment_id, item_id):
        get_assignment(assignment_id)
        content = request.form.get("content", "").strip()
        if not content or len(content) > 300:
            flash("할 일은 1~300자로 입력해 주세요.", "error")
            return redirect(url_for("assignment_detail", assignment_id=assignment_id))
        with connect_db() as connection:
            cursor = connection.execute(
                "UPDATE checklist_items SET content = ? WHERE id = ? AND assignment_id = ?",
                (content, item_id, assignment_id)
            )
            if cursor.rowcount == 0:
                abort(404)
        flash("할 일이 수정되었습니다.", "success")
        return redirect(url_for("assignment_detail", assignment_id=assignment_id))

    @app.post("/assignments/<int:assignment_id>/checklist/<int:item_id>/delete")
    def delete_checklist_item(assignment_id, item_id):
        get_assignment(assignment_id)
        with connect_db() as connection:
            cursor = connection.execute(
                "DELETE FROM checklist_items WHERE id = ? AND assignment_id = ?",
                (item_id, assignment_id)
            )
            if cursor.rowcount == 0:
                abort(404)
        flash("할 일이 삭제되었습니다.", "success")
        return redirect(url_for("assignment_detail", assignment_id=assignment_id))

    @app.post("/assignments/<int:assignment_id>/notes")
    def add_assignment_note(assignment_id):
        get_assignment(assignment_id)
        content = request.form.get("content", "").strip()
        kind = request.form.get("kind", "note")
        if not content or len(content) > 2000 or kind not in ("note", "progress"):
            flash("기록 종류를 선택하고 내용을 1~2,000자로 입력해 주세요.", "error")
        else:
            with connect_db() as connection:
                connection.execute(
                    "INSERT INTO assignment_notes (assignment_id, kind, content) VALUES (?, ?, ?)",
                    (assignment_id, kind, content),
                )
            flash("진행 기록이 저장되었습니다.", "success")
        return redirect(url_for("assignment_detail", assignment_id=assignment_id) + "#assignment-notes")

    @app.post("/assignments/<int:assignment_id>/notes/<int:note_id>/edit")
    def edit_assignment_note(assignment_id, note_id):
        get_assignment(assignment_id)
        content = request.form.get("content", "").strip()
        kind = request.form.get("kind", "note")
        if not content or len(content) > 2000 or kind not in ("note", "progress"):
            flash("기록 종류를 선택하고 내용을 1~2,000자로 입력해 주세요.", "error")
        else:
            with connect_db() as connection:
                cursor = connection.execute(
                    "UPDATE assignment_notes SET kind=?, content=? WHERE id=? AND assignment_id=?",
                    (kind, content, note_id, assignment_id),
                )
                if cursor.rowcount == 0:
                    abort(404)
            flash("진행 기록이 수정되었습니다.", "success")
        return redirect(url_for("assignment_detail", assignment_id=assignment_id) + "#assignment-notes")

    @app.post("/assignments/<int:assignment_id>/notes/<int:note_id>/delete")
    def delete_assignment_note(assignment_id, note_id):
        get_assignment(assignment_id)
        with connect_db() as connection:
            cursor = connection.execute(
                "DELETE FROM assignment_notes WHERE id=? AND assignment_id=?",
                (note_id, assignment_id),
            )
            if cursor.rowcount == 0:
                abort(404)
        flash("진행 기록이 삭제되었습니다.", "success")
        return redirect(url_for("assignment_detail", assignment_id=assignment_id) + "#assignment-notes")

    @app.get("/export/backup.json")
    def export_backup_json():
        # Export contains private data: keep this endpoint local-only until login exists.
        if request.remote_addr not in ("127.0.0.1", "::1"):
            abort(403)
        with connect_db() as connection:
            assignments = [dict(row) for row in connection.execute(
                "SELECT * FROM assignments WHERE owner_id IS ? ORDER BY id", (current_owner_id(),)
            ).fetchall()]
            checklist = [dict(row) for row in connection.execute(
                "SELECT * FROM checklist_items WHERE assignment_id IN "
                "(SELECT id FROM assignments WHERE owner_id IS ?) ORDER BY id", (current_owner_id(),)
            ).fetchall()]
            notes = [dict(row) for row in connection.execute(
                "SELECT * FROM assignment_notes WHERE assignment_id IN "
                "(SELECT id FROM assignments WHERE owner_id IS ?) ORDER BY id", (current_owner_id(),)
            ).fetchall()]
            plans = [dict(row) for row in connection.execute(
                "SELECT * FROM study_plan WHERE assignment_id IN "
                "(SELECT id FROM assignments WHERE owner_id IS ?) ORDER BY id", (current_owner_id(),)
            ).fetchall()]
        payload = {
            "format_version": 1,
            "exported_at_utc": datetime.now(timezone.utc).isoformat(),
            "assignments": assignments,
            "checklist_items": checklist,
            "assignment_notes": notes,
            "study_plan": plans,
        }
        return Response(
            json.dumps(payload, ensure_ascii=False, indent=2),
            content_type="application/json; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="assignments-backup.json"',
                     "Cache-Control": "no-store"},
        )

    @app.get("/export/assignments.csv")
    def export_assignments_csv():
        if request.remote_addr not in ("127.0.0.1", "::1"):
            abort(403)
        # Escape spreadsheet formula prefixes in untrusted user-entered fields.
        def safe_cell(value):
            value = "" if value is None else str(value)
            if value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n")):
                return "'" + value
            return value
        with connect_db() as connection:
            assignments = connection.execute(
                "SELECT id, title, course, description, due_date, status, priority, created_at "
                "FROM assignments WHERE owner_id IS ? ORDER BY id", (current_owner_id(),)
            ).fetchall()
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        columns = ("id", "title", "course", "description", "due_date", "status", "priority", "created_at")
        writer.writerow(columns)
        for assignment in assignments:
            writer.writerow([safe_cell(assignment[key]) for key in columns])
        return Response(
            "\ufeff" + output.getvalue(),
            content_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="assignments.csv"',
                     "Cache-Control": "no-store"},
        )

    @app.route("/ai/analyze", methods=["GET", "POST"])
    def ai_analyze():
        if request.method == "GET":
            return render_template("ai_analyze.html", notice="", result=None, error=None)
        notice = request.form.get("notice", "").strip()
        if not notice or len(notice) > 10000:
            return render_template("ai_analyze.html", notice=notice[:10000], result=None,
                                   error="공지문은 1~10,000자로 입력해 주세요."), 400
        try:
            result = analyze_notice(notice)
        except GeminiAnalysisError as exc:
            return render_template("ai_analyze.html", notice=notice, result=None, error=str(exc)), 502
        return render_template("ai_analyze.html", notice=notice, result=result, error=None)

    @app.post("/ai/save")
    def ai_save():
        # Store only the user-reviewed fields; F-04 analysis never writes to the DB.
        fields = {key: request.form.get(key, "").strip()
                  for key in ("title", "course", "due_date", "summary")}
        deliverables_raw = request.form.get("deliverables", "")
        tasks_raw = request.form.get("tasks", "")
        deliverables = [x.strip() for x in deliverables_raw.splitlines() if x.strip()]
        tasks = [x.strip() for x in tasks_raw.splitlines() if x.strip()]
        description = "\n\n".join(filter(None, [
            fields["summary"],
            "필수 제출물\n" + "\n".join("- " + x for x in deliverables) if deliverables else "",
        ]))
        values, errors = validate_form({
            **fields, "description": description, "status": "todo"
        })
        if len(fields["summary"]) > 2000:
            errors.append("요약은 2,000자 이내로 입력해 주세요.")
        if len(deliverables) > 30 or any(len(x) > 300 for x in deliverables):
            errors.append("제출물은 최대 30개, 항목당 300자 이내로 입력해 주세요.")
        if len(tasks) > 30 or any(len(x) > 300 for x in tasks):
            errors.append("할 일은 최대 30개, 항목당 300자 이내로 입력해 주세요.")
        if len(deliverables_raw) > 10000 or len(tasks_raw) > 10000:
            errors.append("제출물과 할 일 입력은 각각 10,000자 이내로 작성해 주세요.")
        if errors:
            draft = {**fields, "deliverables": deliverables, "tasks": tasks}
            return render_template("ai_analyze.html", notice="", result=draft,
                                   error=None, save_errors=errors), 400

        with connect_db() as connection:
            cursor = connection.execute(
                "INSERT INTO assignments (title, course, description, due_date, status, owner_id) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (values["title"], values["course"], values["description"],
                 values["due_date"] or None, "todo", current_owner_id()),
            )
            assignment_id = cursor.lastrowid
            connection.executemany(
                "INSERT INTO checklist_items (assignment_id, content) VALUES (?, ?)",
                [(assignment_id, item) for item in tasks],
            )
        flash("검토한 AI 분석 결과가 과제와 체크리스트에 저장되었습니다.", "success")
        return redirect(url_for("assignment_detail", assignment_id=assignment_id))

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
