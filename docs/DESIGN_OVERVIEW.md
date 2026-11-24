# 과제 노트 — 시스템 설계 정리

2026-11-24 현재 구현을 기준으로 기능·UI 확장을 마무리하고 정리한 설계 문서다. 기준 애플리케이션 커밋은 `537e49f`이며, 이번 작업은 애플리케이션 동작을 바꾸지 않는다. 선택하지 않은 UI 시안은 반영하지 않았다.

## 읽는 순서

1. [전체 아키텍처](ARCHITECTURE.md): 실행 구조, 모듈 책임, 외부 서비스, 인증과 데이터 경계.
2. [화면 구성](SCREEN_DESIGN.md): 공개 소개부터 로그인 후 대시보드·과제 관리·AI·일정·백업까지 화면과 상태.
3. [데이터 모델](DATA_MODEL.md): 실제 6개 테이블의 필드·제약·관계와 파생 데이터.
4. [draw.io 플로우차트 안내](FLOWCHART.md): 전체 구조·화면 이동·ERD와 핵심 이용 흐름 7장.
5. [실제 경로 목록](ROUTE_CATALOG.md): 40개 라우트 규칙과 접근 조건.

## 바로 열기

- [수정 가능한 draw.io 원본](diagrams/assignment-system.drawio)
- [7페이지 PDF](diagrams/assignment-system.pdf)
- [전체 설계 자료 ZIP](diagrams/assignment-system-design.zip)
- [아키텍처 이미지](diagrams/previews/01-architecture.png)
- [화면 구성 이미지](diagrams/previews/02-screens.png)
- [ERD 이미지](diagrams/previews/03-erd.png)

## 설계 범위

Flask + Jinja2 + SQLite의 단일 웹 애플리케이션이다. 로그인, 분리된 대시보드와 과제 관리, 체크리스트, 오늘 지정, 메모·진행 기록, 달력·일정 충돌, 과목별 보기, 첨부파일, Gemini 통합 분석·요청 점검, 학습 계획·자동 재계획, 완료 보관함, 계정별 ZIP 백업·추가 복원을 정리했다.

과목·완료 보관함은 별도 테이블이 아니라 과제 데이터에서 계산한다. AI는 입력 자료를 외부 Gemini API로 전송한다. 회원가입은 로컬 주소로 제한된다. 알림은 대시보드 접속 중 브라우저 권한을 받아 제공하며 서버 푸시는 아니다.

운영 배포용 WSGI·TLS 프록시, 작업 큐, 정기 백그라운드 작업, 별도 과목 테이블, AI 의미 검증의 완전 자동화는 구현된 기능으로 표시하지 않는다. 운영 보완 사항은 아키텍처 문서에 별도로 기술했다.

## 제출·발표 구성 예시

전체 아키텍처 → 공개/인증 화면 구분 → 대시보드와 과제 관리의 책임 분리 → ERD → AI 분석과 검토·저장 → 학습 계획 → 백업·복원 순서로 설명하면 된다. 오류 경로, 계정별 접근 제어, AI 결과의 사용자 검토를 함께 설명한다.

문서 근거는 소스 코드, 격리된 빈 DB에서 추출한 스키마, Flask URL 맵이다. 사용자 과제 데이터·API 키·비밀번호는 설계 자료에 포함하지 않았다. [검증 기록](diagrams/VALIDATION.md) · [구현 목록 JSON](diagrams/implementation-inventory.json).
