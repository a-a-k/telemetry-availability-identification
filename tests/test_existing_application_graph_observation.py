import unittest

from telemetry_availability.existing_application_graph_observation import bind_database, replay
from telemetry_availability.graph_observation_model import identify


class DeclaredPeerAndGraphTests(unittest.TestCase):
    def peer(self):
        return dict(owner='catalog', system='postgresql', address='database', port='5432', database='catalog')

    def span(self):
        return dict(service='catalog', native_kind='3', attributes={'db.system.name':'postgresql'})

    def test_partial_client_identity_requires_unique_compatible_declaration(self):
        node, record = bind_database(self.span(), [self.peer()])
        self.assertTrue(node.startswith('declared-db-client-'))
        self.assertEqual(record['completed_fields'], ['address', 'database', 'port'])
        self.assertIsNone(record['observed']['address'])
        self.assertEqual(record['declared']['address'], 'database')
        for peers in ([], [self.peer(), dict(self.peer(), address='another-database')]):
            with self.assertRaises(ValueError):
                bind_database(self.span(), peers)

    def test_conflicting_native_endpoint_and_nonclient_are_rejected(self):
        span = self.span(); span['attributes']['server.address'] = 'unexpected'
        with self.assertRaises(ValueError):
            bind_database(span, [self.peer()])
        span = self.span(); span['native_kind'] = '2'
        with self.assertRaises(ValueError):
            bind_database(span, [self.peer()])

    def test_replay_checks_each_required_dependency_on_nontrivial_joint_law(self):
        graph = dict(services=['entry', 'catalog', 'db'], edges=[
            dict(source='entry', target='catalog', type='sync', factors=[]),
            dict(source='catalog', target='db', type='sync', factors=[])])
        values = [(False, False)]*3 + [(True, False)]*2 + [(False, True)]*2 + [(True, True)]*3
        model = identify(graph, dict(entry=[[]], catalog=[['a'], ['b']], db=[[]]),
            dict(id='artificial', entry='entry', required=['catalog', 'db'], semantics='immediate_sync_all_required'),
            ['a', 'b'], [dict(a=a, b=b) for a,b in values], {})
        model['identity'] = dict(method='artificial')
        report = replay(model)
        self.assertEqual(report['prediction']['lower_exact'], '7/10')
        controls = report['structural_control']['remove_incoming_required_edges']
        self.assertEqual(set(controls), {'catalog', 'db'})
        self.assertTrue(all(value['upper_exact'] == '0' for value in controls.values()))
