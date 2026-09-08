import ast
from pathlib import Path
import unittest

from telemetry_availability.health_prefix_audit_v2 import validate_qualification


class PrefixCensusSchemaTests(unittest.TestCase):
    def test_old_m7_and_new_petclinic_require_explicit_boundary(self):
        validate_qualification({}, {'usable':True}, 'M7')
        validate_qualification({'usable':True}, {'usable':True}, 'Petclinic')
        for manifest, boundary, family in [({}, {'usable':False}, 'M7'),
                                          ({'usable':False}, {'usable':True}, 'M7'),
                                          ({'usable':False}, {'usable':True}, 'Petclinic')]:
            with self.assertRaises(AssertionError):
                validate_qualification(manifest,boundary,family)
        with self.assertRaises(KeyError):
            validate_qualification({}, {'usable':True}, 'Petclinic')

    def test_decoder_and_census_unchanged_from_frozen_v1(self):
        root=Path(__file__).resolve().parents[1]/'src/telemetry_availability'
        functions=[]
        for name in ('health_prefix_audit.py','health_prefix_audit_v2.py'):
            tree=ast.parse((root/name).read_text())
            functions.append({n.name:ast.dump(n) for n in tree.body if isinstance(n,ast.FunctionDef)})
        for name in ('corrected_signal','census','restore'):
            self.assertEqual(functions[0][name],functions[1][name])


if __name__=='__main__':
    unittest.main()
