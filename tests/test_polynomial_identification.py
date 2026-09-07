from fractions import Fraction
from itertools import product
from math import prod
import unittest

from telemetry_availability.polynomial_identification import (
    boolean_probability_terms, certify_polynomial_target,
)


class PolynomialIdentificationTests(unittest.TestCase):
    def check_certificates(self, rows, result):
        for term in result.terms:
            if term.row_combination is not None:
                reconstructed = tuple(sum(a * row[j] for a, row in zip(term.row_combination, rows))
                                      for j in range(result.parameter_count))
                self.assertEqual(reconstructed, term.exponent)
                self.assertIsNone(term.null_direction)
            else:
                v = term.null_direction
                self.assertTrue(all(sum(a * b for a, b in zip(row, v)) == 0 for row in rows))
                self.assertNotEqual(sum(a * b for a, b in zip(term.exponent, v)), 0)

    def test_all_two_bit_boolean_expansions_match_independent_atom_expectations(self):
        for table in product((0, 1), repeat=4):
            terms = boolean_probability_terms(table)
            for p in ((Fraction(1, 3), Fraction(2, 5)), (Fraction(3, 4), Fraction(1, 7))):
                atoms = sum(table[mask] * prod(p[j] if mask & (1 << j) else 1 - p[j]
                                               for j in range(2)) for mask in range(4))
                polynomial = sum(c * prod(p[j] ** exponent[j] for j in range(2))
                                 for exponent, c in terms.items())
                self.assertEqual(atoms, polynomial)
        self.assertEqual(boolean_probability_terms([0, 1, 1, 0]), {(1, 0): 1, (0, 1): 1, (1, 1): -2})

    def test_disjoint_union_is_identified_without_individual_primitives(self):
        rows = [(1, 1, 0, 0), (0, 0, 1, 1)]
        terms = {(1, 1, 0, 0): 1, (0, 0, 1, 1): 1, (1, 1, 1, 1): -1}
        result = certify_polynomial_target(4, rows, terms)
        self.assertTrue(result.globally_identified)
        self.assertEqual(result.moment_rank, 2)
        self.check_certificates(rows, result)
        self.assertFalse(certify_polynomial_target(4, rows, {(1, 0, 0, 0): 1}).globally_identified)

    def test_shared_union_requires_the_missing_joint_moment(self):
        rows = [(1, 1, 0), (0, 1, 1)]
        terms = {(1, 1, 0): 1, (0, 1, 1): 1, (1, 1, 1): -1}
        incomplete = certify_polynomial_target(3, rows, terms)
        self.assertFalse(incomplete.globally_identified)
        self.check_certificates(rows, incomplete)
        complete_rows = rows + [(1, 1, 1)]
        complete = certify_polynomial_target(3, complete_rows, terms)
        self.assertTrue(complete.globally_identified)
        self.check_certificates(complete_rows, complete)

    def test_identified_combination_with_all_distinct_columns(self):
        rows = [(1, 1, 0, 0), (0, 1, 1, 0), (0, 0, 1, 1)]
        result = certify_polynomial_target(4, rows, {(1, 0, 0, 1): 1})
        self.assertTrue(result.globally_identified)
        self.assertEqual(result.terms[0].row_combination, (1, -1, 1))
        self.check_certificates(rows, result)

    def test_stationary_point_does_not_become_an_identification_certificate(self):
        rows = [(1, 1)]
        result = certify_polynomial_target(2, rows, boolean_probability_terms([0, 1, 1, 1]))
        self.assertFalse(result.globally_identified)
        self.check_certificates(rows, result)
        first, second = (Fraction(1, 2), Fraction(1, 2)), (Fraction(2, 5), Fraction(5, 8))
        self.assertEqual(prod(first), prod(second))
        self.assertEqual(first[0] - first[1], 0)  # derivative along the log-kernel at first
        self.assertEqual(sum(first) - prod(first), Fraction(3, 4))
        self.assertEqual(sum(second) - prod(second), Fraction(31, 40))

    def test_zero_rows_duplicate_rows_constants_and_fractional_certificates(self):
        for rows, terms in [([], {(0, 0): 1}), ([(0, 0), (1, 1), (1, 1)], {(1, 1): 1}),
                            ([(2, 2)], {(1, 1): 1}), ([], {(1, 0): 1}), ([], {})]:
            result = certify_polynomial_target(2, rows, terms)
            self.check_certificates(rows, result)
            self.assertEqual(result.globally_identified, terms != {(1, 0): 1})
        self.assertTrue(certify_polynomial_target(0, [], {(): 1}).globally_identified)

    def test_rejects_approximate_or_incomplete_contracts(self):
        for table in ([], [0, 1, 0], [0, 2]):
            with self.assertRaises(ValueError):
                boolean_probability_terms(table)
        for dimension, rows, terms in [(2, [(1.0, 1)], {}), (2, [(1,)], {}),
                                       (2, [], {(1, -1): 1}), (2, [], {(1, 0): 0.5}), (-1, [], {})]:
            with self.assertRaises(ValueError):
                certify_polynomial_target(dimension, rows, terms)


if __name__ == "__main__":
    unittest.main()
