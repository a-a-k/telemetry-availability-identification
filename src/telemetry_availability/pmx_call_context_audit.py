"""Retained application call-graph cycles and native invocation contexts."""
import argparse
from collections import Counter, defaultdict
import os
from pathlib import Path

from .pmx_composition_control import _download, _hash, _read, _remote, _write


def cyclic_components(edges):
    graph = defaultdict(set)
    for left, right in edges:
        graph[left].add(right)
        graph[right]
    indices, low, stack, active, components = {}, {}, [], set(), []
    def visit(node):
        indices[node] = low[node] = len(indices)
        stack.append(node)
        active.add(node)
        for child in sorted(graph[node]):
            if child not in indices:
                visit(child)
                low[node] = min(low[node], low[child])
            elif child in active:
                low[node] = min(low[node], indices[child])
        if low[node] == indices[node]:
            component = []
            while True:
                top = stack.pop()
                active.remove(top)
                component.append(top)
                if top == node:
                    break
            if len(component) > 1 or node in graph[node]:
                components.append(sorted(component))
    for node in sorted(graph):
        if node not in indices:
            visit(node)
    return sorted(components)


def run(config_path, inputs, out):
    _remote()
    config = _read(config_path)
    for lock in config['repository_locks']:
        if _hash(Path(lock['path'])) != lock['sha256']:
            raise ValueError('cycle audit source differs')
    metadata = _download(config, inputs)
    source = inputs / 'application'
    contract = _read(source / 'application-input-contract.json')
    for name, digest in contract['files'].items():
        if _hash(source / name) != digest:
            raise ValueError('retained input differs')
    records = []
    for sample in contract['samples']:
        extraction = inputs / ('extract-'+sample['sample']['key'])
        for case in sample['cases']:
            root = source / 'cases' / case['case_id']
            resolved = _read(extraction / 'raw' / case['case_id'] / 'resolved-pcm.json')
            mapping = _read(root / 'mapping.json')
            labels = {r['pmx_operation']: {k: r[k] for k in ('service', 'operation', 'instance_key', 'instance_value')} for r in mapping}
            cycles = cyclic_components(resolved['edges'])
            envelope = _read(root / 'traces/observed.json')
            ancestor_repeats, context_paths, depths = Counter(), set(), Counter()
            examples = []
            for trace in envelope['data']:
                spans = {span['spanID']: span for span in trace['spans']}
                for span in spans.values():
                    cursor, path, seen = span, [], set()
                    while cursor:
                        if cursor['spanID'] in seen:
                            raise ValueError('native span-parent cycle')
                        seen.add(cursor['spanID'])
                        path.append(cursor['operationName'])
                        parent = cursor['references'][0]['spanID'] if cursor['references'] else None
                        cursor = spans.get(parent)
                    path.reverse()
                    context_paths.add(tuple(path))
                    depths[len(path)] += 1
                    if path[-1] in path[:-1]:
                        ancestor_repeats[path[-1]] += 1
                        if len(examples) < 4:
                            examples.append({'trace_id': trace['traceID'], 'span_id': span['spanID'], 'operation_path': path})
            records.append({'case_id': case['case_id'], 'operation_count': len(resolved['operations']),
                'cyclic_operation_components': cycles, 'cyclic_operation_labels': {key: labels[key] for cycle in cycles for key in cycle},
                'native_ancestor_operation_repeats': dict(ancestor_repeats), 'ancestor_repeat_examples': examples,
                'observed_full_caller_context_count': len(context_paths), 'invocation_depth_counts': dict(depths)})
    _write(out / 'call-context-audit.json', {'source_run_id': config['source_run_id'],
        'source_commit': config['source_head_sha'], 'audit_run_id': os.environ['GITHUB_RUN_ID'],
        'audit_commit': os.environ['GITHUB_SHA'], 'cases': records, 'metadata': metadata,
        'pmx_invocations': 0, 'fits': 0, 'solver_calls': 0, 'evaluator_rows_read': 0})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=Path('configs/m9v_call_context_audit.json'))
    parser.add_argument('--inputs', type=Path, default=Path('workflow-input/call-context'))
    parser.add_argument('--out', type=Path, default=Path('workflow-results/call-context'))
    args = parser.parse_args()
    run(args.config, args.inputs, args.out)


if __name__ == '__main__':
    main()
