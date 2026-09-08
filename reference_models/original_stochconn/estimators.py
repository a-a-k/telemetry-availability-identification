from __future__ import annotations

import math
import time
from dataclasses import dataclass

import numpy as np

from .model import SYNC, EndpointPredicate, ServiceGraph


Z_95 = 1.959963984540054


@dataclass(frozen=True)
class MonteCarloResult:
    estimate: float
    successes: int
    n_samples: int
    ci_half_width: float
    runtime_ms: float

    @property
    def standard_error(self) -> float:
        return math.sqrt(max(self.estimate * (1.0 - self.estimate), 0.0) / self.n_samples)


def exact_enumeration(
    graph: ServiceGraph,
    endpoint: EndpointPredicate,
    max_states: int = 1_000_000,
) -> float:
    service_count = len(graph.services)
    edge_count = len(graph.edges)
    states = (1 << service_count) * (1 << edge_count)
    if states > max_states:
        raise ValueError(f"exact enumeration refused for {states} states")
    service_probs = [graph.service_live_probability(service) for service in graph.services]
    edge_probs = [graph.rho[edge.key] for edge in graph.edges]
    total = 0.0
    for service_mask in range(1 << service_count):
        alive_services: set[str] = set()
        service_probability = 1.0
        for index, service in enumerate(graph.services):
            live = (service_mask & (1 << index)) != 0
            prob = service_probs[index]
            service_probability *= prob if live else 1.0 - prob
            if live:
                alive_services.add(service)
        if service_probability == 0.0:
            continue
        for edge_mask in range(1 << edge_count):
            live_edges = set()
            edge_probability = 1.0
            for index, edge in enumerate(graph.edges):
                live = (edge_mask & (1 << index)) != 0
                prob = edge_probs[index]
                edge_probability *= prob if live else 1.0 - prob
                if live:
                    live_edges.add(edge.key)
            probability = service_probability * edge_probability
            if probability and graph.endpoint_success(endpoint, alive_services, live_edges):
                total += probability
    return total


def monte_carlo_availability(
    graph: ServiceGraph,
    endpoint: EndpointPredicate,
    n_samples: int,
    seed: int,
) -> MonteCarloResult:
    if n_samples < 1:
        raise ValueError("n_samples must be positive")
    rng = np.random.default_rng(seed)
    started = time.perf_counter()
    successes = 0
    cache: dict[tuple[tuple[str, ...], tuple[tuple[str, str, str], ...]], bool] = {}
    service_specs = [
        (service, graph.replicas[service], np.asarray(graph.theta[service], dtype=float))
        for service in graph.services
    ]
    edge_specs = [(edge.key, graph.rho[edge.key]) for edge in graph.edges]
    for _ in range(n_samples):
        alive_services: set[str] = set()
        for service, replicas, theta in service_specs:
            draws = rng.random(replicas)
            if bool(np.any(draws < theta)):
                alive_services.add(service)
        live_edges: set[tuple[str, str, str]] = set()
        for edge_key, edge_rho in edge_specs:
            if rng.random() < edge_rho:
                live_edges.add(edge_key)
        key = (tuple(sorted(alive_services)), tuple(sorted(live_edges)))
        success = cache.get(key)
        if success is None:
            success = graph.endpoint_success(endpoint, alive_services, live_edges)
            cache[key] = success
        successes += int(success)
    estimate = successes / n_samples
    ci_half_width = Z_95 * math.sqrt(max(estimate * (1.0 - estimate), 0.0) / n_samples)
    runtime_ms = (time.perf_counter() - started) * 1000.0
    return MonteCarloResult(estimate, successes, n_samples, ci_half_width, runtime_ms)


def monte_carlo_probability(probability: float, n_samples: int, seed: int) -> MonteCarloResult:
    if n_samples < 1:
        raise ValueError("n_samples must be positive")
    if not 0.0 <= probability <= 1.0:
        raise ValueError("probability must be in [0, 1]")
    rng = np.random.default_rng(seed)
    started = time.perf_counter()
    successes = int(rng.binomial(n_samples, probability))
    estimate = successes / n_samples
    ci_half_width = Z_95 * math.sqrt(max(estimate * (1.0 - estimate), 0.0) / n_samples)
    runtime_ms = (time.perf_counter() - started) * 1000.0
    return MonteCarloResult(estimate, successes, n_samples, ci_half_width, runtime_ms)


def path_closed_form(graph: ServiceGraph, path_services: list[str]) -> float:
    if len(path_services) < 2:
        raise ValueError("path must contain at least two services")
    value = 1.0
    for service in path_services:
        value *= graph.service_live_probability(service)
    for source, target in zip(path_services, path_services[1:]):
        edge = graph.find_edge(source, target, SYNC)
        value *= graph.rho[edge.key]
    return value


def fanout_closed_form(graph: ServiceGraph, entry: str, targets: list[str]) -> float:
    value = graph.service_live_probability(entry)
    for target in targets:
        edge = graph.find_edge(entry, target, SYNC)
        value *= graph.service_live_probability(target) * graph.rho[edge.key]
    return value


def replicated_edge_bottleneck_availability(entry_theta: float, target_theta: float, replicas: int, rho: float) -> float:
    return entry_theta * (1.0 - (1.0 - target_theta) ** replicas) * rho


def service_live_probability(theta: float, replicas: int) -> float:
    return 1.0 - (1.0 - theta) ** replicas
