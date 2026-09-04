#!/usr/bin/env python3
"""Cross-check the custom API against the pinned benchmark inputs and verifier."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import platform
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'benchmarks'))

import numpy as np
from ccz_certify import certify
import verify_polytof as legacy
from reproduce import collect_inputs, ensure_upstream


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('polytof', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    manifest = legacy.load_manifest(ROOT/'benchmarks/polytof_manifest.json')
    if legacy.git_head(args.polytof) != manifest['sources']['polytof']['commit']:
        parser.error('The checkout must be at the pinned Polytof commit.')
    args.polytof = args.polytof.resolve()
    ensure_upstream(args.polytof, manifest, fetch=False)
    inputs = collect_inputs(args.polytof, manifest)
    source_files = ('ccz_certify/core.py', 'benchmarks/verify_polytof.py',
                    'benchmarks/polytof_manifest.json', 'scripts/check_custom_benchmarks.py')
    sources = {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in source_files}
    results = []
    started = time.monotonic()
    for entry in manifest['benchmarks']:
        tid = entry['tensor_id']
        n, triples = legacy.read_sparse_tensor(args.polytof/'data/tensors'/f'{tid}.npy')
        m, cp_file = legacy.released_length(args.polytof/'data/paper/cpd/topp', tid)
        q, phase_file = legacy.released_length(args.polytof/'data/paper/waring', tid)
        cp, phase = legacy.load_witnesses(cp_path=cp_file, waring_path=phase_file, n=n, m=m, q=q)
        transform = legacy.load_basis_transform(args.polytof/'data/paper/transform'/f'{tid}.npy', n)
        cp = legacy.pull_back_vectors(cp, transform)
        phase = legacy.pull_back_vectors(phase, transform)
        atoms = [[np.flatnonzero(cp[3*j+k]).tolist() for k in range(3)] for j in range(m)]
        data = {'schema_version': 1, 'n_qubits': n, 'ccz_atoms': atoms,
                'phase_witness': [np.flatnonzero(row).tolist() for row in phase]}
        result = certify(data)
        assert result['target']['active_dimension'] == entry['d'], tid
        assert result['phase_count']['lower_bound'] == 2*entry['d']+1, tid
        assert result['phase_count']['upper_bound'] <= q, tid
        if entry['class'] != 'U':
            assert result['phase_count']['exact'], tid
        witness = result['phase_count']['witness']
        matrix = np.zeros((len(witness), n), dtype=np.uint8)
        for j, row in enumerate(witness):
            matrix[j, row] = 1
        legacy.verify_waring_signature(matrix, n, set(triples), Path(f'custom-output-{tid}'))
        results.append({'tensor_id': tid, 'name': entry['name'], 'n': n,
                        'active_dimension': entry['d'], 'released_q': q,
                        'phase_lower': result['phase_count']['lower_bound'],
                        'phase_upper': result['phase_count']['upper_bound'],
                        'phase_exact': result['phase_count']['exact'],
                        'legacy_full_signature_check': True})
        print(f"{tid}: d={entry['d']}; phase [{results[-1]['phase_lower']}, {results[-1]['phase_upper']}]", flush=True)
    assert collect_inputs(args.polytof, manifest) == inputs, 'Upstream inputs changed during the check'
    assert sources == {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in source_files}
    report = {'schema_version': 1, 'kind': 'custom_api_crosscheck', 'status': 'passed',
              'completed_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
              'duration_seconds': round(time.monotonic()-started, 3),
              'polytof_commit': legacy.git_head(args.polytof),
              'source_sha256': sources, 'upstream_inputs': inputs,
              'environment': {'python': platform.python_version(), 'numpy': np.__version__},
              'targets_checked': len(results), 'exact_phase_counts': sum(r['phase_exact'] for r in results),
              'rows': results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write('\n')
    print(f"PASS: {len(results)} custom API certificates cross-checked with the original verifier.")


if __name__ == '__main__':
    main()
