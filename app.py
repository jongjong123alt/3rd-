from datetime import date
from pathlib import Path
import os
import secrets
import sqlite3

from flask import Flask, abort, flash, jsonify, redirect, render_template, request, session, url_for
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / '.env')
from services.gemini_service import analyze_notice, GeminiAnalysisError

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "instance" / "assignments.db"
STATUSES = {"todo": "시작 전", "doing": "진행 중", "done": "완료"}


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
        connection.execute("""CREATE TABLE IF NOT EXISTS checklist_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assignment_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            is_done INTEGER NOT NULL DEFAULT 0 CHECK(is_done IN (0,1)),
            FOREIGN KEY (assignment_id) REFERENCES assignments(id) ON DELETE CASCADE
        )""")


def get_assignment(assignment_id):
    with connect_db() as connection:
        assignment = connection.execute(
            "SELECT * FROM assignments WHERE id = ?", (assignment_id,)
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
    app.config.update(SECRET_KEY=os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32))
    if test_config:
        app.config.update(test_config)
    init_db()

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
        return {"csrf_token": session["csrf_token"], "statuses": STATUSES}

    @app.get("/")
    def dashboard():
        with connect_db() as connection:
            assignments = connection.execute(
                "SELECT * FROM assignments ORDER BY CASE WHEN due_date IS NULL OR due_date = '' THEN 1 ELSE 0 END, due_date ASC, id DESC"
            ).fetchall()
        today = date.today().isoformat()
        counts = {
            "total": len(assignments),
            "doing": sum(a["status"] == "doing" for a in assignments),
            "upcoming": sum(bool(a["due_date"]) and a["due_date"] >= today and a["status"] != "done" for a in assignments),
        }
        return render_template("dashboard.html", assignments=assignments, counts=counts)

    @app.route("/assignments/new", methods=["GET", "POST"])
    def new_assignment():
        if request.method == "POST":
            values, errors = validate_form(request.form)
            if not errors:
                with connect_db() as connection:
                    connection.execute(
                        "INSERT INTO assignments (title, course, description, due_date, status) VALUES (?, ?, ?, ?, ?)",
                        (values["title"], values["course"], values["description"], values["due_date"] or None, values["status"]),
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
        done_count = sum(item["is_done"] for item in items)
        return render_template(
            "assignment_detail.html", assignment=assignment,
            checklist_items=items, done_count=done_count
        )

    @app.route("/assignments/<int:assignment_id>/edit", methods=["GET", "POST"])
    def edit_assignment(assignment_id):
        assignment = get_assignment(assignment_id)
        if request.method == "POST":
            values, errors = validate_form(request.form)
            if not errors:
                with connect_db() as connection:
                    connection.execute(
                        "UPDATE assignments SET title=?, course=?, description=?, due_date=?, status=? WHERE id=?",
                        (values["title"], values["course"], values["description"], values["due_date"] or None, values["status"], assignment_id),
                    )
                flash("과제가 수정되었습니다.", "success")
                return redirect(url_for("assignment_detail", assignment_id=assignment_id))
            return render_template("assignment_form.html", values=values, errors=errors, editing=True, assignment=assignment), 400
        return render_template("assignment_form.html", values=dict(assignment), errors=[], editing=True, assignment=assignment)

    @app.post("/assignments/<int:assignment_id>/delete")
    def delete_assignment(assignment_id):
        get_assignment(assignment_id)
        with connect_db() as connection:
            connection.execute("DELETE FROM assignments WHERE id=?", (assignment_id,))
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

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
