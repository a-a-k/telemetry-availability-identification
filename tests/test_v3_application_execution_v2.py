from copy import deepcopy
import unittest

from test_v3_application_execution_v1 import fixture
from telemetry_availability.v3_application_execution_v1 import fit_operation as old_fit
from telemetry_availability.v3_application_execution_v2 import (
    BindingUnsupported, db_identity, declared_probe_layer, edge_id, fit_operation, replay_operation)


class CorrectedBindingTests(unittest.TestCase):
    def test_declared_l7_success_is_not_masked_as_l4(self):
        data, spec, _, _, declarations = fixture()
        declarations['backend_success_check_statuses'] = ['L7OK']
        for p in data['probes.json']:
            p.update(replica_a_backend_check_status='* L7OK', replica_b_backend_check_status='L7OK')
        _, before = old_fit(data, 'toy', spec)
        self.assertIsNone(before['estimates']['execution']['prediction'])
        model, after = fit_operation(data, 'toy', spec)
        self.assertEqual(after['estimates']['execution']['prediction'], 1)
        self.assertEqual(after['missing_coordinate_counts'], {})
        self.assertEqual(replay_operation(model)['result_sha256'], after['result_sha256'])

    def test_l4_model_calculation_is_exactly_unchanged_and_labels_unused(self):
        data, spec, request, _, declarations = fixture()
        declarations['backend_success_check_statuses'] = ['L4OK']
        _, before = old_fit(data, 'toy', spec)
        model, after = fit_operation(data, 'toy', spec)
        self.assertEqual(before['result_sha256'], after['result_sha256'])
        request.update(semantic_success=False, timed_out=True)
        changed, _ = fit_operation(data, 'toy', spec)
        self.assertEqual(changed, model)

    def test_unrecognized_probe_contract_does_not_fall_back(self):
        for statuses in ([], ['L4OK', 'L7OK'], ['invented']):
            with self.assertRaises(BindingUnsupported):
                declared_probe_layer(dict(backend_success_check_statuses=statuses))

    def test_unique_declared_valkey_default_db_completes_only_missing_field(self):
        _, _, _, spans, _ = fixture(); client = deepcopy(spans[1])
        client.update(service='cart', attributes={'db.system': 'redis', 'server.address': 'valkey-cart', 'server.port': 6379})
        peer = dict(owner='cart', system='redis', address='valkey-cart', port='6379', database='0')
        _, provenance = db_identity(client, [peer])
        self.assertEqual(provenance['completed_fields'], ['database'])
        self.assertEqual(provenance['declared']['database'], '0')
        with self.assertRaises(BindingUnsupported):
            db_identity(client, [peer, dict(peer, database='1')])

    def test_ignored_rpc_descendant_db_failure_remains_optional(self):
        data, spec, _, spans, declarations = fixture()
        declarations['backend_success_check_statuses'] = ['L4OK']
        optional = deepcopy(spans[-1]); optional.update(span_id='optional', operation='/Cart/EmptyCart', error_status=True)
        optional['resource_attributes']['service.instance.id'] = 'target-b'
        data['probes.json'][0]['replica_b_backend_status'] = 'DOWN'
        db = deepcopy(spans[-1]); db.update(span_id='db', parent_id='target', native_kind='3', server=False,
            attributes={'db.system': 'redis', 'server.address': 'store', 'server.port': 6379, 'db.name': '0'})
        failed_db = deepcopy(db); failed_db.update(span_id='optional-db', parent_id='optional', error_status=True)
        spans.extend([optional, db, failed_db])
        # The ignored group and its replica are not mandatory demands.
        spec['ignored_rpc_methods_by_pair'][edge_id('entry', 'target')] = ['EmptyCart']
        _, report = fit_operation(data, 'toy', spec)
        self.assertEqual(len(report['graph_edges']), 2)
        self.assertEqual(report['estimates']['execution']['prediction'], 1)
        spans.remove(db)
        _, optional_only = fit_operation(data, 'toy', spec)
        self.assertEqual(len(optional_only['graph_edges']), 2)
        self.assertEqual(sum(e['completion_required'] for e in optional_only['graph_edges']), 1)
        self.assertEqual(optional_only['estimates']['execution']['prediction'], 1)
        spec['ignored_rpc_methods_by_pair'] = {}
        _, bad = fit_operation(data, 'toy', spec)
        self.assertEqual(bad['estimates']['execution']['prediction'], 0)
