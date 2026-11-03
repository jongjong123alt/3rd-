from pathlib import Path
import sqlite3
from flask import Flask, render_template, jsonify

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "instance" / "assignments.db"

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as connection:
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

def create_app():
    app = Flask(__name__)
    init_db()

    @app.get("/")
    def dashboard():
        with sqlite3.connect(DB_PATH) as connection:
            count = connection.execute("SELECT COUNT(*) FROM assignments").fetchone()[0]
        return render_template("dashboard.html", count=count)

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    return app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
