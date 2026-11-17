"""Deterministic checks only; semantic accuracy always needs human review."""
import re

_WORD_NUMBERS = {'한':1,'하나':1,'두':2,'둘':2,'세':3,'셋':3,'네':4,'넷':4,'다섯':5,'여섯':6,'일곱':7,'여덟':8,'아홉':9,'열':10}


def _compare(actual, target, bound):
    return (actual <= target if bound in ('이내','이하') else actual < target if bound == '미만' else
            actual >= target if bound == '이상' else actual > target if bound == '초과' else actual == target)


def inspect_requirements(requirements, result):
    if not requirements.strip():
        return []
    text = requirements
    for word, number in sorted(_WORD_NUMBERS.items(), key=lambda p:-len(p[0])):
        text = re.sub(r'(?<![가-힣])'+word+r'(?=\s*(?:줄|문장|자|개))', str(number), text)
    summary = result.get('summary','')
    checks = []
    for match in re.finditer(r'(?:(최대|최소|적어도|많아야)\s*)?(\d{1,6})\s*(줄|문장|자)\s*(이내|이하|미만|이상|초과)?', text):
        prefix, target, unit, suffix = match[1], int(match[2]), match[3], match[4]
        bound = suffix or ('이하' if prefix in ('최대','많아야') else '이상' if prefix else None)
        if prefix and suffix and ((prefix in ('최대','많아야')) != (suffix in ('이내','이하','미만'))):
            checks.append({'status':'manual','label':f'{target}{unit} 요청','detail':'최소·최대 조건이 충돌합니다. 직접 확인해 주세요.'})
            continue
        if unit == '줄':
            actual = len([line for line in summary.splitlines() if line.strip()])
        elif unit == '자':
            actual = len(summary)
        else:
            checks.append({'status':'manual', 'label':f'{target}문장 요청', 'detail':'문장 경계가 모호할 수 있어 직접 확인해 주세요.'})
            continue
        ok = _compare(actual, target, bound)
        checks.append({'status':'passed' if ok else 'unmet', 'label':f'{target}{unit}{bound or ""} 요청',
                       'detail':f'현재 {actual}{unit} · '+('조건 충족' if ok else '조건과 다릅니다. 검토·수정하거나 다시 분석하세요.')})
    for pattern in (r'(할\s*일|체크리스트|제출물)[^\d\n]{0,12}(\d{1,4})\s*개\s*(이내|이하|미만|이상|초과)?',
                    r'(\d{1,4})\s*개(?:의)?\s*(할\s*일|체크리스트|제출물)'):
        for match in re.finditer(pattern, text):
            reverse = pattern.startswith(r'(\d')
            label, target = (match[2], int(match[1])) if reverse else (match[1], int(match[2]))
            bound = None if reverse else match[3]
            if not reverse:
                before_number = match[0][:match[0].find(match[2])]
                if not bound:
                    bound = '이하' if '최대' in before_number else '이상' if '최소' in before_number else None
            field = 'deliverables' if label == '제출물' else 'tasks'
            actual = len(result.get(field, []))
            checks.append({'status':'passed' if _compare(actual,target,bound) else 'unmet',
                           'label':f'{label} {target}개{bound or ""} 요청','detail':f'현재 {actual}개 · 항목 수 기준 점검'})
    checks.append({'status':'manual','label':'내용·언어·평가 기준·사실성',
                   'detail':'자동 검사는 개수와 길이만 확인합니다. 원문 반영과 요청의 의미는 직접 검토해 주세요.'})
    return checks
