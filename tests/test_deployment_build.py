"""Synthetic build-policy checks; never register or dispatch an experiment."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "cloud"), str(ROOT / "tools")]
import research
from qresearch.artifacts import content_hash
from qresearch.deployment_sources import SOURCE_IDENTITY_POLICY, source_sha256


class DeploymentBuildTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "config").mkdir()
        (self.root / "cloud/qresearch").mkdir(parents=True)
        for name in ("research", "universe", "data", "workflow", "budget"):
            (self.root / "config" / (name + ".json")).write_bytes((ROOT / "config" / (name + ".json")).read_bytes())
        self.policy = {"schema_version": 1, "manifest_schema_version": 2,
                       "source_identity_policy": SOURCE_IDENTITY_POLICY}
        self.code = b"VALUE = 3\n\n"
        (self.root / "cloud/stub.py").write_bytes(self.code)
        self.addCleanup(patch.stopall)
        patch.object(research, "ROOT", self.root).start()

    def policy_file(self, value=None):
        (self.root / "config/deployment.json").write_text(json.dumps(self.policy if value is None else value), encoding="utf-8")

    def test_explicit_policy_is_in_configuration_identity_and_closed(self):
        legacy = research.configuration()
        self.assertNotIn("deployment", legacy)
        self.policy_file()
        current = research.configuration()
        self.assertEqual(current["deployment"], self.policy)
        self.assertNotEqual(content_hash(current), content_hash(legacy))
        for value in (dict(self.policy, extra=True), dict(self.policy, schema_version=True),
                      dict(self.policy, manifest_schema_version=1),
                      dict(self.policy, source_identity_policy="unknown")):
            self.policy_file(value)
            with self.subTest(value=value), self.assertRaises(ValueError):
                research.configuration()

    def test_build_binds_original_and_canonical_without_debit_or_extra_copies(self):
        self.policy_file()
        before = (self.root / "config/budget.json").read_bytes()
        first = research.build()
        path = self.root / "audit/deployment.json"
        raw, mtime = path.read_bytes(), path.stat().st_mtime_ns
        result = json.loads(raw)
        record = result["deployment_manifest"]["files"]["stub.py"]
        self.assertEqual(result["source_files"]["stub.py"], source_sha256(self.code))
        self.assertEqual(record, {"source_sha256": hashlib.sha256(self.code).hexdigest(),
            "canonical_sha256": hashlib.sha256(b"VALUE = 3\n").hexdigest(), "terminal_lf_count": 2})
        self.assertEqual(result["deployment_manifest"]["source_identity_policy"], SOURCE_IDENTITY_POLICY)
        self.assertFalse(research.build()["config_changed"])
        self.assertEqual((raw, mtime), (path.read_bytes(), path.stat().st_mtime_ns))
        self.assertEqual(before, (self.root / "config/budget.json").read_bytes())
        self.assertFalse((self.root / "audit/runtime").exists())
        self.assertEqual(len(list((self.root / "audit").iterdir())), 1)
        self.assertTrue(first["config_changed"])

    def test_generated_inputs_excluded_without_reading_or_executing_them(self):
        self.policy_file()
        for name in ("_engineering_task_input.py", "_collection_task_input.py"):
            (self.root / "cloud" / name).write_bytes(b"not valid Python\xff")
        research.build()
        value = json.loads((self.root / "audit/deployment.json").read_text())
        for name in ("_engineering_task_input.py", "_collection_task_input.py"):
            self.assertNotIn(name, value["source_files"])
            self.assertNotIn(name, value["deployment_manifest"]["files"])

    def test_legacy_fixture_without_explicit_policy_retains_plain_hash_manifest(self):
        research.build()
        result = json.loads((self.root / "audit/deployment.json").read_text())
        self.assertNotIn("deployment_manifest", result)
        self.assertEqual(result["source_files"]["stub.py"], source_sha256(self.code))
        self.assertNotEqual(result["source_files"]["stub.py"], source_sha256(self.code + b"\n"))


if __name__ == "__main__":
    unittest.main()
