from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


SYNC = "sync"
ASYNC = "async"
EDGE_TYPES = {SYNC, ASYNC}
RULES = {"all_of", "any_of", "k_of_n"}
SEMANTICS = {"immediate_sync", "eventual_async_explicit", "all_blocking"}


@dataclass(frozen=True, order=True)
class Edge:
    source: str
    target: str
    edge_type: str = SYNC

    def __post_init__(self) -> None:
        if self.edge_type not in EDGE_TYPES:
            raise ValueError(f"unsupported edge type: {self.edge_type!r}")

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.source, self.target, self.edge_type)

    @property
    def label(self) -> str:
        return f"{self.source}->{self.target}:{self.edge_type}"


@dataclass(frozen=True)
class EndpointPredicate:
    endpoint_id: str
    entry_service: str
    target_services: tuple[str, ...]
    rule: str = "all_of"
    k: int | None = None
    success_semantics: str = "immediate_sync"

    def __post_init__(self) -> None:
        if self.rule not in RULES:
            raise ValueError(f"unsupported endpoint rule: {self.rule!r}")
        if self.success_semantics not in SEMANTICS:
            raise ValueError(f"unsupported success semantics: {self.success_semantics!r}")
        if not self.target_services:
            raise ValueError("target_services must not be empty")
        if self.rule == "k_of_n":
            if self.k is None or self.k < 1 or self.k > len(self.target_services):
                raise ValueError("k_of_n requires 1 <= k <= len(target_services)")
        elif self.k is not None:
            raise ValueError("k is only valid for k_of_n")

    def evaluate(self, reachable_targets: set[str]) -> bool:
        reached = len(set(self.target_services) & reachable_targets)
        if self.rule == "all_of":
            return reached == len(self.target_services)
        if self.rule == "any_of":
            return reached >= 1
        if self.rule == "k_of_n":
            assert self.k is not None
            return reached >= self.k
        raise ValueError(f"unsupported endpoint rule: {self.rule!r}")


@dataclass
class ServiceGraph:
    services: tuple[str, ...]
    edges: tuple[Edge, ...]
    replicas: dict[str, int]
    theta: dict[str, tuple[float, ...]]
    rho: dict[tuple[str, str, str], float]

    def __post_init__(self) -> None:
        self.services = tuple(dict.fromkeys(self.services))
        self.edges = tuple(dict.fromkeys(self.edges))
        for service in self.services:
            self.replicas.setdefault(service, 1)
            if service not in self.theta:
                self.theta[service] = tuple(1.0 for _ in range(self.replicas[service]))
        for edge in self.edges:
            self.rho.setdefault(edge.key, 1.0)
        self.validate()

    def validate(self) -> None:
        service_set = set(self.services)
        if len(service_set) != len(self.services):
            raise ValueError("services must be unique")
        edge_keys = [edge.key for edge in self.edges]
        if len(set(edge_keys)) != len(edge_keys):
            raise ValueError("edge keys must be unique")
        for service, count in self.replicas.items():
            if service not in service_set:
                raise ValueError(f"replica map references unknown service {service!r}")
            if count < 1:
                raise ValueError(f"replica count must be positive for {service!r}")
            values = self.theta.get(service)
            if values is None or len(values) != count:
                raise ValueError(f"theta for {service!r} must have {count} values")
            for value in values:
                _check_probability(value, f"theta[{service}]")
        for edge in self.edges:
            if edge.source not in service_set or edge.target not in service_set:
                raise ValueError(f"edge references unknown service: {edge}")
            _check_probability(self.rho[edge.key], f"rho[{edge.label}]")

    def allowed_edge_types(self, semantics: str) -> set[str]:
        if semantics == "immediate_sync":
            return {SYNC}
        if semantics in {"eventual_async_explicit", "all_blocking"}:
            return {SYNC, ASYNC}
        raise ValueError(f"unsupported success semantics: {semantics!r}")

    def reachable_targets(
        self,
        endpoint: EndpointPredicate,
        alive_services: set[str],
        live_edge_keys: set[tuple[str, str, str]],
    ) -> set[str]:
        if endpoint.entry_service not in alive_services:
            return set()
        allowed = self.allowed_edge_types(endpoint.success_semantics)
        adjacency: dict[str, list[str]] = {service: [] for service in alive_services}
        for edge in self.edges:
            if edge.edge_type not in allowed:
                continue
            if edge.key not in live_edge_keys:
                continue
            if edge.source in alive_services and edge.target in alive_services:
                adjacency.setdefault(edge.source, []).append(edge.target)
        seen = {endpoint.entry_service}
        stack = [endpoint.entry_service]
        while stack:
            service = stack.pop()
            for target in adjacency.get(service, []):
                if target not in seen:
                    seen.add(target)
                    stack.append(target)
        return seen & set(endpoint.target_services)

    def endpoint_success(
        self,
        endpoint: EndpointPredicate,
        alive_services: set[str],
        live_edge_keys: set[tuple[str, str, str]],
    ) -> bool:
        return endpoint.evaluate(self.reachable_targets(endpoint, alive_services, live_edge_keys))

    def service_live_probability(self, service: str) -> float:
        dead = 1.0
        for value in self.theta[service]:
            dead *= 1.0 - value
        return 1.0 - dead

    def find_edge(self, source: str, target: str, edge_type: str = SYNC) -> Edge:
        for edge in self.edges:
            if edge.source == source and edge.target == target and edge.edge_type == edge_type:
                return edge
        raise KeyError(f"edge not found: {source}->{target}:{edge_type}")

    def without_edges(self, omitted: Iterable[tuple[str, str, str]]) -> "ServiceGraph":
        omitted_set = set(omitted)
        edges = tuple(edge for edge in self.edges if edge.key not in omitted_set)
        rho = {edge.key: self.rho[edge.key] for edge in edges}
        return ServiceGraph(
            self.services,
            edges,
            dict(self.replicas),
            dict(self.theta),
            rho,
        )


def theta_map(services: Iterable[str], replicas: dict[str, int], theta: float | dict[str, float]) -> dict[str, tuple[float, ...]]:
    values: dict[str, tuple[float, ...]] = {}
    for service in services:
        service_theta = theta[service] if isinstance(theta, dict) else theta
        values[service] = tuple(float(service_theta) for _ in range(replicas[service]))
    return values


def rho_map(edges: Iterable[Edge], rho: float | dict[tuple[str, str, str], float]) -> dict[tuple[str, str, str], float]:
    values: dict[tuple[str, str, str], float] = {}
    for edge in edges:
        values[edge.key] = float(rho[edge.key]) if isinstance(rho, dict) else float(rho)
    return values


def _check_probability(value: float, label: str) -> None:
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{label} must be in [0, 1], got {value!r}")
