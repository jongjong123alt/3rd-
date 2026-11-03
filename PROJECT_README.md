# AI 기반 과제 분석 및 일정 관리 웹서비스

**상태:** Flask/SQLite 1단계 프로토타입 · 교수님 승인 대기 · Gemini API 미연동

## 로컬 실행
```powershell
python -m pip install -r requirements.txt
python app.py
```
접속: http://127.0.0.1:5000 / 상태 확인: http://127.0.0.1:5000/health

## 기능 상태
- 완료: 기본 대시보드, SQLite 테이블 초기화, 헬스 체크
- 예정: 과제 CRUD, 체크리스트, Gemini 공지 분석, 달력, 배포
- 현재 외부에 배포되지 않았으며 실제 Flask 실행은 Windows에서 확인 필요

## 제출 관리 문서
- [요구사항](docs/REQUIREMENTS.md) · [설계](docs/ARCHITECTURE.md) · [흐름도](docs/FLOWCHART.md)
- [개발 일정](docs/ROADMAP.md) · [AI 설명](docs/AI_FUNCTION.md)
- [직접 수정·검증 기록](docs/VALIDATION_LOG.md) · [교수 승인](docs/APPROVAL.md)
- [배포](docs/DEPLOYMENT.md) · [발표](docs/DEMO_SCRIPT.md)

**보안:** .env, SQLite DB, 가상환경은 GitHub에 업로드하지 않음.
