"""Command-line interface for user-supplied circuit certificates."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

from . import CertificateError, __version__, certify


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'Duplicate JSON key: {key}')
        result[key] = value
    return result


def nonfinite(value):
    raise ValueError(f'Non-finite JSON value: {value}')


def interval(item):
    return str(item['value'])+' (exact)' if item['exact'] else f"[{item['lower_bound']}, {item['upper_bound']}] (bounded)"


def main(argv=None):
    parser = argparse.ArgumentParser(description='Certify phase T-counts for fixed pure-cubic targets.')
    parser.add_argument('input', type=Path, help='JSON circuit, cubic terms, CCZ atoms, or phase terms')
    parser.add_argument('--output', type=Path, help='write a JSON certificate, including the verified phase witness')
    parser.add_argument('--json', action='store_true', help='print the complete certificate as JSON')
    parser.add_argument('--require-exact', action='store_true', help='exit 1 when phase bounds do not meet')
    parser.add_argument('--force', action='store_true', help='allow replacing an existing output file')
    parser.add_argument('--max-qubits', type=int, default=512, help='resource guard (default: 512)')
    parser.add_argument('--version', action='version', version=__version__)
    args = parser.parse_args(argv)
    try:
        raw = args.input.read_bytes()
        data = json.loads(raw, object_pairs_hook=unique_object, parse_constant=nonfinite)
        result = certify(data, max_qubits=args.max_qubits)
        folder = Path(__file__).parent
        result['provenance'] = {
            'input_file_sha256': hashlib.sha256(raw).hexdigest(),
            'tool_version': __version__,
            'tool_source_sha256': {name: hashlib.sha256((folder/name).read_bytes()).hexdigest()
                                   for name in ('__init__.py', '__main__.py', 'core.py')},
            'created_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        }
        rendered = json.dumps(result, indent=2, sort_keys=True)+'\n'
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open('w' if args.force else 'x', encoding='utf-8') as stream:
                stream.write(rendered)
        if args.json:
            print(rendered, end='')
        else:
            print(f"Phase T-count: {interval(result['phase_count'])}")
            print(f"CCZ count:     {interval(result['ccz_count'])}")
            print(f"Active dimension: {result['target']['active_dimension']}")
            print(f"Verified phase witness: {len(result['phase_count']['witness'])} terms")
            if result['status'] == 'bounded':
                print('The phase bounds do not meet; optimality is not certified.')
            print('Scope: fixed pure-cubic phase target, up to free Clifford corrections.')
        return 1 if args.require_exact and result['status'] != 'exact' else 0
    except (CertificateError, ValueError, OSError) as exc:
        error = {'schema_version': 1, 'status': getattr(exc, 'status', 'invalid'),
                 'error': {'code': getattr(exc, 'code', 'input_or_output_error'), 'message': str(exc)}}
        if args.json:
            print(json.dumps(error, indent=2, sort_keys=True))
        else:
            print(f"{error['status'].upper()}: {exc}", file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
