"""Disclosed PCM representation and independently fitted local-error substitutions."""
import math
import re
from xml.etree import ElementTree as ET
from xml.sax.saxutils import quoteattr

from .pmx_composition_control import contain_failure_types
from .pmx_pmf_bridge import integer_loop_pmfs

SEFF = re.compile(r'<serviceEffectSpecifications__BasicComponent\b[^>]*>.*?</serviceEffectSpecifications__BasicComponent>', re.S)
FAILURE = re.compile(r'\bfailureProbability="([^"]*)"')


def conditional_probabilities(text, operation_oracle):
    """Change only already represented error attributes; reject unsupported data."""
    expected = {row['operation']: row for row in operation_oracle}
    if any(row['conditional_local_probability'] is None or not row['observed_propagation_compatible'] for row in expected.values()):
        raise ValueError('conditional local propagation or positivity unsupported')
    tree = ET.fromstring(text)
    names = {node.attrib['id']: node.attrib['entityName'] for node in tree.iter()
             if 'id' in node.attrib and 'entityName' in node.attrib}
    visited, changes = set(), []
    def replace_block(match):
        block = match[0]
        signature = re.search(r'\bdescribedService__SEFF="([^"]+)"', block)
        operation = names[signature[1]]
        if operation in visited or operation not in expected:
            raise ValueError('ambiguous or unexpected operation')
        visited.add(operation)
        row = expected[operation]
        before = FAILURE.findall(block)
        if len(before) > 1 or abs((float(before[0]) if before else 0)-row['inclusive_probability']) > 1e-12:
            raise ValueError('native inclusive parameter differs')
        after = row['conditional_local_probability']
        if not math.isfinite(after) or not 0 <= after <= 1 or (not before and after != 0):
            raise ValueError('unsupported local error substitution')
        changes.append({'operation': operation, 'before': float(before[0]) if before else 0, 'after': after})
        return FAILURE.sub(lambda _: 'failureProbability='+quoteattr(format(after, '.17g')), block)
    updated = SEFF.sub(replace_block, text)
    if visited != set(expected):
        raise ValueError('incomplete conditional operation coverage')
    # Erasing all target values must yield byte-identical XML.
    if FAILURE.sub('failureProbability="TARGET"', text) != FAILURE.sub('failureProbability="TARGET"', updated):
        raise ValueError('non-parameter XML changed')
    ET.fromstring(updated)
    return updated, changes


def bridge(text, operation_oracle, variant):
    if variant not in ('inclusive', 'conditional_local'):
        raise ValueError('unknown error parameterization')
    changes = []
    if variant == 'conditional_local':
        text, changes = conditional_probabilities(text, operation_oracle)
    text = contain_failure_types(text)
    text, loops = integer_loop_pmfs(text)
    return text, {'error_parameter_changes': changes, 'loop_representation_changes': loops}
