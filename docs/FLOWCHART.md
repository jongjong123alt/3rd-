# draw.io 설계도와 플로우차트

현재 구현 기준일: 2026-11-24 · 애플리케이션 기준 커밋: `537e49f`.

[수정 가능한 draw.io 원본](diagrams/assignment-system.drawio) · [전체 PDF](diagrams/assignment-system.pdf)

## 열기와 편집

1. `.drawio` 파일을 다운로드한다.
2. draw.io 데스크톱 또는 https://app.diagrams.net 에서 **파일 → 열기 → 장치**로 연다.
3. 하단 페이지 탭으로 도면을 선택한다. 도형·문구·화살표를 각각 수정할 수 있다.
4. 저장할 때 `.drawio` 형식을 유지한다. PDF와 PNG는 열람용이다.

| 페이지 | 내용 | 이미지 |
|---|---|---|
| 01 전체 아키텍처 | 브라우저, Flask, 인증·권한, SQLite, 파일, Gemini, ZIP 경계 | [PNG](diagrams/previews/01-architecture.png) |
| 02 화면 구성과 이동 | 공개 소개와 로그인 후 워크스페이스, 실제 URL 및 이동 | [PNG](diagrams/previews/02-screens.png) |
| 03 데이터 모델 · ERD | 6개 테이블과 FK, 사용자 소유의 논리 관계 | [PNG](diagrams/previews/03-erd.png) |
| 04 기본 이용 플로우 | 로그인, 접근 제어, 등록·조회·수정·완료·삭제 | [PNG](diagrams/previews/04-core-flow.png) |
| 05 AI 통합 분석 · 검토 · 저장 | 입력 검증, 파일 분기, Gemini 오류, 결과 점검·수정, 명시적 저장 | [PNG](diagrams/previews/05-ai-flow.png) |
| 06 학습 계획 생성과 자동 재계획 | 수동 생성과 자동 재계획의 적용 조건·교체 범위 차이 | [PNG](diagrams/previews/06-planning-flow.png) |
| 07 계정별 ZIP 백업과 추가 복원 | 계정별 추출, ZIP 검증, 새 ID 연결, 트랜잭션·오류 정리 | [PNG](diagrams/previews/07-backup-flow.png) |

## 흐름을 읽을 때의 기준

- 녹색은 주요 처리, 노란 마름모는 판단, 빨간색은 오류, 파란색은 데이터, 보라색은 외부 AI 처리를 표시한다. 색상 외에도 도형과 문구로 구분한다.
- AI 분석 결과는 사용자가 저장을 요청해야 개인 과제로 저장된다. 요청 점검은 로컬 계산이며 의미적 요구사항까지 자동 보장하지 않는다.
- 수동 학습 계획 생성은 검증 성공 후 기존 계획 전체를 교체한다. 자동 재계획은 자동 계획만 교체하고 직접 수정한 계획을 보존한다. 별도 작업 큐는 없다.
- ZIP 복원은 현재 계정에 추가한다. 기존 데이터를 덮어쓰지 않으며 같은 ZIP을 다시 가져오면 중복될 수 있다.
- `users → assignments` 점선은 논리 관계다. 실제 SQL FK인 네 자식 테이블 관계와 구분한다.

## 재생성

```bash
python docs/diagrams/generate_design.py
```

표준 라이브러리만으로 편집 가능한 XML 원본을 재생성한다. 생성기를 실행하면 수동으로 편집한 원본을 덮어쓰므로, 직접 수정본은 별도 이름으로 저장한다. PNG·SVG·PDF는 XML 원본을 렌더링한 열람본으로, 생성기만 실행해서 자동 갱신되지는 않는다. [검증 기록](diagrams/VALIDATION.md)을 참고한다.
