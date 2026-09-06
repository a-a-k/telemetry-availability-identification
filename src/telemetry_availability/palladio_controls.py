from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
import textwrap
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_XSI_TYPE = "{http://www.w3.org/2001/XMLSchema-instance}type"
_MODEL_SUFFIXES = (
    "allocation",
    "repository",
    "resourceenvironment",
    "system",
    "usagemodel",
)
_EXPECTED_CASE_IDS = {
    "conditional_b0",
    "conditional_b100",
    "conditional_b25",
    "fallback_failed_alternative",
    "fallback_nominal",
    "fallback_perfect_alternative",
    "independent_redundant_paths",
    "network_call_failure_10_mapped",
    "network_q0",
    "network_q10_raw",
    "network_q100",
    "shared_domain_redundant_paths",
    "single_p0",
    "single_p100",
    "single_p20",
}


@dataclass(frozen=True)
class PalladioControlCase:
    id: str
    kind: str
    parameters: Mapping[str, float]
    expected_success_probability: float


@dataclass(frozen=True)
class PalladioControlModel:
    id: str
    kind: str
    expected_physical_states: int
    cases: tuple[PalladioControlCase, ...]


@dataclass(frozen=True)
class PalladioControlsConfig:
    path: Path
    schema_version: int
    id: str
    diagnostic_only: bool
    comparison_status: str
    analyzer_repository: str
    analyzer_commit: str
    analyzer_visitor_path: str
    analyzer_visitor_bytes: int
    analyzer_visitor_sha256: str
    analyzer_source_markers: tuple[str, ...]
    pcm_repository: str
    pcm_release_tag: str
    pcm_commit: str
    pcm_ecore_path: str
    pcm_ecore_bytes: int
    pcm_ecore_sha256: str
    pcm_network_documentation_marker: str
    bootstrap_config_path: str
    bootstrap_config_sha256: str
    repeat_runs: int
    probability_tolerance: float
    network_documented_call_failure_probability: float
    network_documented_call_success_reference: float
    network_raw_q_solver_success_oracle: float
    network_mapped_link_failure_probability: float
    network_mapped_solver_success_oracle: float
    network_mapping: str
    java_distribution: str
    java_version: int
    job_timeout_minutes: int
    remote_only: bool
    models: tuple[PalladioControlModel, ...]

    @property
    def cases(self) -> tuple[PalladioControlCase, ...]:
        return tuple(case for model in self.models for case in model.cases)


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return value


def _required_string(data: Mapping[str, Any], key: str, label: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}.{key} must be a non-empty string")
    return value


def _positive_integer(data: Mapping[str, Any], key: str, label: str) -> int:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label}.{key} must be a positive integer")
    return value


def _probability(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result) or result < 0.0 or result > 1.0:
        raise ValueError(f"{label} must be a finite probability")
    return result


def _sha256_string(data: Mapping[str, Any], key: str, label: str) -> str:
    value = _required_string(data, key, label)
    if not _SHA256_RE.fullmatch(value):
        raise ValueError(f"{label}.{key} must be a lowercase SHA-256")
    return value


def _commit(data: Mapping[str, Any], key: str, label: str) -> str:
    value = _required_string(data, key, label)
    if not _COMMIT_RE.fullmatch(value):
        raise ValueError(f"{label}.{key} must be a full lowercase commit")
    return value


def _availability(mttf: float, mttr: float) -> float:
    if mttf <= 0.0 or mttr <= 0.0:
        return 1.0
    return mttf / (mttf + mttr)


def _required_parameter(
    parameters: Mapping[str, float], key: str, case_id: str
) -> float:
    if key not in parameters:
        raise ValueError(f"control case {case_id} is missing parameter {key}")
    return float(parameters[key])


def expected_control_success(kind: str, parameters: Mapping[str, float]) -> float:
    if kind == "single":
        return 1.0 - _required_parameter(parameters, "failure_probability", kind)
    if kind == "fallback":
        primary = _required_parameter(parameters, "primary_failure_probability", kind)
        alternative = _required_parameter(
            parameters, "alternative_failure_probability", kind
        )
        return 1.0 - primary * alternative
    if kind == "conditional":
        branch = _required_parameter(parameters, "branch_probability", kind)
        failure = _required_parameter(parameters, "failure_probability", kind)
        return 1.0 - branch * failure
    if kind == "network":
        link_failure = _required_parameter(
            parameters, "link_failure_probability", kind
        )
        return (1.0 - link_failure) ** 2
    if kind in {"redundant_paths", "shared_domain"}:
        availability_a = _availability(
            _required_parameter(parameters, "path_a_mttf", kind),
            _required_parameter(parameters, "path_a_mttr", kind),
        )
        availability_b = _availability(
            _required_parameter(parameters, "path_b_mttf", kind),
            _required_parameter(parameters, "path_b_mttr", kind),
        )
        redundant = availability_a + (1.0 - availability_a) * availability_b
        common = _availability(
            _required_parameter(parameters, "common_mttf", kind),
            _required_parameter(parameters, "common_mttr", kind),
        )
        return common * redundant
    raise ValueError(f"unsupported Palladio control kind {kind}")


def _expected_physical_states(case: PalladioControlCase) -> int:
    if case.kind not in {"redundant_paths", "shared_domain"}:
        return 1
    unreliable = 0
    for prefix in ("common", "path_a", "path_b"):
        if (
            case.parameters[f"{prefix}_mttf"] > 0.0
            and case.parameters[f"{prefix}_mttr"] > 0.0
        ):
            unreliable += 1
    return 2**unreliable


def load_palladio_controls_config(path: Path) -> PalladioControlsConfig:
    with path.open("r", encoding="utf-8") as handle:
        root = _mapping(json.load(handle), "root")
    if root.get("schema_version") != 1:
        raise ValueError("schema_version must equal 1")
    if root.get("diagnostic_only") is not True:
        raise ValueError("M9B controls must remain diagnostic_only")
    if root.get("comparison_status") != "not_started":
        raise ValueError("M9B controls cannot start the comparative analysis")

    analyzer = _mapping(root.get("analyzer"), "analyzer")
    markers = analyzer.get("source_markers")
    if (
        not isinstance(markers, list)
        or len(markers) < 3
        or any(not isinstance(item, str) or not item for item in markers)
    ):
        raise ValueError("analyzer.source_markers must contain at least three strings")
    pcm = _mapping(root.get("pcm_metamodel"), "pcm_metamodel")
    bootstrap = _mapping(root.get("bootstrap_lock"), "bootstrap_lock")
    network_contract = _mapping(
        root.get("network_parameter_contract"), "network_parameter_contract"
    )
    runtime = _mapping(root.get("runtime"), "runtime")
    repeat_runs = _positive_integer(root, "repeat_runs", "root")
    if repeat_runs < 2:
        raise ValueError("repeat_runs must be at least two")
    tolerance_value = root.get("probability_tolerance")
    if isinstance(tolerance_value, bool) or not isinstance(
        tolerance_value, (int, float)
    ):
        raise ValueError("probability_tolerance must be numeric")
    probability_tolerance = float(tolerance_value)
    if not 0.0 < probability_tolerance <= 1e-9:
        raise ValueError("probability_tolerance must be in (0, 1e-9]")
    if runtime.get("remote_only") is not True:
        raise ValueError("full Palladio controls must remain remote_only")
    timeout = _positive_integer(runtime, "job_timeout_minutes", "runtime")
    if timeout != 360:
        raise ValueError("M9B job_timeout_minutes must equal 360")
    java_distribution = _required_string(runtime, "java_distribution", "runtime")
    java_version = _positive_integer(runtime, "java_version", "runtime")
    if java_distribution != "temurin" or java_version != 17:
        raise ValueError("M9B runtime must remain Temurin Java 17")

    raw_models = root.get("models")
    if not isinstance(raw_models, list) or not raw_models:
        raise ValueError("models must be a non-empty list")
    models: list[PalladioControlModel] = []
    model_ids: set[str] = set()
    case_ids: set[str] = set()
    allowed_model_kinds = {"software_suite", "network", "redundancy"}
    allowed_case_kinds = {
        "single",
        "fallback",
        "conditional",
        "network",
        "redundant_paths",
        "shared_domain",
    }
    for model_index, raw_model in enumerate(raw_models):
        model_label = f"models[{model_index}]"
        model_data = _mapping(raw_model, model_label)
        model_id = _required_string(model_data, "id", model_label)
        model_kind = _required_string(model_data, "kind", model_label)
        if model_id in model_ids:
            raise ValueError(f"duplicate model id {model_id}")
        if model_kind not in allowed_model_kinds:
            raise ValueError(f"unsupported model kind {model_kind}")
        model_ids.add(model_id)
        raw_cases = model_data.get("cases")
        if not isinstance(raw_cases, list) or not raw_cases:
            raise ValueError(f"{model_label}.cases must be non-empty")
        cases: list[PalladioControlCase] = []
        for case_index, raw_case in enumerate(raw_cases):
            case_label = f"{model_label}.cases[{case_index}]"
            case_data = _mapping(raw_case, case_label)
            case_id = _required_string(case_data, "id", case_label)
            kind = _required_string(case_data, "kind", case_label)
            if case_id in case_ids:
                raise ValueError(f"duplicate case id {case_id}")
            if kind not in allowed_case_kinds:
                raise ValueError(f"unsupported case kind {kind}")
            if model_kind == "software_suite" and kind not in {
                "single",
                "fallback",
                "conditional",
            }:
                raise ValueError(f"software suite cannot contain {kind}")
            if model_kind == "network" and kind != "network":
                raise ValueError("network model must contain a network case")
            if model_kind == "redundancy" and kind not in {
                "redundant_paths",
                "shared_domain",
            }:
                raise ValueError("redundancy model has the wrong case kind")
            raw_parameters = _mapping(case_data.get("parameters"), f"{case_label}.parameters")
            parameters = {
                str(key): _probability(value, f"{case_label}.parameters.{key}")
                for key, value in raw_parameters.items()
            }
            expected = _probability(
                case_data.get("expected_success_probability"),
                f"{case_label}.expected_success_probability",
            )
            calculated = expected_control_success(kind, parameters)
            if not math.isclose(calculated, expected, rel_tol=0.0, abs_tol=1e-15):
                raise ValueError(
                    f"{case_id} expected value {expected} disagrees with frozen oracle {calculated}"
                )
            case = PalladioControlCase(case_id, kind, parameters, expected)
            cases.append(case)
            case_ids.add(case_id)
        expected_states = _positive_integer(
            model_data, "expected_physical_states", model_label
        )
        for case in cases:
            if _expected_physical_states(case) != expected_states:
                raise ValueError(
                    f"{model_id} physical-state count disagrees with its parameters"
                )
        models.append(
            PalladioControlModel(
                model_id, model_kind, expected_states, tuple(cases)
            )
        )
    if case_ids != _EXPECTED_CASE_IDS:
        raise ValueError(
            "M9B control set differs from the frozen protocol: "
            f"missing={sorted(_EXPECTED_CASE_IDS - case_ids)}, "
            f"extra={sorted(case_ids - _EXPECTED_CASE_IDS)}"
        )

    documented_failure = _probability(
        network_contract.get("documented_call_failure_probability"),
        "network_parameter_contract.documented_call_failure_probability",
    )
    documented_success = _probability(
        network_contract.get("documented_call_success_reference"),
        "network_parameter_contract.documented_call_success_reference",
    )
    raw_solver_oracle = _probability(
        network_contract.get("raw_q_solver_success_oracle"),
        "network_parameter_contract.raw_q_solver_success_oracle",
    )
    mapped_link_failure = _probability(
        network_contract.get("mapped_link_failure_probability"),
        "network_parameter_contract.mapped_link_failure_probability",
    )
    mapped_solver_oracle = _probability(
        network_contract.get("mapped_solver_success_oracle"),
        "network_parameter_contract.mapped_solver_success_oracle",
    )
    if not math.isclose(
        documented_success, 1.0 - documented_failure, rel_tol=0.0, abs_tol=1e-15
    ):
        raise ValueError("documented network call reference is inconsistent")
    if not math.isclose(
        raw_solver_oracle,
        (1.0 - documented_failure) ** 2,
        rel_tol=0.0,
        abs_tol=1e-15,
    ):
        raise ValueError("raw network solver oracle is inconsistent")
    expected_mapped_link = 1.0 - math.sqrt(documented_success)
    if not math.isclose(
        mapped_link_failure, expected_mapped_link, rel_tol=0.0, abs_tol=1e-15
    ):
        raise ValueError("mapped network link probability is inconsistent")
    if not math.isclose(
        mapped_solver_oracle,
        (1.0 - mapped_link_failure) ** 2,
        rel_tol=0.0,
        abs_tol=1e-15,
    ):
        raise ValueError("mapped network solver oracle is inconsistent")

    analyzer_repository = _required_string(analyzer, "repository", "analyzer")
    pcm_repository = _required_string(pcm, "repository", "pcm_metamodel")
    if analyzer_repository != (
        "https://github.com/PalladioSimulator/"
        "Palladio-Analyzer-Reliability.git"
    ):
        raise ValueError("analyzer.repository must be official")
    if pcm_repository != "https://github.com/PalladioSimulator/Palladio-Core-PCM.git":
        raise ValueError("pcm_metamodel.repository must be official")
    pcm_release_tag = _required_string(pcm, "release_tag", "pcm_metamodel")
    if pcm_release_tag != "releases/5.2.2":
        raise ValueError("PCM metamodel release must remain 5.2.2")

    return PalladioControlsConfig(
        path=path,
        schema_version=1,
        id=_required_string(root, "id", "root"),
        diagnostic_only=True,
        comparison_status="not_started",
        analyzer_repository=analyzer_repository,
        analyzer_commit=_commit(analyzer, "commit", "analyzer"),
        analyzer_visitor_path=_required_string(
            analyzer, "visitor_path", "analyzer"
        ),
        analyzer_visitor_bytes=_positive_integer(
            analyzer, "visitor_bytes", "analyzer"
        ),
        analyzer_visitor_sha256=_sha256_string(
            analyzer, "visitor_sha256", "analyzer"
        ),
        analyzer_source_markers=tuple(markers),
        pcm_repository=pcm_repository,
        pcm_release_tag=pcm_release_tag,
        pcm_commit=_commit(pcm, "commit", "pcm_metamodel"),
        pcm_ecore_path=_required_string(pcm, "ecore_path", "pcm_metamodel"),
        pcm_ecore_bytes=_positive_integer(pcm, "ecore_bytes", "pcm_metamodel"),
        pcm_ecore_sha256=_sha256_string(pcm, "ecore_sha256", "pcm_metamodel"),
        pcm_network_documentation_marker=_required_string(
            pcm, "network_documentation_marker", "pcm_metamodel"
        ),
        bootstrap_config_path=_required_string(
            bootstrap, "config_path", "bootstrap_lock"
        ),
        bootstrap_config_sha256=_sha256_string(
            bootstrap, "config_sha256", "bootstrap_lock"
        ),
        repeat_runs=repeat_runs,
        probability_tolerance=probability_tolerance,
        network_documented_call_failure_probability=documented_failure,
        network_documented_call_success_reference=documented_success,
        network_raw_q_solver_success_oracle=raw_solver_oracle,
        network_mapped_link_failure_probability=mapped_link_failure,
        network_mapped_solver_success_oracle=mapped_solver_oracle,
        network_mapping=_required_string(
            network_contract, "mapping", "network_parameter_contract"
        ),
        java_distribution=java_distribution,
        java_version=java_version,
        job_timeout_minutes=timeout,
        remote_only=True,
        models=tuple(models),
    )


def _float_text(value: float) -> str:
    return format(value, ".17g")


def _xml(text: str) -> str:
    return textwrap.dedent(text).strip() + "\n"


def _software_action(case: PalladioControlCase) -> str:
    prefix = case.id
    if case.kind == "single":
        probability = _float_text(case.parameters["failure_probability"])
        return f"""
          <steps_Behaviour xsi:type="seff:StartAction" id="_{prefix}_start" successor_AbstractAction="_{prefix}_action"/>
          <steps_Behaviour xsi:type="seff:InternalAction" id="_{prefix}_action" entityName="{prefix}" predecessor_AbstractAction="_{prefix}_start" successor_AbstractAction="_{prefix}_stop">
            <internalFailureOccurrenceDescriptions__InternalAction id="_{prefix}_failure" failureProbability="{probability}" softwareInducedFailureType__InternalFailureOccurrenceDescription="_sw_failure"/>
          </steps_Behaviour>
          <steps_Behaviour xsi:type="seff:StopAction" id="_{prefix}_stop" predecessor_AbstractAction="_{prefix}_action"/>
        """
    if case.kind == "fallback":
        primary = _float_text(case.parameters["primary_failure_probability"])
        alternative = _float_text(
            case.parameters["alternative_failure_probability"]
        )
        return f"""
          <steps_Behaviour xsi:type="seff:StartAction" id="_{prefix}_start" successor_AbstractAction="_{prefix}_recovery"/>
          <steps_Behaviour xsi:type="seff_reliability:RecoveryAction" id="_{prefix}_recovery" entityName="{prefix}" predecessor_AbstractAction="_{prefix}_start" successor_AbstractAction="_{prefix}_stop" primaryBehaviour__RecoveryAction="_{prefix}_primary">
            <recoveryActionBehaviours__RecoveryAction id="_{prefix}_primary" entityName="primary" failureHandlingAlternatives__RecoveryActionBehaviour="_{prefix}_alternative">
              <steps_Behaviour xsi:type="seff:StartAction" id="_{prefix}_primary_start" successor_AbstractAction="_{prefix}_primary_action"/>
              <steps_Behaviour xsi:type="seff:InternalAction" id="_{prefix}_primary_action" predecessor_AbstractAction="_{prefix}_primary_start" successor_AbstractAction="_{prefix}_primary_stop">
                <internalFailureOccurrenceDescriptions__InternalAction id="_{prefix}_primary_failure" failureProbability="{primary}" softwareInducedFailureType__InternalFailureOccurrenceDescription="_sw_failure"/>
              </steps_Behaviour>
              <steps_Behaviour xsi:type="seff:StopAction" id="_{prefix}_primary_stop" predecessor_AbstractAction="_{prefix}_primary_action"/>
            </recoveryActionBehaviours__RecoveryAction>
            <recoveryActionBehaviours__RecoveryAction id="_{prefix}_alternative" entityName="alternative" failureTypes_FailureHandlingEntity="_sw_failure">
              <steps_Behaviour xsi:type="seff:StartAction" id="_{prefix}_alternative_start" successor_AbstractAction="_{prefix}_alternative_action"/>
              <steps_Behaviour xsi:type="seff:InternalAction" id="_{prefix}_alternative_action" predecessor_AbstractAction="_{prefix}_alternative_start" successor_AbstractAction="_{prefix}_alternative_stop">
                <internalFailureOccurrenceDescriptions__InternalAction id="_{prefix}_alternative_failure" failureProbability="{alternative}" softwareInducedFailureType__InternalFailureOccurrenceDescription="_sw_failure"/>
              </steps_Behaviour>
              <steps_Behaviour xsi:type="seff:StopAction" id="_{prefix}_alternative_stop" predecessor_AbstractAction="_{prefix}_alternative_action"/>
            </recoveryActionBehaviours__RecoveryAction>
          </steps_Behaviour>
          <steps_Behaviour xsi:type="seff:StopAction" id="_{prefix}_stop" predecessor_AbstractAction="_{prefix}_recovery"/>
        """
    if case.kind == "conditional":
        branch = _float_text(case.parameters["branch_probability"])
        other = _float_text(1.0 - case.parameters["branch_probability"])
        failure = _float_text(case.parameters["failure_probability"])
        return f"""
          <steps_Behaviour xsi:type="seff:StartAction" id="_{prefix}_start" successor_AbstractAction="_{prefix}_branch"/>
          <steps_Behaviour xsi:type="seff:BranchAction" id="_{prefix}_branch" entityName="{prefix}" predecessor_AbstractAction="_{prefix}_start" successor_AbstractAction="_{prefix}_stop">
            <branches_Branch xsi:type="seff:ProbabilisticBranchTransition" id="_{prefix}_taken" entityName="taken" branchProbability="{branch}">
              <branchBehaviour_BranchTransition id="_{prefix}_taken_behaviour">
                <steps_Behaviour xsi:type="seff:StartAction" id="_{prefix}_taken_start" successor_AbstractAction="_{prefix}_taken_action"/>
                <steps_Behaviour xsi:type="seff:InternalAction" id="_{prefix}_taken_action" predecessor_AbstractAction="_{prefix}_taken_start" successor_AbstractAction="_{prefix}_taken_stop">
                  <internalFailureOccurrenceDescriptions__InternalAction id="_{prefix}_taken_failure" failureProbability="{failure}" softwareInducedFailureType__InternalFailureOccurrenceDescription="_sw_failure"/>
                </steps_Behaviour>
                <steps_Behaviour xsi:type="seff:StopAction" id="_{prefix}_taken_stop" predecessor_AbstractAction="_{prefix}_taken_action"/>
              </branchBehaviour_BranchTransition>
            </branches_Branch>
            <branches_Branch xsi:type="seff:ProbabilisticBranchTransition" id="_{prefix}_skipped" entityName="skipped" branchProbability="{other}">
              <branchBehaviour_BranchTransition id="_{prefix}_skipped_behaviour">
                <steps_Behaviour xsi:type="seff:StartAction" id="_{prefix}_skipped_start" successor_AbstractAction="_{prefix}_skipped_stop"/>
                <steps_Behaviour xsi:type="seff:StopAction" id="_{prefix}_skipped_stop" predecessor_AbstractAction="_{prefix}_skipped_start"/>
              </branchBehaviour_BranchTransition>
            </branches_Branch>
          </steps_Behaviour>
          <steps_Behaviour xsi:type="seff:StopAction" id="_{prefix}_stop" predecessor_AbstractAction="_{prefix}_branch"/>
        """
    raise AssertionError(case.kind)


def _software_failure_reverse_references(
    model: PalladioControlModel,
) -> tuple[str, ...]:
    references: list[str] = []
    for index, case in enumerate(model.cases):
        base = (
            "//@components__Repository.0/"
            f"@serviceEffectSpecifications__BasicComponent.{index}"
        )
        if case.kind == "single":
            references.append(
                f"{base}/@steps_Behaviour.1/"
                "@internalFailureOccurrenceDescriptions__InternalAction.0"
            )
        elif case.kind == "fallback":
            for behaviour_index in range(2):
                references.append(
                    f"{base}/@steps_Behaviour.1/"
                    "@recoveryActionBehaviours__RecoveryAction."
                    f"{behaviour_index}/@steps_Behaviour.1/"
                    "@internalFailureOccurrenceDescriptions__InternalAction.0"
                )
        elif case.kind == "conditional":
            references.append(
                f"{base}/@steps_Behaviour.1/@branches_Branch.0/"
                "@branchBehaviour_BranchTransition/@steps_Behaviour.1/"
                "@internalFailureOccurrenceDescriptions__InternalAction.0"
            )
        else:
            raise AssertionError(case.kind)
    return tuple(references)


def _software_repository(model: PalladioControlModel) -> str:
    seffs = []
    signatures = []
    for case in model.cases:
        body = textwrap.indent(textwrap.dedent(_software_action(case)).strip(), "      ")
        seffs.append(
            f"""    <serviceEffectSpecifications__BasicComponent xsi:type="seff:ResourceDemandingSEFF" id="_seff_{case.id}" describedService__SEFF="_sig_{case.id}">\n{body}\n    </serviceEffectSpecifications__BasicComponent>"""
        )
        signatures.append(
            f'    <signatures__OperationInterface id="_sig_{case.id}" entityName="{case.id}"/>'
        )
    failure_reverse_references = " ".join(
        _software_failure_reverse_references(model)
    )
    return _xml(
        f"""
        <?xml version="1.0" encoding="UTF-8"?>
        <repository:Repository xmi:version="2.0" xmlns:xmi="http://www.omg.org/XMI" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:reliability="http://palladiosimulator.org/PalladioComponentModel/Reliability/5.2" xmlns:repository="http://palladiosimulator.org/PalladioComponentModel/Repository/5.2" xmlns:seff="http://palladiosimulator.org/PalladioComponentModel/SEFF/5.2" xmlns:seff_reliability="http://palladiosimulator.org/PalladioComponentModel/SEFF/SEFF_Reliability/5.2" id="_sw_repository" entityName="M9BSoftwareSemantics">
          <components__Repository xsi:type="repository:BasicComponent" id="_sw_component" entityName="software-controls">
            <providedRoles_InterfaceProvidingEntity xsi:type="repository:OperationProvidedRole" id="_sw_provided" entityName="software-controls" providedInterface__OperationProvidedRole="_sw_interface"/>
        {chr(10).join(seffs)}
          </components__Repository>
          <interfaces__Repository xsi:type="repository:OperationInterface" id="_sw_interface" entityName="software-controls">
        {chr(10).join(signatures)}
          </interfaces__Repository>
          <failureTypes__Repository xsi:type="reliability:SoftwareInducedFailureType" id="_sw_failure" entityName="controlled-software-failure" internalFailureOccurrenceDescriptions__SoftwareInducedFailureType="{failure_reverse_references}"/>
        </repository:Repository>
        """
    )


def _single_component_system(
    repository_component: str, repository_interface: str, repository_role: str
) -> str:
    return _xml(
        f"""
        <?xml version="1.0" encoding="UTF-8"?>
        <system:System xmi:version="2.0" xmlns:xmi="http://www.omg.org/XMI" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:composition="http://palladiosimulator.org/PalladioComponentModel/Core/Composition/5.2" xmlns:repository="http://palladiosimulator.org/PalladioComponentModel/Repository/5.2" xmlns:system="http://palladiosimulator.org/PalladioComponentModel/System/5.2" id="_control_system" entityName="M9BControlSystem">
          <assemblyContexts__ComposedStructure id="_control_context" entityName="control-component">
            <encapsulatedComponent__AssemblyContext xsi:type="repository:BasicComponent" href="default.repository#{repository_component}"/>
          </assemblyContexts__ComposedStructure>
          <connectors__ComposedStructure xsi:type="composition:ProvidedDelegationConnector" id="_control_delegation" entityName="control-delegation" outerProvidedRole_ProvidedDelegationConnector="_control_outer_role" assemblyContext_ProvidedDelegationConnector="_control_context">
            <innerProvidedRole_ProvidedDelegationConnector href="default.repository#{repository_role}"/>
          </connectors__ComposedStructure>
          <providedRoles_InterfaceProvidingEntity xsi:type="repository:OperationProvidedRole" id="_control_outer_role" entityName="control-outer-role">
            <providedInterface__OperationProvidedRole href="default.repository#{repository_interface}"/>
          </providedRoles_InterfaceProvidingEntity>
        </system:System>
        """
    )


def _usage_model(cases: Sequence[PalladioControlCase]) -> str:
    scenarios = []
    for case in cases:
        scenarios.append(
            f"""  <usageScenario_UsageModel id="_usage_{case.id}" entityName="{case.id}">
    <scenarioBehaviour_UsageScenario id="_usage_behaviour_{case.id}" entityName="{case.id}">
      <actions_ScenarioBehaviour xsi:type="usagemodel:Start" id="_usage_start_{case.id}" successor="_usage_call_{case.id}"/>
      <actions_ScenarioBehaviour xsi:type="usagemodel:EntryLevelSystemCall" id="_usage_call_{case.id}" predecessor="_usage_start_{case.id}" successor="_usage_stop_{case.id}">
        <providedRole_EntryLevelSystemCall href="default.system#_control_outer_role"/>
        <operationSignature__EntryLevelSystemCall href="default.repository#_sig_{case.id}"/>
      </actions_ScenarioBehaviour>
      <actions_ScenarioBehaviour xsi:type="usagemodel:Stop" id="_usage_stop_{case.id}" predecessor="_usage_call_{case.id}"/>
    </scenarioBehaviour_UsageScenario>
    <workload_UsageScenario xsi:type="usagemodel:OpenWorkload">
      <interArrivalTime_OpenWorkload specification="1"/>
    </workload_UsageScenario>
  </usageScenario_UsageModel>"""
        )
    return _xml(
        f"""
        <?xml version="1.0" encoding="UTF-8"?>
        <usagemodel:UsageModel xmi:version="2.0" xmlns:xmi="http://www.omg.org/XMI" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:usagemodel="http://palladiosimulator.org/PalladioComponentModel/UsageModel/5.2">
        {chr(10).join(scenarios)}
        </usagemodel:UsageModel>
        """
    )


def _single_container_environment() -> str:
    return _xml(
        """
        <?xml version="1.0" encoding="UTF-8"?>
        <resourceenvironment:ResourceEnvironment xmi:version="2.0" xmlns:xmi="http://www.omg.org/XMI" xmlns:resourceenvironment="http://palladiosimulator.org/PalladioComponentModel/ResourceEnvironment/5.2">
          <resourceContainer_ResourceEnvironment id="_control_container" entityName="control-domain">
            <activeResourceSpecifications_ResourceContainer id="_control_cpu" requiredByContainer="false" MTTF="1" MTTR="0">
              <schedulingPolicy href="pathmap://PCM_MODELS/Palladio.resourcetype#ProcessorSharing"/>
              <activeResourceType_ActiveResourceSpecification href="pathmap://PCM_MODELS/Palladio.resourcetype#_oro4gG3fEdy4YaaT-RYrLQ"/>
              <processingRate_ProcessingResourceSpecification specification="1"/>
            </activeResourceSpecifications_ResourceContainer>
          </resourceContainer_ResourceEnvironment>
        </resourceenvironment:ResourceEnvironment>
        """
    )


def _single_component_allocation() -> str:
    return _xml(
        """
        <?xml version="1.0" encoding="UTF-8"?>
        <allocation:Allocation xmi:version="2.0" xmlns:xmi="http://www.omg.org/XMI" xmlns:allocation="http://palladiosimulator.org/PalladioComponentModel/Allocation/5.2" id="_control_allocation" entityName="M9BControlAllocation">
          <targetResourceEnvironment_Allocation href="default.resourceenvironment#/"/>
          <system_Allocation href="default.system#_control_system"/>
          <allocationContexts_Allocation id="_control_allocation_context" entityName="control-allocation">
            <resourceContainer_AllocationContext href="default.resourceenvironment#_control_container"/>
            <assemblyContext_AllocationContext href="default.system#_control_context"/>
          </allocationContexts_Allocation>
        </allocation:Allocation>
        """
    )


def _software_model_files(model: PalladioControlModel) -> Mapping[str, str]:
    return {
        "default.repository": _software_repository(model),
        "default.system": _single_component_system(
            "_sw_component", "_sw_interface", "_sw_provided"
        ),
        "default.usagemodel": _usage_model(model.cases),
        "default.resourceenvironment": _single_container_environment(),
        "default.allocation": _single_component_allocation(),
    }


def _network_repository(case: PalladioControlCase) -> str:
    return _xml(
        f"""
        <?xml version="1.0" encoding="UTF-8"?>
        <repository:Repository xmi:version="2.0" xmlns:xmi="http://www.omg.org/XMI" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:repository="http://palladiosimulator.org/PalladioComponentModel/Repository/5.2" xmlns:seff="http://palladiosimulator.org/PalladioComponentModel/SEFF/5.2" id="_net_repository" entityName="M9BNetworkControl">
          <components__Repository xsi:type="repository:BasicComponent" id="_net_caller" entityName="network-caller">
            <providedRoles_InterfaceProvidingEntity xsi:type="repository:OperationProvidedRole" id="_net_caller_provided" entityName="network-entry" providedInterface__OperationProvidedRole="_net_entry_interface"/>
            <requiredRoles_InterfaceRequiringEntity xsi:type="repository:OperationRequiredRole" id="_net_caller_required" entityName="network-backend-required" requiredInterface__OperationRequiredRole="_net_backend_interface"/>
            <serviceEffectSpecifications__BasicComponent xsi:type="seff:ResourceDemandingSEFF" id="_net_caller_seff" describedService__SEFF="_sig_{case.id}">
              <steps_Behaviour xsi:type="seff:StartAction" id="_net_caller_start" successor_AbstractAction="_net_call"/>
              <steps_Behaviour xsi:type="seff:ExternalCallAction" id="_net_call" entityName="cross-container-call" predecessor_AbstractAction="_net_caller_start" successor_AbstractAction="_net_caller_stop" calledService_ExternalService="_net_backend_signature" role_ExternalService="_net_caller_required"/>
              <steps_Behaviour xsi:type="seff:StopAction" id="_net_caller_stop" predecessor_AbstractAction="_net_call"/>
            </serviceEffectSpecifications__BasicComponent>
          </components__Repository>
          <components__Repository xsi:type="repository:BasicComponent" id="_net_backend" entityName="network-backend">
            <providedRoles_InterfaceProvidingEntity xsi:type="repository:OperationProvidedRole" id="_net_backend_provided" entityName="network-backend-provided" providedInterface__OperationProvidedRole="_net_backend_interface"/>
            <serviceEffectSpecifications__BasicComponent xsi:type="seff:ResourceDemandingSEFF" id="_net_backend_seff" describedService__SEFF="_net_backend_signature">
              <steps_Behaviour xsi:type="seff:StartAction" id="_net_backend_start" successor_AbstractAction="_net_backend_stop"/>
              <steps_Behaviour xsi:type="seff:StopAction" id="_net_backend_stop" predecessor_AbstractAction="_net_backend_start"/>
            </serviceEffectSpecifications__BasicComponent>
          </components__Repository>
          <interfaces__Repository xsi:type="repository:OperationInterface" id="_net_entry_interface" entityName="network-entry">
            <signatures__OperationInterface id="_sig_{case.id}" entityName="{case.id}"/>
          </interfaces__Repository>
          <interfaces__Repository xsi:type="repository:OperationInterface" id="_net_backend_interface" entityName="network-backend">
            <signatures__OperationInterface id="_net_backend_signature" entityName="backend-call"/>
          </interfaces__Repository>
        </repository:Repository>
        """
    )


def _network_system() -> str:
    return _xml(
        """
        <?xml version="1.0" encoding="UTF-8"?>
        <system:System xmi:version="2.0" xmlns:xmi="http://www.omg.org/XMI" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:composition="http://palladiosimulator.org/PalladioComponentModel/Core/Composition/5.2" xmlns:repository="http://palladiosimulator.org/PalladioComponentModel/Repository/5.2" xmlns:system="http://palladiosimulator.org/PalladioComponentModel/System/5.2" id="_control_system" entityName="M9BNetworkSystem">
          <assemblyContexts__ComposedStructure id="_net_caller_context" entityName="network-caller">
            <encapsulatedComponent__AssemblyContext xsi:type="repository:BasicComponent" href="default.repository#_net_caller"/>
          </assemblyContexts__ComposedStructure>
          <assemblyContexts__ComposedStructure id="_net_backend_context" entityName="network-backend">
            <encapsulatedComponent__AssemblyContext xsi:type="repository:BasicComponent" href="default.repository#_net_backend"/>
          </assemblyContexts__ComposedStructure>
          <connectors__ComposedStructure xsi:type="composition:AssemblyConnector" id="_net_assembly_connector" entityName="caller-to-backend" requiringAssemblyContext_AssemblyConnector="_net_caller_context" providingAssemblyContext_AssemblyConnector="_net_backend_context">
            <providedRole_AssemblyConnector href="default.repository#_net_backend_provided"/>
            <requiredRole_AssemblyConnector href="default.repository#_net_caller_required"/>
          </connectors__ComposedStructure>
          <connectors__ComposedStructure xsi:type="composition:ProvidedDelegationConnector" id="_net_delegation" entityName="network-entry" outerProvidedRole_ProvidedDelegationConnector="_control_outer_role" assemblyContext_ProvidedDelegationConnector="_net_caller_context">
            <innerProvidedRole_ProvidedDelegationConnector href="default.repository#_net_caller_provided"/>
          </connectors__ComposedStructure>
          <providedRoles_InterfaceProvidingEntity xsi:type="repository:OperationProvidedRole" id="_control_outer_role" entityName="network-entry">
            <providedInterface__OperationProvidedRole href="default.repository#_net_entry_interface"/>
          </providedRoles_InterfaceProvidingEntity>
        </system:System>
        """
    )


def _network_environment(link_failure_probability: float) -> str:
    q = _float_text(link_failure_probability)
    return _xml(
        f"""
        <?xml version="1.0" encoding="UTF-8"?>
        <resourceenvironment:ResourceEnvironment xmi:version="2.0" xmlns:xmi="http://www.omg.org/XMI" xmlns:resourceenvironment="http://palladiosimulator.org/PalladioComponentModel/ResourceEnvironment/5.2">
          <linkingResources__ResourceEnvironment id="_net_link" entityName="controlled-link" connectedResourceContainers_LinkingResource="_net_caller_container _net_backend_container">
            <communicationLinkResourceSpecifications_LinkingResource id="_net_link_spec" failureProbability="{q}">
              <communicationLinkResourceType_CommunicationLinkResourceSpecification href="pathmap://PCM_MODELS/Palladio.resourcetype#_o3sScH2AEdyH8uerKnHYug"/>
              <latency_CommunicationLinkResourceSpecification specification="0"/>
              <throughput_CommunicationLinkResourceSpecification specification="1"/>
            </communicationLinkResourceSpecifications_LinkingResource>
          </linkingResources__ResourceEnvironment>
          <resourceContainer_ResourceEnvironment id="_net_caller_container" entityName="network-caller-domain">
            <activeResourceSpecifications_ResourceContainer id="_net_caller_cpu" requiredByContainer="false" MTTF="1" MTTR="0">
              <schedulingPolicy href="pathmap://PCM_MODELS/Palladio.resourcetype#ProcessorSharing"/>
              <activeResourceType_ActiveResourceSpecification href="pathmap://PCM_MODELS/Palladio.resourcetype#_oro4gG3fEdy4YaaT-RYrLQ"/>
              <processingRate_ProcessingResourceSpecification specification="1"/>
            </activeResourceSpecifications_ResourceContainer>
          </resourceContainer_ResourceEnvironment>
          <resourceContainer_ResourceEnvironment id="_net_backend_container" entityName="network-backend-domain">
            <activeResourceSpecifications_ResourceContainer id="_net_backend_cpu" requiredByContainer="false" MTTF="1" MTTR="0">
              <schedulingPolicy href="pathmap://PCM_MODELS/Palladio.resourcetype#ProcessorSharing"/>
              <activeResourceType_ActiveResourceSpecification href="pathmap://PCM_MODELS/Palladio.resourcetype#_oro4gG3fEdy4YaaT-RYrLQ"/>
              <processingRate_ProcessingResourceSpecification specification="1"/>
            </activeResourceSpecifications_ResourceContainer>
          </resourceContainer_ResourceEnvironment>
        </resourceenvironment:ResourceEnvironment>
        """
    )


def _network_allocation() -> str:
    return _xml(
        """
        <?xml version="1.0" encoding="UTF-8"?>
        <allocation:Allocation xmi:version="2.0" xmlns:xmi="http://www.omg.org/XMI" xmlns:allocation="http://palladiosimulator.org/PalladioComponentModel/Allocation/5.2" id="_net_allocation" entityName="M9BNetworkAllocation">
          <targetResourceEnvironment_Allocation href="default.resourceenvironment#/"/>
          <system_Allocation href="default.system#_control_system"/>
          <allocationContexts_Allocation id="_net_caller_allocation" entityName="network-caller-allocation">
            <resourceContainer_AllocationContext href="default.resourceenvironment#_net_caller_container"/>
            <assemblyContext_AllocationContext href="default.system#_net_caller_context"/>
          </allocationContexts_Allocation>
          <allocationContexts_Allocation id="_net_backend_allocation" entityName="network-backend-allocation">
            <resourceContainer_AllocationContext href="default.resourceenvironment#_net_backend_container"/>
            <assemblyContext_AllocationContext href="default.system#_net_backend_context"/>
          </allocationContexts_Allocation>
        </allocation:Allocation>
        """
    )


def _network_model_files(model: PalladioControlModel) -> Mapping[str, str]:
    if len(model.cases) != 1:
        raise ValueError("each network model must contain exactly one case")
    case = model.cases[0]
    return {
        "default.repository": _network_repository(case),
        "default.system": _network_system(),
        "default.usagemodel": _usage_model(model.cases),
        "default.resourceenvironment": _network_environment(
            case.parameters["link_failure_probability"]
        ),
        "default.allocation": _network_allocation(),
    }


def _redundancy_repository(case: PalladioControlCase) -> str:
    return _xml(
        f"""
        <?xml version="1.0" encoding="UTF-8"?>
        <repository:Repository xmi:version="2.0" xmlns:xmi="http://www.omg.org/XMI" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:reliability="http://palladiosimulator.org/PalladioComponentModel/Reliability/5.2" xmlns:repository="http://palladiosimulator.org/PalladioComponentModel/Repository/5.2" xmlns:seff="http://palladiosimulator.org/PalladioComponentModel/SEFF/5.2" xmlns:seff_reliability="http://palladiosimulator.org/PalladioComponentModel/SEFF/SEFF_Reliability/5.2" id="_redundancy_repository" entityName="M9BRedundancyControl">
          <components__Repository xsi:type="repository:BasicComponent" id="_dispatcher_component" entityName="dispatcher">
            <providedRoles_InterfaceProvidingEntity xsi:type="repository:OperationProvidedRole" id="_dispatcher_provided" entityName="dispatcher-entry" providedInterface__OperationProvidedRole="_entry_interface"/>
            <requiredRoles_InterfaceRequiringEntity xsi:type="repository:OperationRequiredRole" id="_path_a_required" entityName="path-a-required" requiredInterface__OperationRequiredRole="_backend_interface"/>
            <requiredRoles_InterfaceRequiringEntity xsi:type="repository:OperationRequiredRole" id="_path_b_required" entityName="path-b-required" requiredInterface__OperationRequiredRole="_backend_interface"/>
            <serviceEffectSpecifications__BasicComponent xsi:type="seff:ResourceDemandingSEFF" id="_dispatcher_seff" describedService__SEFF="_sig_{case.id}">
              <steps_Behaviour xsi:type="seff:StartAction" id="_dispatcher_start" successor_AbstractAction="_dispatcher_recovery"/>
              <steps_Behaviour xsi:type="seff_reliability:RecoveryAction" id="_dispatcher_recovery" entityName="explicit-primary-fallback" predecessor_AbstractAction="_dispatcher_start" successor_AbstractAction="_dispatcher_stop" primaryBehaviour__RecoveryAction="_path_a_behaviour">
                <recoveryActionBehaviours__RecoveryAction id="_path_a_behaviour" entityName="path-a" failureHandlingAlternatives__RecoveryActionBehaviour="_path_b_behaviour">
                  <steps_Behaviour xsi:type="seff:StartAction" id="_path_a_start" successor_AbstractAction="_path_a_call"/>
                  <steps_Behaviour xsi:type="seff:ExternalCallAction" id="_path_a_call" entityName="path-a-call" predecessor_AbstractAction="_path_a_start" successor_AbstractAction="_path_a_stop" calledService_ExternalService="_backend_signature" role_ExternalService="_path_a_required"/>
                  <steps_Behaviour xsi:type="seff:StopAction" id="_path_a_stop" predecessor_AbstractAction="_path_a_call"/>
                </recoveryActionBehaviours__RecoveryAction>
                <recoveryActionBehaviours__RecoveryAction id="_path_b_behaviour" entityName="path-b" failureTypes_FailureHandlingEntity="_cpu_failure">
                  <steps_Behaviour xsi:type="seff:StartAction" id="_path_b_start" successor_AbstractAction="_path_b_call"/>
                  <steps_Behaviour xsi:type="seff:ExternalCallAction" id="_path_b_call" entityName="path-b-call" predecessor_AbstractAction="_path_b_start" successor_AbstractAction="_path_b_stop" calledService_ExternalService="_backend_signature" role_ExternalService="_path_b_required"/>
                  <steps_Behaviour xsi:type="seff:StopAction" id="_path_b_stop" predecessor_AbstractAction="_path_b_call"/>
                </recoveryActionBehaviours__RecoveryAction>
              </steps_Behaviour>
              <steps_Behaviour xsi:type="seff:StopAction" id="_dispatcher_stop" predecessor_AbstractAction="_dispatcher_recovery"/>
            </serviceEffectSpecifications__BasicComponent>
          </components__Repository>
          <components__Repository xsi:type="repository:BasicComponent" id="_path_a_component" entityName="path-a">
            <providedRoles_InterfaceProvidingEntity xsi:type="repository:OperationProvidedRole" id="_path_a_provided" entityName="path-a-provided" providedInterface__OperationProvidedRole="_backend_interface"/>
            <serviceEffectSpecifications__BasicComponent xsi:type="seff:ResourceDemandingSEFF" id="_path_a_seff" describedService__SEFF="_backend_signature">
              <steps_Behaviour xsi:type="seff:StartAction" id="_path_a_backend_start" successor_AbstractAction="_path_a_backend_stop"/>
              <steps_Behaviour xsi:type="seff:StopAction" id="_path_a_backend_stop" predecessor_AbstractAction="_path_a_backend_start"/>
            </serviceEffectSpecifications__BasicComponent>
          </components__Repository>
          <components__Repository xsi:type="repository:BasicComponent" id="_path_b_component" entityName="path-b">
            <providedRoles_InterfaceProvidingEntity xsi:type="repository:OperationProvidedRole" id="_path_b_provided" entityName="path-b-provided" providedInterface__OperationProvidedRole="_backend_interface"/>
            <serviceEffectSpecifications__BasicComponent xsi:type="seff:ResourceDemandingSEFF" id="_path_b_seff" describedService__SEFF="_backend_signature">
              <steps_Behaviour xsi:type="seff:StartAction" id="_path_b_backend_start" successor_AbstractAction="_path_b_backend_stop"/>
              <steps_Behaviour xsi:type="seff:StopAction" id="_path_b_backend_stop" predecessor_AbstractAction="_path_b_backend_start"/>
            </serviceEffectSpecifications__BasicComponent>
          </components__Repository>
          <interfaces__Repository xsi:type="repository:OperationInterface" id="_entry_interface" entityName="dispatcher-entry">
            <signatures__OperationInterface id="_sig_{case.id}" entityName="{case.id}"/>
          </interfaces__Repository>
          <interfaces__Repository xsi:type="repository:OperationInterface" id="_backend_interface" entityName="backend">
            <signatures__OperationInterface id="_backend_signature" entityName="backend-call"/>
          </interfaces__Repository>
          <failureTypes__Repository xsi:type="reliability:HardwareInducedFailureType" id="_cpu_failure" entityName="controlled-cpu-unavailability">
            <processingResourceType__HardwareInducedFailureType href="pathmap://PCM_MODELS/Palladio.resourcetype#_oro4gG3fEdy4YaaT-RYrLQ"/>
          </failureTypes__Repository>
        </repository:Repository>
        """
    )


def _redundancy_system() -> str:
    return _xml(
        """
        <?xml version="1.0" encoding="UTF-8"?>
        <system:System xmi:version="2.0" xmlns:xmi="http://www.omg.org/XMI" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:composition="http://palladiosimulator.org/PalladioComponentModel/Core/Composition/5.2" xmlns:repository="http://palladiosimulator.org/PalladioComponentModel/Repository/5.2" xmlns:system="http://palladiosimulator.org/PalladioComponentModel/System/5.2" id="_control_system" entityName="M9BRedundancySystem">
          <assemblyContexts__ComposedStructure id="_dispatcher_context" entityName="dispatcher">
            <encapsulatedComponent__AssemblyContext xsi:type="repository:BasicComponent" href="default.repository#_dispatcher_component"/>
          </assemblyContexts__ComposedStructure>
          <assemblyContexts__ComposedStructure id="_path_a_context" entityName="path-a">
            <encapsulatedComponent__AssemblyContext xsi:type="repository:BasicComponent" href="default.repository#_path_a_component"/>
          </assemblyContexts__ComposedStructure>
          <assemblyContexts__ComposedStructure id="_path_b_context" entityName="path-b">
            <encapsulatedComponent__AssemblyContext xsi:type="repository:BasicComponent" href="default.repository#_path_b_component"/>
          </assemblyContexts__ComposedStructure>
          <connectors__ComposedStructure xsi:type="composition:AssemblyConnector" id="_path_a_connector" entityName="dispatcher-to-path-a" requiringAssemblyContext_AssemblyConnector="_dispatcher_context" providingAssemblyContext_AssemblyConnector="_path_a_context">
            <providedRole_AssemblyConnector href="default.repository#_path_a_provided"/>
            <requiredRole_AssemblyConnector href="default.repository#_path_a_required"/>
          </connectors__ComposedStructure>
          <connectors__ComposedStructure xsi:type="composition:AssemblyConnector" id="_path_b_connector" entityName="dispatcher-to-path-b" requiringAssemblyContext_AssemblyConnector="_dispatcher_context" providingAssemblyContext_AssemblyConnector="_path_b_context">
            <providedRole_AssemblyConnector href="default.repository#_path_b_provided"/>
            <requiredRole_AssemblyConnector href="default.repository#_path_b_required"/>
          </connectors__ComposedStructure>
          <connectors__ComposedStructure xsi:type="composition:ProvidedDelegationConnector" id="_dispatcher_delegation" entityName="dispatcher-entry" outerProvidedRole_ProvidedDelegationConnector="_control_outer_role" assemblyContext_ProvidedDelegationConnector="_dispatcher_context">
            <innerProvidedRole_ProvidedDelegationConnector href="default.repository#_dispatcher_provided"/>
          </connectors__ComposedStructure>
          <providedRoles_InterfaceProvidingEntity xsi:type="repository:OperationProvidedRole" id="_control_outer_role" entityName="dispatcher-entry">
            <providedInterface__OperationProvidedRole href="default.repository#_entry_interface"/>
          </providedRoles_InterfaceProvidingEntity>
        </system:System>
        """
    )


def _redundancy_environment(parameters: Mapping[str, float]) -> str:
    values = {key: _float_text(value) for key, value in parameters.items()}
    return _xml(
        f"""
        <?xml version="1.0" encoding="UTF-8"?>
        <resourceenvironment:ResourceEnvironment xmi:version="2.0" xmlns:xmi="http://www.omg.org/XMI" xmlns:resourceenvironment="http://palladiosimulator.org/PalladioComponentModel/ResourceEnvironment/5.2">
          <linkingResources__ResourceEnvironment id="_redundancy_link" entityName="perfect-control-link" connectedResourceContainers_LinkingResource="_dispatcher_container _path_a_container _path_b_container">
            <communicationLinkResourceSpecifications_LinkingResource id="_redundancy_link_spec" failureProbability="0">
              <communicationLinkResourceType_CommunicationLinkResourceSpecification href="pathmap://PCM_MODELS/Palladio.resourcetype#_o3sScH2AEdyH8uerKnHYug"/>
              <latency_CommunicationLinkResourceSpecification specification="0"/>
              <throughput_CommunicationLinkResourceSpecification specification="1"/>
            </communicationLinkResourceSpecifications_LinkingResource>
          </linkingResources__ResourceEnvironment>
          <resourceContainer_ResourceEnvironment id="_dispatcher_container" entityName="dispatcher-domain">
            <activeResourceSpecifications_ResourceContainer id="_dispatcher_cpu" requiredByContainer="true" MTTF="{values['common_mttf']}" MTTR="{values['common_mttr']}">
              <schedulingPolicy href="pathmap://PCM_MODELS/Palladio.resourcetype#ProcessorSharing"/>
              <activeResourceType_ActiveResourceSpecification href="pathmap://PCM_MODELS/Palladio.resourcetype#_oro4gG3fEdy4YaaT-RYrLQ"/>
              <processingRate_ProcessingResourceSpecification specification="1"/>
            </activeResourceSpecifications_ResourceContainer>
          </resourceContainer_ResourceEnvironment>
          <resourceContainer_ResourceEnvironment id="_path_a_container" entityName="path-a-domain">
            <activeResourceSpecifications_ResourceContainer id="_path_a_cpu" requiredByContainer="true" MTTF="{values['path_a_mttf']}" MTTR="{values['path_a_mttr']}">
              <schedulingPolicy href="pathmap://PCM_MODELS/Palladio.resourcetype#ProcessorSharing"/>
              <activeResourceType_ActiveResourceSpecification href="pathmap://PCM_MODELS/Palladio.resourcetype#_oro4gG3fEdy4YaaT-RYrLQ"/>
              <processingRate_ProcessingResourceSpecification specification="1"/>
            </activeResourceSpecifications_ResourceContainer>
          </resourceContainer_ResourceEnvironment>
          <resourceContainer_ResourceEnvironment id="_path_b_container" entityName="path-b-domain">
            <activeResourceSpecifications_ResourceContainer id="_path_b_cpu" requiredByContainer="true" MTTF="{values['path_b_mttf']}" MTTR="{values['path_b_mttr']}">
              <schedulingPolicy href="pathmap://PCM_MODELS/Palladio.resourcetype#ProcessorSharing"/>
              <activeResourceType_ActiveResourceSpecification href="pathmap://PCM_MODELS/Palladio.resourcetype#_oro4gG3fEdy4YaaT-RYrLQ"/>
              <processingRate_ProcessingResourceSpecification specification="1"/>
            </activeResourceSpecifications_ResourceContainer>
          </resourceContainer_ResourceEnvironment>
        </resourceenvironment:ResourceEnvironment>
        """
    )


def _redundancy_allocation() -> str:
    return _xml(
        """
        <?xml version="1.0" encoding="UTF-8"?>
        <allocation:Allocation xmi:version="2.0" xmlns:xmi="http://www.omg.org/XMI" xmlns:allocation="http://palladiosimulator.org/PalladioComponentModel/Allocation/5.2" id="_redundancy_allocation" entityName="M9BRedundancyAllocation">
          <targetResourceEnvironment_Allocation href="default.resourceenvironment#/"/>
          <system_Allocation href="default.system#_control_system"/>
          <allocationContexts_Allocation id="_dispatcher_allocation" entityName="dispatcher-allocation">
            <resourceContainer_AllocationContext href="default.resourceenvironment#_dispatcher_container"/>
            <assemblyContext_AllocationContext href="default.system#_dispatcher_context"/>
          </allocationContexts_Allocation>
          <allocationContexts_Allocation id="_path_a_allocation" entityName="path-a-allocation">
            <resourceContainer_AllocationContext href="default.resourceenvironment#_path_a_container"/>
            <assemblyContext_AllocationContext href="default.system#_path_a_context"/>
          </allocationContexts_Allocation>
          <allocationContexts_Allocation id="_path_b_allocation" entityName="path-b-allocation">
            <resourceContainer_AllocationContext href="default.resourceenvironment#_path_b_container"/>
            <assemblyContext_AllocationContext href="default.system#_path_b_context"/>
          </allocationContexts_Allocation>
        </allocation:Allocation>
        """
    )


def _redundancy_model_files(model: PalladioControlModel) -> Mapping[str, str]:
    if len(model.cases) != 1:
        raise ValueError("each redundancy model must contain exactly one case")
    case = model.cases[0]
    return {
        "default.repository": _redundancy_repository(case),
        "default.system": _redundancy_system(),
        "default.usagemodel": _usage_model(model.cases),
        "default.resourceenvironment": _redundancy_environment(case.parameters),
        "default.allocation": _redundancy_allocation(),
    }


def _model_files(model: PalladioControlModel) -> Mapping[str, str]:
    if model.kind == "software_suite":
        return _software_model_files(model)
    if model.kind == "network":
        return _network_model_files(model)
    if model.kind == "redundancy":
        return _redundancy_model_files(model)
    raise AssertionError(model.kind)


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _file_record(path: Path, root: Path) -> dict[str, object]:
    payload = path.read_bytes()
    return {
        "path": path.relative_to(root).as_posix(),
        "bytes": len(payload),
        "sha256": _sha256_bytes(payload),
    }


def _write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def generate_palladio_control_models(
    config_path: Path, output_root: Path, manifest_path: Path
) -> dict[str, object]:
    config = load_palladio_controls_config(config_path)
    if output_root.exists():
        raise ValueError(f"control model output already exists: {output_root}")
    output_root.mkdir(parents=True)
    model_records: list[dict[str, object]] = []
    for model in config.models:
        model_root = output_root / model.id
        model_root.mkdir()
        for name, content in _model_files(model).items():
            (model_root / name).write_text(content, encoding="utf-8", newline="\n")
        files = [
            _file_record(model_root / f"default.{suffix}", output_root)
            for suffix in _MODEL_SUFFIXES
        ]
        model_records.append(
            {
                "id": model.id,
                "kind": model.kind,
                "expected_physical_states": model.expected_physical_states,
                "cases": [case.id for case in model.cases],
                "files": files,
            }
        )
    manifest: dict[str, object] = {
        "schema_version": 1,
        "status": "generated",
        "experiment_id": config.id,
        "config_sha256": _sha256_bytes(config_path.read_bytes()),
        "model_count": len(config.models),
        "case_count": len(config.cases),
        "models": model_records,
    }
    _write_json(manifest_path, manifest)
    return manifest


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _children(element: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in element if _local_name(child.tag) == name]


def _descendants(element: ET.Element, name: str) -> list[ET.Element]:
    return [item for item in element.iter() if _local_name(item.tag) == name]


def _xsi_type(element: ET.Element) -> str:
    return element.attrib.get(_XSI_TYPE, "").split(":")[-1]


def _single(items: Sequence[ET.Element], label: str) -> ET.Element:
    if len(items) != 1:
        raise ValueError(f"{label} must contain exactly one item, found {len(items)}")
    return items[0]


def _fragment(reference: str, label: str) -> str:
    if "#" in reference:
        fragment = reference.rsplit("#", 1)[1]
    else:
        fragment = reference
    if not fragment:
        raise ValueError(f"{label} has no reference fragment")
    return fragment


def _reference_fragment(element: ET.Element, label: str) -> str:
    reference = element.attrib.get("href")
    if not reference:
        raise ValueError(f"{label} is missing href")
    return _fragment(reference, label)


def _element_id(element: ET.Element, label: str) -> str:
    identifier = element.attrib.get("id")
    if not identifier:
        raise ValueError(f"{label} is missing id")
    return identifier


def _float_attribute(element: ET.Element, name: str, label: str) -> float:
    value = element.attrib.get(name)
    if value is None:
        raise ValueError(f"{label} is missing {name}")
    try:
        result = float(value)
    except ValueError as error:
        raise ValueError(f"{label}.{name} is not numeric") from error
    if not math.isfinite(result):
        raise ValueError(f"{label}.{name} must be finite")
    return result


def _assert_close(left: float, right: float, tolerance: float, label: str) -> None:
    if not math.isclose(left, right, rel_tol=0.0, abs_tol=tolerance):
        raise ValueError(f"{label}: {left} != {right}")


def _model_trees(model_root: Path) -> Mapping[str, ET.Element]:
    trees: dict[str, ET.Element] = {}
    for suffix in _MODEL_SUFFIXES:
        path = model_root / f"default.{suffix}"
        if not path.is_file():
            raise ValueError(f"missing PCM model file {path}")
        try:
            trees[suffix] = ET.parse(path).getroot()
        except ET.ParseError as error:
            raise ValueError(f"invalid XML in {path}: {error}") from error
    expected_names = {f"default.{suffix}" for suffix in _MODEL_SUFFIXES}
    actual_names = {path.name for path in model_root.iterdir() if path.is_file()}
    if actual_names != expected_names:
        raise ValueError(
            f"{model_root.name} model files differ: "
            f"missing={sorted(expected_names - actual_names)}, "
            f"extra={sorted(actual_names - expected_names)}"
        )
    for suffix, root in trees.items():
        namespaces = " ".join(root.attrib.values()) + root.tag
        if "PalladioComponentModel" not in namespaces and suffix != "allocation":
            raise ValueError(f"{model_root.name}/{suffix} is not a PCM 5.2 model")
    return trees


def _signature_and_seff_maps(
    repository: ET.Element,
) -> tuple[dict[str, str], dict[str, list[ET.Element]]]:
    signatures: dict[str, str] = {}
    for signature in _descendants(repository, "signatures__OperationInterface"):
        identifier = _element_id(signature, "operation signature")
        name = signature.attrib.get("entityName")
        if not name or identifier in signatures:
            raise ValueError("operation signature names and ids must be unique")
        signatures[identifier] = name
    seffs: dict[str, list[ET.Element]] = {}
    for seff in _descendants(
        repository, "serviceEffectSpecifications__BasicComponent"
    ):
        signature_id = seff.attrib.get("describedService__SEFF")
        if not signature_id:
            raise ValueError("each SEFF must reference an operation signature")
        seffs.setdefault(signature_id, []).append(seff)
    return signatures, seffs


def _usage_case_signatures(usage: ET.Element) -> dict[str, str]:
    result: dict[str, str] = {}
    for scenario in _children(usage, "usageScenario_UsageModel"):
        case_id = scenario.attrib.get("entityName")
        if not case_id or case_id in result:
            raise ValueError("usage scenario names must be unique and non-empty")
        call = _single(
            _descendants(scenario, "operationSignature__EntryLevelSystemCall"),
            f"usage scenario {case_id} entry call",
        )
        result[case_id] = _reference_fragment(call, f"usage scenario {case_id}")
    return result


def _assert_case_bindings(
    model: PalladioControlModel,
    repository: ET.Element,
    usage: ET.Element,
) -> dict[str, ET.Element]:
    signatures, seffs = _signature_and_seff_maps(repository)
    usage_signatures = _usage_case_signatures(usage)
    expected_order = [case.id for case in model.cases]
    actual_order = [
        scenario.attrib["entityName"]
        for scenario in _children(usage, "usageScenario_UsageModel")
    ]
    if actual_order != expected_order:
        raise ValueError(
            f"{model.id} usage order {actual_order} != frozen order {expected_order}"
        )
    bound: dict[str, ET.Element] = {}
    for case in model.cases:
        signature_id = usage_signatures.get(case.id)
        if signature_id is None or signatures.get(signature_id) != case.id:
            raise ValueError(f"{case.id} usage call does not bind its named signature")
        matching_seffs = seffs.get(signature_id, [])
        if len(matching_seffs) != 1:
            raise ValueError(
                f"{case.id} must bind exactly one entry SEFF, found {len(matching_seffs)}"
            )
        bound[case.id] = matching_seffs[0]
    return bound


def _failure_probability(action: ET.Element, label: str) -> float:
    descriptions = _descendants(
        action, "internalFailureOccurrenceDescriptions__InternalAction"
    )
    description = _single(descriptions, f"{label} failure description")
    failure_type = description.attrib.get(
        "softwareInducedFailureType__InternalFailureOccurrenceDescription"
    )
    if failure_type != "_sw_failure":
        raise ValueError(f"{label} uses an unexpected software failure type")
    return _float_attribute(description, "failureProbability", label)


def _audit_software_case(
    case: PalladioControlCase, seff: ET.Element
) -> tuple[Mapping[str, float], float, Mapping[str, object]]:
    outer_actions = _children(seff, "steps_Behaviour")
    if case.kind == "single":
        internal = [item for item in outer_actions if _xsi_type(item) == "InternalAction"]
        if len(outer_actions) != 3 or len(internal) != 1:
            raise ValueError(f"{case.id} is not a single-action SEFF")
        probability = _failure_probability(internal[0], case.id)
        parameters = {"failure_probability": probability}
        detail: Mapping[str, object] = {
            "formula": "1 - p",
            "internal_action_count": 1,
        }
    elif case.kind == "fallback":
        recovery = _single(
            [item for item in outer_actions if _xsi_type(item) == "RecoveryAction"],
            f"{case.id} recovery action",
        )
        behaviours = _children(
            recovery, "recoveryActionBehaviours__RecoveryAction"
        )
        if len(outer_actions) != 3 or len(behaviours) != 2:
            raise ValueError(f"{case.id} must have exactly two recovery behaviours")
        by_id = {_element_id(item, case.id): item for item in behaviours}
        primary_id = recovery.attrib.get("primaryBehaviour__RecoveryAction")
        if primary_id not in by_id:
            raise ValueError(f"{case.id} has no valid primary recovery behaviour")
        primary = by_id[primary_id]
        alternatives = primary.attrib.get(
            "failureHandlingAlternatives__RecoveryActionBehaviour", ""
        ).split()
        if len(alternatives) != 1 or alternatives[0] not in by_id:
            raise ValueError(f"{case.id} must have one fallback alternative")
        alternative = by_id[alternatives[0]]
        if alternative.attrib.get("failureTypes_FailureHandlingEntity") != "_sw_failure":
            raise ValueError(f"{case.id} fallback does not handle the primary failure")
        primary_action = _single(
            [
                item
                for item in _children(primary, "steps_Behaviour")
                if _xsi_type(item) == "InternalAction"
            ],
            f"{case.id} primary action",
        )
        alternative_action = _single(
            [
                item
                for item in _children(alternative, "steps_Behaviour")
                if _xsi_type(item) == "InternalAction"
            ],
            f"{case.id} alternative action",
        )
        parameters = {
            "primary_failure_probability": _failure_probability(
                primary_action, f"{case.id} primary"
            ),
            "alternative_failure_probability": _failure_probability(
                alternative_action, f"{case.id} alternative"
            ),
        }
        detail = {
            "formula": "1 - p_primary * p_alternative",
            "explicit_failure_handler": True,
        }
    elif case.kind == "conditional":
        branch = _single(
            [item for item in outer_actions if _xsi_type(item) == "BranchAction"],
            f"{case.id} branch action",
        )
        transitions = _children(branch, "branches_Branch")
        if len(outer_actions) != 3 or len(transitions) != 2:
            raise ValueError(f"{case.id} must have exactly two branch transitions")
        branch_sum = sum(
            _float_attribute(item, "branchProbability", case.id)
            for item in transitions
        )
        _assert_close(branch_sum, 1.0, 1e-15, f"{case.id} branch mass")
        failing = [
            item
            for item in transitions
            if _descendants(item, "internalFailureOccurrenceDescriptions__InternalAction")
        ]
        failing_transition = _single(failing, f"{case.id} failing branch")
        successful = [item for item in transitions if item not in failing]
        successful_transition = _single(successful, f"{case.id} successful branch")
        if _descendants(successful_transition, "internalFailureOccurrenceDescriptions__InternalAction"):
            raise ValueError(f"{case.id} success branch unexpectedly contains a failure")
        internal = _single(
            [
                item
                for item in _descendants(failing_transition, "steps_Behaviour")
                if _xsi_type(item) == "InternalAction"
            ],
            f"{case.id} conditional action",
        )
        parameters = {
            "branch_probability": _float_attribute(
                failing_transition, "branchProbability", case.id
            ),
            "failure_probability": _failure_probability(internal, case.id),
        }
        detail = {
            "formula": "1 - p_branch * p_failure",
            "branch_probability_sum": branch_sum,
        }
    else:
        raise AssertionError(case.kind)
    oracle = expected_control_success(case.kind, parameters)
    return parameters, oracle, detail


def _audit_software_model(
    model: PalladioControlModel, trees: Mapping[str, ET.Element], tolerance: float
) -> list[dict[str, object]]:
    repository = trees["repository"]
    if len(_children(repository, "components__Repository")) != 1:
        raise ValueError("software controls must use one component")
    if any(
        _xsi_type(item) == "ExternalCallAction"
        for item in _descendants(repository, "steps_Behaviour")
    ):
        raise ValueError("software controls must not contain external calls")
    failure_types = _children(repository, "failureTypes__Repository")
    if len(failure_types) != 1 or _xsi_type(failure_types[0]) != "SoftwareInducedFailureType":
        raise ValueError("software controls must define one software failure type")
    descriptions = _descendants(
        repository, "internalFailureOccurrenceDescriptions__InternalAction"
    )
    expected_description_count = sum(
        2 if case.kind == "fallback" else 1 for case in model.cases
    )
    reverse_references = failure_types[0].attrib.get(
        "internalFailureOccurrenceDescriptions__SoftwareInducedFailureType", ""
    ).split()
    if len(descriptions) != expected_description_count:
        raise ValueError("software control failure-description count is incorrect")
    if (
        len(reverse_references) != expected_description_count
        or len(set(reverse_references)) != expected_description_count
        or any(
            not reference.startswith(
                "//@components__Repository.0/"
                "@serviceEffectSpecifications__BasicComponent."
            )
            or not reference.endswith(
                "@internalFailureOccurrenceDescriptions__InternalAction.0"
            )
            for reference in reverse_references
        )
    ):
        raise ValueError("software failure-type reverse references are incomplete")
    bound = _assert_case_bindings(model, repository, trees["usagemodel"])
    records: list[dict[str, object]] = []
    for case in model.cases:
        parameters, oracle, detail = _audit_software_case(case, bound[case.id])
        if set(parameters) != set(case.parameters):
            raise ValueError(f"{case.id} parsed parameter names differ from config")
        for key, value in parameters.items():
            _assert_close(value, case.parameters[key], tolerance, f"{case.id}.{key}")
        _assert_close(
            oracle,
            case.expected_success_probability,
            tolerance,
            f"{case.id} oracle",
        )
        records.append(
            {
                "id": case.id,
                "kind": case.kind,
                "parsed_parameters": parameters,
                "independent_success_oracle": oracle,
                "structure": detail,
            }
        )
    return records


def _assembly_connector_records(system: ET.Element) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for connector in _children(system, "connectors__ComposedStructure"):
        if _xsi_type(connector) != "AssemblyConnector":
            continue
        required = _single(
            _children(connector, "requiredRole_AssemblyConnector"),
            "assembly connector required role",
        )
        provided = _single(
            _children(connector, "providedRole_AssemblyConnector"),
            "assembly connector provided role",
        )
        records.append(
            {
                "required_role": _reference_fragment(required, "required role"),
                "provided_role": _reference_fragment(provided, "provided role"),
                "requiring_context": connector.attrib.get(
                    "requiringAssemblyContext_AssemblyConnector", ""
                ),
                "providing_context": connector.attrib.get(
                    "providingAssemblyContext_AssemblyConnector", ""
                ),
            }
        )
    return records


def _allocation_map(allocation: ET.Element) -> dict[str, str]:
    result: dict[str, str] = {}
    for context in _children(allocation, "allocationContexts_Allocation"):
        assembly = _single(
            _children(context, "assemblyContext_AllocationContext"),
            "allocation assembly context",
        )
        container = _single(
            _children(context, "resourceContainer_AllocationContext"),
            "allocation resource container",
        )
        assembly_id = _reference_fragment(assembly, "allocation assembly")
        if assembly_id in result:
            raise ValueError("an assembly context is allocated more than once")
        result[assembly_id] = _reference_fragment(container, "allocation container")
    return result


def _communication_link(
    resource_environment: ET.Element,
) -> tuple[ET.Element, ET.Element, set[str]]:
    link = _single(
        _children(resource_environment, "linkingResources__ResourceEnvironment"),
        "communication linking resource",
    )
    specification = _single(
        _children(
            link, "communicationLinkResourceSpecifications_LinkingResource"
        ),
        "communication link specification",
    )
    connected = set(
        link.attrib.get("connectedResourceContainers_LinkingResource", "").split()
    )
    if not connected:
        raise ValueError("communication link has no connected containers")
    return link, specification, connected


def _resource_specifications(
    resource_environment: ET.Element,
) -> dict[str, tuple[ET.Element, ET.Element]]:
    result: dict[str, tuple[ET.Element, ET.Element]] = {}
    for container in _children(
        resource_environment, "resourceContainer_ResourceEnvironment"
    ):
        container_id = _element_id(container, "resource container")
        specification = _single(
            _children(
                container, "activeResourceSpecifications_ResourceContainer"
            ),
            f"resource container {container_id} processing resource",
        )
        result[container_id] = (container, specification)
    return result


def _audit_network_model(
    model: PalladioControlModel, trees: Mapping[str, ET.Element], tolerance: float
) -> list[dict[str, object]]:
    case = model.cases[0]
    repository = trees["repository"]
    components = _children(repository, "components__Repository")
    if len(components) != 2:
        raise ValueError(f"{model.id} must contain one caller and one backend")
    bound = _assert_case_bindings(model, repository, trees["usagemodel"])
    call_actions = [
        item
        for item in _descendants(bound[case.id], "steps_Behaviour")
        if _xsi_type(item) == "ExternalCallAction"
    ]
    call = _single(call_actions, f"{model.id} cross-container external call")
    if _descendants(repository, "internalFailureOccurrenceDescriptions__InternalAction"):
        raise ValueError(f"{model.id} must isolate communication failure")
    connectors = _assembly_connector_records(trees["system"])
    connector = _single(connectors, f"{model.id} assembly connector")
    if connector["required_role"] != call.attrib.get("role_ExternalService"):
        raise ValueError(f"{model.id} external call is not bound by its connector")
    if not connector["requiring_context"] or not connector["providing_context"]:
        raise ValueError(f"{model.id} connector has incomplete contexts")
    allocation = _allocation_map(trees["allocation"])
    caller_container = allocation.get(connector["requiring_context"])
    backend_container = allocation.get(connector["providing_context"])
    if not caller_container or not backend_container or caller_container == backend_container:
        raise ValueError(f"{model.id} call must cross two allocated containers")
    _, link_specification, connected = _communication_link(
        trees["resourceenvironment"]
    )
    if connected != {caller_container, backend_container}:
        raise ValueError(f"{model.id} link does not connect the called containers")
    resources = _resource_specifications(trees["resourceenvironment"])
    if set(resources) != connected:
        raise ValueError(f"{model.id} has unexpected resource containers")
    for container_id, (_, specification) in resources.items():
        mttf = _float_attribute(specification, "MTTF", container_id)
        mttr = _float_attribute(specification, "MTTR", container_id)
        if _availability(mttf, mttr) != 1.0:
            raise ValueError(f"{model.id} introduces a hardware failure confound")
    link_failure = _float_attribute(
        link_specification, "failureProbability", model.id
    )
    parameters = {"link_failure_probability": link_failure}
    _assert_close(
        link_failure,
        case.parameters["link_failure_probability"],
        tolerance,
        f"{case.id}.link_failure_probability",
    )
    oracle = expected_control_success(case.kind, parameters)
    _assert_close(
        oracle,
        case.expected_success_probability,
        tolerance,
        f"{case.id} two-transfer oracle",
    )
    return [
        {
            "id": case.id,
            "kind": case.kind,
            "parsed_parameters": parameters,
            "independent_success_oracle": oracle,
            "documented_call_level_success_reference": 1.0 - link_failure,
            "structure": {
                "formula": "(1 - q_link)^2",
                "external_call_count": 1,
                "message_transfer_count_in_solver": 2,
                "caller_container": caller_container,
                "backend_container": backend_container,
            },
        }
    ]


def _audit_redundancy_model(
    model: PalladioControlModel, trees: Mapping[str, ET.Element], tolerance: float
) -> list[dict[str, object]]:
    case = model.cases[0]
    repository = trees["repository"]
    components = _children(repository, "components__Repository")
    if len(components) != 3:
        raise ValueError(f"{model.id} must contain dispatcher and two path components")
    bound = _assert_case_bindings(model, repository, trees["usagemodel"])
    recovery = _single(
        [
            item
            for item in _descendants(bound[case.id], "steps_Behaviour")
            if _xsi_type(item) == "RecoveryAction"
        ],
        f"{model.id} recovery action",
    )
    behaviours = _children(recovery, "recoveryActionBehaviours__RecoveryAction")
    if len(behaviours) != 2:
        raise ValueError(f"{model.id} must contain exactly two explicit paths")
    by_id = {_element_id(item, model.id): item for item in behaviours}
    primary_id = recovery.attrib.get("primaryBehaviour__RecoveryAction")
    if primary_id not in by_id:
        raise ValueError(f"{model.id} has no primary path")
    primary = by_id[primary_id]
    alternative_ids = primary.attrib.get(
        "failureHandlingAlternatives__RecoveryActionBehaviour", ""
    ).split()
    if len(alternative_ids) != 1 or alternative_ids[0] not in by_id:
        raise ValueError(f"{model.id} has no single fallback path")
    alternative = by_id[alternative_ids[0]]
    handled_type = alternative.attrib.get("failureTypes_FailureHandlingEntity")
    if handled_type != "_cpu_failure":
        raise ValueError(f"{model.id} fallback does not handle CPU unavailability")
    hardware_types = [
        item
        for item in _children(repository, "failureTypes__Repository")
        if _xsi_type(item) == "HardwareInducedFailureType"
    ]
    hardware = _single(hardware_types, f"{model.id} hardware failure type")
    if _element_id(hardware, model.id) != handled_type:
        raise ValueError(f"{model.id} handler references the wrong hardware type")
    cpu_type = _single(
        _children(hardware, "processingResourceType__HardwareInducedFailureType"),
        f"{model.id} hardware resource type",
    )
    if not _reference_fragment(cpu_type, model.id).endswith(
        "_oro4gG3fEdy4YaaT-RYrLQ"
    ):
        raise ValueError(f"{model.id} failure handler is not bound to CPU")
    primary_call = _single(
        [
            item
            for item in _children(primary, "steps_Behaviour")
            if _xsi_type(item) == "ExternalCallAction"
        ],
        f"{model.id} primary external call",
    )
    alternative_call = _single(
        [
            item
            for item in _children(alternative, "steps_Behaviour")
            if _xsi_type(item) == "ExternalCallAction"
        ],
        f"{model.id} fallback external call",
    )
    primary_role = primary_call.attrib.get("role_ExternalService", "")
    alternative_role = alternative_call.attrib.get("role_ExternalService", "")
    if not primary_role or not alternative_role or primary_role == alternative_role:
        raise ValueError(f"{model.id} paths must use distinct required roles")
    connectors = _assembly_connector_records(trees["system"])
    if len(connectors) != 2:
        raise ValueError(f"{model.id} must bind exactly two backend paths")
    by_role = {item["required_role"]: item for item in connectors}
    if set(by_role) != {primary_role, alternative_role}:
        raise ValueError(f"{model.id} connectors do not bind both explicit paths")
    primary_connector = by_role[primary_role]
    alternative_connector = by_role[alternative_role]
    if primary_connector["providing_context"] == alternative_connector["providing_context"]:
        raise ValueError(f"{model.id} two paths resolve to one assembly context")
    if primary_connector["requiring_context"] != alternative_connector["requiring_context"]:
        raise ValueError(f"{model.id} paths do not share one dispatcher")
    allocation = _allocation_map(trees["allocation"])
    if len(allocation) != 3 or len(set(allocation.values())) != 3:
        raise ValueError(f"{model.id} must allocate three contexts to three containers")
    dispatcher_container = allocation[primary_connector["requiring_context"]]
    path_a_container = allocation[primary_connector["providing_context"]]
    path_b_container = allocation[alternative_connector["providing_context"]]
    _, link_specification, connected = _communication_link(
        trees["resourceenvironment"]
    )
    if connected != {dispatcher_container, path_a_container, path_b_container}:
        raise ValueError(f"{model.id} perfect link does not connect all paths")
    _assert_close(
        _float_attribute(link_specification, "failureProbability", model.id),
        0.0,
        tolerance,
        f"{model.id} link failure",
    )
    resources = _resource_specifications(trees["resourceenvironment"])
    if set(resources) != connected:
        raise ValueError(f"{model.id} resource environment has unexpected containers")
    expected_names = {
        dispatcher_container: "dispatcher-domain",
        path_a_container: "path-a-domain",
        path_b_container: "path-b-domain",
    }
    extracted: dict[str, float] = {}
    for container_id, prefix in (
        (dispatcher_container, "common"),
        (path_a_container, "path_a"),
        (path_b_container, "path_b"),
    ):
        container, specification = resources[container_id]
        if container.attrib.get("entityName") != expected_names[container_id]:
            raise ValueError(f"{model.id} path allocation names do not match topology")
        if specification.attrib.get("requiredByContainer") != "true":
            raise ValueError(f"{model.id} resource must gate its whole container")
        extracted[f"{prefix}_mttf"] = _float_attribute(
            specification, "MTTF", container_id
        )
        extracted[f"{prefix}_mttr"] = _float_attribute(
            specification, "MTTR", container_id
        )
    if set(extracted) != set(case.parameters):
        raise ValueError(f"{model.id} parsed reliability parameters differ")
    for key, value in extracted.items():
        _assert_close(value, case.parameters[key], tolerance, f"{case.id}.{key}")
    oracle = expected_control_success(case.kind, extracted)
    _assert_close(
        oracle,
        case.expected_success_probability,
        tolerance,
        f"{case.id} redundancy oracle",
    )
    availabilities = {
        prefix: _availability(
            extracted[f"{prefix}_mttf"], extracted[f"{prefix}_mttr"]
        )
        for prefix in ("common", "path_a", "path_b")
    }
    return [
        {
            "id": case.id,
            "kind": case.kind,
            "parsed_parameters": extracted,
            "derived_availabilities": availabilities,
            "independent_success_oracle": oracle,
            "structure": {
                "formula": "A_common * (A_path_a + (1 - A_path_a) * A_path_b)",
                "explicit_path_count": 2,
                "automatic_allocation_replication_used": False,
                "resource_containers": {
                    "common": dispatcher_container,
                    "path_a": path_a_container,
                    "path_b": path_b_container,
                },
            },
        }
    ]


def _audit_model(
    model: PalladioControlModel, model_root: Path, tolerance: float
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    trees = _model_trees(model_root)
    if model.kind == "software_suite":
        cases = _audit_software_model(model, trees, tolerance)
    elif model.kind == "network":
        cases = _audit_network_model(model, trees, tolerance)
    elif model.kind == "redundancy":
        cases = _audit_redundancy_model(model, trees, tolerance)
    else:
        raise AssertionError(model.kind)
    files = [
        _file_record(model_root / f"default.{suffix}", model_root.parent)
        for suffix in _MODEL_SUFFIXES
    ]
    return cases, files


def audit_palladio_control_models(
    config_path: Path,
    models_root: Path,
    pcm_ecore_path: Path,
    bootstrap_config_path: Path,
    output_path: Path,
) -> dict[str, object]:
    config = load_palladio_controls_config(config_path)
    config_sha256 = _sha256_bytes(config_path.read_bytes())
    expected_model_dirs = {model.id for model in config.models}
    actual_model_dirs = {
        path.name for path in models_root.iterdir() if path.is_dir()
    }
    if actual_model_dirs != expected_model_dirs:
        raise ValueError(
            "generated model directories differ from the frozen protocol: "
            f"missing={sorted(expected_model_dirs - actual_model_dirs)}, "
            f"extra={sorted(actual_model_dirs - expected_model_dirs)}"
        )
    bootstrap_payload = bootstrap_config_path.read_bytes()
    if _sha256_bytes(bootstrap_payload) != config.bootstrap_config_sha256:
        raise ValueError("M9A bootstrap config hash differs from the M9B lock")
    if bootstrap_config_path.as_posix().replace("\\", "/").endswith(
        config.bootstrap_config_path
    ) is False:
        raise ValueError("the audited bootstrap config has the wrong path")
    ecore_payload = pcm_ecore_path.read_bytes()
    if len(ecore_payload) != config.pcm_ecore_bytes:
        raise ValueError("PCM metamodel byte count differs from the pin")
    if _sha256_bytes(ecore_payload) != config.pcm_ecore_sha256:
        raise ValueError("PCM metamodel SHA-256 differs from the pin")
    ecore_text = ecore_payload.decode("utf-8")
    if config.pcm_network_documentation_marker not in ecore_text:
        raise ValueError("PCM network-probability documentation marker is absent")

    model_records: list[dict[str, object]] = []
    all_cases: list[dict[str, object]] = []
    for model in config.models:
        cases, files = _audit_model(
            model, models_root / model.id, config.probability_tolerance
        )
        all_cases.extend(cases)
        model_records.append(
            {
                "id": model.id,
                "kind": model.kind,
                "expected_physical_states": model.expected_physical_states,
                "case_ids": [case.id for case in model.cases],
                "files": files,
            }
        )
    if {str(case["id"]) for case in all_cases} != _EXPECTED_CASE_IDS:
        raise ValueError("audited control cases differ from the frozen protocol")
    manifest: dict[str, object] = {
        "schema_version": 1,
        "status": "model_contract_passed",
        "experiment_id": config.id,
        "diagnostic_only": True,
        "comparison_status": "not_started",
        "config_sha256": config_sha256,
        "bootstrap_lock": {
            "path": config.bootstrap_config_path,
            "sha256": config.bootstrap_config_sha256,
        },
        "pcm_metamodel": {
            "repository": config.pcm_repository,
            "release_tag": config.pcm_release_tag,
            "commit": config.pcm_commit,
            "path": config.pcm_ecore_path,
            "bytes": len(ecore_payload),
            "sha256": _sha256_bytes(ecore_payload),
            "network_documentation_marker_present": True,
        },
        "model_count": len(model_records),
        "case_count": len(all_cases),
        "models": model_records,
        "independent_case_audits": all_cases,
        "network_parameter_contract": {
            "metamodel_wording": config.pcm_network_documentation_marker,
            "raw_q_documented_call_success_reference": (
                config.network_documented_call_success_reference
            ),
            "raw_q_two_transfer_solver_oracle": (
                config.network_raw_q_solver_success_oracle
            ),
            "mapped_q_for_documented_call_success": (
                config.network_mapped_link_failure_probability
            ),
            "mapped_solver_success_oracle": (
                config.network_mapped_solver_success_oracle
            ),
            "mapping": config.network_mapping,
            "mapping_assumption": (
                "equal independent failure opportunities for request and response"
            ),
        },
        "m7_interpretation_changed": False,
    }
    _write_json(output_path, manifest)
    return manifest


def _git_head(checkout: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def audit_palladio_capability_source(
    config_path: Path, analyzer_checkout: Path, output_path: Path
) -> dict[str, object]:
    config = load_palladio_controls_config(config_path)
    head = _git_head(analyzer_checkout)
    if head != config.analyzer_commit:
        raise ValueError(f"analyzer checkout {head} != {config.analyzer_commit}")
    visitor = analyzer_checkout / Path(config.analyzer_visitor_path)
    payload = visitor.read_bytes()
    if len(payload) != config.analyzer_visitor_bytes:
        raise ValueError("MarkovSeffVisitor byte count differs from the pin")
    if _sha256_bytes(payload) != config.analyzer_visitor_sha256:
        raise ValueError("MarkovSeffVisitor SHA-256 differs from the pin")
    text = payload.decode("utf-8")
    for marker in config.analyzer_source_markers:
        if marker not in text:
            raise ValueError(f"analyzer source marker absent: {marker}")
    start = text.index("private MarkovChain caseExternalCallActionInsideSystem")
    stop = text.index("private MarkovChain caseExternalCallActionOutsideSystem")
    call_region = text[start:stop]
    transfer_call_count = call_region.count("caseMessageTransfer(commLink)")
    if transfer_call_count != 2:
        raise ValueError(
            f"expected two communication-transfer expansions, found {transfer_call_count}"
        )
    manifest: dict[str, object] = {
        "schema_version": 1,
        "status": "capability_source_audit_passed",
        "experiment_id": config.id,
        "analyzer_repository": config.analyzer_repository,
        "analyzer_commit": head,
        "visitor": {
            "path": config.analyzer_visitor_path,
            "bytes": len(payload),
            "sha256": _sha256_bytes(payload),
        },
        "source_markers": list(config.analyzer_source_markers),
        "internal_call_message_transfer_expansions": transfer_call_count,
        "automatic_allocation_replication": {
            "supported": False,
            "observed_behavior": (
                "when multiple allocation contexts resolve for one assembly context, "
                "the analyzer logs an error and selects one context"
            ),
            "control_encoding": (
                "two explicit components and a typed primary/fallback policy"
            ),
        },
        "interpretation": (
            "source capability boundary only; no comparative accuracy conclusion"
        ),
    }
    _write_json(output_path, manifest)
    return manifest


def _load_json_object(path: Path, label: str) -> Mapping[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return _mapping(json.load(handle), label)


def _verify_model_manifest_inventory(
    model_manifest: Mapping[str, Any], models_root: Path
) -> int:
    raw_models = model_manifest.get("models")
    if not isinstance(raw_models, list):
        raise ValueError("model manifest has no models list")
    verified = 0
    for model_index, raw_model in enumerate(raw_models):
        model = _mapping(raw_model, f"model manifest models[{model_index}]")
        raw_files = model.get("files")
        if not isinstance(raw_files, list) or len(raw_files) != len(_MODEL_SUFFIXES):
            raise ValueError("model manifest file inventory is incomplete")
        for file_index, raw_file in enumerate(raw_files):
            record = _mapping(
                raw_file, f"model manifest models[{model_index}].files[{file_index}]"
            )
            relative = _required_string(record, "path", "model file")
            path = models_root / Path(relative)
            if not path.is_file() or path.resolve().is_relative_to(models_root.resolve()) is False:
                raise ValueError(f"model inventory path is invalid: {relative}")
            payload = path.read_bytes()
            if len(payload) != record.get("bytes"):
                raise ValueError(f"model byte count differs for {relative}")
            if _sha256_bytes(payload) != record.get("sha256"):
                raise ValueError(f"model SHA-256 differs for {relative}")
            verified += 1
    return verified


def _numeric(record: Mapping[str, Any], key: str, label: str) -> float:
    value = record.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label}.{key} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{label}.{key} must be finite")
    return result


def _integer(record: Mapping[str, Any], key: str, label: str) -> int:
    value = record.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label}.{key} must be an integer")
    return value


def _relationship_checks(
    values: Mapping[str, float], tolerance: float
) -> list[dict[str, object]]:
    checks: list[tuple[str, bool, Mapping[str, float]]] = [
        (
            "single_failure_is_monotone",
            values["single_p0"] >= values["single_p20"] >= values["single_p100"],
            {
                "p0": values["single_p0"],
                "p20": values["single_p20"],
                "p100": values["single_p100"],
            },
        ),
        (
            "fallback_quality_is_monotone",
            values["fallback_perfect_alternative"]
            >= values["fallback_nominal"]
            >= values["fallback_failed_alternative"],
            {
                "perfect_alternative": values["fallback_perfect_alternative"],
                "nominal": values["fallback_nominal"],
                "failed_alternative": values["fallback_failed_alternative"],
            },
        ),
        (
            "conditional_exposure_is_monotone",
            values["conditional_b0"]
            >= values["conditional_b25"]
            >= values["conditional_b100"],
            {
                "b0": values["conditional_b0"],
                "b25": values["conditional_b25"],
                "b100": values["conditional_b100"],
            },
        ),
        (
            "raw_link_failure_is_monotone",
            values["network_q0"]
            >= values["network_q10_raw"]
            >= values["network_q100"],
            {
                "q0": values["network_q0"],
                "q10": values["network_q10_raw"],
                "q100": values["network_q100"],
            },
        ),
        (
            "shared_domain_reduces_redundant_success",
            values["shared_domain_redundant_paths"]
            < values["independent_redundant_paths"],
            {
                "independent": values["independent_redundant_paths"],
                "shared": values["shared_domain_redundant_paths"],
            },
        ),
    ]
    ratio = (
        values["shared_domain_redundant_paths"]
        / values["independent_redundant_paths"]
    )
    checks.append(
        (
            "shared_domain_ratio_equals_common_availability",
            math.isclose(ratio, 0.9, rel_tol=0.0, abs_tol=tolerance),
            {"ratio": ratio, "required_common_availability": 0.9},
        )
    )
    checks.append(
        (
            "mapped_link_parameter_recovers_call_success_0_9",
            math.isclose(
                values["network_call_failure_10_mapped"],
                0.9,
                rel_tol=0.0,
                abs_tol=tolerance,
            ),
            {
                "mapped_solver_success": values[
                    "network_call_failure_10_mapped"
                ],
                "call_level_reference": 0.9,
            },
        )
    )
    result: list[dict[str, object]] = []
    for name, passed, observed in checks:
        if not passed:
            raise ValueError(f"Palladio control relationship failed: {name}")
        result.append({"name": name, "passed": True, "observed": observed})
    return result


def audit_palladio_control_results(
    config_path: Path,
    model_manifest_path: Path,
    capability_manifest_path: Path,
    result_path: Path,
    models_root: Path,
    output_path: Path,
) -> dict[str, object]:
    config = load_palladio_controls_config(config_path)
    config_sha256 = _sha256_bytes(config_path.read_bytes())
    model_manifest = _load_json_object(model_manifest_path, "model manifest")
    if model_manifest.get("status") != "model_contract_passed":
        raise ValueError("model contract did not pass")
    if model_manifest.get("config_sha256") != config_sha256:
        raise ValueError("model contract used a different M9B config")
    verified_model_files = _verify_model_manifest_inventory(
        model_manifest, models_root
    )
    capability = _load_json_object(capability_manifest_path, "capability manifest")
    if capability.get("status") != "capability_source_audit_passed":
        raise ValueError("analyzer capability source audit did not pass")
    if capability.get("analyzer_commit") != config.analyzer_commit:
        raise ValueError("capability audit used a different analyzer commit")
    result = _load_json_object(result_path, "raw Palladio result")
    raw_runs = result.get("runs")
    if not isinstance(raw_runs, list):
        raise ValueError("raw Palladio result has no runs list")

    expected_case_to_model = {
        case.id: model
        for model in config.models
        for case in model.cases
    }
    expected_cases = {case.id: case for case in config.cases}
    observed: dict[str, dict[int, dict[str, object]]] = {
        case_id: {} for case_id in expected_cases
    }
    for index, raw_run in enumerate(raw_runs):
        label = f"runs[{index}]"
        run = _mapping(raw_run, label)
        case_id = _required_string(run, "scenario_id", label)
        model_id = _required_string(run, "model_id", label)
        if case_id not in expected_cases:
            raise ValueError(f"unexpected Palladio scenario {case_id}")
        if expected_case_to_model[case_id].id != model_id:
            raise ValueError(f"{case_id} was executed from the wrong model")
        repetition = _integer(run, "repetition", label)
        if repetition < 0 or repetition >= config.repeat_runs:
            raise ValueError(f"{case_id} has invalid repetition {repetition}")
        if repetition in observed[case_id]:
            raise ValueError(f"duplicate {case_id} repetition {repetition}")
        success = _numeric(run, "success_probability", label)
        failure = _numeric(run, "failure_probability_sum", label)
        physical_mass = _numeric(run, "physical_state_probability", label)
        evaluated = _integer(run, "evaluated_physical_states", label)
        total = _integer(run, "total_physical_states", label)
        for probability, probability_label in (
            (success, "success"),
            (failure, "failure"),
            (physical_mass, "physical mass"),
        ):
            if probability < 0.0 or probability > 1.0:
                raise ValueError(f"{case_id} {probability_label} is outside [0,1]")
        _assert_close(
            success + failure,
            1.0,
            config.probability_tolerance,
            f"{case_id} probability mass",
        )
        _assert_close(
            physical_mass,
            1.0,
            config.probability_tolerance,
            f"{case_id} physical-state mass",
        )
        expected_states = expected_case_to_model[case_id].expected_physical_states
        if evaluated != total or total != expected_states:
            raise ValueError(
                f"{case_id} states {evaluated}/{total} != {expected_states}"
            )
        _assert_close(
            success,
            expected_cases[case_id].expected_success_probability,
            config.probability_tolerance,
            f"{case_id} success oracle",
        )
        observed[case_id][repetition] = {
            "success_probability": success,
            "failure_probability_sum": failure,
            "physical_state_probability": physical_mass,
            "evaluated_physical_states": evaluated,
            "total_physical_states": total,
        }
    expected_run_count = len(expected_cases) * config.repeat_runs
    if len(raw_runs) != expected_run_count:
        raise ValueError(
            f"raw result has {len(raw_runs)} runs, expected {expected_run_count}"
        )

    accepted_cases: list[dict[str, object]] = []
    representative_values: dict[str, float] = {}
    for case in config.cases:
        repetitions = observed[case.id]
        if set(repetitions) != set(range(config.repeat_runs)):
            raise ValueError(f"{case.id} does not have all repetitions")
        values = [
            float(repetitions[index]["success_probability"])
            for index in range(config.repeat_runs)
        ]
        for value in values[1:]:
            _assert_close(
                value,
                values[0],
                config.probability_tolerance,
                f"{case.id} repeatability",
            )
        representative_values[case.id] = values[0]
        accepted_cases.append(
            {
                "id": case.id,
                "kind": case.kind,
                "expected_success_probability": case.expected_success_probability,
                "observed_success_probabilities": values,
                "absolute_errors": [
                    abs(value - case.expected_success_probability) for value in values
                ],
                "physical_states": expected_case_to_model[
                    case.id
                ].expected_physical_states,
            }
        )
    relationships = _relationship_checks(
        representative_values, config.probability_tolerance
    )
    raw_network_success = representative_values["network_q10_raw"]
    mapped_network_success = representative_values[
        "network_call_failure_10_mapped"
    ]
    manifest: dict[str, object] = {
        "schema_version": 1,
        "status": "semantic_controls_passed_with_mapping_constraints",
        "experiment_id": config.id,
        "diagnostic_only": True,
        "comparison_status": "not_started",
        "analyzer_commit": config.analyzer_commit,
        "repeat_runs": config.repeat_runs,
        "case_count": len(expected_cases),
        "raw_run_count": len(raw_runs),
        "verified_model_file_count": verified_model_files,
        "cases": accepted_cases,
        "relationship_checks": relationships,
        "network_parameter_interpretation": {
            "metamodel_call_level_reference": (
                config.network_documented_call_success_reference
            ),
            "raw_q_0_1_solver_result": raw_network_success,
            "raw_q_0_1_difference_from_call_level_reference": (
                raw_network_success
                - config.network_documented_call_success_reference
            ),
            "mapped_q": config.network_mapped_link_failure_probability,
            "mapped_solver_result": mapped_network_success,
            "mapping": config.network_mapping,
            "scope_warning": (
                "direction-specific, correlated, or interval-level telemetry requires "
                "a different justified mapping"
            ),
        },
        "replication_interpretation": capability[
            "automatic_allocation_replication"
        ],
        "resource_parameter_interpretation": {
            "control_only": True,
            "stationary_availability_formula": "MTTF / (MTTF + MTTR)",
            "identification_claim": False,
            "warning": (
                "the control ratios do not identify MTTF and MTTR from one "
                "availability observation"
            ),
        },
        "scientific_interpretation": {
            "established": (
                "the pinned PCM encodings reproduce their hand-checkable oracles "
                "under the recorded mapping constraints"
            ),
            "not_established": [
                "comparative predictive gain",
                "correctness of an M7-to-PCM mapping",
                "success or failure of the overall telemetry-driven approach",
            ],
            "m7_interpretation_changed": False,
        },
    }
    _write_json(output_path, manifest)
    return manifest
