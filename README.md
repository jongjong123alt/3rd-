# AI 기반 과제 분석 및 일정 관리 웹서비스

Python Flask + SQLite + Google Gemini 기반 대학 과제 관리 프로토타입. 기존 노션 스타일 UI와 과제·체크리스트·달력 기능을 유지하며 F-01~F-21 기능을 단계적으로 구현했습니다.

## 설치와 실행 (Windows PowerShell)

```powershell
git pull origin main
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python app.py
```

브라우저에서 `http://127.0.0.1:5000` 접속. 처음에는 회원가입 화면으로 이동합니다. **기존 DB가 있다면 첫 계정은 반드시 원래 데이터 소유자가 생성하세요.** 기존 과제는 첫 계정에 귀속됩니다.

### .env 설정

프로젝트 루트에 `.env.example`을 참고하여 `.env` 파일을 만드세요. `.env`는 Git에서 제외됩니다.

```ini
GEMINI_API_KEY=본인_Gemini_API_키
GEMINI_MODEL=gemini-2.5-flash
FLASK_SECRET_KEY=본인이_생성한_랜덤_시크릿
```

시크릿 생성 예시: `python -c "import secrets; print(secrets.token_hex(32))"`

API 키가 없어도 일반 과제 관리 기능은 사용할 수 있으나 Gemini 공지 분석(F-04)과 AI 일정 분배(F-14)는 사용할 수 없습니다.

## 주요 기능

- F-01~F-07: 과제 CRUD, 체크리스트, Gemini 공지 분석·저장, 달력, 검색/필터
- F-08~F-12: D-day, 우선순위, JSON/CSV 내보내기, 메모, 통계
- **F-13:** 앱 내부 마감 알림 및 오늘 할 일
- **F-14:** Gemini 기반 날짜별 학습 계획 생성 및 일정 편집
- **F-15:** 동일 날짜 마감 충돌 감지 및 규칙 기반 시작일 추천
- **F-16:** JSON 백업 검증·병합 복원 (첨부파일 미포함)
- **F-17:** PDF·PNG·JPG·UTF-8 TXT·DOCX 첨부파일 관리 (파일당 5MB)
- **F-18:** 비밀번호 해시, 로그인·로그아웃, 사용자별 데이터 접근 제한
- **F-19:** PDF·PNG·JPG 공지문을 Gemini 멀티모달로 분석하여 수정 가능한 미리보기 제공
- **F-20:** 브라우저 알림 권한 동의 후 대시보드 접속 시 마감 알림 (하루 중복 방지, 페이지 닫힌 상태의 푸시 아님)
- **F-21:** 과제·체크리스트 변경 시 선택형 Gemini 자동 재계획 (실패 시 기존 일정 유지, 직접 수정한 일정 보존)

## 기존 사용자 주의사항

1. **업데이트 전에** `instance/assignments.db`와 `instance/uploads` 폴더를 별도로 백업합니다.
2. DB 스키마는 앱 시작 시 기존 데이터를 유지하면서 필요한 컬럼/테이블을 추가합니다.
3. 첫 계정 생성 시 기존 소유자 미지정 과제는 그 계정으로 이전됩니다.
4. JSON 복원은 기존 데이터를 지우지 않고 새 과제로 **추가**합니다. 같은 파일을 반복 복원하면 중복됩니다.
5. 로그인/데이터 분리를 구현했지만 **공개 인터넷 서비스로 배포하기 위한 보안 검증은 아직 완료되지 않았습니다.**

## 테스트

GitHub Actions가 push 시 Python 문법 검사 및 `python -m unittest discover -s tests -v`를 실행합니다. 실제 Gemini API 응답, Windows 환경, 브라우저에서의 파일 업로드·다운로드는 사용자가 별도 확인해야 합니다.

자세한 검증 절차: [F-13~F-18 검증 문서](docs/F13_F18_VALIDATION.md) · [F-19~F-21 검증 문서](docs/F19_F21_VALIDATION.md)
