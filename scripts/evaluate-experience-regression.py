#!/usr/bin/env python3
"""Replay reviewed historical fixtures through the production explicit gateway.

Private artifacts only. Never migrate the owner's ledger or manufacture reviews.
The evaluation adapter is intentionally separate from production extraction.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import ExitStack
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import struct
import subprocess
import sys
import time
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))


def sha(path):
    with Path(path).open('rb') as stream:
        return 'sha256:' + hashlib.file_digest(stream, 'sha256').hexdigest()


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines()
            if line.strip()]


def readonly(path):
    conn = sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def gateway(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def convert_ref(vault, legacy):
    """Convert old universal-newline offsets only against the frozen byte hash."""
    import _source_ref as sr
    match = re.fullmatch(r'(.+)#(\d+):(\d+)@(sha256:[0-9a-f]{64})', legacy)
    if not match:
        raise ValueError('malformed legacy reference')
    relative, start, end, digest = match.groups()
    path = sr._candidate(Path(vault), relative, require_exists=True)
    raw = path.read_bytes()
    if 'sha256:' + hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError('frozen source hash mismatch')
    text = raw.decode('utf-8')
    normalized = text.replace('\r\n', '\n').replace('\r', '\n')
    start, end = int(start), int(end)
    if not 0 <= start < end <= len(normalized):
        raise ValueError('invalid frozen offsets')
    # The legacy builder used read_text(); the current resolver uses raw UTF-8.
    def raw_offset(offset):
        if '\r' not in text:
            return offset
        position = 0
        for _ in range(offset):
            position += 2 if text[position:position + 2] == '\r\n' else 1
        return position
    ref = sr.make_source_ref(vault, relative, start=raw_offset(start), end=raw_offset(end))
    if ref['source_sha256'] != digest:
        raise ValueError('source changed during conversion')
    resolved = sr.resolve_source_ref(vault, ref)
    if (resolved['status'] != 'valid' or
            resolved['passage'].replace('\r\n', '\n').replace('\r', '\n')
            != normalized[start:end]):
        raise ValueError('converted passage does not match frozen range')
    return ref


def percentile(values, fraction=.95):
    return sorted(values)[max(0, math.ceil(len(values) * fraction) - 1)] if values else None


def metrics(cases, hits, latencies, statuses=None):
    statuses = statuses if statuses is not None else ['ok'] * len(cases)
    if not len(cases) == len(hits) == len(latencies) == len(statuses):
        raise ValueError('evaluation lengths differ')
    positives = [i for i, case in enumerate(cases) if case.get('expected_experience')]
    negatives = [i for i, case in enumerate(cases) if not case.get('expected_experience')]
    found = sum(cases[i]['expected_experience'] in hits[i][:3] for i in positives)
    abstained = sum(not hits[i] and statuses[i] in {'ok', 'no_hit'} for i in negatives)
    return {'cases': len(cases), 'positive_cases': len(positives),
            'negative_cases': len(negatives), 'positive_hits': found,
            'hit_at_3': found / len(positives) if positives else None,
            'negative_correct_no_hit': abstained,
            'negative_no_hit_specificity': abstained / len(negatives) if negatives else None,
            'unavailable': sum(s not in {'ok', 'no_hit'} for s in statuses),
            'p95_ms': percentile(latencies)}


def validate_output(output, vault):
    output, vault = Path(output).resolve(), Path(vault).resolve()
    private = vault / '06-claude' / 'evaluations'
    if (not output.is_relative_to(private) or output == private
            or output.is_relative_to(SCRIPTS.parent)):
        raise ValueError('output must be a new private vault evaluation subdirectory')
    if output.exists():
        raise ValueError('refusing to overwrite an existing evaluation')
    return output


def decode_record(row):
    return {key.removesuffix('_json'): json.loads(value) if key.endswith('_json') else value
            for key, value in dict(row).items()}


def build_projection(vault, old_db, isolated):
    import _experience as xp
    refs, excluded = {}, []
    old = readonly(old_db)
    try:
        xp.enable_recall_vectors(old)
        meta = dict(old.execute('SELECT key, value FROM meta'))
        dim, embed_id = int(meta['dim']), meta['embed_id']
        conn = xp.connect(xp.projection_path(isolated))
        try:
            xp.ensure_projection_schema(conn, dim=dim, embed_id=embed_id)
            for row in old.execute('SELECT * FROM experiences ORDER BY experience_id'):
                record = decode_record(row)
                try:
                    converted = [convert_ref(vault, ref) for ref in record['source_refs']]
                    if not converted or not record['outcome_refs'] or record['status'] != 'validated':
                        raise ValueError('ineligible historical fixture')
                except (ValueError, OSError, UnicodeError) as exc:
                    excluded.append({'experience_id': record['experience_id'],
                                     'reason': str(exc)})
                    continue
                body = ' '.join(record[key] for key in
                                ('situation', 'goal', 'approach', 'action', 'lesson', 'applicability'))
                stored = old.execute('SELECT d.doc_id, f.body FROM docs d JOIN fts_docs f '
                                     'ON f.rowid=d.doc_id WHERE d.path=?',
                                     ('experience::' + record['experience_id'],)).fetchone()
                if stored is None or stored['body'] != body:
                    raise ValueError('frozen vector text mismatch')
                blob = old.execute('SELECT embedding FROM vec_docs WHERE doc_id=?',
                                   (stored['doc_id'],)).fetchone()[0]
                vector = struct.unpack('<' + 'f' * dim, blob)
                record.update(source_refs=converted, evidence_state='verified', review_state='accepted')
                record['content_hash'] = xp.experience_content_hash(record)
                xp.projection_upsert(conn, record)
                xp.index_experience(conn, record['experience_id'], vector=vector)
                refs.update({ref['source_ref_id']: ref for ref in converted})
            conn.commit()
            included = conn.execute('SELECT COUNT(*) FROM experiences').fetchone()[0]
        finally:
            conn.close()
    finally:
        old.close()
    return {'included': included, 'excluded': excluded, 'dim': dim, 'embed_id': embed_id}, refs


def owner_snapshot(vault):
    import _experience as xp
    import _source_ref as sr
    result = {}
    for kind, path in [('ledger', xp.ledger_path(vault)), ('projection', xp.projection_path(vault))]:
        if not path.exists():
            result[kind] = {'available': False}
            continue
        conn = readonly(path)
        try:
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            counts = {t: conn.execute('SELECT COUNT(*) FROM ' + t).fetchone()[0]
                      for t in ('experience_events', 'experience_outcomes', 'experience_reviews', 'experiences')
                      if t in tables}
            if 'experiences' in tables:
                records = [xp.experience(conn, r[0]) for r in conn.execute('SELECT experience_id FROM experiences')]
                counts['eligible'] = sum(xp._production_eligible(r) for r in records)
                counts['reference_states'] = dict(Counter(
                    sr.resolve_source_ref(vault, ref)['status'] for r in records for ref in r['source_refs']))
            if 'experience_outcomes' in tables:
                counts['outcome_states'] = dict(conn.execute('SELECT state, COUNT(*) FROM experience_outcomes GROUP BY state'))
            result[kind] = counts
        finally:
            conn.close()
    return result


def negative_controls(exp_gateway, src_gateway, vault, isolated, refs):
    import _source_ref as sr
    results = {}
    for name, api in [('experience', exp_gateway), ('source', src_gateway)]:
        for mode in ('normal', 'advisory', 'automatic', 'fallback', 'ranking', 'promotion', 'hook', 'injection'):
            out = api.run({'mode': mode, 'prompt': 'test'}, vault=isolated)
            expected = 'not_routed' if mode == 'normal' else 'policy_disabled'
            results[name + '_' + mode] = out['status'] == expected and not out['hits']
        with patch('_settings.get', return_value=False):
            out = api.run({'mode': 'explicit', 'prompt': 'test'}, vault=isolated)
            results[name + '_disabled'] = out['status'] == 'disabled' and not out['hits']
    if refs:
        valid = next(iter(refs.values()))
        for state in ('invalid', 'stale', 'missing', 'redacted'):
            ref = dict(valid)
            if state == 'invalid':
                ref['source_ref_id'] = 'invalid'
            elif state == 'stale':
                ref['source_sha256'] = 'sha256:' + '0' * 64
                ref['source_ref_id'] = sr.source_ref_id(ref)
            elif state == 'missing':
                ref['source_path'] = '01-raw/sessies/evaluation-nonexistent-' + os.urandom(12).hex() + '.md'
                ref['source_ref_id'] = sr.source_ref_id(ref)
            else:
                ref['redaction_state'] = 'redacted'
            out = src_gateway.run({'mode': 'verify', 'source_ref': ref}, vault=vault)
            results['source_' + state] = (out['status'] == 'evidence_unavailable'
                and state in out['flags'] and all('passage' not in hit for hit in out['hits']))
    return results


def run_arm(cases, api, source_api, isolated, vault, refs, embed_id, vectors, arm):
    rows, durations, hit_ids, statuses = [], [], [], []
    shown = valid_refs = leaks = state_errors = checked_states = 0
    routes = Counter()
    for index, case in enumerate(cases):
        vector = vectors.get(case['id']) if arm == 'hybrid' else None
        started = time.perf_counter()
        out = api.run({'mode': 'explicit', 'prompt': case['query'], 'embed_id': embed_id},
                      embed_fn=lambda _query: vector, vault=isolated)
        elapsed = (time.perf_counter() - started) * 1000
        durations.append(elapsed)
        routes[out.get('retrieval_route', 'none')] += 1
        ids = [hit['experience_id'] for hit in out['hits']]
        hit_ids.append(ids)
        statuses.append(out['status'])
        for hit in out['hits']:
            stamp = hit.get('validation_stamp', {})
            leaks += int(stamp.get('status') != 'validated' or stamp.get('evidence_state') != 'verified'
                         or stamp.get('review_state') != 'accepted'
                         or 'source_refs' in hit or 'passage' in hit)
            for ref_id in hit.get('source_ref_ids', []):
                shown += 1
                exact = source_api.run({'mode': 'verify', 'source_ref': refs.get(ref_id)}, vault=vault)
                valid_refs += int(exact['status'] == 'ok' and exact['hits'][0].get('fresh', False))
            if hit['experience_id'] == case.get('expected_experience'):
                for field, expected in [('outcome_state', 'expected_state'),
                                        ('attempt_state', 'expected_attempt_state'),
                                        ('resolution_state', 'expected_resolution_state')]:
                    if expected in case:
                        checked_states += 1
                        state_errors += int(hit.get(field) != case[expected])
        rows.append({'id': case['id'], 'response': out, 'gateway_ms': elapsed})
    result = metrics(cases, hit_ids, durations, statuses)
    result.update(routes=dict(routes), shown_references=shown, valid_references=valid_refs,
                  exact_evidence_precision=valid_refs / shown if shown else None,
                  candidate_or_raw_leaks=leaks, state_checks=checked_states, state_errors=state_errors)
    result['gates'] = {'hit_at_3': result['hit_at_3'] is not None and result['hit_at_3'] >= .85,
                       'exact_evidence': shown > 0 and shown == valid_refs,
                       'no_leakage': bool(cases) and leaks == 0,
                       'state_labels': checked_states > 0 and state_errors == 0,
                       'warm_gateway_latency': result['p95_ms'] is not None and result['p95_ms'] <= 250,
                       'availability': bool(cases) and result['unavailable'] == 0}
    result['negative_specificity_target_met'] = (result['negative_no_hit_specificity'] is not None
                                               and result['negative_no_hit_specificity'] >= .90)
    return result, rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vault', type=Path, required=True)
    parser.add_argument('--input-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    configured = os.environ.get('KENNISBANK_VAULT')
    if configured and Path(configured).resolve() != args.vault.resolve():
        parser.error('vault differs from KENNISBANK_VAULT')
    os.environ['KENNISBANK_VAULT'] = str(args.vault.resolve())
    os.environ['KB_USAGE_DISABLE'] = '1'
    output = validate_output(args.output_dir, args.vault)
    output.mkdir(parents=True)
    paths = {name: args.input_dir / name for name in ('experience-cases.jsonl',
             'experience-holdout-final.db', 'experience-action-master.jsonl', 'experience-action-reviews.jsonl')}
    hashes = {name: sha(path) for name, path in paths.items()}
    cases = read_rows(paths['experience-cases.jsonl'])
    if not cases or len({case['id'] for case in cases}) != len(cases):
        raise ValueError('nonempty unique case IDs required')
    isolated = output / 'isolated-vault'
    before = owner_snapshot(args.vault)
    projection, refs = build_projection(args.vault, paths['experience-holdout-final.db'], isolated)
    print(json.dumps({'stage': 'projection', 'included': projection['included'],
                      'excluded': len(projection['excluded'])}), flush=True)
    import _embeddings as emb
    import _settings
    if emb.embed_id() != projection['embed_id']:
        raise ValueError('configured embedder does not match frozen vectors')
    api, src_api = gateway('kb-experience-recall'), gateway('kb-source-recall')
    original_get = _settings.get
    def eval_setting(key, default=None):
        return True if key in {'experience_explicit_recall', 'source_explicit_recall'} else original_get(key, default)
    summary, private = {}, {}
    with ExitStack() as stack:
        stack.enter_context(patch('_settings.get', side_effect=eval_setting))
        # Both telemetry entrypoints are disabled as well as KB_USAGE_DISABLE.
        stack.enter_context(patch('_usage.log_exposures', return_value=None))
        stack.enter_context(patch('_usage.log_projection_metric', return_value=None))
        api.run({'mode': 'explicit', 'prompt': cases[0]['query']}, embed_fn=lambda _: None, vault=isolated)
        summary['lexical'], private['lexical'] = run_arm(cases, api, src_api, isolated, args.vault,
                                                       refs, projection['embed_id'], {}, 'lexical')
        print(json.dumps({'stage': 'lexical', **summary['lexical']}), flush=True)
        vectors, embedding_ms, failures = {}, [], []
        for index, case in enumerate(cases):
            started = time.perf_counter()
            try:
                vector = emb.embed_query(case['query'], timeout=60)
                if vector is None or len(vector) != projection['dim']:
                    raise ValueError('missing or incompatible embedding')
                vectors[case['id']] = list(vector)
            except Exception as exc:
                failures.append({'id': case['id'], 'error': type(exc).__name__})
            embedding_ms.append((time.perf_counter() - started) * 1000)
            if (index + 1) % 5 == 0 or index + 1 == len(cases):
                print(json.dumps({'stage': 'query_embedding', 'done': index + 1,
                                  'total': len(cases), 'failures': len(failures)}), flush=True)
        if vectors:
            api.run({'mode': 'explicit', 'prompt': cases[0]['query'], 'embed_id': projection['embed_id']},
                    embed_fn=lambda _: next(iter(vectors.values())), vault=isolated)
        summary['hybrid'], private['hybrid'] = run_arm(cases, api, src_api, isolated, args.vault,
                                                     refs, projection['embed_id'], vectors, 'hybrid')
        summary['hybrid']['gates']['all_queries_hybrid'] = summary['hybrid']['routes'] == {'hybrid': len(cases)}
        summary['embedding'] = {'successful': len(vectors), 'failed': len(failures),
                                'p95_ms': percentile(embedding_ms), 'first_query_ms': embedding_ms[0]}
        summary['hybrid']['end_to_end_p95_ms'] = percentile(
            [t + row['gateway_ms'] for t, row in zip(embedding_ms, private['hybrid'])])
        summary['controls'] = negative_controls(api, src_api, args.vault, isolated, refs)
    import _paired_action_eval
    master = read_rows(paths['experience-action-master.jsonl'])
    summary['historical_action_rescore'] = _paired_action_eval.score(
        [r['blind'] for r in master], [r['key'] for r in master], read_rows(paths['experience-action-reviews.jsonl']))
    summary.update(schema_version=1, evaluation_kind='historical_regression_replay_not_natural_canary',
                   commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=SCRIPTS.parent, text=True).strip(),
                   harness_sha256=sha(__file__), frozen_inputs_sha256=hashes,
                   frozen_inputs_unchanged=all(sha(paths[name]) == digest for name, digest in hashes.items()),
                   projection={key: value for key, value in projection.items() if key != 'excluded'},
                   excluded_records=len(projection['excluded']), owner_before=before, owner_after=owner_snapshot(args.vault))
    private.update(excluded=projection['excluded'], embedding_failures=failures,
                   query_vectors=vectors, refs=refs)
    for name, data in [('private-results.json', private), ('aggregate.json', summary)]:
        (output / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary, indent=2), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
