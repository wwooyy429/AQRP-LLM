"""Persisted attempt recovery after local context changes; synthetic only."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "cloud"), str(ROOT / "tools"), str(ROOT / "tests")]
import collection_task_cli as cli
import stage2_collection as entry
from qresearch.artifacts import MemoryArtifactStore, canonical_json
from qresearch.registry import Registry
from qresearch.collection_execution import stdout_marker
from test_collection_tasks import CAT, raw_plan, manifest, WorkerAdapter


class WR12AttemptRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        (self.root / "audit").mkdir()
        (self.root / "audit/deployment.json").write_text(json.dumps({"source_files": manifest()}), encoding="utf-8")
        self.store = MemoryArtifactStore()
        self.limits = {key: {"normal": 8, "reserve": 2, "total": 10} for key in ("configurations", "research", "lean")}
        self.registry = Registry(self.store, self.limits)
        self.patches = [patch.object(cli, "ROOT", self.root), patch.object(cli, "open_registry", return_value=self.registry),
                        patch.object(cli, "execution_source_manifest", return_value={"source_hash": "a" * 64}),
                        patch.object(cli, "export_usage", return_value=None)]
        for p in self.patches:
            p.start()
        self.freeze("A", 17)
        self.command("register-task")
        self.attempt = self.command("claim-task")["attempt_id"]
        self.admission = self.command("prepare-task", attempt=self.attempt)
        self.original_bridge = cli.current_bridge(field_catalog=CAT)
        adapter = WorkerAdapter()
        adapter.submit_research(self.admission["payload"], operation_key=self.original_bridge._operation("research"))
        wrapper = {key: adapter.result["completion"][key] for key in ("cloud_report", "report_ref")}
        self.tool = {"tool_name": "mcp__quantconnect__jupyter_execute_cell", "arguments": {"projectId": 17, "index": 0},
                     "result": {"structuredContent": {"status": "completed", "outputs": [{"output_type": "stream", "name": "stdout",
                     "text": stdout_marker(wrapper, payload=self.admission["payload"], field_catalog=CAT) + "\n"}]}}}
        self.tool_file = self.root / "synthetic-tool.json"
        self.tool_file.write_text(json.dumps(self.tool), encoding="utf-8")

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.directory.cleanup()

    def freeze(self, name, project):
        raw = raw_plan(); raw.update(plan_id=name, project_id=project)
        return cli.freeze_task(raw, {"success": True, "projects": [{"projectId": 17}, {"projectId": 18}]}, field_catalog=CAT)

    def command(self, name, *, catalog=CAT, **kwargs):
        args = NS(command=name, attempt=None, tool_file=None, allocation="normal", retry_of=None, reason=None)
        vars(args).update(kwargs)
        return cli.execute_metadata_command(args, field_catalog=catalog)

    def settle(self, catalog=CAT):
        return self.command("research-result", attempt=self.attempt, tool_file=self.tool_file, catalog=catalog)

    def test_pointer_switch_then_valid_old_result_completes_without_new_charge(self):
        usage = self.registry.snapshot()["usage"]
        self.freeze("B", 18)
        result = self.settle()
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["config_id"], self.original_bridge.config_id)
        self.assertEqual(self.registry.snapshot()["usage"], usage)
        self.assertEqual(self.settle()["status"], "completed")
        self.assertEqual(self.registry.snapshot()["usage"], usage)

    def test_current_catalog_changed_old_result_still_uses_registered_catalog(self):
        changed = deepcopy(CAT); changed["dollar_volume"]["unit"] = "new-unit"
        usage = self.registry.snapshot()["usage"]
        self.assertEqual(self.settle(changed)["status"], "completed")
        self.assertEqual(self.registry.snapshot()["usage"], usage)
        with self.assertRaises(ValueError):
            cli.current_bridge(field_catalog=changed)

    def test_restart_and_missing_current_pointer_does_not_prevent_old_settlement(self):
        (self.root / "audit/collection_current.json").unlink()
        reopened = Registry(self.store, self.limits)
        usage = reopened.snapshot()["usage"]
        with patch.object(cli, "open_registry", return_value=reopened):
            self.assertEqual(self.settle(catalog=None)["status"], "completed")
        self.assertEqual(reopened.snapshot()["usage"], usage)

    def test_existing_admitted_input_can_be_read_after_switch_and_source_change(self):
        original_bytes = (self.root / self.admission["input_path"]).read_bytes()
        self.freeze("B", 18)
        usage = self.registry.snapshot()["usage"]
        with patch.object(cli, "execution_source_manifest", return_value={"source_hash": "b" * 64}):
            result = self.command("prepare-task", attempt=self.attempt, catalog=None)
        self.assertEqual(result, self.admission)
        self.assertEqual((self.root / self.admission["input_path"]).read_bytes(), original_bytes)
        self.assertEqual(self.registry.snapshot()["usage"], usage)

    def test_unknown_attempt_and_foreign_receipt_do_not_release_project_or_charge(self):
        usage = self.registry.snapshot()["usage"]
        with self.assertRaises((ValueError, RuntimeError)):
            self.command("research-result", attempt="0" * 32, tool_file=self.tool_file)
        bad = deepcopy(self.tool); bad["arguments"]["projectId"] = 18
        self.tool_file.write_text(json.dumps(bad), encoding="utf-8")
        with self.assertRaises((ValueError, RuntimeError)):
            self.settle()
        self.assertEqual(self.registry.snapshot()["attempts"][-1]["status"], "started")
        self.assertEqual(self.registry.snapshot()["usage"], usage)

    def test_tampered_admitted_input_is_rejected_without_refund_or_completion(self):
        key = "collection/admitted-inputs/" + self.attempt + ".json"
        admission = json.loads(self.store.read_bytes(key))
        admission["deployment"]["input_hash"] = "0" * 64
        self.store._data[key] = canonical_json(admission)
        usage = self.registry.snapshot()["usage"]
        with self.assertRaises((ValueError, RuntimeError)):
            self.settle()
        self.assertEqual(self.registry.snapshot()["attempts"][-1]["status"], "started")
        self.assertEqual(self.registry.snapshot()["usage"], usage)

    def test_entry_does_not_read_current_catalog_when_settling_old_attempt(self):
        with patch.object(entry, "catalog", side_effect=AssertionError("Do not load today's catalog")), \
             patch.object(sys, "argv", ["stage2_collection.py", "research-result", "--attempt", self.attempt,
                                         "--tool-file", str(self.tool_file)]):
            import contextlib, io
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                entry.main()
        self.assertEqual(json.loads(output.getvalue())["status"], "completed")

    def test_attempt_status_survives_pointer_switch_and_unavailable_current_catalog(self):
        self.freeze("B", 18)
        with patch.object(entry, "catalog", side_effect=AssertionError("Today's catalog is not settlement evidence")), \
             patch.object(sys, "argv", ["stage2_collection.py", "task-status", "--attempt", self.attempt]):
            import contextlib, io
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                entry.main()
        observed = json.loads(output.getvalue())
        self.assertEqual(observed["attempts"][0]["attempt_id"], self.attempt)
        self.assertEqual(observed["attempts"][0]["status"], "started")

    def test_missing_local_input_can_settle_but_new_stale_source_claim_is_refused(self):
        (self.root / self.admission["input_path"]).unlink()
        usage = self.registry.snapshot()["usage"]
        with patch.object(cli, "execution_source_manifest", return_value={"source_hash": "b" * 64}):
            with self.assertRaises(ValueError):
                self.command("claim-task")
            self.assertEqual(self.registry.snapshot()["usage"], usage)
            self.assertEqual(self.settle(catalog=None)["status"], "completed")
        self.assertEqual(self.registry.snapshot()["usage"], usage)


if __name__ == "__main__":
    unittest.main()
