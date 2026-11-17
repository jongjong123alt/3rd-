"""Additional analysis requests stay separate from source data and survive review/save."""
import io
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import app as project
from services.gemini_service import GeminiAnalysisError, _normalize, analyze_notice, analyze_document


SUMMARY = '\n'.join(f'{i}. 공지에서 확인한 핵심 항목' for i in range(1, 21))
RESULT = dict(title='과제', course='운영체제', due_date='', summary=SUMMARY,
              deliverables=['PDF'], tasks=['자료 조사'])


class RequirementsPromptTests(unittest.TestCase):
    def test_text_and_file_receive_separate_format_request(self):
        for with_file in (False, True):
            with self.subTest(with_file=with_file):
                sdk = MagicMock()
                sdk.__enter__.return_value.models.generate_content.return_value = SimpleNamespace(
                    text=json.dumps(RESULT, ensure_ascii=False), candidates=[])
                with patch.dict('os.environ', {'GEMINI_API_KEY': 'test-key'}), patch(
                        'services.gemini_service.genai.Client', return_value=sdk):
                    if with_file:
                        answer = analyze_document(b'%PDF-1.4', 'application/pdf', '실제 공지',
                                                  requirements='핵심 요약을 20줄로 작성해 줘')
                    else:
                        answer = analyze_notice('실제 공지', requirements='핵심 요약을 20줄로 작성해 줘')
                contents = sdk.__enter__.return_value.models.generate_content.call_args.kwargs['contents']
                prompt = contents[0].text if with_file else contents
                self.assertIn('<공지문>\n실제 공지\n</공지문>', prompt)
                self.assertIn('사용자 추가 요구사항(JSON 문자열)', prompt)
                self.assertIn('20줄', prompt)
                self.assertIn('기본 1~3문장 대신', prompt)
                self.assertNotIn('summary(string, 한국어 1~3문장)', prompt)
                self.assertEqual(answer['summary'].splitlines(), SUMMARY.splitlines())

    def test_long_summary_is_not_silently_cut(self):
        with self.assertRaisesRegex(GeminiAnalysisError, '2,000자'):
            _normalize({**RESULT, 'summary': '가' * 2001})

    def test_service_rejects_oversized_requirements_before_sdk_call(self):
        with patch('services.gemini_service.genai.Client') as sdk:
            for call in (lambda: analyze_notice('공지', requirements='가' * 2001),
                         lambda: analyze_document(b'%PDF-1.4', 'application/pdf', requirements='가' * 2001)):
                with self.assertRaisesRegex(GeminiAnalysisError, '2,000자'):
                    call()
            sdk.assert_not_called()


class RequirementsRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.db_patch = patch.object(project, 'DB_PATH', Path(self.temp.name) / 'test.db')
        self.db_patch.start()
        self.client = project.create_app({'TESTING': True, 'SECRET_KEY': 'tests-only'}).test_client()
        self.client.get('/ai/analyze')
        with self.client.session_transaction() as session:
            self.token = session['csrf_token']

    def tearDown(self):
        self.db_patch.stop()
        self.temp.cleanup()

    def post(self, **fields):
        return self.client.post('/ai/analyze', data={'csrf_token': self.token, **fields})

    def test_text_request_forwarding_and_multiline_review_save(self):
        with patch('app.analyze_notice', return_value=RESULT) as analyze:
            response = self.post(notice='실제 공지', requirements='핵심 요약을 20줄로 작성해 줘')
        analyze.assert_called_once_with('실제 공지', requirements='핵심 요약을 20줄로 작성해 줘')
        self.assertEqual(response.status_code, 200)
        self.assertIn(SUMMARY, response.get_data(as_text=True))
        with project.connect_db() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM assignments').fetchone()[0], 0)
        saved = self.client.post('/ai/save', data={
            'csrf_token': self.token, 'title': '검토한 과제', 'summary': SUMMARY,
            'deliverables': 'PDF', 'tasks': '자료 조사'})
        self.assertEqual(saved.status_code, 302)
        with project.connect_db() as db:
            self.assertIn(SUMMARY, db.execute('SELECT description FROM assignments').fetchone()[0])

    def test_pdf_request_forwarding(self):
        with patch('app.analyze_document', return_value=RESULT) as analyze:
            response = self.post(notice='', requirements='20줄로 요약해 줘',
                                 document=(io.BytesIO(b'%PDF-1.4\nnotice'), 'notice.pdf'))
        self.assertEqual(response.status_code, 200)
        analyze.assert_called_once_with(b'%PDF-1.4\nnotice', 'application/pdf', '', requirements='20줄로 요약해 줘')

    def test_requirements_alone_do_not_invoke_ai(self):
        with patch('app.analyze_notice') as text, patch('app.analyze_document') as document:
            response = self.post(requirements='20줄로 요약해 줘')
        self.assertEqual(response.status_code, 400)
        self.assertIn('추가 요구사항만으로는 분석할 수 없습니다', response.get_data(as_text=True))
        text.assert_not_called()
        document.assert_not_called()

    def test_error_keeps_additional_request(self):
        with patch('app.analyze_notice', side_effect=GeminiAnalysisError('잠시 후 재시도')):
            response = self.post(notice='실제 공지', requirements='20줄로 요약해 줘')
        self.assertEqual(response.status_code, 502)
        self.assertIn('20줄로 요약해 줘', response.get_data(as_text=True))

    def test_oversized_request_is_rejected(self):
        with patch('app.analyze_notice') as analyze:
            response = self.post(notice='실제 공지', requirements='가' * 2001)
        self.assertEqual(response.status_code, 400)
        analyze.assert_not_called()
