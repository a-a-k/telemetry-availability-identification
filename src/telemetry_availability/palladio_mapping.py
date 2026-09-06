from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import textwrap
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_XSI_TYPE = "{http://www.w3.org/2001/XMLSchema-instance}type"
_MODEL_FILES = (
    "default.allocation",
    "default.repository",
    "default.resourceenvironment",
    "default.system",
    "default.usagemodel",
)
_APPLICATION_IDS = {
    "deathstarbench_social_network",
    "opentelemetry_demo",
}
_MAPPING_ELEMENTS = {
    "request_success",
    "operation_path",
    "replication",
    "individual_failure",
    "communication_failure",
    "common_domain",
    "parameters",
    "placement",
}
_EVIDENCE_CLASSES = {
    "observed_m8b",
    "frozen_study_contract",
    "pinned_upstream_source",
    "manual_equivalence_assumption",
    "synthetic_structural_witness",
    "unsupported",
    "unidentified",
}


@dataclass(frozen=True)
class ApplicationMapping:
    id: str
    operation: str
    entry_service: str
    target_service: str
    target_port: int
    proxy_mode: str
    success_rule: str
    timeout_rule: str
    upstream_repository: str
    upstream_commit: str
    source_evidence: tuple[Mapping[str, Any], ...]
    m8b_summary: Mapping[str, Any]
    mapping: tuple[Mapping[str, str], ...]


@dataclass(frozen=True)
class ApplicationModel:
    id: str
    application: str
    operation: str
    placement: str
    expected_physical_states: int
    expected_success_probability: float


@dataclass(frozen=True)
class PalladioMappingConfig:
    path: Path
    raw: Mapping[str, Any]
    id: str
    analyzer_commit: str
    pcm_commit: str
    repeat_runs: int
    probability_tolerance: float
    job_timeout_minutes: int
    applications: tuple[ApplicationMapping, ...]
    models: tuple[ApplicationModel, ...]
    witness: Mapping[str, float]


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return value


def _string(data: Mapping[str, Any], key: str, label: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}.{key} must be a non-empty string")
    return value


def _integer(data: Mapping[str, Any], key: str, label: str) -> int:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label}.{key} must be a positive integer")
    return value


def _probability(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result) or not 0.0 < result < 1.0:
        raise ValueError(f"{label} must be strictly between zero and one")
    return result


def _sha256(value: object, label: str) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise ValueError(f"{label} must be a lowercase SHA-256")
    return value


def _commit(value: object, label: str) -> str:
    if not isinstance(value, str) or not _COMMIT_RE.fullmatch(value):
        raise ValueError(f"{label} must be a full lowercase commit")
    return value


def _load_object(path: Path, label: str) -> Mapping[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return _mapping(json.load(handle), label)


def _float_text(value: float) -> str:
    return format(value, ".17g")


def _xml(value: str) -> str:
    return textwrap.dedent(value).strip() + "\n"


def _xml_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _canonical_model_parameters(
    config: PalladioMappingConfig, placement: str
) -> dict[str, float]:
    witness = config.witness
    residual = float(witness["residual_success"])
    common = float(witness["common_domain_availability"])
    individual_a = float(witness["individual_availability_a"])
    individual_b = float(witness["individual_availability_b"])
    communication_a = float(witness["communication_call_success_a"])
    communication_b = float(witness["communication_call_success_b"])
    if placement == "colocated":
        common_resource = common
        path_a_resource = individual_a
        path_b_resource = individual_b
    elif placement == "split":
        common_resource = 1.0
        path_a_resource = common * individual_a
        path_b_resource = common * individual_b
    else:
        raise ValueError(f"unsupported placement {placement!r}")
    return {
        "residual_success": residual,
        "common_resource_availability": common_resource,
        "path_a_resource_availability": path_a_resource,
        "path_b_resource_availability": path_b_resource,
        "communication_call_success_a": communication_a,
        "communication_call_success_b": communication_b,
        "link_failure_probability_a": 1.0 - math.sqrt(communication_a),
        "link_failure_probability_b": 1.0 - math.sqrt(communication_b),
    }


def expected_application_success(
    config: PalladioMappingConfig, placement: str
) -> float:
    parameters = _canonical_model_parameters(config, placement)
    path_a = (
        parameters["path_a_resource_availability"]
        * parameters["communication_call_success_a"]
    )
    path_b = (
        parameters["path_b_resource_availability"]
        * parameters["communication_call_success_b"]
    )
    route = path_a + (1.0 - path_a) * path_b
    return (
        parameters["residual_success"]
        * parameters["common_resource_availability"]
        * route
    )


def _validate_file_record(record: Mapping[str, Any], label: str) -> None:
    path = _string(record, "path", label)
    if Path(path).is_absolute() or ".." in Path(path).parts:
        raise ValueError(f"{label}.path must be repository-relative")
    _integer(record, "bytes", label)
    _sha256(record.get("sha256"), f"{label}.sha256")
    markers = record.get("markers")
    if (
        not isinstance(markers, list)
        or not markers
        or any(not isinstance(item, str) or not item for item in markers)
    ):
        raise ValueError(f"{label}.markers must be a non-empty string list")


def load_palladio_mapping_config(path: Path) -> PalladioMappingConfig:
    root = _load_object(path, "root")
    if root.get("schema_version") != 1:
        raise ValueError("schema_version must equal 1")
    if root.get("diagnostic_only") is not True:
        raise ValueError("M9C must remain diagnostic_only")
    if root.get("accuracy_comparison_status") != "not_started":
        raise ValueError("M9C cannot start the accuracy comparison")
    _string(root, "selection_rule", "root")

    lock = _mapping(root.get("analyzer_lock"), "analyzer_lock")
    analyzer_commit = _commit(lock.get("commit"), "analyzer_lock.commit")
    pcm_commit = _commit(lock.get("pcm_commit"), "analyzer_lock.pcm_commit")
    if analyzer_commit != "a694e570afb705dc9e0470dc321e77b7219dcea4":
        raise ValueError("M9C analyzer commit must remain aligned with accepted M9A/M9B")
    if pcm_commit != "5fbcc3409e02687881f88ab78b6242d8acd2677c":
        raise ValueError("M9C PCM commit must remain aligned with accepted M9B")
    for prefix in ("m9a", "m9b"):
        _string(lock, f"{prefix}_config_path", "analyzer_lock")
        _sha256(
            lock.get(f"{prefix}_config_sha256"),
            f"analyzer_lock.{prefix}_config_sha256",
        )

    runtime = _mapping(root.get("runtime"), "runtime")
    repeat_runs = _integer(runtime, "repeat_runs", "runtime")
    if repeat_runs < 2:
        raise ValueError("M9C requires at least two technical repetitions")
    tolerance = runtime.get("probability_tolerance")
    if isinstance(tolerance, bool) or not isinstance(tolerance, (int, float)):
        raise ValueError("runtime.probability_tolerance must be numeric")
    probability_tolerance = float(tolerance)
    if not 0.0 < probability_tolerance <= 1e-9:
        raise ValueError("runtime.probability_tolerance must be in (0, 1e-9]")
    if runtime.get("remote_only") is not True:
        raise ValueError("full M9C Palladio execution must remain remote-only")
    if _integer(runtime, "job_timeout_minutes", "runtime") != 360:
        raise ValueError("M9C job_timeout_minutes must equal 360")
    if runtime.get("java_distribution") != "temurin" or runtime.get(
        "java_version"
    ) != 17:
        raise ValueError("M9C runtime must remain Temurin Java 17")

    evidence_classes = root.get("evidence_classes")
    if not isinstance(evidence_classes, list) or set(evidence_classes) != _EVIDENCE_CLASSES:
        raise ValueError("M9C evidence_classes must retain the frozen provenance taxonomy")
    stationary = _mapping(root.get("stationary_encoding"), "stationary_encoding")
    for key in (
        "scope",
        "route_formula_colocated",
        "route_formula_split",
        "operation_formula",
        "communication_mapping",
        "replication_encoding",
        "mttf_mttr_encoding",
    ):
        _string(stationary, key, "stationary_encoding")
    unsupported = stationary.get("unsupported")
    if not isinstance(unsupported, list) or len(unsupported) < 5:
        raise ValueError("stationary_encoding.unsupported must retain all boundaries")

    artifact = _mapping(root.get("accepted_m8b_evidence"), "accepted_m8b_evidence")
    for key in ("run_id", "artifact_id", "artifact_size_bytes", "source_run_id"):
        _integer(artifact, key, "accepted_m8b_evidence")
    if artifact["run_id"] != 34017401101 or artifact["artifact_id"] != 9984348911:
        raise ValueError("M9C must use the accepted M8B artifact")
    digest = _string(artifact, "artifact_digest", "accepted_m8b_evidence")
    if not digest.startswith("sha256:") or not _SHA256_RE.fullmatch(digest[7:]):
        raise ValueError("accepted_m8b_evidence.artifact_digest must be sha256-prefixed")
    _commit(artifact.get("head_commit"), "accepted_m8b_evidence.head_commit")
    artifact_files = _mapping(artifact.get("files"), "accepted_m8b_evidence.files")
    for name in ("topology-branches.csv", "topology-diagnostics.csv", "topology-examples.csv"):
        _sha256(artifact_files.get(name), f"accepted_m8b_evidence.files.{name}")

    study_evidence = root.get("study_evidence")
    if not isinstance(study_evidence, list) or len(study_evidence) < 6:
        raise ValueError("study_evidence must contain the frozen study contracts")
    study_paths: set[str] = set()
    for index, raw_record in enumerate(study_evidence):
        record = _mapping(raw_record, f"study_evidence[{index}]")
        _validate_file_record(record, f"study_evidence[{index}]")
        if record["path"] in study_paths:
            raise ValueError("study_evidence paths must be unique")
        study_paths.add(str(record["path"]))

    witness_raw = _mapping(root.get("structural_witness"), "structural_witness")
    if witness_raw.get("provenance") != "synthetic_structural_witness":
        raise ValueError("M9C witness provenance must remain explicit")
    if witness_raw.get("not_an_m7_estimate") is not True:
        raise ValueError("M9C witness must not be represented as an M7 estimate")
    witness = {
        key: _probability(witness_raw.get(key), f"structural_witness.{key}")
        for key in (
            "residual_success",
            "common_domain_availability",
            "individual_availability_a",
            "individual_availability_b",
            "communication_call_success_a",
            "communication_call_success_b",
        )
    }

    raw_applications = root.get("applications")
    if not isinstance(raw_applications, list) or len(raw_applications) != 2:
        raise ValueError("M9C requires exactly two application mappings")
    applications: list[ApplicationMapping] = []
    for index, raw_application in enumerate(raw_applications):
        item = _mapping(raw_application, f"applications[{index}]")
        app_id = _string(item, "id", f"applications[{index}]")
        upstream = _mapping(item.get("upstream"), f"applications[{index}].upstream")
        sources = item.get("source_evidence")
        if not isinstance(sources, list) or len(sources) < 4:
            raise ValueError(f"{app_id} needs at least four pinned source files")
        source_paths: set[str] = set()
        parsed_sources: list[Mapping[str, Any]] = []
        for source_index, raw_source in enumerate(sources):
            source = _mapping(raw_source, f"{app_id}.source_evidence[{source_index}]")
            _validate_file_record(source, f"{app_id}.source_evidence[{source_index}]")
            _commit(source.get("git_blob"), f"{app_id}.source_evidence[{source_index}].git_blob")
            if source["path"] in source_paths:
                raise ValueError(f"{app_id} source paths must be unique")
            source_paths.add(str(source["path"]))
            parsed_sources.append(source)
        raw_mapping = item.get("mapping")
        if not isinstance(raw_mapping, list) or len(raw_mapping) != len(_MAPPING_ELEMENTS):
            raise ValueError(f"{app_id} must map all mandatory elements exactly once")
        mapping_rows: list[Mapping[str, str]] = []
        for row_index, raw_row in enumerate(raw_mapping):
            row = _mapping(raw_row, f"{app_id}.mapping[{row_index}]")
            for key in ("element", "source_statement", "pcm_encoding", "evidence_class", "status"):
                _string(row, key, f"{app_id}.mapping[{row_index}]")
            if row["evidence_class"] not in _EVIDENCE_CLASSES:
                raise ValueError(f"{app_id} mapping uses an unknown evidence class")
            mapping_rows.append({key: str(row[key]) for key in row})
        if {row["element"] for row in mapping_rows} != _MAPPING_ELEMENTS:
            raise ValueError(f"{app_id} mapping element inventory differs")
        applications.append(
            ApplicationMapping(
                id=app_id,
                operation=_string(item, "operation", app_id),
                entry_service=_string(item, "entry_service", app_id),
                target_service=_string(item, "target_service", app_id),
                target_port=_integer(item, "target_port", app_id),
                proxy_mode=_string(item, "proxy_mode", app_id),
                success_rule=_string(item, "success_rule", app_id),
                timeout_rule=_string(item, "timeout_rule", app_id),
                upstream_repository=_string(upstream, "repository", f"{app_id}.upstream"),
                upstream_commit=_commit(upstream.get("commit"), f"{app_id}.upstream.commit"),
                source_evidence=tuple(parsed_sources),
                m8b_summary=_mapping(item.get("m8b_summary"), f"{app_id}.m8b_summary"),
                mapping=tuple(mapping_rows),
            )
        )
    if {item.id for item in applications} != _APPLICATION_IDS:
        raise ValueError("M9C application inventory differs from the frozen selection")

    raw_models = root.get("models")
    if not isinstance(raw_models, list) or len(raw_models) != 4:
        raise ValueError("M9C requires both placements for both application templates")
    application_by_id = {item.id: item for item in applications}
    models: list[ApplicationModel] = []
    model_ids: set[str] = set()
    pairs: set[tuple[str, str]] = set()
    placeholder = PalladioMappingConfig(
        path=path,
        raw=root,
        id=_string(root, "id", "root"),
        analyzer_commit=analyzer_commit,
        pcm_commit=pcm_commit,
        repeat_runs=repeat_runs,
        probability_tolerance=probability_tolerance,
        job_timeout_minutes=360,
        applications=tuple(applications),
        models=(),
        witness=witness,
    )
    for index, raw_model in enumerate(raw_models):
        item = _mapping(raw_model, f"models[{index}]")
        model_id = _string(item, "id", f"models[{index}]")
        application = _string(item, "application", f"models[{index}]")
        operation = _string(item, "operation", f"models[{index}]")
        placement = _string(item, "placement", f"models[{index}]")
        if application not in application_by_id:
            raise ValueError(f"model {model_id} has an unknown application")
        if operation != application_by_id[application].operation:
            raise ValueError(f"model {model_id} operation differs from its application mapping")
        if placement not in {"colocated", "split"}:
            raise ValueError(f"model {model_id} has an unsupported placement")
        if model_id in model_ids or (application, placement) in pairs:
            raise ValueError("M9C model ids and application-placement pairs must be unique")
        model_ids.add(model_id)
        pairs.add((application, placement))
        expected_states = 8 if placement == "colocated" else 4
        if _integer(item, "expected_physical_states", model_id) != expected_states:
            raise ValueError(f"model {model_id} physical-state count differs")
        expected = item.get("expected_success_probability")
        if isinstance(expected, bool) or not isinstance(expected, (int, float)):
            raise ValueError(f"model {model_id} expected probability must be numeric")
        calculated = expected_application_success(placeholder, placement)
        if abs(float(expected) - calculated) > probability_tolerance:
            raise ValueError(f"model {model_id} oracle differs from the frozen formula")
        models.append(
            ApplicationModel(
                id=model_id,
                application=application,
                operation=operation,
                placement=placement,
                expected_physical_states=expected_states,
                expected_success_probability=float(expected),
            )
        )
    if pairs != {(app, placement) for app in _APPLICATION_IDS for placement in ("colocated", "split")}:
        raise ValueError("M9C must instantiate both placements for both applications")
    return PalladioMappingConfig(
        path=path,
        raw=root,
        id=placeholder.id,
        analyzer_commit=analyzer_commit,
        pcm_commit=pcm_commit,
        repeat_runs=repeat_runs,
        probability_tolerance=probability_tolerance,
        job_timeout_minutes=360,
        applications=tuple(applications),
        models=tuple(models),
        witness=witness,
    )


def _application_repository(model: ApplicationModel) -> str:
    name = _xml_escape(f"{model.application}/{model.operation}/{model.placement}")
    scenario = _xml_escape(model.operation)
    return _xml(
        f"""
        <?xml version="1.0" encoding="UTF-8"?>
        <repository:Repository xmi:version="2.0" xmlns:xmi="http://www.omg.org/XMI" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:reliability="http://palladiosimulator.org/PalladioComponentModel/Reliability/5.2" xmlns:repository="http://palladiosimulator.org/PalladioComponentModel/Repository/5.2" xmlns:seff="http://palladiosimulator.org/PalladioComponentModel/SEFF/5.2" xmlns:seff_reliability="http://palladiosimulator.org/PalladioComponentModel/SEFF/SEFF_Reliability/5.2" id="_app_repository" entityName="M9C {name}">
          <components__Repository xsi:type="repository:BasicComponent" id="_dispatcher_component" entityName="operation-boundary-and-router">
            <providedRoles_InterfaceProvidingEntity xsi:type="repository:OperationProvidedRole" id="_dispatcher_provided" entityName="operation-entry" providedInterface__OperationProvidedRole="_entry_interface"/>
            <requiredRoles_InterfaceRequiringEntity xsi:type="repository:OperationRequiredRole" id="_path_a_required" entityName="replica-a-required" requiredInterface__OperationRequiredRole="_backend_interface"/>
            <requiredRoles_InterfaceRequiringEntity xsi:type="repository:OperationRequiredRole" id="_path_b_required" entityName="replica-b-required" requiredInterface__OperationRequiredRole="_backend_interface"/>
            <serviceEffectSpecifications__BasicComponent xsi:type="seff:ResourceDemandingSEFF" id="_dispatcher_seff" describedService__SEFF="_operation_signature">
              <steps_Behaviour xsi:type="seff:StartAction" id="_dispatcher_start" successor_AbstractAction="_residual_action"/>
              <steps_Behaviour xsi:type="seff:InternalAction" id="_residual_action" entityName="collapsed-semantic-residual" predecessor_AbstractAction="_dispatcher_start" successor_AbstractAction="_route_recovery">
                <internalFailureOccurrenceDescriptions__InternalAction id="_residual_failure_occurrence" failureProbability="__RESIDUAL_FAILURE__" softwareInducedFailureType__InternalFailureOccurrenceDescription="_residual_failure_type"/>
              </steps_Behaviour>
              <steps_Behaviour xsi:type="seff_reliability:RecoveryAction" id="_route_recovery" entityName="stationary-two-path-or" predecessor_AbstractAction="_residual_action" successor_AbstractAction="_dispatcher_stop" primaryBehaviour__RecoveryAction="_path_a_behaviour">
                <recoveryActionBehaviours__RecoveryAction id="_path_a_behaviour" entityName="replica-a-path" failureHandlingAlternatives__RecoveryActionBehaviour="_path_b_behaviour">
                  <steps_Behaviour xsi:type="seff:StartAction" id="_path_a_start" successor_AbstractAction="_path_a_call"/>
                  <steps_Behaviour xsi:type="seff:ExternalCallAction" id="_path_a_call" entityName="call-replica-a" predecessor_AbstractAction="_path_a_start" successor_AbstractAction="_path_a_stop" calledService_ExternalService="_backend_signature" role_ExternalService="_path_a_required"/>
                  <steps_Behaviour xsi:type="seff:StopAction" id="_path_a_stop" predecessor_AbstractAction="_path_a_call"/>
                </recoveryActionBehaviours__RecoveryAction>
                <recoveryActionBehaviours__RecoveryAction id="_path_b_behaviour" entityName="replica-b-path" failureTypes_FailureHandlingEntity="_cpu_failure_type _network_failure_type">
                  <steps_Behaviour xsi:type="seff:StartAction" id="_path_b_start" successor_AbstractAction="_path_b_call"/>
                  <steps_Behaviour xsi:type="seff:ExternalCallAction" id="_path_b_call" entityName="call-replica-b" predecessor_AbstractAction="_path_b_start" successor_AbstractAction="_path_b_stop" calledService_ExternalService="_backend_signature" role_ExternalService="_path_b_required"/>
                  <steps_Behaviour xsi:type="seff:StopAction" id="_path_b_stop" predecessor_AbstractAction="_path_b_call"/>
                </recoveryActionBehaviours__RecoveryAction>
              </steps_Behaviour>
              <steps_Behaviour xsi:type="seff:StopAction" id="_dispatcher_stop" predecessor_AbstractAction="_route_recovery"/>
            </serviceEffectSpecifications__BasicComponent>
          </components__Repository>
          <components__Repository xsi:type="repository:BasicComponent" id="_replica_a_component" entityName="explicit-target-replica-a">
            <providedRoles_InterfaceProvidingEntity xsi:type="repository:OperationProvidedRole" id="_replica_a_provided" entityName="replica-a-provided" providedInterface__OperationProvidedRole="_backend_interface"/>
            <serviceEffectSpecifications__BasicComponent xsi:type="seff:ResourceDemandingSEFF" id="_replica_a_seff" describedService__SEFF="_backend_signature">
              <steps_Behaviour xsi:type="seff:StartAction" id="_replica_a_start" successor_AbstractAction="_replica_a_stop"/>
              <steps_Behaviour xsi:type="seff:StopAction" id="_replica_a_stop" predecessor_AbstractAction="_replica_a_start"/>
            </serviceEffectSpecifications__BasicComponent>
          </components__Repository>
          <components__Repository xsi:type="repository:BasicComponent" id="_replica_b_component" entityName="explicit-target-replica-b">
            <providedRoles_InterfaceProvidingEntity xsi:type="repository:OperationProvidedRole" id="_replica_b_provided" entityName="replica-b-provided" providedInterface__OperationProvidedRole="_backend_interface"/>
            <serviceEffectSpecifications__BasicComponent xsi:type="seff:ResourceDemandingSEFF" id="_replica_b_seff" describedService__SEFF="_backend_signature">
              <steps_Behaviour xsi:type="seff:StartAction" id="_replica_b_start" successor_AbstractAction="_replica_b_stop"/>
              <steps_Behaviour xsi:type="seff:StopAction" id="_replica_b_stop" predecessor_AbstractAction="_replica_b_start"/>
            </serviceEffectSpecifications__BasicComponent>
          </components__Repository>
          <interfaces__Repository xsi:type="repository:OperationInterface" id="_entry_interface" entityName="application-operation">
            <signatures__OperationInterface id="_operation_signature" entityName="{scenario}"/>
          </interfaces__Repository>
          <interfaces__Repository xsi:type="repository:OperationInterface" id="_backend_interface" entityName="target-service">
            <signatures__OperationInterface id="_backend_signature" entityName="target-call"/>
          </interfaces__Repository>
          <failureTypes__Repository xsi:type="reliability:SoftwareInducedFailureType" id="_residual_failure_type" entityName="collapsed-semantic-residual-failure" internalFailureOccurrenceDescriptions__SoftwareInducedFailureType="//@components__Repository.0/@serviceEffectSpecifications__BasicComponent.0/@steps_Behaviour.1/@internalFailureOccurrenceDescriptions__InternalAction.0"/>
          <failureTypes__Repository xsi:type="reliability:HardwareInducedFailureType" id="_cpu_failure_type" entityName="target-or-domain-unavailable">
            <processingResourceType__HardwareInducedFailureType href="pathmap://PCM_MODELS/Palladio.resourcetype#_oro4gG3fEdy4YaaT-RYrLQ"/>
          </failureTypes__Repository>
          <failureTypes__Repository xsi:type="reliability:NetworkInducedFailureType" id="_network_failure_type" entityName="target-path-unreachable">
            <communicationLinkResourceType__NetworkInducedFailureType href="pathmap://PCM_MODELS/Palladio.resourcetype#_o3sScH2AEdyH8uerKnHYug"/>
          </failureTypes__Repository>
        </repository:Repository>
        """
    )


def _application_system(model: ApplicationModel) -> str:
    return _xml(
        f"""
        <?xml version="1.0" encoding="UTF-8"?>
        <system:System xmi:version="2.0" xmlns:xmi="http://www.omg.org/XMI" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:composition="http://palladiosimulator.org/PalladioComponentModel/Core/Composition/5.2" xmlns:repository="http://palladiosimulator.org/PalladioComponentModel/Repository/5.2" xmlns:system="http://palladiosimulator.org/PalladioComponentModel/System/5.2" id="_application_system" entityName="M9C {_xml_escape(model.application)}">
          <assemblyContexts__ComposedStructure id="_dispatcher_context" entityName="operation-boundary-and-router">
            <encapsulatedComponent__AssemblyContext xsi:type="repository:BasicComponent" href="default.repository#_dispatcher_component"/>
          </assemblyContexts__ComposedStructure>
          <assemblyContexts__ComposedStructure id="_replica_a_context" entityName="target-replica-a">
            <encapsulatedComponent__AssemblyContext xsi:type="repository:BasicComponent" href="default.repository#_replica_a_component"/>
          </assemblyContexts__ComposedStructure>
          <assemblyContexts__ComposedStructure id="_replica_b_context" entityName="target-replica-b">
            <encapsulatedComponent__AssemblyContext xsi:type="repository:BasicComponent" href="default.repository#_replica_b_component"/>
          </assemblyContexts__ComposedStructure>
          <connectors__ComposedStructure xsi:type="composition:AssemblyConnector" id="_path_a_connector" entityName="router-to-replica-a" requiringAssemblyContext_AssemblyConnector="_dispatcher_context" providingAssemblyContext_AssemblyConnector="_replica_a_context">
            <providedRole_AssemblyConnector href="default.repository#_replica_a_provided"/>
            <requiredRole_AssemblyConnector href="default.repository#_path_a_required"/>
          </connectors__ComposedStructure>
          <connectors__ComposedStructure xsi:type="composition:AssemblyConnector" id="_path_b_connector" entityName="router-to-replica-b" requiringAssemblyContext_AssemblyConnector="_dispatcher_context" providingAssemblyContext_AssemblyConnector="_replica_b_context">
            <providedRole_AssemblyConnector href="default.repository#_replica_b_provided"/>
            <requiredRole_AssemblyConnector href="default.repository#_path_b_required"/>
          </connectors__ComposedStructure>
          <connectors__ComposedStructure xsi:type="composition:ProvidedDelegationConnector" id="_entry_delegation" entityName="application-entry" outerProvidedRole_ProvidedDelegationConnector="_outer_role" assemblyContext_ProvidedDelegationConnector="_dispatcher_context">
            <innerProvidedRole_ProvidedDelegationConnector href="default.repository#_dispatcher_provided"/>
          </connectors__ComposedStructure>
          <providedRoles_InterfaceProvidingEntity xsi:type="repository:OperationProvidedRole" id="_outer_role" entityName="application-operation">
            <providedInterface__OperationProvidedRole href="default.repository#_entry_interface"/>
          </providedRoles_InterfaceProvidingEntity>
        </system:System>
        """
    )


def _resource_specification(identifier: str, availability: float) -> str:
    mttf = _float_text(availability)
    mttr = _float_text(1.0 - availability)
    return f"""
      <activeResourceSpecifications_ResourceContainer id="_{identifier}_cpu" requiredByContainer="true" MTTF="{mttf}" MTTR="{mttr}">
        <schedulingPolicy href="pathmap://PCM_MODELS/Palladio.resourcetype#ProcessorSharing"/>
        <activeResourceType_ActiveResourceSpecification href="pathmap://PCM_MODELS/Palladio.resourcetype#_oro4gG3fEdy4YaaT-RYrLQ"/>
        <processingRate_ProcessingResourceSpecification specification="1"/>
      </activeResourceSpecifications_ResourceContainer>
    """


def _application_environment(parameters: Mapping[str, float]) -> str:
    common = _resource_specification(
        "common", parameters["common_resource_availability"]
    )
    path_a = _resource_specification(
        "path_a", parameters["path_a_resource_availability"]
    )
    path_b = _resource_specification(
        "path_b", parameters["path_b_resource_availability"]
    )
    return _xml(
        f"""
        <?xml version="1.0" encoding="UTF-8"?>
        <resourceenvironment:ResourceEnvironment xmi:version="2.0" xmlns:xmi="http://www.omg.org/XMI" xmlns:resourceenvironment="http://palladiosimulator.org/PalladioComponentModel/ResourceEnvironment/5.2">
          <linkingResources__ResourceEnvironment id="_path_a_link" entityName="target-path-a" connectedResourceContainers_LinkingResource="_dispatcher_container _replica_a_container">
            <communicationLinkResourceSpecifications_LinkingResource id="_path_a_link_spec" failureProbability="{_float_text(parameters['link_failure_probability_a'])}">
              <communicationLinkResourceType_CommunicationLinkResourceSpecification href="pathmap://PCM_MODELS/Palladio.resourcetype#_o3sScH2AEdyH8uerKnHYug"/>
              <latency_CommunicationLinkResourceSpecification specification="0"/>
              <throughput_CommunicationLinkResourceSpecification specification="1"/>
            </communicationLinkResourceSpecifications_LinkingResource>
          </linkingResources__ResourceEnvironment>
          <linkingResources__ResourceEnvironment id="_path_b_link" entityName="target-path-b" connectedResourceContainers_LinkingResource="_dispatcher_container _replica_b_container">
            <communicationLinkResourceSpecifications_LinkingResource id="_path_b_link_spec" failureProbability="{_float_text(parameters['link_failure_probability_b'])}">
              <communicationLinkResourceType_CommunicationLinkResourceSpecification href="pathmap://PCM_MODELS/Palladio.resourcetype#_o3sScH2AEdyH8uerKnHYug"/>
              <latency_CommunicationLinkResourceSpecification specification="0"/>
              <throughput_CommunicationLinkResourceSpecification specification="1"/>
            </communicationLinkResourceSpecifications_LinkingResource>
          </linkingResources__ResourceEnvironment>
          <resourceContainer_ResourceEnvironment id="_dispatcher_container" entityName="shared-operation-domain">
        {textwrap.indent(textwrap.dedent(common).strip(), '    ')}
          </resourceContainer_ResourceEnvironment>
          <resourceContainer_ResourceEnvironment id="_replica_a_container" entityName="explicit-replica-a-domain">
        {textwrap.indent(textwrap.dedent(path_a).strip(), '    ')}
          </resourceContainer_ResourceEnvironment>
          <resourceContainer_ResourceEnvironment id="_replica_b_container" entityName="explicit-replica-b-domain">
        {textwrap.indent(textwrap.dedent(path_b).strip(), '    ')}
          </resourceContainer_ResourceEnvironment>
        </resourceenvironment:ResourceEnvironment>
        """
    )


def _application_allocation() -> str:
    return _xml(
        """
        <?xml version="1.0" encoding="UTF-8"?>
        <allocation:Allocation xmi:version="2.0" xmlns:xmi="http://www.omg.org/XMI" xmlns:allocation="http://palladiosimulator.org/PalladioComponentModel/Allocation/5.2" id="_application_allocation" entityName="M9CApplicationAllocation">
          <targetResourceEnvironment_Allocation href="default.resourceenvironment#/"/>
          <system_Allocation href="default.system#_application_system"/>
          <allocationContexts_Allocation id="_dispatcher_allocation" entityName="operation-boundary-allocation">
            <resourceContainer_AllocationContext href="default.resourceenvironment#_dispatcher_container"/>
            <assemblyContext_AllocationContext href="default.system#_dispatcher_context"/>
          </allocationContexts_Allocation>
          <allocationContexts_Allocation id="_replica_a_allocation" entityName="replica-a-allocation">
            <resourceContainer_AllocationContext href="default.resourceenvironment#_replica_a_container"/>
            <assemblyContext_AllocationContext href="default.system#_replica_a_context"/>
          </allocationContexts_Allocation>
          <allocationContexts_Allocation id="_replica_b_allocation" entityName="replica-b-allocation">
            <resourceContainer_AllocationContext href="default.resourceenvironment#_replica_b_container"/>
            <assemblyContext_AllocationContext href="default.system#_replica_b_context"/>
          </allocationContexts_Allocation>
        </allocation:Allocation>
        """
    )


def _application_usage(model: ApplicationModel) -> str:
    operation = _xml_escape(model.operation)
    return _xml(
        f"""
        <?xml version="1.0" encoding="UTF-8"?>
        <usagemodel:UsageModel xmi:version="2.0" xmlns:xmi="http://www.omg.org/XMI" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:repository="http://palladiosimulator.org/PalladioComponentModel/Repository/5.2" xmlns:usagemodel="http://palladiosimulator.org/PalladioComponentModel/UsageModel/5.2">
          <usageScenario_UsageModel id="_usage_scenario" entityName="{operation}">
            <scenarioBehaviour_UsageScenario id="_scenario_behaviour">
              <actions_ScenarioBehaviour xsi:type="usagemodel:Start" id="_usage_start" successor="_usage_call"/>
              <actions_ScenarioBehaviour xsi:type="usagemodel:EntryLevelSystemCall" id="_usage_call" entityName="{operation}" predecessor="_usage_start" successor="_usage_stop">
                <providedRole_EntryLevelSystemCall href="default.system#_outer_role"/>
                <operationSignature__EntryLevelSystemCall href="default.repository#_operation_signature"/>
              </actions_ScenarioBehaviour>
              <actions_ScenarioBehaviour xsi:type="usagemodel:Stop" id="_usage_stop" predecessor="_usage_call"/>
            </scenarioBehaviour_UsageScenario>
          </usageScenario_UsageModel>
        </usagemodel:UsageModel>
        """
    )


def _model_payloads(
    config: PalladioMappingConfig, model: ApplicationModel
) -> Mapping[str, str]:
    parameters = _canonical_model_parameters(config, model.placement)
    repository = _application_repository(model).replace(
        "__RESIDUAL_FAILURE__", _float_text(1.0 - parameters["residual_success"])
    )
    return {
        "default.repository": repository,
        "default.system": _application_system(model),
        "default.usagemodel": _application_usage(model),
        "default.resourceenvironment": _application_environment(parameters),
        "default.allocation": _application_allocation(),
    }


def generate_palladio_application_models(
    config_path: Path, output_root: Path, manifest_path: Path
) -> Mapping[str, Any]:
    config = load_palladio_mapping_config(config_path)
    output_root.mkdir(parents=True, exist_ok=True)
    expected_directories = {model.id for model in config.models}
    existing = {item.name for item in output_root.iterdir() if item.is_dir()}
    if existing - expected_directories:
        raise ValueError("output model root contains unexpected directories")
    records: list[dict[str, Any]] = []
    for model in config.models:
        model_root = output_root / model.id
        model_root.mkdir(parents=True, exist_ok=True)
        payloads = _model_payloads(config, model)
        for filename, payload in payloads.items():
            path = model_root / filename
            path.write_text(payload, encoding="utf-8")
            records.append(
                {
                    "model_id": model.id,
                    "path": str(path.relative_to(output_root)).replace("\\", "/"),
                    "bytes": path.stat().st_size,
                    "sha256": file_sha256(path),
                }
            )
    manifest: Mapping[str, Any] = {
        "schema_version": 1,
        "kind": "m9c_generated_application_models",
        "status": "generated_not_yet_audited",
        "config_sha256": file_sha256(config_path),
        "model_count": len(config.models),
        "file_count": len(records),
        "files": sorted(records, key=lambda item: (item["model_id"], item["path"])),
    }
    _write_json(manifest_path, manifest)
    return manifest


def _local_name(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _descendants(root: ET.Element, name: str) -> list[ET.Element]:
    return [item for item in root.iter() if _local_name(item) == name]


def _children(root: ET.Element, name: str) -> list[ET.Element]:
    return [item for item in root if _local_name(item) == name]


def _xsi_type(element: ET.Element) -> str:
    return element.attrib.get(_XSI_TYPE, "").rsplit(":", 1)[-1]


def _fragment(element: ET.Element, label: str) -> str:
    reference = element.attrib.get("href", "")
    if "#" not in reference:
        raise ValueError(f"{label} has no model fragment")
    return reference.rsplit("#", 1)[-1]


def _assert_close(left: float, right: float, tolerance: float, label: str) -> None:
    if not math.isclose(left, right, rel_tol=0.0, abs_tol=tolerance):
        raise ValueError(f"{label} differs: {left!r} versus {right!r}")


def _parse_models(model_root: Path) -> Mapping[str, ET.Element]:
    return {
        filename.split(".", 1)[1]: ET.parse(model_root / filename).getroot()
        for filename in _MODEL_FILES
    }


def _resource_availabilities(environment: ET.Element) -> dict[str, float]:
    result: dict[str, float] = {}
    for container in _children(environment, "resourceContainer_ResourceEnvironment"):
        container_id = container.attrib.get("id", "")
        specs = _children(container, "activeResourceSpecifications_ResourceContainer")
        if len(specs) != 1:
            raise ValueError(f"resource container {container_id} must contain one gate")
        spec = specs[0]
        if spec.attrib.get("requiredByContainer") != "true":
            raise ValueError(f"resource container {container_id} is not gated")
        mttf = float(spec.attrib["MTTF"])
        mttr = float(spec.attrib["MTTR"])
        if mttf < 0.0 or mttr < 0.0 or mttf + mttr <= 0.0:
            raise ValueError(f"resource container {container_id} has invalid ratio coordinates")
        result[container_id] = mttf / (mttf + mttr)
    return result


def _audit_one_application_model(
    config: PalladioMappingConfig, model: ApplicationModel, model_root: Path
) -> Mapping[str, Any]:
    trees = _parse_models(model_root)
    repository = trees["repository"]
    components = _children(repository, "components__Repository")
    if len(components) != 3:
        raise ValueError(f"{model.id} must contain one router and two explicit replicas")
    component_names = {item.attrib.get("entityName") for item in components}
    if component_names != {
        "operation-boundary-and-router",
        "explicit-target-replica-a",
        "explicit-target-replica-b",
    }:
        raise ValueError(f"{model.id} component inventory differs")
    scenarios = _children(trees["usagemodel"], "usageScenario_UsageModel")
    if len(scenarios) != 1 or scenarios[0].attrib.get("entityName") != model.operation:
        raise ValueError(f"{model.id} usage scenario does not name the frozen operation")
    calls = [
        item
        for item in _descendants(repository, "steps_Behaviour")
        if _xsi_type(item) == "ExternalCallAction"
    ]
    if len(calls) != 2 or {item.attrib.get("role_ExternalService") for item in calls} != {
        "_path_a_required",
        "_path_b_required",
    }:
        raise ValueError(f"{model.id} must call two distinct required roles")
    internal_actions = [
        item
        for item in _descendants(repository, "steps_Behaviour")
        if _xsi_type(item) == "InternalAction"
    ]
    if len(internal_actions) != 1:
        raise ValueError(f"{model.id} must have one collapsed residual action")
    occurrences = _children(
        internal_actions[0], "internalFailureOccurrenceDescriptions__InternalAction"
    )
    if len(occurrences) != 1:
        raise ValueError(f"{model.id} residual failure occurrence differs")
    residual_success = 1.0 - float(occurrences[0].attrib["failureProbability"])
    recovery = [
        item
        for item in _descendants(repository, "steps_Behaviour")
        if _xsi_type(item) == "RecoveryAction"
    ]
    if len(recovery) != 1:
        raise ValueError(f"{model.id} must contain one route recovery action")
    behaviours = _children(recovery[0], "recoveryActionBehaviours__RecoveryAction")
    if len(behaviours) != 2:
        raise ValueError(f"{model.id} must contain two route behaviours")
    alternative = next(
        (item for item in behaviours if item.attrib.get("id") == "_path_b_behaviour"),
        None,
    )
    if alternative is None or set(
        alternative.attrib.get("failureTypes_FailureHandlingEntity", "").split()
    ) != {"_cpu_failure_type", "_network_failure_type"}:
        raise ValueError(f"{model.id} fallback must handle hardware and network failures")
    failure_types = {
        _xsi_type(item): item.attrib.get("id")
        for item in _children(repository, "failureTypes__Repository")
    }
    if failure_types != {
        "SoftwareInducedFailureType": "_residual_failure_type",
        "HardwareInducedFailureType": "_cpu_failure_type",
        "NetworkInducedFailureType": "_network_failure_type",
    }:
        raise ValueError(f"{model.id} failure-type inventory differs")

    system = trees["system"]
    assembly_connectors = [
        item
        for item in _children(system, "connectors__ComposedStructure")
        if _xsi_type(item) == "AssemblyConnector"
    ]
    if len(assembly_connectors) != 2:
        raise ValueError(f"{model.id} must bind both explicit replicas")
    allocations: dict[str, str] = {}
    for allocation in _children(trees["allocation"], "allocationContexts_Allocation"):
        contexts = _children(allocation, "assemblyContext_AllocationContext")
        containers = _children(allocation, "resourceContainer_AllocationContext")
        if len(contexts) != 1 or len(containers) != 1:
            raise ValueError(f"{model.id} allocation is incomplete")
        allocations[_fragment(contexts[0], model.id)] = _fragment(containers[0], model.id)
    expected_allocations = {
        "_dispatcher_context": "_dispatcher_container",
        "_replica_a_context": "_replica_a_container",
        "_replica_b_context": "_replica_b_container",
    }
    if allocations != expected_allocations:
        raise ValueError(f"{model.id} allocation inventory differs")

    environment = trees["resourceenvironment"]
    availabilities = _resource_availabilities(environment)
    expected_parameters = _canonical_model_parameters(config, model.placement)
    expected_availabilities = {
        "_dispatcher_container": expected_parameters["common_resource_availability"],
        "_replica_a_container": expected_parameters["path_a_resource_availability"],
        "_replica_b_container": expected_parameters["path_b_resource_availability"],
    }
    if set(availabilities) != set(expected_availabilities):
        raise ValueError(f"{model.id} resource-container inventory differs")
    for identifier, expected in expected_availabilities.items():
        _assert_close(
            availabilities[identifier], expected, config.probability_tolerance, identifier
        )
    links = _children(environment, "linkingResources__ResourceEnvironment")
    if len(links) != 2:
        raise ValueError(f"{model.id} must contain one communication link per path")
    link_probabilities: dict[frozenset[str], float] = {}
    for link in links:
        connected = frozenset(
            link.attrib.get("connectedResourceContainers_LinkingResource", "").split()
        )
        specs = _children(
            link, "communicationLinkResourceSpecifications_LinkingResource"
        )
        if len(specs) != 1:
            raise ValueError(f"{model.id} link has no unique specification")
        link_probabilities[connected] = float(specs[0].attrib["failureProbability"])
    expected_links = {
        frozenset(("_dispatcher_container", "_replica_a_container")): expected_parameters[
            "link_failure_probability_a"
        ],
        frozenset(("_dispatcher_container", "_replica_b_container")): expected_parameters[
            "link_failure_probability_b"
        ],
    }
    if set(link_probabilities) != set(expected_links):
        raise ValueError(f"{model.id} link topology differs")
    for connected, expected in expected_links.items():
        _assert_close(
            link_probabilities[connected],
            expected,
            config.probability_tolerance,
            f"{model.id} link {sorted(connected)}",
        )
    _assert_close(
        residual_success,
        expected_parameters["residual_success"],
        config.probability_tolerance,
        f"{model.id} residual",
    )
    oracle = expected_application_success(config, model.placement)
    _assert_close(
        oracle,
        model.expected_success_probability,
        config.probability_tolerance,
        f"{model.id} independent oracle",
    )
    physical_states = 2 ** sum(
        0.0 < value < 1.0 for value in availabilities.values()
    )
    if physical_states != model.expected_physical_states:
        raise ValueError(f"{model.id} physical-state oracle differs")
    return {
        "model_id": model.id,
        "application": model.application,
        "operation": model.operation,
        "placement": model.placement,
        "parameters_parsed_from_xmi": {
            "residual_success": residual_success,
            "resource_availabilities": availabilities,
            "link_failure_probabilities": {
                "+".join(sorted(key)): value
                for key, value in link_probabilities.items()
            },
        },
        "expected_success_probability": oracle,
        "expected_physical_states": physical_states,
        "automatic_allocation_replication_used": False,
        "literal_haproxy_retry_claimed": False,
    }


def _verify_lock(config: PalladioMappingConfig, repository_root: Path) -> None:
    lock = _mapping(config.raw["analyzer_lock"], "analyzer_lock")
    for prefix in ("m9a", "m9b"):
        target = repository_root / str(lock[f"{prefix}_config_path"])
        if file_sha256(target) != lock[f"{prefix}_config_sha256"]:
            raise ValueError(f"{prefix.upper()} configuration lock differs")


def audit_palladio_application_models(
    config_path: Path,
    models_root: Path,
    repository_root: Path,
    manifest_path: Path,
) -> Mapping[str, Any]:
    config = load_palladio_mapping_config(config_path)
    _verify_lock(config, repository_root)
    expected_directories = {item.id for item in config.models}
    actual_directories = {item.name for item in models_root.iterdir() if item.is_dir()}
    if actual_directories != expected_directories:
        raise ValueError("application model directory inventory differs")
    audits: list[Mapping[str, Any]] = []
    files: list[Mapping[str, Any]] = []
    for model in config.models:
        model_root = models_root / model.id
        actual_files = {item.name for item in model_root.iterdir() if item.is_file()}
        if actual_files != set(_MODEL_FILES):
            raise ValueError(f"{model.id} model-file inventory differs")
        audits.append(_audit_one_application_model(config, model, model_root))
        for filename in _MODEL_FILES:
            path = model_root / filename
            files.append(
                {
                    "model_id": model.id,
                    "path": f"{model.id}/{filename}",
                    "bytes": path.stat().st_size,
                    "sha256": file_sha256(path),
                }
            )
    manifest: Mapping[str, Any] = {
        "schema_version": 1,
        "kind": "m9c_application_model_contract",
        "status": "application_model_contract_passed",
        "config_sha256": file_sha256(config_path),
        "model_count": len(audits),
        "scenario_count": len(audits),
        "models": audits,
        "files": sorted(files, key=lambda item: (item["model_id"], item["path"])),
        "scientific_boundary": {
            "accuracy_comparison_started": False,
            "m7_parameters_consumed": False,
            "witness_is_synthetic": True,
        },
    }
    _write_json(manifest_path, manifest)
    return manifest


def _find_m8b_root(input_root: Path) -> tuple[Path, Mapping[str, Any]]:
    candidates: list[tuple[Path, Mapping[str, Any]]] = []
    for path in input_root.rglob("manifest.json"):
        try:
            payload = _load_object(path, "M8B manifest")
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
            continue
        if payload.get("kind") == "m7_posthoc_causal_diagnostics":
            candidates.append((path.parent, payload))
    if len(candidates) != 1:
        raise ValueError("expected exactly one accepted M8B diagnostic root")
    return candidates[0]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _sum_int(rows: Sequence[Mapping[str, str]], key: str) -> int:
    return sum(int(row[key]) for row in rows)


def _audit_m8b_application(
    application: ApplicationMapping,
    diagnostics: Sequence[Mapping[str, str]],
    branches: Sequence[Mapping[str, str]],
    examples: Sequence[Mapping[str, str]],
) -> Mapping[str, Any]:
    rows = [
        row
        for row in diagnostics
        if row["profile"] == application.id
        and row["operation"] == application.operation
        and row["mode"] == "full"
    ]
    normal = [row for row in rows if row["failure_law"] in {"N", "ND"}]
    communication = [row for row in rows if row["failure_law"] in {"NC", "NCD"}]
    summary = application.m8b_summary
    actual = {
        "normal_or_domain_rows": len(normal),
        "normal_or_domain_confirmed": sum(row["status"] == "confirmed" for row in normal),
        "normal_or_domain_trace_support": _sum_int(normal, "trace_support"),
        "normal_or_domain_replica_a_assignments": _sum_int(normal, "replica_a_assignments"),
        "normal_or_domain_replica_b_assignments": _sum_int(normal, "replica_b_assignments"),
        "communication_rows": len(communication),
        "communication_confirmed": sum(row["status"] == "confirmed" for row in communication),
        "communication_ambiguous": sum(row["status"] != "confirmed" for row in communication),
        "communication_trace_support": _sum_int(communication, "trace_support"),
        "communication_replica_a_assignments": _sum_int(communication, "replica_a_assignments"),
        "communication_replica_b_assignments": _sum_int(communication, "replica_b_assignments"),
    }
    for key, value in actual.items():
        if int(summary[key]) != int(value):
            raise ValueError(f"{application.id} M8B summary differs for {key}")
    target_fraction = float(summary["normal_or_domain_target_fraction"])
    if target_fraction != 1.0 or any(float(row["target_trace_fraction"]) != 1.0 for row in normal):
        raise ValueError(f"{application.id} normal/domain target support is not complete")
    selected_branches = [
        row
        for row in branches
        if row["profile"] == application.id and row["operation"] == application.operation
    ]
    branch_actual = {
        "branch_rows": len(selected_branches),
        "successful_requests": _sum_int(selected_branches, "successful_requests"),
        "successful_traces": _sum_int(selected_branches, "successful_traces"),
        "successful_traces_with_target": _sum_int(
            selected_branches, "successful_traces_with_target"
        ),
        "successful_traces_without_target": _sum_int(
            selected_branches, "successful_traces_without_target"
        ),
    }
    for key, value in branch_actual.items():
        if int(summary[key]) != value:
            raise ValueError(f"{application.id} M8B branch summary differs for {key}")
    selected_examples = [
        row
        for row in examples
        if row["profile"] == application.id and row["operation"] == application.operation
    ]
    evidence_classes = {row["evidence_class"] for row in selected_examples}
    replicas = set(
        replica
        for row in selected_examples
        for replica in row["target_replicas"].split(";")
        if replica
    )
    if not {"target_present", "target_absent"}.issubset(evidence_classes):
        raise ValueError(f"{application.id} lacks both M8B target-presence examples")
    if not {"a", "b"}.issubset(replicas):
        raise ValueError(f"{application.id} lacks trace assignments to both replicas")
    return {
        "application": application.id,
        "operation": application.operation,
        **actual,
        **branch_actual,
        "selected_example_count": len(selected_examples),
        "selected_example_evidence_classes": sorted(evidence_classes),
        "selected_example_replicas": sorted(replicas),
    }


def _verify_evidence_file(path: Path, record: Mapping[str, Any], label: str) -> None:
    if not path.is_file():
        raise ValueError(f"{label} is missing: {path}")
    payload = path.read_bytes()
    if len(payload) != int(record["bytes"]):
        raise ValueError(f"{label} byte count differs")
    if hashlib.sha256(payload).hexdigest() != record["sha256"]:
        raise ValueError(f"{label} SHA-256 differs")
    text = payload.decode("utf-8")
    missing = [marker for marker in record["markers"] if marker not in text]
    if missing:
        raise ValueError(f"{label} is missing frozen markers: {missing}")


def _write_mapping_table(config: PalladioMappingConfig, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = (
        "application",
        "operation",
        "element",
        "source_statement",
        "pcm_encoding",
        "evidence_class",
        "status",
    )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for application in config.applications:
            for row in application.mapping:
                writer.writerow(
                    {
                        "application": application.id,
                        "operation": application.operation,
                        **{key: row[key] for key in fields[2:]},
                    }
                )


def audit_palladio_application_evidence(
    config_path: Path,
    m8b_input_root: Path,
    artifact_metadata_path: Path,
    upstream_root: Path,
    repository_root: Path,
    output_directory: Path,
) -> Mapping[str, Any]:
    config = load_palladio_mapping_config(config_path)
    artifact = _mapping(config.raw["accepted_m8b_evidence"], "accepted_m8b_evidence")
    metadata = _load_object(artifact_metadata_path, "artifact metadata")
    for key, expected in (
        ("id", artifact["artifact_id"]),
        ("name", artifact["artifact_name"]),
        ("size_in_bytes", artifact["artifact_size_bytes"]),
        ("digest", artifact["artifact_digest"]),
        ("expires_at", artifact["artifact_expires_at"]),
    ):
        if metadata.get(key) != expected:
            raise ValueError(f"M8B artifact metadata differs for {key}")
    if metadata.get("expired") is not False:
        raise ValueError("accepted M8B artifact is expired")
    workflow_run = _mapping(metadata.get("workflow_run"), "artifact metadata.workflow_run")
    if workflow_run.get("id") != artifact["run_id"] or workflow_run.get(
        "head_sha"
    ) != artifact["head_commit"]:
        raise ValueError("M8B artifact workflow identity differs")

    m8b_root, m8b_manifest = _find_m8b_root(m8b_input_root)
    github = _mapping(
        _mapping(m8b_manifest.get("environment"), "M8B environment").get("github"),
        "M8B github environment",
    )
    if int(github.get("GITHUB_RUN_ID", -1)) != artifact["run_id"]:
        raise ValueError("M8B manifest run differs")
    if github.get("GITHUB_SHA") != artifact["head_commit"]:
        raise ValueError("M8B manifest commit differs")
    if m8b_manifest.get("source_run_ids") != [str(artifact["source_run_id"])]:
        raise ValueError("M8B source-run identity differs")
    manifest_hashes = _mapping(m8b_manifest.get("files"), "M8B manifest.files")
    for filename, expected_hash in _mapping(artifact["files"], "artifact.files").items():
        if filename == "manifest.json":
            continue
        path = m8b_root / filename
        if file_sha256(path) != expected_hash or manifest_hashes.get(filename) != expected_hash:
            raise ValueError(f"accepted M8B file differs: {filename}")

    diagnostics = _read_csv(m8b_root / "topology-diagnostics.csv")
    branches = _read_csv(m8b_root / "topology-branches.csv")
    examples = _read_csv(m8b_root / "topology-examples.csv")
    application_audits = [
        _audit_m8b_application(application, diagnostics, branches, examples)
        for application in config.applications
    ]

    source_files: list[Mapping[str, Any]] = []
    for application in config.applications:
        for record in application.source_evidence:
            path = upstream_root / application.id / str(record["path"])
            _verify_evidence_file(path, record, f"{application.id}/{record['path']}")
            source_files.append(
                {
                    "application": application.id,
                    "repository": application.upstream_repository,
                    "commit": application.upstream_commit,
                    "path": record["path"],
                    "bytes": path.stat().st_size,
                    "git_blob": record["git_blob"],
                    "sha256": file_sha256(path),
                }
            )
    study_files: list[Mapping[str, Any]] = []
    for raw_record in config.raw["study_evidence"]:
        record = _mapping(raw_record, "study evidence")
        path = repository_root / str(record["path"])
        _verify_evidence_file(path, record, str(record["path"]))
        study_files.append(
            {
                "path": record["path"],
                "bytes": path.stat().st_size,
                "sha256": file_sha256(path),
            }
        )
    _verify_lock(config, repository_root)

    mapping_table = output_directory / "mapping-table.csv"
    _write_mapping_table(config, mapping_table)
    manifest: Mapping[str, Any] = {
        "schema_version": 1,
        "kind": "m9c_application_mapping_evidence",
        "status": "application_mapping_evidence_passed",
        "config_sha256": file_sha256(config_path),
        "m8b": {
            "run_id": artifact["run_id"],
            "artifact_id": artifact["artifact_id"],
            "artifact_digest": artifact["artifact_digest"],
            "application_checks": application_audits,
        },
        "upstream_source_files": source_files,
        "study_evidence_files": study_files,
        "mapping_table": {
            "path": mapping_table.name,
            "rows": len(config.applications) * len(_MAPPING_ELEMENTS),
            "sha256": file_sha256(mapping_table),
        },
        "boundary": {
            "accuracy_comparison_started": False,
            "m7_predictions_or_scores_changed": False,
            "missing_target_spans_under_communication_faults_resolved": False,
            "unsupported_mapping_count": len(
                _mapping(config.raw["stationary_encoding"], "stationary")["unsupported"]
            ),
        },
    }
    _write_json(output_directory / "evidence-manifest.json", manifest)
    return manifest


def _verify_model_inventory(
    manifest: Mapping[str, Any], models_root: Path
) -> None:
    records = manifest.get("files")
    if not isinstance(records, list):
        raise ValueError("model manifest has no file inventory")
    expected = {str(record["path"]): record for record in records}
    actual = {
        str(path.relative_to(models_root)).replace("\\", "/"): path
        for path in models_root.rglob("default.*")
        if path.is_file()
    }
    if set(actual) != set(expected):
        raise ValueError("accepted model inventory differs from solver input")
    for relative, path in actual.items():
        record = expected[relative]
        if path.stat().st_size != int(record["bytes"]):
            raise ValueError(f"model byte count differs: {relative}")
        if file_sha256(path) != record["sha256"]:
            raise ValueError(f"model SHA-256 differs: {relative}")


def audit_palladio_application_results(
    config_path: Path,
    evidence_manifest_path: Path,
    model_manifest_path: Path,
    result_path: Path,
    models_root: Path,
    output_path: Path,
) -> Mapping[str, Any]:
    config = load_palladio_mapping_config(config_path)
    evidence = _load_object(evidence_manifest_path, "evidence manifest")
    models = _load_object(model_manifest_path, "model manifest")
    result = _load_object(result_path, "Palladio result")
    if evidence.get("status") != "application_mapping_evidence_passed":
        raise ValueError("M9C evidence was not accepted")
    if models.get("status") != "application_model_contract_passed":
        raise ValueError("M9C model contract was not accepted")
    config_hash = file_sha256(config_path)
    if evidence.get("config_sha256") != config_hash or models.get(
        "config_sha256"
    ) != config_hash:
        raise ValueError("M9C artifact configurations differ")
    _verify_model_inventory(models, models_root)
    raw_runs = result.get("runs")
    if not isinstance(raw_runs, list):
        raise ValueError("Palladio result must contain runs")
    expected_count = len(config.models) * config.repeat_runs
    if len(raw_runs) != expected_count:
        raise ValueError("Palladio application run count differs")
    model_by_id = {item.id: item for item in config.models}
    keys: set[tuple[str, int]] = set()
    first: dict[str, Mapping[str, Any]] = {}
    max_oracle_error = 0.0
    max_mass_residual = 0.0
    max_probability_residual = 0.0
    max_repeat_delta = 0.0
    accepted_rows: list[Mapping[str, Any]] = []
    for index, raw_run in enumerate(raw_runs):
        run = _mapping(raw_run, f"runs[{index}]")
        model_id = str(run.get("model_id", ""))
        if model_id not in model_by_id:
            raise ValueError(f"unknown Palladio application model {model_id!r}")
        model = model_by_id[model_id]
        if run.get("scenario_id") != model.operation:
            raise ValueError(f"{model_id} scenario id differs")
        repetition = int(run.get("repetition", -1))
        key = (model_id, repetition)
        if repetition not in range(config.repeat_runs) or key in keys:
            raise ValueError(f"{model_id} repetition inventory differs")
        keys.add(key)
        success = float(run["success_probability"])
        failure = float(run["failure_probability_sum"])
        physical_mass = float(run["physical_state_probability"])
        evaluated = int(run["evaluated_physical_states"])
        total = int(run["total_physical_states"])
        oracle_error = abs(success - model.expected_success_probability)
        probability_residual = abs(success + failure - 1.0)
        mass_residual = abs(physical_mass - 1.0)
        max_oracle_error = max(max_oracle_error, oracle_error)
        max_probability_residual = max(max_probability_residual, probability_residual)
        max_mass_residual = max(max_mass_residual, mass_residual)
        if oracle_error > config.probability_tolerance:
            raise ValueError(f"{model_id} differs from the predeclared success oracle")
        if probability_residual > config.probability_tolerance:
            raise ValueError(f"{model_id} does not conserve success and failure")
        if mass_residual > config.probability_tolerance:
            raise ValueError(f"{model_id} does not conserve physical-state mass")
        if evaluated != model.expected_physical_states or total != model.expected_physical_states:
            raise ValueError(f"{model_id} does not completely enumerate physical states")
        if repetition == 0:
            first[model_id] = run
        else:
            baseline = first.get(model_id)
            if baseline is None:
                raise ValueError(f"{model_id} repetitions are out of order")
            delta = abs(success - float(baseline["success_probability"]))
            max_repeat_delta = max(max_repeat_delta, delta)
            if delta > config.probability_tolerance:
                raise ValueError(f"{model_id} solver repetitions differ")
        accepted_rows.append(
            {
                "model_id": model_id,
                "application": model.application,
                "operation": model.operation,
                "placement": model.placement,
                "repetition": repetition,
                "success_probability": success,
                "expected_success_probability": model.expected_success_probability,
                "physical_states": total,
            }
        )
    expected_keys = {
        (model.id, repetition)
        for model in config.models
        for repetition in range(config.repeat_runs)
    }
    if keys != expected_keys:
        raise ValueError("Palladio application result key inventory differs")
    manifest: Mapping[str, Any] = {
        "schema_version": 1,
        "kind": "m9c_palladio_application_acceptance",
        "status": "application_mapping_and_models_passed",
        "config_sha256": config_hash,
        "raw_run_count": len(raw_runs),
        "accepted_runs": sorted(
            accepted_rows, key=lambda item: (item["model_id"], item["repetition"])
        ),
        "maximum_errors": {
            "success_oracle": max_oracle_error,
            "success_plus_failure": max_probability_residual,
            "physical_state_mass": max_mass_residual,
            "technical_repeat": max_repeat_delta,
        },
        "scientific_interpretation": {
            "application_mapping_completed": True,
            "accuracy_comparison_started": False,
            "m7_interpretation_changed": False,
            "m7_position": "Published M7 calculations establish no predictive gain and disagree with observations; causes remain insufficiently diagnosed for an overall success/failure verdict.",
            "claim": "The two source-grounded operation abstractions load and solve as their predeclared stationary mathematical witnesses.",
            "non_claim": "This does not establish application-level predictive accuracy, native HAProxy semantics, or superiority of either approach.",
        },
    }
    _write_json(output_path, manifest)
    return manifest
