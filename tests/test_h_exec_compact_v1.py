import unittest
from telemetry_availability.h_exec_compact_v1 import routes


class RoutingCensusTests(unittest.TestCase):
    def test_multiple_calls_failures_foreign_and_missing_context_remain_distinct(self):
        trace='1'*32;context='00-'+trace+'-'+'2'*16+'-01'
        text='\n'.join([
            f'study_route trace={context} backend=study_replicas server=replica_a status=503 total_ms=2000 termination=SD--',
            f'study_route trace={context} backend=study_replicas server=replica_b status=200 total_ms=2 termination=----',
            'study_route trace=- backend=study_replicas server=replica_a status=200 total_ms=1 termination=----',
            'study_route trace=00-'+'3'*32+'-'+'2'*16+'-01 backend=study_replicas server=replica_b status=200 total_ms=1 termination=----',
            'study_route malformed'])
        result,audit=routes(text,{trace})
        self.assertEqual(len(result[trace]),2)
        self.assertEqual([r['status'] for r in result[trace]],[503,200])
        self.assertEqual(result[trace][0]['total_ms'],2000)
        self.assertEqual(audit,dict(joined_routes=2,missing_or_invalid_traceparent=1,outside_external_census=1,malformed_route_lines=1))
