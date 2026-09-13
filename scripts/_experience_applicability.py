"""Pure development helpers for applicability evaluation, not a rollout policy.

No selected threshold lives here. Candidate scorers must earn one on separate
development data before their frozen policy is evaluated or wired to production.
"""
from __future__ import annotations

import math
import re

# Question framing is not evidence of subject agreement. Intentionally scoped to
# this experimental scorer; the normal wiki/memory tokenizer is unchanged.
_STOP = set('''a an and are as at be been being by can could did do does for from
had has have how i if in into is it its me my of on or our should so than that the
their them then there these they this those to us was we were what when where
which why will with would you your
aan als bij dan dat de deze die dit een en er geen gedaan ging had hebben heb het
hier hoe hun ik in is je kan kunnen maar meer met mijn moet naar niet nog nu of
om ons ook op over te toen tot uit van voor waar waarom was wat we welke werd
werden werkte werken wil willen wordt zijn zo zou zullen'''.split())
_TEXT_FIELDS = ('situation', 'goal', 'approach', 'action', 'observed_result',
                'lesson', 'applicability')


def terms(value):
    return {token for token in re.findall(r'\w+', str(value).casefold())
            if token not in _STOP and (len(token) >= 3 or token.isdigit())}


def lexical_score(query, record):
    """Fraction of non-framing query terms supported by the bounded record."""
    query_terms = terms(query)
    document_terms = terms(' '.join(str(record.get(key) or '') for key in _TEXT_FIELDS))
    return len(query_terms & document_terms) / len(query_terms) if query_terms else 0.0


def _validate_rows(rows):
    ids = [str(row.get('id') or '') for row in rows]
    if any(not key for key in ids) or len(set(ids)) != len(ids):
        raise ValueError('nonempty unique observation IDs required')
    for row in rows:
        for candidate in row.get('candidates', []):
            if not math.isfinite(float(candidate['score'])):
                raise ValueError('candidate scores must be finite')


def measure(observations, threshold):
    rows = list(observations)
    _validate_rows(rows)
    if not math.isfinite(float(threshold)):
        raise ValueError('threshold must be finite')
    positive = negative = found = abstained = failed = shown = wrong = 0
    for row in rows:
        expected = row.get('expected_experience')
        positive += expected is not None
        negative += expected is None
        if row.get('status', 'ok') not in {'ok', 'no_hit'}:
            failed += 1
            continue
        selected = sorted((item for item in row.get('candidates', [])
                           if float(item['score']) >= threshold),
                          key=lambda item: (-float(item['score']), item['id']))[:3]
        shown += len(selected)
        if expected is not None:
            found += any(item['id'] == expected for item in selected)
        else:
            abstained += not selected
            wrong += bool(selected)
    return {'positive_n': positive, 'negative_n': negative, 'positive_hits': found,
            'hit_at_3': found / positive if positive else None,
            'negative_correct_no_hit': abstained,
            'negative_no_hit_specificity': abstained / negative if negative else None,
            'failed': failed, 'shown': shown, 'negative_false_hits': wrong}


def select_threshold(observations, *, thresholds, min_hit=.85, min_specificity=.90):
    rows = list(observations)
    values = sorted({float(value) for value in thresholds})
    if not values or any(not math.isfinite(value) for value in values):
        raise ValueError('finite nonempty threshold grid required')
    trials = [{'threshold': value, **measure(rows, value)} for value in values]
    eligible = [row for row in trials if row['positive_n'] and row['negative_n']
                and row['failed'] == 0 and row['hit_at_3'] >= min_hit
                and row['negative_no_hit_specificity'] >= min_specificity]
    selected = max(eligible, key=lambda row: (row['hit_at_3'],
                   row['negative_no_hit_specificity'], row['threshold'])) if eligible else None
    return {'selection_source': 'development_only', 'selected_threshold':
            selected['threshold'] if selected else None, 'selected': selected,
            'trials': trials, 'constraints': {'min_hit_at_3': min_hit,
                                            'min_negative_specificity': min_specificity}}


def _paths(case):
    result = set()
    refs = list(case.get('source_refs') or [])
    for record in case.get('records') or []:
        refs.extend(record.get('source_refs') or [])
    for ref in refs:
        value = ref.get('source_path', '') if isinstance(ref, dict) else str(ref).split('#')[0]
        if value:
            result.add(value.replace('\\', '/').casefold())
    return result


def assert_independent(left, right):
    left, right = list(left), list(right)
    for key in ('id', 'query'):
        def normalized(row):
            return ' '.join(re.findall(r'\w+', str(row.get(key) or '').casefold()))
        first = {normalized(row) for row in left} - {''}
        second = {normalized(row) for row in right} - {''}
        if first & second:
            raise ValueError(key + ' overlap')
    sources_left = set().union(*(_paths(case) for case in left)) if left else set()
    sources_right = set().union(*(_paths(case) for case in right)) if right else set()
    if sources_left & sources_right:
        raise ValueError('raw source overlap')
