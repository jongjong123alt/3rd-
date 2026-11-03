# Gemini API 로컬 실행 (교수님 3회차 안내 4장 기준)

## 1. 패키지 설치
VS Code에서 프로젝트 폴더를 열고 PowerShell 터미널에 입력:
```powershell
python -m pip install -r requirements.txt
```

## 2. .env 만들기
프로젝트 최상위 폴더(`app.py`와 같은 위치)에 `.env` 파일을 만든다.
```dotenv
GEMINI_API_KEY=발급받은_실제_API_키
GEMINI_MODEL=gemini-2.5-flash
```
- `.env.example`을 복사해 `.env`로 이름을 변경한 다음 입력해도 된다.
- 키를 큰따옴표로 감쌀 필요는 없다.
- `.env`는 `.gitignore`에 포함되어 GitHub에 업로드되지 않는다.
- 키를 채팅, 스크린샷, 공개 저장소에 올리지 않는다.

## 3. 실행
```powershell
python app.py
```
브라우저에서 http://127.0.0.1:5000/ai/analyze 로 접속하고 공지문을 입력한다.
이제 PowerShell에서 매번 API 키를 입력할 필요가 없다.

## 4. SSL 문제 참고
기존 사용자 환경에서 `CERTIFICATE_VERIFY_FAILED: Basic Constraints of CA cert not marked critical` 오류가 확인되었다.
SDK를 변경해도 동일한 네트워크/인증서 오류가 발생할 수 있다.
SSL 검증을 끄지 말고 네트워크의 HTTPS 검사 및 신뢰 인증서 체인을 확인한다.

## 5. 기타 오류
- 키 없음: `.env` 위치와 내용 확인 후 서버 재시작
- 403: API 키 권한 확인
- 429: 요청 한도 확인
- 모델 사용 불가: Google AI Studio에서 지원 모델 확인 후 `GEMINI_MODEL` 변경
- AI 결과는 현재 DB에 자동 저장되지 않음 (F-05 예정)
