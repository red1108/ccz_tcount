"""Regression checks for the signature conditions used by the paper."""

import unittest
from pathlib import Path

import numpy as np

from verify_polytof import binary_values, verify_waring_signature


class WaringSignatureTests(unittest.TestCase):
    def setUp(self):
        self.ccz = np.array([
            [mask & 1, (mask >> 1) & 1, (mask >> 2) & 1]
            for mask in range(1, 8)
        ], dtype=np.uint8)
        self.target = {(0, 1, 2)}

    def check_witness(self, vectors):
        verify_waring_signature(vectors, 3, self.target, Path('test-witness'))

    def test_seven_term_ccz(self):
        self.check_witness(self.ccz)

    def test_extra_linear_phase_is_not_a_clifford_correction(self):
        # Adding T(x1) leaves every distinct-index cubic entry unchanged.
        corrupted = np.vstack([self.ccz, [1, 0, 0]])
        with self.assertRaisesRegex(ValueError, r'\(0, 0, 0\)'):
            self.check_witness(corrupted)

    def test_extra_quadratic_phase_is_not_a_clifford_correction(self):
        # These three labels have zero first moments and no cubic term,
        # but have a nonzero (0,0,1) entry, corresponding to CS-type data.
        corrupted = np.vstack([self.ccz, [1, 0, 0], [0, 1, 0], [1, 1, 0]])
        with self.assertRaisesRegex(ValueError, r'\(0, 0, 1\)'):
            self.check_witness(corrupted)

    def test_fractional_entries_are_not_binary(self):
        with self.assertRaisesRegex(ValueError, 'expected binary data'):
            binary_values(np.array([[0.5, 1.0]]), Path('test-witness'))


if __name__ == '__main__':
    unittest.main()
