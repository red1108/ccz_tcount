import contextlib
import io
from itertools import product
import json
from pathlib import Path
import random
import tempfile
import unittest

from ccz_certify import CertificateError, certify
from ccz_certify.__main__ import main

ROOT = Path(__file__).resolve().parents[1]


def gate(name, *qs):
    return {'gate': name, 'qubits': list(qs)}


def cc_phase_terms():
    return [[i for i in range(3) if mask >> i & 1] for mask in range(1, 8)]


def check_full_tensor(test, n, atoms, witness):
    """Independent dense determinant/cube check, including repeated indices."""
    for i, j, k in product(range(n), repeat=3):
        expected = 0
        for a, b, c in atoms:
            expected ^= ((i in a and j in b and k in c)
                         ^ (i in a and k in b and j in c)
                         ^ (j in a and i in b and k in c)
                         ^ (j in a and k in b and i in c)
                         ^ (k in a and i in b and j in c)
                         ^ (k in a and j in b and i in c))
        observed = sum(i in v and j in v and k in v for v in witness) % 2
        test.assertEqual(observed, expected, (i, j, k))


def simulate_phase(gates, n, x):
    bits = [(x >> i) & 1 for i in range(n)]
    phase = 0
    for operation in gates:
        name, qs = operation['gate'], operation['qubits']
        if name == 'cx':
            bits[qs[1]] ^= bits[qs[0]]
        elif name == 'swap':
            bits[qs[0]], bits[qs[1]] = bits[qs[1]], bits[qs[0]]
        elif name == 'x':
            bits[qs[0]] ^= 1
        elif name in ('t', 'tdg', 's', 'sdg', 'z'):
            phase += {'t': 1, 'tdg': -1, 's': 2, 'sdg': -2, 'z': 4}[name] * bits[qs[0]]
        elif name in ('ccz', 'cz'):
            phase += 4 * int(all(bits[q] for q in qs))
    return phase % 8


def check_clifford_residual(test, gates, n, witness):
    # Exhaustive basis simulation and an independent Mobius transform over
    # Z/8Z: the residual may only have even linear and 4-divisible quadratic
    # coefficients, plus an irrelevant global phase.
    coefficients = []
    for x in range(1 << n):
        phases = sum(sum((x >> i) & 1 for i in v) % 2 for v in witness)
        coefficients.append((simulate_phase(gates, n, x)-phases) % 8)
    for i in range(n):
        for x in range(1 << n):
            if x >> i & 1:
                coefficients[x] = (coefficients[x]-coefficients[x ^ (1 << i)]) % 8
    for monomial, coefficient in enumerate(coefficients):
        degree = monomial.bit_count()
        if degree == 1:
            test.assertEqual(coefficient % 2, 0)
        elif degree == 2:
            test.assertEqual(coefficient % 4, 0)
        elif degree >= 3:
            test.assertEqual(coefficient, 0)


class CertificateTests(unittest.TestCase):
    def test_documented_examples(self):
        expected = {'ccz': (3, 7, 7), 'ccz_with_witness': (3, 7, 7),
                    'computed_parities': (5, 11, 11), 'three_ccz_independent': (9, 19, 19),
                    'three_ccz_dependent': (8, 17, 17), 'bounded': (6, 13, 15)}
        for name, values in expected.items():
            with self.subTest(name=name):
                data = json.loads((ROOT/'examples'/f'{name}.json').read_text())
                result = certify(data)
                self.assertEqual((result['target']['active_dimension'], result['phase_count']['lower_bound'],
                                  result['phase_count']['upper_bound']), values)
                if 'gates' in data:
                    check_clifford_residual(self, data['gates'], data['n_qubits'], result['phase_count']['witness'])

    def test_full_rank_and_sharp_gap_families(self):
        for t in range(1, 7):
            data = {'schema_version': 1, 'n_qubits': 3*t,
                    'cubic_terms': [[3*j, 3*j+1, 3*j+2] for j in range(t)]}
            result = certify(data)
            self.assertEqual(result['phase_count']['value'], 6*t+1)
            self.assertEqual(result['ccz_count']['value'], t)
        for t in range(2, 7):
            terms = [[0, 1, 2], [0, 3, 4]] + [[5+3*j, 6+3*j, 7+3*j] for j in range(t-2)]
            result = certify({'schema_version': 1, 'n_qubits': 3*t-1, 'cubic_terms': terms})
            self.assertEqual(result['phase_count']['value'], 6*t-1)
            self.assertEqual(result['ccz_count']['value'], t)

    def test_random_atom_witnesses_against_full_dense_tensor(self):
        rng = random.Random(1709)
        for _ in range(24):
            n = 6
            gates, wires, atoms = [], [set([i]) for i in range(n)], []
            for _ in range(5):
                a, b = rng.sample(range(n), 2)
                gates.append(gate('cx', a, b))
                wires[b] ^= wires[a]
                qs = rng.sample(range(n), 3)
                gates.append(gate('ccz', *qs))
                atoms.append([set(wires[q]) for q in qs])
            result = certify({'schema_version': 1, 'n_qubits': n, 'gates': gates})
            check_full_tensor(self, n, atoms, result['phase_count']['witness'])
            check_clifford_residual(self, gates, n, result['phase_count']['witness'])

    def test_affine_and_clifford_gates(self):
        gates = [gate('x', 0), gate('s', 2), gate('ccz', 0, 1, 2), gate('swap', 2, 4),
                 gate('cx', 4, 1), gate('cz', 1, 2), gate('sdg', 3), gate('z', 4),
                 gate('ccz', 0, 1, 3), gate('x', 1)]
        result = certify({'schema_version': 1, 'n_qubits': 5, 'gates': gates})
        check_clifford_residual(self, gates, 5, result['phase_count']['witness'])

    def test_pure_cubic_t_circuit_and_phase_list(self):
        gates = [gate('x', 0)]
        for j, term in enumerate(cc_phase_terms()):
            gates.extend(gate('cx', control, term[0]) for control in term[1:])
            gates.append(gate('tdg' if j % 2 else 't', term[0]))
            gates.extend(gate('cx', control, term[0]) for control in reversed(term[1:]))
        result = certify({'schema_version': 1, 'n_qubits': 3, 'gates': gates})
        self.assertEqual(result['phase_count']['value'], 7)
        check_clifford_residual(self, gates, 3, result['phase_count']['witness'])
        phase_result = certify({'schema_version': 1, 'n_qubits': 3, 'phase_terms': cc_phase_terms()})
        self.assertEqual(phase_result['phase_count']['value'], 7)

    def test_zero_and_cancelled_targets(self):
        for data in [
            {'schema_version': 1, 'n_qubits': 1, 'gates': []},
            {'schema_version': 1, 'n_qubits': 1, 'phase_terms': []},
            {'schema_version': 1, 'n_qubits': 3, 'cubic_terms': [[0, 1, 2], [2, 1, 0]]},
            {'schema_version': 1, 'n_qubits': 3, 'ccz_atoms': [[[0], [1], [2]]]*2},
        ]:
            result = certify(data)
            self.assertEqual(result['phase_count']['value'], 0)
            self.assertEqual(result['ccz_count']['value'], 0)
            self.assertEqual(result['phase_count']['witness'], [])

    def test_nonminimal_supplied_witnesses(self):
        result = certify({'schema_version': 1, 'n_qubits': 3, 'cubic_terms': [[0, 1, 2]],
                          'ccz_witness': [[[0], [1], [2]]]*3,
                          'phase_witness': cc_phase_terms()+[[0], [0]]})
        self.assertEqual(result['phase_count']['value'], 7)
        self.assertEqual(result['ccz_count']['value'], 1)
        self.assertFalse(result['input']['supplied_phase_witness']['certified_minimum_as_supplied'])
        self.assertFalse(result['input']['supplied_ccz_witness']['certified_minimum_as_supplied'])

    def test_phase_exactness_is_separate_from_ccz_exactness(self):
        result = certify({'schema_version': 1, 'n_qubits': 4,
                          'ccz_atoms': [[[0], [1], [2]], [[0], [1], [3]]]})
        self.assertEqual(result['status'], 'exact')
        self.assertFalse(result['ccz_count']['exact'])

    def test_bad_phase_witnesses(self):
        for appended in [[[0]], [[0], [1], [0, 1]]]:
            with self.assertRaises(CertificateError) as caught:
                certify({'schema_version': 1, 'n_qubits': 3, 'cubic_terms': [[0, 1, 2]],
                         'phase_witness': cc_phase_terms()+appended})
            self.assertEqual(caught.exception.code, 'invalid_phase_witness')
        wrong = [[3 if i == 2 else i for i in term] for term in cc_phase_terms()]
        with self.assertRaises(CertificateError):
            certify({'schema_version': 1, 'n_qubits': 4, 'cubic_terms': [[0, 1, 2]], 'phase_witness': wrong})
        with self.assertRaises(CertificateError):
            certify({'schema_version': 1, 'n_qubits': 4, 'cubic_terms': [[0, 1, 2]],
                     'ccz_witness': [[[0], [1], [3]]]})

    def test_unsupported_model_is_rejected(self):
        for name in ('h', 'measure', 'reset', 'ccx'):
            with self.assertRaises(CertificateError) as caught:
                certify({'schema_version': 1, 'n_qubits': 3, 'gates': [gate(name, 0)]})
            self.assertEqual(caught.exception.status, 'unsupported')
        for terms in [[[0]], [[0], [1], [0, 1]]]:
            with self.assertRaises(CertificateError) as caught:
                certify({'schema_version': 1, 'n_qubits': 2, 'phase_terms': terms})
            self.assertEqual(caught.exception.code, 'non_alternating_target')

    def test_malformed_inputs_are_rejected(self):
        malformed = [
            {'schema_version': 1, 'n_qubits': True, 'gates': []},
            {'schema_version': 1, 'n_qubits': 3, 'gates': [gate('ccz', 0, 1, 1)]},
            {'schema_version': 1, 'n_qubits': 3, 'gates': [gate('cx', 0, 3)]},
            {'schema_version': 1, 'n_qubits': 3, 'gates': [gate('cx', False, 1)]},
            {'schema_version': 1, 'n_qubits': 3, 'gates': [], 'ignored': True},
            {'schema_version': 1, 'n_qubits': 3, 'gates': [], 'phase_terms': []},
            {'schema_version': 1, 'n_qubits': 3, 'ccz_atoms': [[[0], [0], [1]]]},
        ]
        for data in malformed:
            with self.subTest(data=data), self.assertRaises(CertificateError):
                certify(data)

    def test_resource_guard_is_explicit_and_configurable(self):
        data = {'schema_version': 1, 'n_qubits': 513, 'gates': []}
        with self.assertRaises(CertificateError) as caught:
            certify(data)
        self.assertEqual(caught.exception.code, 'resource_limit')
        self.assertEqual(certify(data, max_qubits=513)['phase_count']['value'], 0)


class CliTests(unittest.TestCase):
    def test_exact_bounded_and_require_exact(self):
        for name, flag, expected in [('ccz', [], 0), ('bounded', [], 0), ('bounded', ['--require-exact'], 1)]:
            with self.subTest(name=name, flag=flag), contextlib.redirect_stdout(io.StringIO()) as output:
                code = main([str(ROOT/'examples'/f'{name}.json'), '--json', *flag])
                self.assertEqual(code, expected)
                self.assertIn(json.loads(output.getvalue())['status'], ('exact', 'bounded'))

    def test_output_roundtrip_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'certificate.json'
            arguments = [str(ROOT/'examples/ccz.json'), '--output', str(path)]
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(arguments), 0)
                before = path.read_bytes()
                self.assertEqual(main(arguments), 2)
                self.assertEqual(path.read_bytes(), before)
                self.assertEqual(main([*arguments, '--force']), 0)
            data = json.loads((ROOT/'examples/ccz.json').read_text())
            data['phase_witness'] = json.loads(path.read_text())['phase_count']['witness']
            self.assertTrue(certify(data)['input']['supplied_phase_witness']['valid'])

    def test_duplicate_json_and_unsupported_errors(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'input.json'
            for content, status in [
                ('{"schema_version":1,"n_qubits":3,"gates":[],"gates":[]}', 'invalid'),
                (json.dumps({'schema_version': 1, 'n_qubits': 1, 'gates': [gate('h', 0)]}), 'unsupported'),
            ]:
                path.write_text(content)
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    self.assertEqual(main([str(path), '--json']), 2)
                    self.assertEqual(json.loads(output.getvalue())['status'], status)


if __name__ == '__main__':
    unittest.main()
