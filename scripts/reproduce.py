#!/usr/bin/env python3
"""Generate or check portable, content-addressed benchmark run records."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import platform
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
SOURCE_FILES = [
    'requirements.txt', 'scripts/reproduce.py',
    'benchmarks/verify_polytof.py', 'benchmarks/test_verify_polytof.py',
    'benchmarks/polytof_manifest.json', 'benchmarks/benchmark_tables.tex',
]


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def git(path, *args):
    return subprocess.check_output(['git', '-C', str(path), *args], text=True, stderr=subprocess.PIPE).strip()


def source_snapshot():
    hashes = {name: sha256(ROOT / name) for name in SOURCE_FILES}
    try:
        commit = git(ROOT, 'rev-parse', 'HEAD')
        clean = not git(ROOT, 'status', '--porcelain', '--untracked-files=no', '--', *SOURCE_FILES)
    except subprocess.CalledProcessError:
        commit, clean = None, None
    return {'git_commit': commit, 'tracked_source_clean': clean, 'sha256': hashes}


def ensure_upstream(path, manifest, fetch):
    expected = manifest['sources']['polytof']
    if not path.exists():
        if not fetch:
            raise ValueError('The supplied Polytof checkout does not exist.')
        path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(['git', 'clone', '--quiet', expected['url'], str(path)], check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        subprocess.run(['git', '-C', str(path), 'checkout', '--quiet', '--detach', expected['commit']],
                       check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if git(path, 'rev-parse', 'HEAD') != expected['commit']:
        raise ValueError('Polytof HEAD differs from the pinned commit; use a clean checkout of the recorded revision.')
    if git(path, 'status', '--porcelain', '--untracked-files=no'):
        raise ValueError('Polytof has tracked modifications; use a clean checkout.')


def collect_inputs(path, manifest):
    commit = manifest['sources']['polytof']['commit']
    entries = git(path, 'ls-tree', '-r', commit, '--', 'data/tensors', 'data/paper')
    blobs = {}
    for entry in entries.splitlines():
        header, name = entry.split('\t', 1)
        blobs[name] = header.split()[2]
    records = []
    for row in manifest['benchmarks']:
        tid = row['tensor_id']
        names = {
            'tensor': f'data/tensors/{tid}.npy',
            'transform': f'data/paper/transform/{tid}.npy',
        }
        for role, folder in [('ccz_witness', 'cpd/topp'), ('phase_witness', 'waring')]:
            matches = sorted((path / 'data/paper' / folder).glob(f'{tid}-*.npy'))
            if len(matches) != 1:
                raise ValueError(f'{tid}: expected one {role} file, found {len(matches)}')
            names[role] = matches[0].relative_to(path).as_posix()
        for role, name in names.items():
            data = (path / name).read_bytes()
            blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
            if blobs.get(name) != blob:
                raise ValueError(f'{name}: bytes differ from the pinned Git object')
            records.append({'tensor_id': tid, 'role': role, 'path': name, 'bytes': len(data),
                            'sha256': hashlib.sha256(data).hexdigest(), 'git_blob': blob})
    return {'repository': manifest['sources']['polytof']['url'], 'commit': commit,
            'files': sorted(records, key=lambda item: (item['tensor_id'], item['role']))}


def csv_text(report):
    buffer = io.StringIO(newline='')
    fields = ['suite', 'tensor_id', 'name', 'n', 'nnz', 'm', 'd', 'lower_bound',
              'released_q', 'literature_q', 'best_reported_q', 'class', 'q_certified',
              'cp_signature_ok', 'waring_signature_ok']
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator='\n')
    writer.writeheader()
    for row in report['rows']:
        values = {key: row[key] for key in fields if key in row}
        values.update(released_q=row['q'], literature_q=row.get('latest_q', ''),
                      best_reported_q=min(row['q'], row.get('latest_q', row['q'])))
        writer.writerow(values)
    return buffer.getvalue()


def summary_text(report, metadata):
    rows = report['rows']
    exact = sum(row['q_certified'] for row in rows)
    exact_ccz = sum(row['class'] in ('C0', 'C1') for row in rows)
    lines = [
        '# Recorded benchmark verification', '',
        f"Completed: {metadata['completed_at']} (UTC). Status: **PASS**.", '',
        f'All {len(rows)} released witnesses passed the full-signature checks.',
        f'**{exact} exact phase counts; {len(rows)-exact} not certified by these bounds.**',
        f'The displayed CCZ count is also certified on {exact_ccz} targets.', '',
        '| Suite | Total | Exact phase counts | C0 | C1 | L | U |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: |',
    ]
    for suite, counts in sorted(report['summaries'].items()):
        lines.append(f"| {suite} | {counts['total']} | {counts['q_certified']} | {counts['C0']} | {counts['C1']} | {counts['L']} | {counts['U']} |")
    lines.extend([
        '', 'Both subprocesses exited successfully: the four regression tests and the complete benchmark verifier.',
        f'Each of the {4*len(rows)} consumed upstream files matched the pinned Git blob before verification and was unchanged afterward.',
        'The source-file hashes were also unchanged during the run.', '',
        'The CSV separates released phase-witness lengths from the two literature-only upper bounds. Those external witnesses were not checked.',
        'Exactness refers to the fixed pure-cubic phase targets and the model stated in the accompanying paper.', '',
        f"Source Git commit: `{metadata['source']['git_commit'] or 'uncommitted source; use the recorded file hashes'}`.",
        f"Polytof commit: `{report['polytof_commit']}`.", '',
    ])
    return '\n'.join(lines)


def checksums(output):
    files = sorted(p for p in output.iterdir() if p.is_file() and p.name != 'SHA256SUMS')
    (output / 'SHA256SUMS').write_text(''.join(f'{sha256(p)}  {p.name}\n' for p in files), encoding='utf-8')


def validate_report(report, manifest):
    if not report.get('ok') or report.get('errors'):
        raise ValueError('The benchmark verifier did not pass.')
    commit = manifest['sources']['polytof']['commit']
    if report['polytof_commit'] != commit or report['pinned_commit'] != commit:
        raise ValueError('Reported upstream commit does not match the manifest.')
    expected = {(row['suite'], row['tensor_id']): row for row in manifest['benchmarks']}
    observed = {}
    for row in report['rows']:
        key = row['suite'], row['tensor_id']
        if key in observed or key not in expected:
            raise ValueError(f'Duplicate or unexpected benchmark: {key}')
        observed[key] = row
        for field in ('name', 'n', 'm', 'd', 'q', 'class'):
            if row[field] != expected[key][field]:
                raise ValueError(f'{key}: inconsistent {field}')
        if row['lower_bound'] != 2*row['d']+1 or row['q'] < row['lower_bound']:
            raise ValueError(f'{key}: inconsistent lower bound')
        if not row['cp_signature_ok'] or not row['waring_signature_ok']:
            raise ValueError(f'{key}: witness check did not pass')
        if row['q_certified'] != (row['class'] != 'U'):
            raise ValueError(f'{key}: inconsistent certification status')
    if set(observed) != set(expected):
        raise ValueError('Missing benchmarks in the record.')
    for suite, target in manifest['expected_summaries'].items():
        rows = [r for r in observed.values() if r['suite'] == suite]
        classes = Counter(row['class'] for row in rows)
        counts = {'total': len(rows), 'q_certified': sum(r['q_certified'] for r in rows),
                  **{name: classes[name] for name in ('C0', 'C1', 'L', 'U')}}
        if counts != target or report['summaries'][suite] != counts:
            raise ValueError(f'{suite}: inconsistent summary')


def check_record(output):
    listed = set()
    for line in (output / 'SHA256SUMS').read_text().splitlines():
        digest, name = line.split('  ', 1)
        if not re.fullmatch(r'[0-9a-f]{64}', digest) or Path(name).name != name or name in listed:
            raise ValueError('Invalid checksum entry.')
        listed.add(name)
        if sha256(output / name) != digest:
            raise ValueError(f'Record checksum mismatch: {name}')
    present = {p.name for p in output.iterdir() if p.is_file() and p.name != 'SHA256SUMS'}
    if present != listed:
        raise ValueError('Record contains unhashed or missing files.')
    required = {'run.json', 'manifest.json', 'inputs.json', 'verification.json',
                'results.csv', 'tests.log', 'verification.log', 'summary.md'}
    if not required <= listed:
        raise ValueError('Incomplete record.')
    metadata = json.loads((output / 'run.json').read_text())
    if metadata['status'] != 'passed' or len(metadata['commands']) != 2:
        raise ValueError('Record is not a completed successful run.')
    if any(cmd['exit_code'] != 0 for cmd in metadata['commands']):
        raise ValueError('A recorded subprocess failed.')
    manifest = json.loads((output / 'manifest.json').read_text())
    if sha256(output / 'manifest.json') != metadata['source']['sha256']['benchmarks/polytof_manifest.json']:
        raise ValueError('Manifest snapshot differs from the executed source snapshot.')
    report = json.loads((output / 'verification.json').read_text())
    validate_report(report, manifest)
    if (output / 'results.csv').read_text() != csv_text(report):
        raise ValueError('CSV differs from JSON results.')
    inputs = json.loads((output / 'inputs.json').read_text())
    if inputs['commit'] != report['polytof_commit'] or len(inputs['files']) != 4*len(report['rows']):
        raise ValueError('Incomplete input provenance.')
    return report, inputs


def reproduce(args):
    import numpy as np
    started = time.monotonic()
    manifest_path = ROOT / 'benchmarks/polytof_manifest.json'
    manifest = json.loads(manifest_path.read_text())
    upstream = (args.polytof or ROOT / '.cache/polytof').resolve()
    output = (args.output or ROOT / 'runs' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')).resolve()
    output.mkdir(parents=True, exist_ok=False)

    def portable(text):
        for path, label in [(str(ROOT), '<repository>'), (str(upstream), '<polytof>'),
                            (sys.executable, '<python>'), (str(Path.home()), '<home>')]:
            text = text.replace(path, label)
        return text

    metadata = {'schema_version': 1, 'status': 'running', 'started_at': now(),
                'source': source_snapshot(), 'commands': [],
                'environment': {'python': platform.python_version(), 'numpy': np.__version__,
                                'os': platform.system(), 'architecture': platform.machine(),
                                'git': subprocess.check_output(['git', '--version'], text=True).strip()}}
    write_json(output / 'run.json', metadata)
    try:
        ensure_upstream(upstream, manifest, fetch=args.polytof is None)
        inputs = collect_inputs(upstream, manifest)
        (output / 'manifest.json').write_bytes(manifest_path.read_bytes())
        write_json(output / 'inputs.json', inputs)
        commands = [
            ('regression_tests', ['-m', 'unittest', 'discover', '-s', 'benchmarks', '-p', 'test_verify_polytof.py', '-v']),
            ('benchmark_verifier', ['benchmarks/verify_polytof.py', str(upstream), '--format', 'json']),
        ]
        for label, command in commands:
            command_start = time.monotonic()
            result = subprocess.run([sys.executable, *command], cwd=ROOT, text=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            metadata['commands'].append({'name': label,
                'argv': ['python', *[portable(arg) for arg in command]],
                'exit_code': result.returncode, 'duration_seconds': round(time.monotonic()-command_start, 3)})
            if label == 'regression_tests':
                (output / 'tests.log').write_text(portable(result.stdout + result.stderr), encoding='utf-8')
            else:
                (output / 'verification.json').write_text(portable(result.stdout), encoding='utf-8')
                (output / 'verification.log').write_text(portable(result.stderr), encoding='utf-8')
            write_json(output / 'run.json', metadata)
            if result.returncode:
                raise ValueError(f'{label} failed; see its recorded log.')
        report = json.loads((output / 'verification.json').read_text())
        validate_report(report, manifest)
        if collect_inputs(upstream, manifest) != inputs:
            raise ValueError('Upstream input bytes changed during verification.')
        if source_snapshot()['sha256'] != metadata['source']['sha256']:
            raise ValueError('Verifier source bytes changed during verification.')
        if args.compare:
            baseline, baseline_inputs = check_record(args.compare.resolve())
            if report != baseline or inputs != baseline_inputs:
                raise ValueError('Results or consumed inputs differ from the reference record.')
            metadata['reference_comparison'] = 'identical results and input provenance'
        (output / 'results.csv').write_text(csv_text(report), encoding='utf-8')
        metadata.update(status='passed', completed_at=now(), duration_seconds=round(time.monotonic()-started, 3))
        write_json(output / 'run.json', metadata)
        (output / 'summary.md').write_text(summary_text(report, metadata), encoding='utf-8')
        checksums(output)
        check_record(output)
    except Exception as exc:
        detail = exc.stderr if isinstance(exc, subprocess.CalledProcessError) and exc.stderr else str(exc)
        metadata.update(status='failed', completed_at=now(), error=portable(detail),
                        duration_seconds=round(time.monotonic()-started, 3))
        write_json(output / 'run.json', metadata)
        checksums(output)
        print(f'FAIL: {portable(str(output))}: {portable(detail)}', file=sys.stderr)
        return 1
    total = len(report['rows'])
    exact = sum(row['q_certified'] for row in report['rows'])
    print(f'PASS: {total} targets; {exact} exact phase counts; {total-exact} uncertified. Record: {portable(str(output))}')
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--polytof', type=Path, help='existing clean checkout at the pinned commit')
    parser.add_argument('--output', type=Path, help='new record directory (default: runs/<UTC timestamp>)')
    parser.add_argument('--compare', type=Path, help='reference record whose results and input hashes must match')
    parser.add_argument('--check-records', type=Path, help='check an existing record without NumPy or upstream data')
    args = parser.parse_args()
    try:
        if args.check_records:
            if args.polytof or args.output or args.compare:
                parser.error('--check-records cannot be combined with run options')
            check_record(args.check_records.resolve())
            print('PASS: record hashes, exit statuses, per-target results, CSV, and summaries agree.')
            return 0
        return reproduce(args)
    except Exception as exc:
        # No record is overwritten when output-directory creation fails.
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
