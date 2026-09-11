"""Actual native backend qualification, run only on the remote benchmark runner."""
import os
from pathlib import Path
import sys
sys.path[:0] = [str(Path(__file__).resolve().parents[1]/'src'), str(Path(__file__).resolve().parents[1]/'tests')]
from test_graph_execution_bdd_v1 import tiny_model
from telemetry_availability.graph_execution_model_v1 import solve, predicates
from telemetry_availability.graph_execution_bdd_v1 import CompiledModel, POLICIES, verify_result
from itertools import product

assert os.environ.get('GITHUB_ACTIONS') == 'true'
for policy in POLICIES:
    model = tiny_model(); compiled = CompiledModel(model, policy)
    for values in product((False, True), repeat=len(model['signal_ids'])):
        state = dict(zip(model['signal_ids'], values)); cube = compiled.bdd.cube(state)
        assert {name:int(cube & root != compiled.bdd.false) for name, root in compiled.roots.items()} == predicates(model, state)
    print(policy, verify_result(model, compiled.solve(), solve(model)), compiled.statistics(), flush=True)
    del compiled
