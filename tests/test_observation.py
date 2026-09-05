from __future__ import annotations

import unittest
from pathlib import Path

import numpy as np

from telemetry_availability.config import load_config
from telemetry_availability.observation import generate_observation_mask


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPOSITORY_ROOT / "configs" / "rq1_synthetic.yaml"


class ObservationPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_config(CONFIG_PATH)
        cls.family = next(
            item for item in cls.config.families if item.id == "mandatory_fanout"
        )

    def test_staggered_health_never_creates_synchronous_health_pair(self) -> None:
        policy = next(
            item for item in self.config.observation_modes if item.id == "no_joint_health"
        )
        mask = generate_observation_mask(
            self.family,
            episode_count=200,
            policy=policy,
            rng=np.random.default_rng(7),
        )
        health_positions = [
            index
            for index, observable in enumerate(self.family.observables)
            if observable.kind == "health"
        ]
        trace_positions = [
            index
            for index, observable in enumerate(self.family.observables)
            if observable.kind == "trace"
        ]

        self.assertTrue(np.all(np.sum(mask[:, health_positions], axis=1) == 1))
        self.assertTrue(np.all(mask[:, trace_positions]))

    def test_trace_sampling_is_grouped_at_episode_level(self) -> None:
        from telemetry_availability.observation import ObservationPolicy

        policy = ObservationPolicy(
            id="sampled",
            mode="full",
            sampling_by_kind={"trace": 0.5},
        )
        mask = generate_observation_mask(
            self.family,
            episode_count=200,
            policy=policy,
            rng=np.random.default_rng(11),
        )
        trace_positions = [
            index
            for index, observable in enumerate(self.family.observables)
            if observable.kind == "trace"
        ]
        first = mask[:, trace_positions[0]]
        for position in trace_positions[1:]:
            np.testing.assert_array_equal(first, mask[:, position])
        self.assertGreater(np.count_nonzero(first), 0)
        self.assertLess(np.count_nonzero(first), len(first))


if __name__ == "__main__":
    unittest.main()
