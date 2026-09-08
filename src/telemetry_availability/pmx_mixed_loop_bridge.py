"""Equivalent integer conversion while preserving native PMX integer PMFs."""
import math
import re
from xml.etree import ElementTree as ET

from .pmx_composition_control import contain_failure_types
from .pmx_pmf_bridge import LOOP_TAG, LOOP_TOKEN
from .pmx_request_pcm import conditional_probabilities

NUMBER = r'(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?'
PAIR = re.compile(r'\(\s*(0|[1-9][0-9]*)\s*;\s*('+NUMBER+r')\s*\)')


def validate_integer_pmf(specification):
    if not specification.startswith('IntPMF[') or not specification.endswith(']'):
        raise ValueError('not an integer PMF literal')
    body = specification[7:-1]
    pairs = PAIR.findall(body)
    if not pairs or PAIR.sub('', body).strip():
        raise ValueError('unsupported integer PMF syntax')
    counts = [int(count) for count, _ in pairs]
    probabilities = [float(probability) for _, probability in pairs]
    if (len(set(counts)) != len(counts) or any(not math.isfinite(p) or not 0 <= p <= 1 for p in probabilities)
            or abs(math.fsum(probabilities)-1) > 1e-12):
        raise ValueError('invalid integer PMF support or probability mass')
    return list(zip(counts, probabilities, strict=True))


def mixed_loop_pmfs(text):
    tree = ET.fromstring(text)
    parent = {child: node for node in tree.iter() for child in node}
    nodes = list(tree.iter(LOOP_TAG))
    if not nodes or len(LOOP_TOKEN.findall(text)) != len(nodes):
        raise ValueError('absent or unsupported loop serialization')
    changes = []
    for node in nodes:
        owner = parent[node]
        if not owner.get('id') or not owner.get('{http://www.w3.org/2001/XMLSchema-instance}type', '').endswith(':LoopAction'):
            raise ValueError('ambiguous loop owner')
        value = node.get('specification', '')
        if re.fullmatch(r'0|[1-9][0-9]*', value):
            after, law = f'IntPMF[({value};1.0)]', [(int(value), 1.0)]
        else:
            after, law = value, validate_integer_pmf(value)
        changes.append({'loop_id': owner.attrib['id'], 'before': value, 'after': after,
            'existing_pmf_preserved': value == after, 'integer_probability_law': law})
    iterator = iter(changes)
    rewritten = LOOP_TOKEN.sub(lambda match: match[1]+next(iterator)['after']+match[3], text)
    restored = ET.fromstring(rewritten)
    for original, updated in zip(nodes, restored.iter(LOOP_TAG), strict=True):
        updated.set('specification', original.attrib['specification'])
    if ET.tostring(tree) != ET.tostring(restored):
        raise ValueError('non-loop XML changed')
    return rewritten, changes


def bridge(text, oracle, variant):
    if variant not in ('inclusive', 'conditional_local'):
        raise ValueError('unknown parameter variant')
    changes = []
    if variant == 'conditional_local':
        text, changes = conditional_probabilities(text, oracle)
    text = contain_failure_types(text)
    text, loops = mixed_loop_pmfs(text)
    return text, {'error_parameter_changes': changes, 'loop_representation_changes': loops}
