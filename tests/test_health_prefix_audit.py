import unittest

from telemetry_availability.health_prefix_audit import corrected_signal
from telemetry_availability.isolated_stochastic_fit import health_signal
from telemetry_availability.live_validation_analysis import _health_signal


class HealthPrefixCorrectionTests(unittest.TestCase):
    def row(self, check='* L4OK', **fields):
        values = dict(observed='true',running='true',paused='false',network_count='1',
                      backend_status='UP',backend_check_status=check)
        values.update(fields)
        return {'replica_a_'+key:value for key,value in values.items()}

    def test_documented_in_progress_preserves_last_success(self):
        row = self.row()
        self.assertEqual(_health_signal(row,'a'),(1,0))
        self.assertEqual(corrected_signal(row,'a'),(1,1))
        self.assertEqual(row['replica_a_backend_check_status'],'* L4OK')
        row = self.row('* L7OK')
        self.assertEqual(health_signal(row,'a',['L7OK']),(1,0))
        self.assertEqual(corrected_signal(row,'a',['L7OK']),(1,1))

    def test_all_other_legacy_rules_preserved(self):
        for check in ('','L4OK','L4TOUT','UNK','*L4OK',' * L4OK'):
            row = self.row(check)
            self.assertEqual(corrected_signal(row,'a'),_health_signal(row,'a'))
        for fields in (dict(paused='true'),dict(running='false'),dict(network_count='0'),
                       dict(backend_status='DOWN')):
            row = self.row(**fields)
            self.assertEqual(corrected_signal(row,'a'),_health_signal(row,'a'))
        self.assertEqual(corrected_signal(self.row('* L4TOUT'),'a'),(1,0))

    def test_declared_layer_mismatch_still_rejected(self):
        with self.assertRaises(ValueError):
            corrected_signal(self.row('* L4OK'),'a',['L7OK'])


if __name__ == '__main__':
    unittest.main()
