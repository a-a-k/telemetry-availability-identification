from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from telemetry_availability.pmx_adapter_conformance import (
    AdapterError, CASES, compare_pcm, fixture, inspect_pcm, run_pmx,
)


class AdapterConformanceTests(unittest.TestCase):
    def test_independent_artificial_counts_edges_and_coverage(self):
        for case in CASES:
            with self.subTest(case=case):
                result, expected, documents = fixture(case)
                self.assertEqual(len(documents), 10)
                self.assertEqual(len(result["mapping"]), 30)
                self.assertEqual(len(expected["operations"]), 3)
                self.assertEqual(len(result["envelope"]["data"]), 20 if case == "contracted_forest" else 10)
                probabilities = sorted(expected["operations"].values())
                self.assertEqual(probabilities, [0, .1, .2] if case == "nested_errors" else
                                 ([0, 0, .1] if case == "contracted_forest" else [0, 0, 0]))
                if case == "colliding_instances":
                    self.assertEqual(len(set(expected["component_hosts"].values())), 3)
                if case == "contracted_forest":
                    self.assertEqual(sum(r["missing_parent_roots"] for r in result["census"]), 10)
                    self.assertEqual(sum(r["nonserver_errors"] for r in result["census"]), 1)

    def test_xml_reference_resolution_ignores_node_order(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "x.repository").write_text('''<Repository>
              <components__Repository id="B" entityName="component-b">
                <serviceEffectSpecifications__BasicComponent describedService__SEFF="sb"><step>
                  <failure failureProbability="0.1"/>
                  <specification_ParametericResourceDemand specification="0.005"/>
                </step></serviceEffectSpecifications__BasicComponent>
              </components__Repository>
              <components__Repository id="A" entityName="component-a">
                <serviceEffectSpecifications__BasicComponent describedService__SEFF="sa">
                  <call calledService_ExternalService="sb"/>
                </serviceEffectSpecifications__BasicComponent>
              </components__Repository>
              <interface><signature id="sa" entityName="operation-a"/>
                <signature id="sb" entityName="operation-b"/></interface>
            </Repository>''')
            (root / "x.system").write_text('''<System>
              <assembly id="aa"><encapsulatedComponent__AssemblyContext href="x.repository#A"/></assembly>
              <assembly id="ab"><encapsulatedComponent__AssemblyContext href="x.repository#B"/></assembly>
            </System>''')
            (root / "x.resourceenvironment").write_text('<Resources><host id="h" entityName="HOST-SRV"/></Resources>')
            (root / "x.allocation").write_text('''<Allocation>
              <allocationContexts_Allocation><resourceContainer_AllocationContext href="x.resourceenvironment#h"/>
                <assemblyContext_AllocationContext href="x.system#ab"/></allocationContexts_Allocation>
              <allocationContexts_Allocation><assemblyContext_AllocationContext href="x.system#aa"/>
                <resourceContainer_AllocationContext href="x.resourceenvironment#h"/></allocationContexts_Allocation>
            </Allocation>''')
            (root / "x.usagemodel").write_text('''<Usage xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
              <action xsi:type="usagemodel:EntryLevelSystemCall"><operationSignature__EntryLevelSystemCall href="x.repository#sa"/></action>
            </Usage>''')
            actual = inspect_pcm(root)
            expected = {"operations": {"operation-a": 0, "operation-b": .1},
                        "edges": [["operation-a", "operation-b"]],
                        "component_hosts": {"component-a": "HOST-SRV", "component-b": "HOST-SRV"},
                        "operation_components": {"operation-a": "component-a", "operation-b": "component-b"},
                        "entry_operation_counts": {"operation-a": 1},
                        "leaf_operation_seconds": {"operation-b": .005}}
            self.assertTrue(compare_pcm(actual, expected)["qualified"])
            self.assertEqual(actual["operations"]["operation-b"]["component"], "component-b")
            for mutator in (
                lambda x: x["operations"]["operation-a"].update(failure_probability=.1),
                lambda x: x["edges"].clear(),
                lambda x: x["allocations"][0].update(host="WRONG-HOST"),
            ):
                changed = deepcopy(actual)
                mutator(changed)
                self.assertFalse(compare_pcm(changed, expected)["qualified"])
            # Broken references must not resolve through nearby entity names.
            path = root / "x.system"
            path.write_text(path.read_text().replace("#B", "#does-not-exist"))
            with self.assertRaisesRegex(AdapterError, "unresolved_pcm_reference"):
                inspect_pcm(root)

    def test_dynamic_invocation_is_remote_only(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(AdapterError, "remote_only"):
                run_pmx(Path("missing.jar"), Path("input"), Path("output"))


if __name__ == "__main__":
    unittest.main()
