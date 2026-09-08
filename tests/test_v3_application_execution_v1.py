from copy import deepcopy
import unittest

from telemetry_availability.v3_application_execution_v1 import (
    align_probe, boundary_context, completion_observation, edge_id, explicit_status,
    fit_operation, replay_operation, request_evidence, timestamp_ns)


PROFILE = 'spring_petclinic_microservices'


def fixture():
    trace, parent = boundary_context(PROFILE, 'toy-1')
    started = '2026-01-01T00:00:01+00:00'
    request = dict(request_id='toy-1', trace_id=trace, operation='toy', period='calibration',
        started_at=started, completed_at='2026-01-01T00:00:01.100000+00:00',
        semantic_success=True, timed_out=False)
    def span(sid, pid, service, kind, attrs):
        return dict(trace_id=trace, span_id=sid, parent_id=pid, service=service,
            operation='Call', server=kind == '2', native_kind=kind, error_tag=False, error_status=False,
            start_us=timestamp_ns(started)//1000, duration_us=1000, start_remainder_ns=0,
            duration_remainder_ns=0, attributes=attrs,
            resource_attributes={'service.instance.id': 'target-a'} if service == 'target' else {})
    spans = [span('entry', parent, 'entry', '2', {'http.status_code': 200}),
             span('client', 'entry', 'entry', '3', {'server.address': 'target'}),
             span('target', 'client', 'target', '2', {'rpc.grpc.status_code': 0})]
    declarations = dict(profile=PROFILE, placement='colocated', target_service='target',
        replicas={'a': 'target-a', 'b': 'target-b'})
    spec = dict(entry='entry', external_roots=1, target_calls=1, database_peers=[],
        client_route_names=['target'], deadline_ns=2000000000, minimum_calls_by_pair={},
        ignored_rpc_methods_by_pair={}, source_error_propagation_assumed=True,
        expected_attempts=1, required_native_services=['target'], allowed_native_services=['entry', 'target'],
        required_native_pairs=[['entry', 'target']], maximum_probe_age_ns=2000000000, assumptions={})
    probe = dict(observed_at='2026-01-01T00:00:00+00:00',
        replica_a_backend_status='UP', replica_a_backend_check_status='* L4OK',
        replica_b_backend_status='UP', replica_b_backend_check_status='L4OK')
    data = {'requests.json': [request], 'declarations.json': declarations,
            'native.json': {'spans': {trace: spans}}, 'probes.json': [probe]}
    return data, spec, request, spans, declarations


class ApplicationBindingTests(unittest.TestCase):
    def test_labels_cannot_change_graph_parameters_or_predictions(self):
        data, spec, _, _, _ = fixture()
        model, report = fit_operation(data, 'toy', spec)
        altered = deepcopy(data)
        altered['requests.json'][0].update(semantic_success=False, timed_out=True)
        changed, changed_report = fit_operation(altered, 'toy', spec)
        self.assertEqual(model, changed); self.assertEqual(report, changed_report)
        self.assertEqual(report['estimates']['execution']['prediction'], 1)
        self.assertEqual(replay_operation(model)['result_sha256'], report['result_sha256'])

    def test_no_error_and_status_unset_are_not_success(self):
        _, _, _, spans, _ = fixture()
        span = deepcopy(spans[0]); span['attributes'] = {}
        self.assertIsNone(explicit_status(span))
        span['error_status'] = True
        self.assertFalse(explicit_status(span))

    def test_swallowed_required_client_error_and_missing_server_are_retained(self):
        data, spec, request, spans, declarations = fixture()
        missing = deepcopy(spans[:2]); missing[1]['error_status'] = True
        evidence = request_evidence(request, missing, declarations, spec)
        self.assertTrue(evidence['root_status'])
        self.assertEqual(evidence['demands'], {'a': None, 'b': None})
        self.assertEqual(completion_observation(('entry', 'target'), evidence, spec),
                         (False, 'explicit_required_client_failure'))
        # Include a normal attempt to discover the edge, without excluding the failed attempt.
        trace, parent = boundary_context(PROFILE, 'toy-2')
        second = dict(request, request_id='toy-2', trace_id=trace)
        normal = deepcopy(spans)
        for span in normal:
            span['trace_id'] = trace
        normal[0]['parent_id'] = parent
        data['requests.json'].append(second); spec['expected_attempts'] = 2
        data['native.json']['spans'] = {request['trace_id']: missing, trace: normal}
        _, report = fit_operation(data, 'toy', spec)
        self.assertEqual(report['attempts'], 2)
        self.assertEqual(report['estimates']['execution']['lower_exact'], '1/2')

    def test_timeout_without_native_error_is_a_failed_deadline(self):
        data, spec, request, _, _ = fixture()
        request['completed_at'] = '2026-01-01T00:00:03.010000+00:00'
        _, report = fit_operation(data, 'toy', spec)
        self.assertEqual(report['estimates']['without_deadline']['prediction'], 1)
        self.assertEqual(report['estimates']['execution']['prediction'], 0)

    def test_optional_failed_call_is_excluded_by_declared_method(self):
        _, spec, request, spans, declarations = fixture()
        optional = deepcopy(spans[-1]); optional.update(span_id='ignored', operation='/Cart/EmptyCart', error_status=True)
        spans.append(optional)
        spec['ignored_rpc_methods_by_pair'][edge_id('entry', 'target')] = ['EmptyCart']
        e = request_evidence(request, spans, declarations, spec)
        self.assertEqual(completion_observation(('entry', 'target'), e, spec)[0], True)
        spec['ignored_rpc_methods_by_pair'] = {}
        self.assertEqual(completion_observation(('entry', 'target'), e, spec)[0], False)

    def test_probe_alignment_never_uses_future_or_excessively_old_value(self):
        data, _, _, _, _ = fixture(); probes = data['probes.json']; t = timestamp_ns(probes[0]['observed_at'])
        self.assertEqual(align_probe(t-1, probes, [t], 2000000000)[0], dict(probe_a=None, probe_b=None))
        self.assertEqual(align_probe(t+2000000001, probes, [t], 2000000000)[0], dict(probe_a=None, probe_b=None))
        self.assertEqual(align_probe(t+2000000000, probes, [t], 2000000000)[0], dict(probe_a=True, probe_b=True))
