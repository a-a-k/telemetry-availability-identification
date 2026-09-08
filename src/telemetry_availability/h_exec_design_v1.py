"""Pure prospective H-EXEC assignment, routing control and exact randomization."""
from fractions import Fraction
from itertools import product
import random

ARMS = ('sham', 'transition', 'settled', 'repaired')


def assignments(blocks, seed):
    result = []
    for block in range(blocks):
        arms = list(ARMS)
        random.Random(seed + block).shuffle(arms)
        result.extend(dict(block=block, slot=slot, arm=arm) for slot, arm in enumerate(arms))
    return result


def exact_paired_test(differences):
    """Exact two-sided label-swap test; all assignments, including observed ties."""
    values = [Fraction(value) for value in differences]
    if not values or len(values) > 16:
        raise ValueError('bounded paired randomization requires 1..16 complete blocks')
    observed = abs(sum(values))
    exceed = sum(abs(sum(v*s for v,s in zip(values, signs))) >= observed
                 for signs in product((-1, 1), repeat=len(values)))
    return dict(blocks=len(values), mean_exact=str(sum(values)/len(values)),
        mean=float(sum(values)/len(values)), assignments=2**len(values),
        two_sided_p=exceed/2**len(values), exceed_or_tie=exceed)


def routing_control():
    """Independent rational arithmetic for the stated semantic reduction boundary."""
    records = []
    for a,b in product((0,1), repeat=2):
        for pi_a in (Fraction(0), Fraction(1,4), Fraction(1,2), Fraction(1)):
            pi_b = 1-pi_a
            actual = a*pi_a+b*pi_b; ideal = Fraction(bool(a or b))
            deficit = a*(1-b)*pi_b+b*(1-a)*pi_a
            assert ideal-actual == deficit and deficit >= 0
            records.append(dict(a=a, b=b, pi_a=str(pi_a), actual=str(actual), ideal=str(ideal), deficit=str(deficit)))
    for k in (1,2,3):
        # Enumerate selection sequences instead of assuming the power formula.
        actual = sum(Fraction(1,2**k) for sequence in product(('a','b'),repeat=k) if all(x=='b' for x in sequence))
        assert actual == Fraction(1,2)**k
        records.append(dict(k=k, sequence_success=str(actual), ideal='1'))
    return dict(controls=records, known_probability_fact=True, application_behavior_inferred=False)


def instrument_haproxy(source):
    if not source.startswith('global\n') or source.splitlines().count('global') != 1 or source.count('  option httplog\n') != 1:
        raise ValueError('unexpected pinned HTTP/2 proxy layout')
    if 'stats socket' in source or 'capture request header' in source:
        raise ValueError('instrumentation already present')
    return source.replace('global\n', 'global\n  stats socket /var/run/study/admin.sock mode 666 level admin\n', 1).replace(
        '  option httplog\n',
        '  option httplog\n  capture request header traceparent len 128\n'
        '  log-format "study_route trace=%[capture.req.hdr(0)] backend=%b server=%s status=%ST total_ms=%Ta termination=%tsc"\n')
