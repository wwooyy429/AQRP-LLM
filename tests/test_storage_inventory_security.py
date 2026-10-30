"""Cooperative adversarial synthetic checks; no independent acceptance claim."""
from pathlib import Path
from hashlib import sha256
import json
import tempfile
import unittest

from qresearch import storage_inventory as worker


class Event:
    def __init__(self):
        self.callbacks = []
    def __iadd__(self, value):
        self.callbacks.append(value)
        return self
    def __isub__(self, value):
        self.callbacks.remove(value)
        return self


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def digest(value):
    return sha256(encoded(value)).hexdigest()


class Store:
    def __init__(self, root, values):
        self.values = values
        self.paths = {}
        self.read_calls = []
        self.error_raised = Event()
        self.max_size = 100 * 1024 * 1024
        self.max_files = 1000
        for number, (key, value) in enumerate(values.items()):
            path = root / str(number)
            path.write_bytes(value)
            self.paths[key] = str(path.resolve())
    @property
    def keys(self):
        return list(self.values)
    def contains_key(self, key):
        return key in self.values
    def get_file_path(self, key):
        return self.paths[key]
    def read_bytes(self, key):
        self.read_calls.append(key)
        return self.values[key]


class InventorySecurityKnownAnswers(unittest.TestCase):
    def policy(self, metadata_keys):
        return {"schema_version": 1, "metadata_keys": metadata_keys, **worker.LIMITS}

    def identity(self):
        return {"project_id": 1, "attempt_id": "a" * 32, "config_id": "b" * 64,
                "plan_hash": "c" * 64, "stage": "research", "worker_sha256": "d" * 64}

    def fixture(self, *, nested):
        plan_identity = {"synthetic_fixture": "test-owned"}
        window = {"start": "2018-01-01T00:00:00-05:00", "end_exclusive": "2019-01-01T00:00:00-05:00"}
        common = {"schema_version": 1, "plan_hash": digest(plan_identity), "synthetic": True, "window": window}
        payload = {**common, "batch_index": 0, "records": []}
        payload_raw = encoded(payload)
        payload_hash = sha256(payload_raw).hexdigest()
        middle = "unexpected-nesting/" if nested else ""
        relative = "historical-snapshots/v1/objects/" + middle + payload_hash + ".json"
        target = worker.PREFIX + relative
        source = worker.PREFIX + "historical-snapshots/v1/windows/" + digest({key: common[key] for key in ("plan_hash", "synthetic", "window")}) + ".json"
        manifest = {**common, "status": "completed", "plan_identity": plan_identity,
                    "batches": [{"key": relative, "sha256": payload_hash}], "record_count": 0,
                    "snapshot_count": 0, "unique_sid_count": 0, "missing_values": {}, "provider_calls": 0,
                    "full_historical_US200_certified": False, "actual_availability_certified": False,
                    "research_certified": False, "row_values_exported": False}
        return source, target, {source: encoded(manifest), target: payload_raw}

    def run_fixture(self, *, nested):
        source, target, values = self.fixture(nested=nested)
        scratch = Path(__file__).resolve().parents[1] / ".git/repair-work"
        scratch.mkdir(exist_ok=True, parents=True)
        with tempfile.TemporaryDirectory(prefix="inventory-security-", dir=scratch) as temp:
            area = Path(temp).resolve()
            self.assertTrue(area.is_relative_to(scratch.resolve()))
            store = Store(area, values)
            report = worker.run_inventory(store, self.policy([source]), self.identity())
            return report, list(store.read_calls), target

    def test_flat_owned_payload_positive_control(self):
        report, reads, target = self.run_fixture(nested=False)
        self.assertEqual(report["status"], "completed")
        self.assertIn(target, reads)
        self.assertEqual(report["read_summary"]["payload_read_calls"], 1)
        self.assertFalse(report["retention"]["global_reference_closure"])
        self.assertEqual(report["retention"]["confirmed_reclaimable_bytes"], 0)

    def test_nested_unclassified_target_is_not_payload_read_authorization(self):
        report, reads, target = self.run_fixture(nested=True)
        self.assertEqual(worker._role(target), "other_unread")
        self.assertNotIn(target, reads, "A known metadata source cannot authorize an unclassified nested payload path")
        self.assertTrue(all(row["deletion_authorized"] is False for row in report["objects"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
