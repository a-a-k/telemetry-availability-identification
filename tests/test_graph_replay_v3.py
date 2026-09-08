import importlib.util
from pathlib import Path
import tempfile
import unittest

from telemetry_availability.graph_replay_v3 import build_model, solve, Unsupported


class GraphReplayV3Tests(unittest.TestCase):
    def test_independent_oracles_and_separate_process_chain(self):
        path=Path(__file__).resolve().parents[1]/'scripts/check_graph_chain_v3.py'
        spec=importlib.util.spec_from_file_location('graph_chain_controls',path)
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            report=module.run_checks(Path(directory))
        self.assertEqual(25,len(report['checks']))

    def test_malformed_saved_model_is_rejected(self):
        with self.assertRaises(Unsupported):
            solve({'version':'not-a-qualified-model'})


if __name__=='__main__': unittest.main()
