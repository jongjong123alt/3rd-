# 구조 및 데이터 모델
Browser → Flask → SQLite (과제·체크리스트)
Browser → Flask → Gemini API (추후 구현) → 사용자 검토 → SQLite

현재 엔드포인트: GET /, GET /health
현재 테이블:
- assignments(id, title, course, description, due_date, status, created_at)
- checklist_items(id, assignment_id, content, is_done)

후속: 외래 키 활성화, 사용자 격리, 마이그레이션, 배포용 영구 DB 검토.
