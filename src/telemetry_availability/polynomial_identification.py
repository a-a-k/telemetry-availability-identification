"""Exact reference for polynomial targets under monomial moment observations.

This is a population algebra certificate, not a model-adequacy or uncertainty
test. Boolean/nonmonomial observations and boundary-only domains are outside
the contract. See docs/CONJUNCTIVE_OBSERVATION_TARGET_THEOREMS.md.
"""
from dataclasses import dataclass
from fractions import Fraction
from typing import Mapping, Sequence


@dataclass(frozen=True)
class MonomialCertificate:
    exponent: tuple[int, ...]
    coefficient: int
    row_combination: tuple[Fraction, ...] | None
    null_direction: tuple[Fraction, ...] | None


@dataclass(frozen=True)
class PolynomialCertificate:
    parameter_count: int
    moment_rank: int
    globally_identified: bool
    terms: tuple[MonomialCertificate, ...]


def boolean_probability_terms(truth_table: Sequence[int | bool]) -> dict[tuple[int, ...], int]:
    """Multilinear expectation coefficients; table index bit j is primitive j.

    Input is the complete truth table, so its size is already exponential.
    Zero coefficients are removed after the Boolean-lattice Mobius transform.
    """
    size = len(truth_table)
    if size == 0 or size & (size - 1) or any(value not in (0, 1) for value in truth_table):
        raise ValueError("a complete binary truth table of power-of-two size is required")
    dimension = size.bit_length() - 1
    coefficients = [int(value) for value in truth_table]
    for bit in range(dimension):
        for mask in range(size):
            if mask & (1 << bit):
                coefficients[mask] -= coefficients[mask ^ (1 << bit)]
    return {tuple((mask >> bit) & 1 for bit in range(dimension)): coefficient
            for mask, coefficient in enumerate(coefficients) if coefficient}


def _integer_vector(row: Sequence[int], dimension: int) -> tuple[int, ...]:
    vector = tuple(row)
    if len(vector) != dimension or any(type(x) is not int or x < 0 for x in vector):
        raise ValueError("exponents must be nonnegative integer vectors of the declared dimension")
    return vector


def certify_polynomial_target(
    parameter_count: int,
    moment_exponents: Sequence[Sequence[int]],
    terms: Mapping[tuple[int, ...], int],
) -> PolynomialCertificate:
    """Certify global target identification on an open positive parameter box.

    Exact row combinations certify identified terms. For an unsupported term,
    an exact null direction satisfies H v = 0 and exponent.v != 0. That is a
    global nonidentification certificate, not a numerical parameter-pair
    witness at any particular supplied point. Like polynomial terms must be
    collected before this call; mapping keys encode that canonical expansion.
    """
    if type(parameter_count) is not int or parameter_count < 0:
        raise ValueError("parameter_count must be a nonnegative integer")
    original = [_integer_vector(row, parameter_count) for row in moment_exponents]
    canonical = []
    for exponent, coefficient in terms.items():
        exponent = _integer_vector(exponent, parameter_count)
        if type(coefficient) is not int:
            raise ValueError("the exact reference requires integer polynomial coefficients")
        if coefficient:
            canonical.append((exponent, coefficient))
    count = len(original)
    reduced = [[Fraction(x) for x in row] for row in original]
    transforms = [[Fraction(int(i == j)) for j in range(count)] for i in range(count)]
    pivots = []
    rank = 0
    for column in range(parameter_count):
        pivot = next((i for i in range(rank, count) if reduced[i][column]), None)
        if pivot is None:
            continue
        reduced[rank], reduced[pivot] = reduced[pivot], reduced[rank]
        transforms[rank], transforms[pivot] = transforms[pivot], transforms[rank]
        divisor = reduced[rank][column]
        reduced[rank] = [x / divisor for x in reduced[rank]]
        transforms[rank] = [x / divisor for x in transforms[rank]]
        for i in range(count):
            if i == rank:
                continue
            multiplier = reduced[i][column]
            if multiplier:
                reduced[i] = [a - multiplier * b for a, b in zip(reduced[i], reduced[rank])]
                transforms[i] = [a - multiplier * b for a, b in zip(transforms[i], transforms[rank])]
        pivots.append(column)
        rank += 1
    certificates = []
    for exponent, coefficient in sorted(canonical):
        remaining = [Fraction(x) for x in exponent]
        combination = [Fraction(0) for _ in range(count)]
        for i, pivot in enumerate(pivots):
            multiplier = remaining[pivot]
            remaining = [a - multiplier * b for a, b in zip(remaining, reduced[i])]
            combination = [a + multiplier * b for a, b in zip(combination, transforms[i])]
        if not any(remaining):
            certificates.append(MonomialCertificate(exponent, coefficient, tuple(combination), None))
            continue
        free = next(j for j in range(parameter_count) if remaining[j])
        direction = [Fraction(0) for _ in range(parameter_count)]
        direction[free] = Fraction(1)
        for i, pivot in enumerate(pivots):
            direction[pivot] = -reduced[i][free]
        certificates.append(MonomialCertificate(exponent, coefficient, None, tuple(direction)))
    return PolynomialCertificate(parameter_count, rank,
                                 all(term.row_combination is not None for term in certificates),
                                 tuple(certificates))
