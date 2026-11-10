"""Public feature previews. Never load user-owned assignments for guests."""
from datetime import date, timedelta
import calendar
from flask import abort, render_template

# Descriptions are product documentation, not live user data.
FEATURES = [
    ("F-01", "과제 대시보드", "과제 수와 진행 현황을 한눈에 확인", "dashboard"),
    ("F-02", "과제 등록·관리", "과제명, 과목, 제출기한, 진행 상태 관리", "assignments"),
    ("F-03", "체크리스트", "할 일 추가·수정·완료 및 진행률 확인", "checklist"),
    ("F-04", "AI 공지 분석", "공지문에서 과제 조건과 해야 할 일 추출", "ai"),
    ("F-05", "AI 분석 결과 저장", "AI 분석을 검토·수정한 뒤 과제로 저장", "ai"),
    ("F-06", "마감 달력", "월별 과제 마감일 확인", "calendar"),
    ("F-07", "검색·필터", "과목·상태·기한·우선순위별 검색", "assignments"),
    ("F-08", "D-day 표시", "마감 임박 과제와 기한 지난 과제 구분", "dashboard"),
    ("F-09", "우선순위", "높음·보통·낮음으로 분류·정렬", "assignments"),
    ("F-10", "백업·내보내기", "JSON 백업과 CSV 내보내기", "files"),
    ("F-11", "과제별 메모", "진행 기록과 참고 메모 저장", "checklist"),
    ("F-12", "과제 통계", "상태·과목·체크리스트 진행률 분석", "insights"),
    ("F-13", "마감 알림·오늘 할 일", "다가오는 기한과 오늘의 작업 확인", "alerts"),
    ("F-14", "AI 학습 일정", "Gemini가 과제 작업을 날짜별로 제안", "ai"),
    ("F-15", "일정 충돌 확인", "같은 날 마감하는 과제를 묶어 표시", "schedule"),
    ("F-16", "백업 복원", "기존 백업 데이터를 검증하고 추가 복원", "files"),
    ("F-17", "첨부파일", "과제별 파일 업로드·다운로드·삭제", "files"),
    ("F-18", "회원가입·로그인", "계정별 과제 및 데이터 접근 분리", "dashboard"),
    ("F-19", "PDF·이미지 AI 분석", "파일 속 공지 내용을 Gemini로 분석", "ai"),
    ("F-20", "브라우저 마감 알림", "동의 후 대시보드에서 마감 알림 표시", "alerts"),
    ("F-21", "AI 자동 재계획", "변경된 과제에 맞춰 AI 일정을 다시 제안", "ai"),
]
PREVIEWS = {
    "dashboard": ("대시보드", "과제와 마감 현황을 한눈에 보는 화면"),
    "assignments": ("과제 관리", "과제 등록, 검색, 필터, 우선순위"),
    "checklist": ("체크리스트·메모", "과제별 진행률과 작업 기록"),
    "ai": ("Gemini AI 분석·일정", "공지 텍스트·파일 분석과 학습 일정 생성"),
    "calendar": ("마감 달력", "월별 제출기한을 확인하는 달력"),
    "schedule": ("일정 충돌", "같은 날 마감하는 과제를 파악하는 화면"),
    "insights": ("과제 통계", "진행 상태와 과목별 분포"),
    "files": ("파일·백업", "과제 첨부파일과 내보내기·복원"),
    "alerts": ("마감 알림", "오늘의 작업과 브라우저 알림"),
}


def register_public(app):
    @app.get("/features")
    def public_features():
        return render_template("public_features.html", features=FEATURES, previews=PREVIEWS)

    @app.get("/preview/<slug>")
    def feature_preview(slug):
        if slug not in PREVIEWS:
            abort(404)
        today = date.today()
        weeks = calendar.Calendar(firstweekday=6).monthdayscalendar(today.year, today.month)
        example_day = min(today.day + 2, calendar.monthrange(today.year, today.month)[1])
        return render_template(
            "public_preview.html", slug=slug, info=PREVIEWS[slug],
            features=[item for item in FEATURES if item[3] == slug],
            year=today.year, month=today.month, weeks=weeks, example_day=example_day,
        )
