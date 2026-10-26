"""Local command preparation on temporary stores; no authoritative ledger I/O."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "cloud"))
import collection_task_cli as cli
import research
import stages
from test_collection_tasks import raw_plan, CAT
from qresearch.artifacts import MemoryArtifactStore, content_hash
from qresearch.collection_tasks import CollectionTaskBridge
from qresearch.registry import Registry, RegistryError

REAL_EXECUTION_MANIFEST = cli.execution_source_manifest


class CollectionTaskCLITests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.store = MemoryArtifactStore()
        self.registry = Registry(self.store, {key: {"normal": 8, "reserve": 2, "total": 10}
                                 for key in ("configurations", "research", "lean")})
        (self.root / "audit").mkdir()
        self.deployment = {"synthetic.py": "b" * 64}
        (self.root / "audit/deployment.json").write_text(json.dumps({"source_files": self.deployment}), encoding="utf-8")
        self.patches = [patch.object(cli, "ROOT", self.root), patch.object(cli, "open_registry", return_value=self.registry),
                        patch.object(cli, "execution_source_manifest", return_value={"source_hash": "a" * 64}),
                        patch.object(cli, "export_usage", return_value=None)]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.directory.cleanup()

    def freeze(self):
        return cli.freeze_task(raw_plan(), {"success": True, "projects": [{"projectId": 17}]}, field_catalog=CAT)

    def test_freeze_does_not_debit_and_current_plan_is_bound_to_listing(self):
        frozen = self.freeze()
        self.assertFalse(frozen["configuration_registered"])
        self.assertEqual(self.registry.snapshot()["usage"]["configurations"]["total"], 0)
        bridge = cli.current_bridge(field_catalog=CAT)
        self.assertEqual(bridge.plan.hash, frozen["plan_hash"])
        ref = frozen["project_listing_ref"]
        self.store._data[ref["key"]] = b"{}"
        with self.assertRaises(ValueError):
            cli.current_bridge(field_catalog=CAT)

    def test_undiscovered_project_or_catalog_override_is_not_persisted(self):
        for projects in ({"success": False, "projects": []}, {"success": True, "projects": [{"projectId": 18}]}):
            with self.assertRaises(ValueError):
                cli.freeze_task(raw_plan(), projects, field_catalog=CAT)
        changed = raw_plan(); changed["field_catalog"]["dollar_volume"]["unit"] = "other"
        with self.assertRaises(ValueError):
            cli.freeze_task(changed, {"success": True, "projects": [{"projectId": 17}]}, field_catalog=CAT)
        self.assertFalse((self.root / "audit/collection_current.json").exists())

    def test_prepare_requires_precharged_attempt_and_is_immutable_and_separate(self):
        self.freeze(); bridge = cli.current_bridge(field_catalog=CAT); bridge.register()
        with self.assertRaises(ValueError):
            cli.prepare_task(bridge, "0" * 32)
        attempt = bridge.claim(); first = cli.prepare_task(bridge, attempt.attempt_id)
        second = cli.prepare_task(bridge, attempt.attempt_id)
        self.assertEqual(first, second)
        self.assertEqual(first["cloud_input_path"], "_collection_task_input.py")
        path = self.root / first["input_path"]
        original = path.read_bytes()
        self.assertTrue(original.startswith(b"TASK_INPUT_JSON = "))
        self.assertFalse((self.root / "audit/task_inputs").exists())
        path.write_bytes(b"changed")
        with self.assertRaises(ValueError):
            cli.prepare_task(bridge, attempt.attempt_id)
        self.assertEqual(path.read_bytes(), b"changed")

    def test_stale_source_rejected_before_new_debit_but_status_read_allowed(self):
        self.freeze(); bridge = cli.current_bridge(field_catalog=CAT)
        args = NS(command="register-task", allocation="normal")
        with patch.object(cli, "execution_source_manifest", return_value={"source_hash": "c" * 64}):
            with self.assertRaises(ValueError):
                cli.execute_metadata_command(args, field_catalog=CAT)
        self.assertEqual(self.registry.snapshot()["usage"]["configurations"]["total"], 0)
        cli.export_usage.assert_called_once()
        with patch.object(cli, "execution_source_manifest", return_value={"source_hash": "c" * 64}):
            status = cli.execute_metadata_command(NS(command="task-status"), field_catalog=CAT)
        self.assertEqual(status["usage"]["research"]["total"], 0)

    def test_completed_attempt_cannot_prepare_new_input(self):
        self.freeze(); bridge = cli.current_bridge(field_catalog=CAT); bridge.register(); attempt = bridge.claim()
        self.registry.complete(attempt, {"synthetic": True})
        with self.assertRaises(ValueError):
            cli.prepare_task(bridge, attempt.attempt_id)

    def test_real_usage_export_does_not_break_freeze_register_claim_prepare(self):
        (self.root / "config").mkdir()
        path = self.root / "config/budget.json"
        path.write_text(json.dumps({"schema_version": 1, "limits": {"full_configurations": 10},
                                   "allocations": {"policy": "synthetic-fixed"}, "usage": {}}), encoding="utf-8")
        with patch.object(cli, "execution_source_manifest", side_effect=REAL_EXECUTION_MANIFEST), \
             patch.object(stages, "ROOT", self.root), patch.object(research, "ROOT", self.root), \
             patch.object(cli, "export_usage", side_effect=research.export_usage):
            self.freeze()
            frozen = cli.execution_source_manifest()["source_hash"]
            registered = cli.execute_metadata_command(NS(command="register-task", allocation="normal"), field_catalog=CAT)
            self.assertEqual(json.loads(path.read_text())["usage"]["configuration_budget_charges"], 1)
            self.assertEqual(cli.execution_source_manifest()["source_hash"], frozen)
            claimed = cli.execute_metadata_command(NS(command="claim-task", allocation="normal", retry_of=None, reason=None), field_catalog=CAT)
            self.assertTrue(claimed["should_execute"])
            self.assertEqual(cli.execution_source_manifest()["source_hash"], frozen)
            admitted = cli.execute_metadata_command(NS(command="prepare-task", attempt=claimed["attempt_id"]), field_catalog=CAT)
            self.assertEqual(admitted["payload"]["identity"]["config_id"], registered["config_id"])
            self.assertEqual(json.loads(path.read_text())["usage"]["research_execution_attempts"], 1)
            policy = json.loads(path.read_text()); policy["limits"]["full_configurations"] = 11
            path.write_text(json.dumps(policy), encoding="utf-8")
            self.assertNotEqual(cli.execution_source_manifest()["source_hash"], frozen)
            with self.assertRaises(ValueError):
                cli.verify_current_source(cli.current_bridge(field_catalog=CAT))


if __name__ == "__main__":
    unittest.main()
