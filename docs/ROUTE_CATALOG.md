# 경로 카탈로그

구현 기준 `537e49f`, 2026-11-24. Flask URL map에서 HEAD/OPTIONS를 제외하고 추출한 40개 규칙이다. `<int:...>` 값은 실제 숫자 ID다. HTML 화면, 변경 폼, 파일 응답을 함께 나열하므로 전부 REST API라는 뜻은 아니다.

공통 정책: 개인 GET은 비로그인 시 로그인으로 이동, 개인 POST는 비로그인 401. 모든 POST는 CSRF 토큰 확인. 개인 항목에는 소유권/부모 연결 검증이 적용된다.

| 메서드 | 경로 | Flask endpoint | 접근/비고 |
|---|---|---|---|
| GET | `/` | `dashboard` | 공개 소개 / 로그인 시 대시보드 |
| GET / POST | `/ai/analyze` | `ai_analyze` | 로그인 필요 |
| POST | `/ai/analyze-file` | `ai_analyze` | 로그인 필요 |
| POST | `/ai/check-requirements` | `check_requirements` | 로그인; 로컬 수량 계산, 저장/외부 호출 없음 |
| POST | `/ai/save` | `ai_save` | 로그인 필요 |
| GET | `/assignments` | `assignment_list` | 로그인 필요 |
| GET | `/assignments/<int:assignment_id>` | `assignment_detail` | 로그인 필요 |
| POST | `/assignments/<int:assignment_id>/attachments` | `add_attachment` | 로그인 필요 |
| GET | `/assignments/<int:assignment_id>/attachments/<int:attachment_id>` | `download_attachment` | 로그인 필요 |
| POST | `/assignments/<int:assignment_id>/attachments/<int:attachment_id>/delete` | `delete_attachment` | 로그인 필요 |
| POST | `/assignments/<int:assignment_id>/auto-replan` | `toggle_auto_replan` | 로그인 필요 |
| POST | `/assignments/<int:assignment_id>/checklist` | `add_checklist_item` | 로그인 필요 |
| POST | `/assignments/<int:assignment_id>/checklist/<int:item_id>/delete` | `delete_checklist_item` | 로그인 필요 |
| POST | `/assignments/<int:assignment_id>/checklist/<int:item_id>/edit` | `edit_checklist_item` | 로그인 필요 |
| POST | `/assignments/<int:assignment_id>/checklist/<int:item_id>/focus` | `focus_task` | 로그인 필요 |
| POST | `/assignments/<int:assignment_id>/checklist/<int:item_id>/toggle` | `toggle_checklist_item` | 로그인 필요 |
| POST | `/assignments/<int:assignment_id>/delete` | `delete_assignment` | 로그인 필요 |
| GET / POST | `/assignments/<int:assignment_id>/edit` | `edit_assignment` | 로그인 필요 |
| POST | `/assignments/<int:assignment_id>/notes` | `add_assignment_note` | 로그인 필요 |
| POST | `/assignments/<int:assignment_id>/notes/<int:note_id>/delete` | `delete_assignment_note` | 로그인 필요 |
| POST | `/assignments/<int:assignment_id>/notes/<int:note_id>/edit` | `edit_assignment_note` | 로그인 필요 |
| POST | `/assignments/<int:assignment_id>/plan` | `make_study_plan` | 로그인 필요 |
| POST | `/assignments/<int:assignment_id>/plan/<int:entry_id>/delete` | `delete_study_plan` | 로그인 필요 |
| POST | `/assignments/<int:assignment_id>/plan/<int:entry_id>/edit` | `edit_study_plan` | 로그인 필요 |
| POST | `/assignments/<int:assignment_id>/replan` | `retry_auto_replan` | 로그인 필요 |
| POST | `/assignments/<int:assignment_id>/status` | `quick_status` | 로그인 필요 |
| GET / POST | `/assignments/new` | `new_assignment` | 로그인 필요 |
| GET / POST | `/auth/login` | `login` | 공개 |
| POST | `/auth/logout` | `logout` | 로그인 필요 |
| GET / POST | `/auth/register` | `register` | 로컬 주소에서만 허용 |
| GET | `/backup` | `backup_settings` | 로그인 필요 |
| POST | `/backup/download` | `backup_download` | 로그인 필요 |
| POST | `/backup/import` | `backup_restore` | 로그인; 동의 + 검증 후 새 항목 추가 |
| GET | `/calendar` | `calendar_view` | 로그인 필요 |
| GET | `/courses` | `courses` | 로그인 필요 |
| GET | `/features` | `public_features` | 공개 |
| GET | `/health` | `health` | 공개 |
| GET | `/preview/<slug>` | `feature_preview` | 공개 고정 예시; 미지정 slug 404 |
| GET | `/schedule` | `schedule_view` | 로그인 필요 |
| GET | `/static/<path:filename>` | `static` | 공개 정적 파일 |

## 경로에서 주의할 구분

- `/`는 로그인 전후 다른 화면을 제공한다. 공개 분기는 개인 과제를 조회하기 전에 반환된다.
- `/ai/analyze-file`은 통합 분석의 POST 호환 경로다. 별도 파일 분석 화면을 가정하지 않는다.
- `/ai/check-requirements`는 Gemini 호출 없이 검토 입력의 개수·길이만 계산한다.
- `/ai/save`는 공지 분석 결과 저장이며, `/assignments/<id>/plan`은 학습 계획 생성 후 저장이다.
- `/assignments/<id>/status`의 done 전환이 완료 보관함 이동이다. 독립적인 archive 엔드포인트/테이블은 없다.
- `/backup/import`는 새 ZIP의 추가 복원이다. 이전 `/backup/restore`, `/export/backup.json`, `/export/assignments.csv`는 제거 상태다.
- `/health`는 앱의 간단한 응답 확인이지 DB·외부 Gemini의 종합 준비 상태 검사는 아니다.
