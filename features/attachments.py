"""F-17: private attachment upload/download/delete (local disk, no inline serving)."""
from pathlib import Path
from uuid import uuid4
from flask import abort, flash, redirect, request, send_file, url_for

ALLOWED = {".pdf", ".png", ".jpg", ".jpeg", ".txt", ".docx"}
MAX_FILE_BYTES = 5 * 1024 * 1024


def init_attachment_db(connect_db):
    with connect_db() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assignment_id INTEGER NOT NULL,
            stored_name TEXT NOT NULL UNIQUE,
            original_name TEXT NOT NULL,
            byte_size INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(assignment_id) REFERENCES assignments(id) ON DELETE CASCADE
        )""")


def attachment_root(db_path):
    return db_path.parent / "uploads"


def register_attachments(app, connect_db, get_assignment, get_db_path):
    init_attachment_db(connect_db)

    @app.post("/assignments/<int:assignment_id>/attachments")
    def add_attachment(assignment_id):
        get_assignment(assignment_id)
        upload = request.files.get("attachment")
        if upload is None or not upload.filename:
            flash("첨부파일을 선택해 주세요.", "error")
            return redirect(url_for("assignment_detail", assignment_id=assignment_id) + "#attachments")
        filename = Path(upload.filename.replace("\\", "/").split("/")[-1]).name
        ext = Path(filename).suffix.lower()
        if not filename or len(filename) > 180 or ext not in ALLOWED:
            flash("PDF, PNG, JPG, TXT, DOCX 파일만 첨부할 수 있습니다.", "error")
            return redirect(url_for("assignment_detail", assignment_id=assignment_id) + "#attachments")
        data = upload.stream.read(MAX_FILE_BYTES + 1)
        if not data or len(data) > MAX_FILE_BYTES:
            flash("파일 크기는 1바이트~5MB여야 합니다.", "error")
            return redirect(url_for("assignment_detail", assignment_id=assignment_id) + "#attachments")
        if ext == ".pdf" and not data.startswith(b"%PDF-"):
            abort(400, description="올바르지 않은 PDF 파일입니다.")
        if ext == ".png" and not data.startswith(b"\x89PNG\r\n\x1a\n"):
            abort(400, description="올바르지 않은 PNG 파일입니다.")
        if ext in (".jpg", ".jpeg") and not data.startswith(b"\xff\xd8\xff"):
            abort(400, description="올바르지 않은 JPEG 파일입니다.")
        if ext == ".docx" and not data.startswith(b"PK"):
            abort(400, description="올바르지 않은 DOCX 파일입니다.")
        if ext == ".txt":
            try:
                data.decode("utf-8-sig")
            except UnicodeDecodeError:
                abort(400, description="TXT 파일은 UTF-8 형식이어야 합니다.")
        root = attachment_root(get_db_path())
        root.mkdir(parents=True, exist_ok=True)
        stored = uuid4().hex
        destination = root / stored
        destination.write_bytes(data)
        try:
            with connect_db() as db:
                db.execute(
                    "INSERT INTO attachments(assignment_id, stored_name, original_name, byte_size) VALUES (?,?,?,?)",
                    (assignment_id, stored, filename, len(data)))
        except Exception:
            destination.unlink(missing_ok=True)
            raise
        flash("첨부파일을 저장했습니다.", "success")
        return redirect(url_for("assignment_detail", assignment_id=assignment_id) + "#attachments")

    @app.get("/assignments/<int:assignment_id>/attachments/<int:attachment_id>")
    def download_attachment(assignment_id, attachment_id):
        get_assignment(assignment_id)
        with connect_db() as db:
            item = db.execute("SELECT * FROM attachments WHERE id=? AND assignment_id=?",
                              (attachment_id, assignment_id)).fetchone()
        if item is None:
            abort(404)
        path = attachment_root(get_db_path()) / item["stored_name"]
        if not path.is_file():
            abort(404)
        return send_file(path, as_attachment=True, download_name=item["original_name"],
                         mimetype="application/octet-stream")

    @app.post("/assignments/<int:assignment_id>/attachments/<int:attachment_id>/delete")
    def delete_attachment(assignment_id, attachment_id):
        get_assignment(assignment_id)
        with connect_db() as db:
            item = db.execute("SELECT stored_name FROM attachments WHERE id=? AND assignment_id=?",
                              (attachment_id, assignment_id)).fetchone()
            if item is None:
                abort(404)
            db.execute("DELETE FROM attachments WHERE id=? AND assignment_id=?",
                       (attachment_id, assignment_id))
        (attachment_root(get_db_path()) / item["stored_name"]).unlink(missing_ok=True)
        flash("첨부파일이 삭제되었습니다.", "success")
        return redirect(url_for("assignment_detail", assignment_id=assignment_id) + "#attachments")


def cleanup_assignment_files(connect_db, db_path, assignment_id):
    with connect_db() as db:
        files = [r["stored_name"] for r in db.execute(
            "SELECT stored_name FROM attachments WHERE assignment_id=?", (assignment_id,))]
    for stored in files:
        (attachment_root(db_path) / stored).unlink(missing_ok=True)
