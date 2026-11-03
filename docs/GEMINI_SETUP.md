# F-04 Gemini 설정 및 로컬 테스트

## 1. API 키
Google AI Studio에서 본인 Gemini API 키를 발급받는다.
**키를 채팅·스크린샷·GitHub에 붙여 넣지 않는다.**

## 2. Windows PowerShell에서 실행
프로젝트 폴더에서 아래 명령을 입력한다. `YOUR_KEY`는 실제 키로 교체한다.
```powershell
$env:GEMINI_API_KEY = "YOUR_KEY"
python app.py
```
이 방법은 현재 터미널 세션에만 키를 설정한다.
환경변수가 없는 경우에도 기존 과제 관리 기능은 실행된다.

## 3. 브라우저 테스트
- http://127.0.0.1:5000/ai/analyze 접속
- 과제 공지문 입력 후 AI 분석하기 클릭
- 과제명·기한·제출물·체크리스트 후보가 원문과 맞는지 확인
- 분석 결과는 **저장되지 않음**. F-05에서 검토·저장 기능 구현 예정.

## 4. 오류 시
- API 키 미설정: GEMINI_API_KEY 확인
- 403: 키 권한/프로젝트 API 접근 확인
- 429: 할당량/요금제 제한 확인
- 모델 미지원: `$env:GEMINI_MODEL = "지원되는-모델명"` 설정
- 서버 재실행 시 환경변수를 새 터미널에 다시 설정
