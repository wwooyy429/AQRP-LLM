"""Independent literal synthetic answers for the metadata-only analyzer."""
import importlib.util
import json
from pathlib import Path
import unittest


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("storage_inventory_audit_analyzer", HERE / "analyze_inventory.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def selected(value, path):
    for part in path.split("."):
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


class InventoryKnownAnswers(unittest.TestCase):
    pass


def install(case):
    def test(self):
        result = MODULE.analyze(case["UI"], case.get("local_roots", {}), case.get("rules", {}))
        for path, expected in case["expected"].items():
            self.assertEqual(selected(result, path), expected, path)
        self.assertEqual(result["confirmed_reclaimable_bytes"], 0)
        self.assertIsNone(result["potential_reclaimable_total_bytes"])
        self.assertEqual(result["cloud_calls"], 0)
        self.assertEqual(result["Registry_or_budget_changes"], 0)
        self.assertFalse(result["final_test_enabled"])
        for item in result["objects"]:
            self.assertFalse(item["deletion_authorized"])
            self.assertFalse(item["reference_closure_verified"])
            self.assertFalse(item["raw_content_hash_verified"])
    setattr(InventoryKnownAnswers, "test_" + case["id"], test)


for CASE in json.loads((HERE / "synthetic_fixtures.json").read_bytes())["cases"]:
    install(CASE)


if __name__ == "__main__":
    unittest.main(verbosity=2)
