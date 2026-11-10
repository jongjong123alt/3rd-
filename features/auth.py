"""Local account authentication for the assignment workspace (F-18)."""
import re
import secrets
import time
from flask import abort, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

_FAILED = {}
_LOCAL = {"127.0.0.1", "::1"}


def register_auth(app, connect_db):
    @app.before_request
    def require_login():
        if app.config.get("TESTING") and not app.config.get("AUTH_REQUIRED", False):
            return
        if request.endpoint in ("login", "register", "static", "health") or request.endpoint is None:
            return
        if session.get("user_id") is None:
            if request.method == "GET":
                return redirect(url_for("login"))
            abort(401)

    @app.route("/auth/register", methods=["GET", "POST"])
    def register():
        # Local-only signup: prevents remote first-user capture of migrated data.
        if request.remote_addr not in _LOCAL:
            abort(403)
        if request.method == "GET":
            return render_template("auth.html", mode="register", error=None)
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        if not re.fullmatch(r"[a-z0-9_]{3,32}", username) or not 10 <= len(password) <= 128:
            return render_template("auth.html", mode="register", error="아이디는 영문 소문자·숫자·밑줄 3~32자, 비밀번호는 10~128자로 입력해 주세요."), 400
        with connect_db() as db:
            first_user = db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
            try:
                cursor = db.execute("INSERT INTO users(username, password_hash) VALUES (?,?)",
                                    (username, generate_password_hash(password)))
            except Exception as exc:
                if "UNIQUE" in str(exc).upper():
                    return render_template("auth.html", mode="register", error="이미 사용 중인 아이디입니다."), 400
                raise
            user_id = cursor.lastrowid
            if first_user:
                db.execute("UPDATE assignments SET owner_id=? WHERE owner_id IS NULL", (user_id,))
        session.clear()
        session["user_id"] = user_id
        session["csrf_token"] = secrets.token_urlsafe(32)
        flash("계정이 생성되었습니다. 기존 과제는 첫 계정으로 이전되었습니다." if first_user else "계정이 생성되었습니다.", "success")
        return redirect(url_for("dashboard"))

    @app.route("/auth/login", methods=["GET", "POST"])
    def login():
        if request.method == "GET":
            return render_template("auth.html", mode="login", error=None)
        address = request.remote_addr or "unknown"
        now = time.monotonic()
        recent = [t for t in _FAILED.get(address, []) if now - t < 300]
        if len(recent) >= 8:
            return render_template("auth.html", mode="login", error="로그인 시도가 많습니다. 5분 후 다시 시도해 주세요."), 429
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        with connect_db() as db:
            user = db.execute("SELECT id, password_hash FROM users WHERE username=?", (username,)).fetchone()
        if not user or not check_password_hash(user["password_hash"], password):
            _FAILED[address] = recent + [now]
            return render_template("auth.html", mode="login", error="아이디 또는 비밀번호가 올바르지 않습니다."), 401
        _FAILED.pop(address, None)
        session.clear()
        session["user_id"] = user["id"]
        session["csrf_token"] = secrets.token_urlsafe(32)
        return redirect(url_for("dashboard"))

    @app.post("/auth/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))
