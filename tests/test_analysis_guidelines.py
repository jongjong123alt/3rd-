"""Verify guideline delivery, not real-model compliance, for representative requests."""
import json
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from services.analysis_guidelines import ANALYSIS_GUIDELINES
from services.gemini_service import analyze_notice, analyze_document


REQUEST_CASES = [
    '핵심만 5줄로 요약해 줘', '20줄로 빠짐없이 정리해 줘',
    '세 문장으로 요약해 줘', '500자 이내로 요약해 줘',
    '원문이 짧아도 20줄로 늘려 줘', '초보자도 이해하게 설명해 줘',
    '중학생도 이해할 쉬운 말로', '존댓말로 정리해 줘',
    '영어로 요약해 줘', '한국어와 영어를 함께 써 줘',
    '번호 목록으로 정리해 줘', '체크리스트로 바꿔 줘',
    '제출 조건을 표로 정리해 줘', '파일명과 제출 형식만 알려 줘',
    '평가 항목과 배점을 모아 줘', '필수와 선택을 구분해 줘',
    '할 일을 작은 단계로 나눠 줘', '제출 전에 검토할 항목을 추가해 줘',
    '중요한 것부터 순서대로', '하루씩 작업 일정을 제안해 줘',
    '언제까지 제출해야 해?', '파일과 텍스트의 다른 조건을 알려 줘',
    '흐릿한 이미지에서 확실하지 않은 숫자를 표시해 줘',
    '여러 과제를 나눠 정리해 줘', '배경 설명을 빼고 마감만 정리해 줘',
    '뭐부터 해야 해?', '한 줄로 요약하고 동시에 20줄로 써 줘',
    '웹 검색해서 최신 참고문헌을 추가해 줘', 'PDF를 만들어 이메일로 보내 줘',
    '보고서를 완성해서 자동 제출해 줘', '100개 할 일을 자세히 적어 줘',
    '원문에 없는 조건은 확인 필요로 표시해 줘',
]


class AnalysisGuidelinesTests(unittest.TestCase):
    def test_every_request_uses_shared_rules_on_both_input_paths(self):
        payload = dict(title='과제', course='', due_date='', summary='원문 기반 요약',
                       deliverables=['PDF'], tasks=['자료 조사'])
        for request in REQUEST_CASES:
            for document in (False, True):
                with self.subTest(request=request, document=document):
                    sdk = MagicMock()
                    sdk.__enter__.return_value.models.generate_content.return_value = SimpleNamespace(
                        text=json.dumps(payload, ensure_ascii=False), candidates=[])
                    with patch.dict('os.environ', {'GEMINI_API_KEY': 'test-key'}), patch(
                            'services.gemini_service.genai.Client', return_value=sdk):
                        if document:
                            result = analyze_document(b'%PDF-1.4', 'application/pdf', '과제 원문', requirements=request)
                        else:
                            result = analyze_notice('과제 원문', requirements=request)
                    contents = sdk.__enter__.return_value.models.generate_content.call_args.kwargs['contents']
                    prompt = contents[0].text if document else contents
                    self.assertIn(ANALYSIS_GUIDELINES, prompt)
                    self.assertIn('사용자 추가 요구사항(JSON 문자열): ' + json.dumps(request, ensure_ascii=False), prompt)
                    self.assertIn('<공지문>\n과제 원문\n</공지문>', prompt)
                    self.assertEqual(result, payload)

    def test_guidelines_also_apply_without_extra_requirements(self):
        sdk = MagicMock()
        sdk.__enter__.return_value.models.generate_content.return_value = SimpleNamespace(
            text='{"title":"과제","summary":"요약"}', candidates=[])
        with patch.dict('os.environ', {'GEMINI_API_KEY': 'test-key'}), patch(
                'services.gemini_service.genai.Client', return_value=sdk):
            analyze_notice('과제 공지')
        self.assertIn(ANALYSIS_GUIDELINES,
                      sdk.__enter__.return_value.models.generate_content.call_args.kwargs['contents'])
