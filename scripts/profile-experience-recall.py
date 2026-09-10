#!/usr/bin/env python3
"""Read-only phase profiling of the real explicit gateway on private fixtures."""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import sqlite3
import statistics
import sys
import threading
import time
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))


def digest(path):
    if not Path(path).is_file():
        return None
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def telemetry_snapshot(vault):
    """Hash the usage database and SQLite sidecars without opening it writable."""
    base = Path(vault) / '.claude' / 'kb-usage.db'
    return {str(path): digest(path) for path in
            (base, Path(str(base) + '-wal'), Path(str(base) + '-shm'))}


def connect_read_only(path):
    return sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)


def validate_cached_vectors(cases, vectors, *, dimension):
    valid, failures = {}, []
    for case in cases:
        key = case['id']
        vector = vectors.get(key)
        if vector is None:
            failures.append({'id': key, 'reason': 'missing_cached_vector'})
        elif (not isinstance(vector, (list, tuple)) or len(vector) != dimension
              or any(not isinstance(x, (int, float)) or not math.isfinite(x) for x in vector)):
            failures.append({'id': key, 'reason': 'incompatible_cached_vector'})
        else:
            valid[key] = vector
    return valid, failures


def summarize(values):
    return {'n': len(values), 'p50_ms': statistics.median(values) if values else None,
            'p95_ms': sorted(values)[math.ceil(.95 * len(values)) - 1] if values else None,
            'max_ms': max(values) if values else None}


def _gateway():
    spec = importlib.util.spec_from_file_location('profile_gateway', SCRIPTS / 'kb-experience-recall.py')
    api = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(api)
    return api


def profile(projection, isolated, cases, vectors, *, repeat=1, gateway_run=None,
            concurrent_load=False, query_embed=None):
    import _experience as xp
    import _settings
    if repeat < 1:
        raise ValueError('repeat must be positive')
    before = digest(projection)
    # The gateway receives the isolated vault explicitly. Point the usage
    # logger at that same private root for the duration of the run so a live
    # maintenance process cannot race the evaluator's integrity check and the
    # evaluator can never append to the owner vault's telemetry database.
    telemetry_vault = Path(isolated).resolve()
    telemetry_before = telemetry_snapshot(telemetry_vault)
    conn = connect_read_only(projection)
    try:
        metadata = dict(conn.execute('SELECT key,value FROM meta'))
    finally:
        conn.close()
    valid, invalid = validate_cached_vectors(cases, vectors, dimension=int(metadata['dim'])) \
        if query_embed is None else ({}, [])
    original_setting = _settings.get
    api = _gateway()
    phases = {key: [] for key in ('open', 'compatibility', 'extension', 'search', 'close')}
    durations, embedding_durations, end_to_end_durations = [], [], []
    failures, round_reports = [], []
    embedding_failures = []
    stop = threading.Event()
    load_scans = [0]
    load_errors = []

    def load():
        try:
            db = connect_read_only(projection)
            try:
                while not stop.is_set():
                    db.execute('SELECT SUM(length(body)) FROM fts_docs').fetchone()
                    load_scans[0] += 1
            finally:
                db.close()
        except Exception as exc:
            load_errors.append(type(exc).__name__)

    thread = threading.Thread(target=load, daemon=True) if concurrent_load else None
    if thread:
        thread.start()
    try:
        with ExitStack() as stack:
            stack.enter_context(patch.dict(os.environ, {'KB_USAGE_DISABLE': '1'}))
            stack.enter_context(patch.dict(os.environ, {
                'KENNISBANK_VAULT': str(telemetry_vault)}))
            stack.enter_context(patch('_usage.log_exposures', return_value=None))
            stack.enter_context(patch('_usage.log_projection_metric', return_value=None))
            stack.enter_context(patch('_settings.get', side_effect=lambda key, default=None:
                True if key == 'experience_explicit_recall' else original_setting(key, default)))
            stack.enter_context(patch.object(xp, 'connect', side_effect=connect_read_only))
            for round_number in range(repeat):
                round_times = []
                for case in cases:
                    key = case['id']
                    started_end_to_end = time.perf_counter()
                    if query_embed is not None:
                        started_embedding = time.perf_counter()
                        try:
                            vector = query_embed(case['query'])
                            if vector is None or len(vector) != int(metadata['dim']):
                                raise ValueError('missing or incompatible query embedding')
                        except Exception as exc:
                            reason = 'query_embedding:' + type(exc).__name__
                            embedding_failures.append({'id': key, 'reason': reason})
                            failures.append({'id': key, 'reason': reason})
                            embedding_durations.append(
                                (time.perf_counter() - started_embedding) * 1000)
                            continue
                        embedding_durations.append(
                            (time.perf_counter() - started_embedding) * 1000)
                    elif key not in valid:
                        failures.append({'id': key, 'reason': 'invalid_cached_vector'})
                        continue
                    else:
                        vector = valid[key]
                    # Standalone component timings do not substitute for gateway timing.
                    times = [time.perf_counter()]
                    db = connect_read_only(projection)
                    times.append(time.perf_counter())
                    try:
                        xp.vector_projection_compatible(db, embed_id=metadata['embed_id'], query_dim=len(vector))
                        times.append(time.perf_counter())
                        xp.enable_recall_vectors(db)
                        times.append(time.perf_counter())
                        xp.experience_hits(db, query_text=case['query'], query_vector=vector, k=3)
                        times.append(time.perf_counter())
                    finally:
                        db.close()
                    times.append(time.perf_counter())
                    for i, name in enumerate(phases):
                        phases[name].append((times[i + 1] - times[i]) * 1000)
                    started = time.perf_counter()
                    request = {'mode': 'explicit', 'prompt': case['query'], 'embed_id': metadata['embed_id']}
                    try:
                        result = (gateway_run(request, isolated) if gateway_run else
                                  api.run(request, vault=Path(isolated), embed_fn=lambda _: vector))
                        if result.get('status') not in {'ok', 'no_hit'}:
                            failures.append({'id': key, 'reason': 'status:' + str(result.get('status'))})
                    except Exception as exc:
                        failures.append({'id': key, 'reason': type(exc).__name__})
                    elapsed = (time.perf_counter() - started) * 1000
                    durations.append(elapsed)
                    end_to_end_durations.append(
                        (time.perf_counter() - started_end_to_end) * 1000)
                    round_times.append(elapsed)
                round_reports.append(summarize(round_times))
    finally:
        stop.set()
        if thread:
            thread.join(timeout=5)
    telemetry_after = telemetry_snapshot(telemetry_vault)
    result = {'gateway': {'attempted': len(cases) * repeat, 'failed': len(failures),
                        'failures': failures, **summarize(durations)},
            'phases': {name: summarize(values) for name, values in phases.items()},
            'rounds': round_reports, 'cached_vector_failures': invalid,
            'load': {'enabled': concurrent_load, 'kind': 'read_only_fts_scan_thread',
                     'scans': load_scans[0], 'errors': load_errors},
            'integrity': {'projection_sha256': before,
                          'projection_changed': digest(projection) != before,
                          'telemetry_changed': telemetry_after != telemetry_before,
                          'telemetry_files_before': telemetry_before,
                          'telemetry_files_after': telemetry_after,
                          'telemetry_strategy': 'snapshot usage database and SQLite sidecars; both logging entrypoints disabled'}}
    if query_embed is not None:
        result['embedding'] = {'attempted': len(cases) * repeat,
                               'failed': len(embedding_failures),
                               'failures': embedding_failures,
                               **summarize(embedding_durations)}
        result['end_to_end'] = summarize(end_to_end_durations)
    return result


def write_result(output, result):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    (output / 'profile.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', required=True, type=Path)
    parser.add_argument('--cases', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--repeat', type=int, default=3)
    parser.add_argument('--concurrent-load', action='store_true')
    parser.add_argument('--actual-embedding', action='store_true',
                        help='measure local query embedding plus gateway end-to-end')
    args = parser.parse_args()
    vault = Path(os.environ['KENNISBANK_VAULT']).resolve()
    private = vault / '06-claude' / 'evaluations'
    if any(not p.resolve().is_relative_to(private) for p in
           (args.run_dir, args.cases, args.output_dir)) or args.output_dir.resolve() == private:
        parser.error('all inputs and output must be inside the active vault evaluation directory')
    if args.output_dir.exists():
        parser.error('output already exists')
    cases = [json.loads(line) for line in args.cases.read_text(encoding='utf-8').splitlines() if line.strip()]
    vectors = {} if args.actual_embedding else json.loads(
        (args.run_dir / 'private-results.json').read_text(encoding='utf-8'))['query_vectors']
    isolated = args.run_dir / 'isolated-vault'
    query_embed = None
    if args.actual_embedding:
        import _embeddings
        provider, _, endpoint, _ = _embeddings._resolve()
        if provider != 'ollama' or not _embeddings.is_local_endpoint(endpoint):
            parser.error('actual embedding profiling requires local Ollama')
        embedding_vault = os.environ['KENNISBANK_VAULT']
        def query_embed(query):
            # profile() temporarily points KENNISBANK_VAULT at the isolated
            # telemetry root. Preserve the active embed config/model while
            # making the actual HTTP request, otherwise OLLAMA_EMBED_MODEL or
            # a missing isolated config can select a different dimension.
            with patch.dict(os.environ, {'KENNISBANK_VAULT': embedding_vault}):
                return _embeddings.embed_query(query, timeout=60)
    result = profile(isolated / '.claude/kb-experience-index.db', isolated,
                     cases, vectors, repeat=args.repeat, concurrent_load=args.concurrent_load,
                     query_embed=query_embed)
    result['harness_sha256'] = digest(__file__)
    result['cases_sha256'] = digest(args.cases)
    write_result(args.output_dir, result)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
