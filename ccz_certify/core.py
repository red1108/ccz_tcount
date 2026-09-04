"""Exact GF(2) certificates, using packed contraction rows and parity labels.

This module has no third-party dependencies. It constructs and verifies phase
witnesses; it does not assume that a displayed CCZ decomposition is minimal.
"""
from __future__ import annotations

from collections import Counter
import hashlib
from itertools import combinations
import json

SCOPE = ('Exact parity-phase synthesis of a fixed pure-cubic target; Clifford '
         'corrections and the final affine wire map are free. No claim is made '
         'about optimization using intermediate Hadamards or measurements.')


class CertificateError(ValueError):
    def __init__(self, message, status='invalid', code='invalid_input'):
        super().__init__(message)
        self.status, self.code = status, code


def fail(message, *, status='invalid', code='invalid_input'):
    raise CertificateError(message, status, code)


def indices(value, n, where, *, size=None, nonempty=False):
    if not isinstance(value, list) or any(type(i) is not int for i in value):
        fail(f'{where}: expected a list of integer, zero-based qubit indices.')
    if any(i < 0 or i >= n for i in value) or len(set(value)) != len(value):
        fail(f'{where}: indices must be distinct and in [0, {n-1}].')
    if size is not None and len(value) != size:
        fail(f'{where}: expected exactly {size} indices.')
    if nonempty and not value:
        fail(f'{where}: omit zero parity labels rather than listing an empty label.')
    return value


def mask(support):
    return sum(1 << i for i in support)


def support(vector):
    result = []
    while vector:
        bit = vector & -vector
        result.append(bit.bit_length()-1)
        vector ^= bit
    return result


def rank(vectors):
    pivots = {}
    for vector in vectors:
        while vector:
            bit = vector.bit_length()-1
            if bit in pivots:
                vector ^= pivots[bit]
            else:
                pivots[bit] = vector
                break
    return len(pivots)


def pair_index(i, j, n):
    return i*(2*n-i-1)//2+j-i-1


def wedge_pair(a, b, n):
    result = 0
    for i in support(a):
        for j in support(b):
            if i != j:
                lo, hi = sorted((i, j))
                result ^= 1 << pair_index(lo, hi, n)
    return result


def atom_rows(atom, n):
    a, b, c = atom
    bc, ac, ab = wedge_pair(b, c, n), wedge_pair(a, c, n), wedge_pair(a, b, n)
    return [((bc if a >> i & 1 else 0) ^ (ac if b >> i & 1 else 0)
             ^ (ab if c >> i & 1 else 0)) for i in range(n)]


def add_rows(left, right):
    return [a ^ b for a, b in zip(left, right)]


def atoms_rows(atoms, n):
    result = [0]*n
    for atom in atoms:
        result = add_rows(result, atom_rows(atom, n))
    return result


def coordinate_terms(rows, n):
    for i in range(n-2):
        for j in range(i+1, n-1):
            for k in range(j+1, n):
                if rows[i] >> pair_index(j, k, n) & 1:
                    yield (i, j, k)


def cubic_count(rows, n):
    return sum((rows[i] >> pair_index(i+1, i+2, n)).bit_count() for i in range(n-2))


def parse_parities(value, n, where):
    if not isinstance(value, list):
        fail(f'{where}: expected a list of parity supports.')
    return [mask(indices(v, n, f'{where}[{i}]', nonempty=True)) for i, v in enumerate(value)]


def parse_atoms(value, n, where):
    if not isinstance(value, list):
        fail(f'{where}: expected a list of triples of parity supports.')
    atoms = []
    for i, triple in enumerate(value):
        if not isinstance(triple, list) or len(triple) != 3:
            fail(f'{where}[{i}]: expected three parity supports.')
        atom = tuple(parse_parities(triple, n, f'{where}[{i}]'))
        if rank(atom) != 3:
            fail(f'{where}[{i}]: the three CCZ directions must be independent.')
        atoms.append(atom)
    return atoms


def phase_rows(labels, n, *, input_target=False):
    """Check repeated indices, then form the alternating contraction matrix."""
    if not labels:
        return [0]*n
    masks = [0]*n
    for term, vector in enumerate(labels):
        for i in support(vector):
            masks[i] |= 1 << term
    bad_status = 'unsupported' if input_target else 'invalid'
    bad_code = 'non_alternating_target' if input_target else 'invalid_phase_witness'
    for i in range(n):
        if masks[i].bit_count() & 1:
            fail(f'Nonzero repeated-index signature entry ({i},{i},{i}); '
                 'this is not a pure-cubic phase presentation.', status=bad_status, code=bad_code)
        for j in range(i+1, n):
            if (masks[i] & masks[j]).bit_count() & 1:
                fail(f'Nonzero repeated-index signature entry ({i},{i},{j}); '
                     'linear/quadratic non-Clifford data cannot be discarded.',
                     status=bad_status, code=bad_code)
    rows = [0]*n
    for i in range(n-2):
        for j in range(i+1, n-1):
            intersection = masks[i] & masks[j]
            for k in range(j+1, n):
                if (intersection & masks[k]).bit_count() & 1:
                    rows[i] ^= 1 << pair_index(j, k, n)
                    rows[j] ^= 1 << pair_index(i, k, n)
                    rows[k] ^= 1 << pair_index(i, j, n)
    return rows


def seven(atom):
    a, b, c = atom
    return [a, b, c, a ^ b, a ^ c, b ^ c, a ^ b ^ c]


def normalize_phases(labels, target):
    if not any(target):
        return []
    reduced = set()
    for label in labels:
        if label:
            reduced.symmetric_difference_update([label])
    if not reduced:
        raise RuntimeError('A nonzero target lost all phase labels.')
    if len(reduced) % 2 == 0:
        pivot = min(reduced)
        reduced = {label ^ pivot for label in reduced} - {0}
    return sorted(reduced)


def find_relation(atoms):
    """One kernel vector of the factor matrix, grouped by CCZ interaction."""
    basis = {}
    for j, atom in enumerate(atoms):
        for k, original in enumerate(atom):
            value, combination = original, 1 << (3*j+k)
            while value:
                bit = value.bit_length()-1
                if bit not in basis:
                    basis[bit] = value, combination
                    break
                value ^= basis[bit][0]
                combination ^= basis[bit][1]
            if not value:
                grouped = []
                for aidx, factors in enumerate(atoms):
                    pivot = 0
                    for fidx, factor in enumerate(factors):
                        if combination >> (3*aidx+fidx) & 1:
                            pivot ^= factor
                    if pivot:
                        grouped.append((aidx, pivot))
                return grouped
    return []


def odd_merge(left, right, pivot):
    if not left:
        return right.copy()
    if len(left) % 2 != 1 or len(right) != 7 or pivot not in right:
        raise RuntimeError('Invalid odd-merge state.')
    omitted = right.index(pivot)
    return [v ^ pivot for v in left] + [v ^ pivot for i, v in enumerate(right) if i != omitted]


def convert_atoms(atoms, n):
    relation = find_relation(atoms)
    phase, target, used = [], [0]*n, set()
    if relation:
        for j, pivot in relation:
            phase = odd_merge(phase, seven(atoms[j]), pivot)
            target = add_rows(target, atom_rows(atoms[j], n))
            used.add(j)
        # The tracked pivot from the first interaction reaches zero.
        phase = normalize_phases(phase, target)
    for j, atom in enumerate(atoms):
        if j not in used:
            phase = odd_merge(phase, seven(atom), atom[0])
            target = add_rows(target, atom_rows(atom, n))
            phase = normalize_phases(phase, target)
    return phase, [{'interaction': j, 'parity': support(v)} for j, v in relation]


def parse_circuit(gates, n):
    if not isinstance(gates, list):
        fail('gates: expected a list of gate objects.')
    wires = [1 << i for i in range(n)]
    atoms, phases, counts = [], [], Counter()
    arity = {'cx': 2, 'ccz': 3, 'swap': 2, 'x': 1, 'z': 1, 's': 1,
             'sdg': 1, 'cz': 2, 't': 1, 'tdg': 1, 'id': 1}
    for i, item in enumerate(gates):
        if not isinstance(item, dict) or set(item) != {'gate', 'qubits'} or not isinstance(item['gate'], str):
            fail(f'gates[{i}]: expected exactly gate and qubits fields.')
        gate = item['gate'].lower()
        gate = 'cx' if gate == 'cnot' else gate
        if gate not in arity:
            fail(f'gates[{i}]: unsupported gate {gate!r}; do not remove Hadamards, '
                 'measurements, or resets to force a certificate.', status='unsupported', code='unsupported_gate')
        qs = indices(item['qubits'], n, f'gates[{i}].qubits', size=arity[gate])
        counts[gate] += 1
        if gate == 'cx':
            wires[qs[1]] ^= wires[qs[0]]
        elif gate == 'swap':
            wires[qs[0]], wires[qs[1]] = wires[qs[1]], wires[qs[0]]
        elif gate == 'ccz':
            atoms.append(tuple(wires[q] for q in qs))
        elif gate in ('t', 'tdg'):
            phases.append(wires[qs[0]])
        # X changes affine constants: this changes T signs/global phases,
        # and only Clifford lower-degree terms of CCZ. Neither changes the
        # binary signature. S/SDG/Z/CZ are also free Clifford corrections.
    target = add_rows(atoms_rows(atoms, n), phase_rows(phases, n, input_target=True))
    return target, atoms, phases, dict(sorted(counts.items()))


def certify(data, *, max_qubits=512):
    """Return deterministic bounds and a verified phase witness for a JSON-like input.

    status='exact' certifies the phase count. CCZ exactness is reported separately.
    A valid input may return status='bounded'; no general rank solver is claimed.
    """
    if not isinstance(data, dict):
        fail('Input must be a JSON object.')
    allowed = {'schema_version', 'name', 'n_qubits', 'gates', 'cubic_terms', 'ccz_atoms',
               'phase_terms', 'ccz_witness', 'phase_witness'}
    if set(data)-allowed:
        fail(f'Unknown input fields: {sorted(set(data)-allowed)}')
    if type(data.get('schema_version')) is not int or data['schema_version'] != 1:
        fail('schema_version must be 1.')
    n = data.get('n_qubits')
    if type(n) is not int or n < 1:
        fail('n_qubits must be a positive integer.')
    if type(max_qubits) is not int or max_qubits < 1:
        fail('max_qubits must be a positive integer.')
    if n > max_qubits:
        fail(f'n_qubits={n} exceeds the configured limit {max_qubits}; increase max_qubits '
             'explicitly if the available time and memory permit it.', status='unsupported', code='resource_limit')
    if 'name' in data and not isinstance(data['name'], str):
        fail('name must be a string.')
    kinds = [key for key in ('gates', 'cubic_terms', 'ccz_atoms', 'phase_terms') if key in data]
    if len(kinds) != 1:
        fail('Provide exactly one target form: gates, cubic_terms, ccz_atoms, or phase_terms.')
    kind = kinds[0]
    atom_candidates, phase_candidates, details = [], [], {'target_form': kind}
    if kind == 'gates':
        target, atoms, phases, gate_counts = parse_circuit(data[kind], n)
        details['gate_counts'] = gate_counts
        if phases:
            phase_candidates.append(('input_circuit', normalize_phases([v for a in atoms for v in seven(a)]+phases, target), []))
        else:
            atom_candidates.append(('input_circuit', atoms))
    elif kind == 'ccz_atoms':
        atoms = parse_atoms(data[kind], n, kind)
        target = atoms_rows(atoms, n)
        atom_candidates.append(('input_atoms', atoms))
    elif kind == 'phase_terms':
        phases = parse_parities(data[kind], n, kind)
        target = phase_rows(phases, n, input_target=True)
        phase_candidates.append(('input_phase_terms', normalize_phases(phases, target), []))
    else:
        if not isinstance(data[kind], list):
            fail('cubic_terms must be a list of triples.')
        terms = set()
        for i, term in enumerate(data[kind]):
            triple = tuple(sorted(indices(term, n, f'cubic_terms[{i}]', size=3)))
            terms.symmetric_difference_update([triple])
        atoms = [tuple(1 << i for i in term) for term in sorted(terms)]
        target = [0]*n
        for i, j, k in terms:
            target[i] ^= 1 << pair_index(j, k, n)
            target[j] ^= 1 << pair_index(i, k, n)
            target[k] ^= 1 << pair_index(i, j, n)
        atom_candidates.append(('coordinate_expansion', atoms))
    d, nnz = rank(target), cubic_count(target, n)
    if 'ccz_witness' in data:
        atoms = parse_atoms(data['ccz_witness'], n, 'ccz_witness')
        if atoms_rows(atoms, n) != target:
            fail('ccz_witness represents a different target.', code='invalid_ccz_witness')
        atom_candidates.append(('supplied_ccz_witness', atoms))
        details['supplied_ccz_witness'] = {'valid': True, 'terms': len(atoms)}
    if 'phase_witness' in data:
        phases = parse_parities(data['phase_witness'], n, 'phase_witness')
        if phase_rows(phases, n) != target:
            fail('phase_witness represents a different cubic target.', code='invalid_phase_witness')
        reduced = normalize_phases(phases, target)
        phase_candidates.append(('supplied_phase_witness', reduced, []))
        details['supplied_phase_witness'] = {'valid': True, 'terms': len(phases), 'reduced_terms': len(reduced)}
    # The coordinate expansion is always a CCZ upper bound. Only materialize
    # it when its phase construction could improve an existing candidate.
    best_available = min((len(v) for _, v, _ in phase_candidates), default=float('inf'))
    best_atoms = min((len(a) for _, a in atom_candidates), default=float('inf'))
    goal = 2*d+1 if d else 0
    if nnz and best_available > goal and nnz < best_atoms and 6*nnz-1 < best_available:
        atoms = [tuple(1 << i for i in term) for term in coordinate_terms(target, n)]
        atom_candidates.append(('coordinate_expansion', atoms))
    # Prefer the smallest available CCZ decomposition. An already optimal
    # supplied phase witness needs no additional synthesis work.
    smallest = min((len(a) for _, a in atom_candidates), default=0)
    for method, atoms in atom_candidates:
        if min((len(v) for _, v, _ in phase_candidates), default=float('inf')) == goal:
            break
        if len(atoms) != smallest:
            continue
        phases, relation = convert_atoms(atoms, n)
        phase_candidates.append((method+'_conversion', phases, relation))
    if not any(target):
        phase_candidates.append(('zero_target', [], []))
    if not phase_candidates:
        raise RuntimeError('No upper-bound construction was produced.')
    method, phases, relation = min(phase_candidates, key=lambda item: (len(item[1]), item[0]))
    if phase_rows(phases, n) != target:
        raise RuntimeError('Constructed phase witness failed full-signature verification.')
    lower, upper = (2*d+1 if d else 0), len(phases)
    if upper < lower:
        raise RuntimeError('Constructed witness contradicts the lower bound.')
    c_lower = (d+2)//3
    c_upper = min([nnz]+[len(atoms) for _, atoms in atom_candidates]) if d else 0
    if c_upper < c_lower:
        raise RuntimeError('CCZ witness contradicts the active-dimension bound.')
    phase_exact, c_exact = lower == upper, c_lower == c_upper
    for key, value in [('supplied_phase_witness', lower if phase_exact else None),
                       ('supplied_ccz_witness', c_lower if c_exact else None)]:
        if key in details:
            details[key]['certified_minimum_as_supplied'] = value is not None and details[key]['terms'] == value
    digest = hashlib.sha256(json.dumps({'n': n, 'contractions': [hex(row) for row in target]}, sort_keys=True).encode()).hexdigest()
    return {'schema_version': 1, 'status': 'exact' if phase_exact else 'bounded', 'name': data.get('name'),
            'n_qubits': n, 'scope': SCOPE, 'input': details,
            'target': {'active_dimension': d, 'cubic_monomials': nnz, 'signature_sha256': digest, 'zero': d == 0},
            'phase_count': {'lower_bound': lower, 'upper_bound': upper, 'exact': phase_exact,
                            'value': lower if phase_exact else None, 'witness': [support(v) for v in phases],
                            'witness_verified': True, 'method': method, 'pivot_relation': relation},
            'ccz_count': {'lower_bound': c_lower, 'upper_bound': c_upper, 'exact': c_exact,
                          'value': c_lower if c_exact else None},
            'verification': {'field': 'GF(2)', 'full_symmetric_signature': True, 'repeated_indices_zero': True}}
