# F-04 Gemini AI 과제 공지 분석 기능

## 과제 안내문 4장 기준 기술 흐름
사용자 공지문 입력 → 프롬프트 구성 → `model.generate_content(prompt)` → `response.text` JSON 파싱 → 화면 미리보기.

- Gemini SDK: 교수님 예시의 `google-generativeai`
- 환경변수: `python-dotenv`의 `load_dotenv()`를 사용해 로컬 `.env` 로드
- 모델: `GEMINI_MODEL` 환경변수 (기본값 `gemini-2.5-flash`, 사용 가능 여부 확인 필요)
- 출력: 과제명, 과목명, 제출기한, 요약, 필수 제출물, 수행할 일
- 프롬프트에 역할과 JSON 출력 형식 지정, 원문에 없는 날짜 추측 방지
- JSON 파싱 및 값 형식 검증, API 오류 안내
- API 키를 소스 코드와 GitHub에 저장하지 않음
- F-04에서는 결과를 화면에만 표시. 수정 후 DB 저장은 F-05 예정

**AI 필요성:** 교수님 공지문은 비정형 자연어이므로 고정 조건문과 SQL만으로 제출물·요구사항을 안정적으로 추출하기 어렵다.

## 검증 상태
- 코드 변경 완료. 실제 Gemini API 및 SSL 연결 테스트는 아직 통과하지 않음.
- 기존 Python 3.14/OpenSSL 3.5 환경에서 인증서 검증 오류가 보고되었음. SDK 전환만으로 해결된다고 보장하지 않음.
- `google-generativeai`는 구형 SDK이지만 교수님이 명시한 패키지와 호출 형태를 따르기 위해 사용함.
