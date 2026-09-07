from datetime import datetime, timedelta, timezone
import os
import unittest
from unittest.mock import patch

from telemetry_availability import temporal_confirmation_gate as gate


class TemporalConfirmationGateTests(unittest.TestCase):
    def record(self):
        now = datetime.now(timezone.utc)
        return {"id": 42, "name": "synthetic", "size_in_bytes": 10, "digest": "sha256:synthetic", "expired": False,
                "created_at": now.isoformat(), "expires_at": (now + timedelta(days=90)).isoformat()}

    def test_retention_rejects_expired_and_short_lived_artifacts(self):
        record = self.record()
        self.assertTrue(gate.retained(record, 90))
        record["expires_at"] = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        self.assertFalse(gate.retained(record, 90))
        record = self.record()
        record["expired"] = True
        self.assertFalse(gate.retained(record, 90))

    def test_artifact_identity_cannot_be_replaced_by_same_name(self):
        record = self.record()
        lock = {key: record[key] for key in ("id", "name", "size_in_bytes", "digest")}
        gate.verify_lock(record, lock)
        for field in lock:
            changed = dict(record)
            changed[field] = "changed"
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "differs"):
                gate.verify_lock(changed, lock)

    def test_local_readiness_does_not_launch_or_download(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "false"}):
            for function, args in ((gate.readiness, ["missing"]), (gate.before_evaluator, [42, "missing"]), (gate.audit_main, ["missing", "missing"])):
                with self.assertRaisesRegex(ValueError, "only in GitHub Actions"):
                    function(*args)


if __name__ == "__main__":
    unittest.main()
