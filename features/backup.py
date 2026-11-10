"""F-16: validate and merge a JSON backup into the current user's workspace."""
import json
from datetime import date
from flask import abort, flash, redirect, render_template, request, url_for


class RestoreError(ValueError):
    pass


def validate_backup(payload, validate_form):
    if not isinstance(payload, dict) or payload.get("format_version") != 1:
        raise RestoreError("지원하지 않는 JSON 백업 형식입니다.")
    arrays = {}
    for key, maximum in (("assignments", 200), ("checklist_items", 2000),
                         ("assignment_notes", 2000), ("study_plan", 1000)):
        values = payload.get(key, [] if key == "study_plan" else None)
        if not isinstance(values, list) or len(values) > maximum:
            raise RestoreError(f"{key} 목록의 형식 또는 개수가 올바르지 않습니다.")
        arrays[key] = values
    ids = set()
    normalized = []
    for item in arrays["assignments"]:
        if not isinstance(item, dict) or type(item.get("id")) is not int or item["id"] <= 0 or item["id"] in ids:
            raise RestoreError("과제 ID가 중복되었거나 올바르지 않습니다.")
        ids.add(item["id"])
        values = {}
        for field in ("title", "course", "description", "due_date", "status", "priority"):
            val = item.get(field, "")
            if val is None and field == "due_date":
                val = ""
            if not isinstance(val, str):
                raise RestoreError("과제 필드 형식이 올바르지 않습니다.")
            values[field] = val
        values, errors = validate_form(values)
        if errors:
            raise RestoreError("백업 과제에 올바르지 않은 값이 있습니다: " + errors[0])
        normalized.append((item["id"], values))
    children = {}
    for key in ("checklist_items", "assignment_notes", "study_plan"):
        parsed = []
        for item in arrays[key]:
            if not isinstance(item, dict) or type(item.get("assignment_id")) is not int or item["assignment_id"] not in ids:
                raise RestoreError("백업의 하위 기록이 존재하지 않는 과제를 참조합니다.")
            if key == "checklist_items":
                value = item.get("content")
                if not isinstance(value, str) or not 1 <= len(value.strip()) <= 300 or item.get("is_done") not in (0, 1):
                    raise RestoreError("체크리스트 내용이 올바르지 않습니다.")
                parsed.append((item["assignment_id"], value.strip(), int(item["is_done"])))
            elif key == "assignment_notes":
                value = item.get("content")
                kind = item.get("kind")
                if not isinstance(value, str) or not 1 <= len(value.strip()) <= 2000 or kind not in ("note", "progress"):
                    raise RestoreError("메모 내용이 올바르지 않습니다.")
                parsed.append((item["assignment_id"], kind, value.strip()))
            else:
                value = item.get("content")
                day = item.get("plan_date")
                if not isinstance(value, str) or not 1 <= len(value.strip()) <= 300 or not isinstance(day, str):
                    raise RestoreError("학습 일정 내용이 올바르지 않습니다.")
                try:
                    date.fromisoformat(day)
                except ValueError as exc:
                    raise RestoreError("학습 일정 날짜가 올바르지 않습니다.") from exc
                parsed.append((item["assignment_id"], day, value.strip()))
        children[key] = parsed
    return normalized, children


def register_backup(app, connect_db, current_owner_id, validate_form):
    @app.route("/backup/restore", methods=["GET", "POST"])
    def restore_backup():
        if request.remote_addr not in ("127.0.0.1", "::1"):
            abort(403)
        if request.method == "GET":
            return render_template("restore.html")
        if request.form.get("confirm") != "yes":
            flash("기존 데이터와 합쳐지는 작업에 동의해 주세요.", "error")
            return redirect(url_for("restore_backup"))
        uploaded = request.files.get("backup")
        if not uploaded:
            flash("JSON 백업 파일을 선택해 주세요.", "error")
            return redirect(url_for("restore_backup"))
        raw = uploaded.read(2 * 1024 * 1024 + 1)
        if len(raw) > 2 * 1024 * 1024:
            flash("백업 파일은 2MB 이하여야 합니다.", "error")
            return redirect(url_for("restore_backup"))
        try:
            normalized, children = validate_backup(json.loads(raw.decode("utf-8-sig")), validate_form)
        except (UnicodeError, ValueError) as exc:
            flash("복원 실패: " + str(exc)[:200], "error")
            return redirect(url_for("restore_backup"))
        with connect_db() as db:
            mapping = {}
            for old_id, values in normalized:
                cursor = db.execute(
                    "INSERT INTO assignments(title, course, description, due_date, status, priority, owner_id) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (values["title"], values["course"], values["description"],
                     values["due_date"] or None, values["status"], values["priority"], current_owner_id()))
                mapping[old_id] = cursor.lastrowid
            db.executemany("INSERT INTO checklist_items(assignment_id, content, is_done) VALUES (?,?,?)",
                           [(mapping[a], content, done) for a, content, done in children["checklist_items"]])
            db.executemany("INSERT INTO assignment_notes(assignment_id, kind, content) VALUES (?,?,?)",
                           [(mapping[a], kind, content) for a, kind, content in children["assignment_notes"]])
            db.executemany("INSERT INTO study_plan(assignment_id, plan_date, content) VALUES (?,?,?)",
                           [(mapping[a], day, content) for a, day, content in children["study_plan"]])
        flash(f"과제 {len(normalized)}개를 기존 데이터에 추가했습니다.", "success")
        return redirect(url_for("dashboard"))
