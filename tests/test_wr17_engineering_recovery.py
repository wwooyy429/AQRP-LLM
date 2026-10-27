"""WR-17 synthetic original-attempt recovery; no QC or real ledger access."""
from copy import deepcopy
import contextlib
import io
import json
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "cloud"), str(ROOT / "tools"), str(ROOT / "tests")]
import stage2 as cli
import stage2_collection as collection_cli
import collection_task_cli as collection_task_cli
from qresearch.artifacts import MemoryArtifactStore, canonical_json, content_hash
from qresearch.engineering_tasks import EngineeringTaskBridge, EngineeringTaskPlan
from qresearch.registry import Registry, RegistryError
from test_engineering_receipts import (context, report, research_tool, envelope,
                                      completed_tool, log_tools)
from test_phase2_joint_boundaries import joint_document, CATALOG, wrapper


STUB_SOURCE = b"synthetic_stub = 1\n"
MANIFEST = {"stub.py": hashlib.sha256(STUB_SOURCE).hexdigest()}
SOURCE = "a" * 64


class SyntheticFixture:
    def __init__(self, version, *, prepare=True):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        (self.root / "config").mkdir()
        (self.root / "audit").mkdir()
        (self.root / "cloud").mkdir()
        (self.root / "cloud" / "stub.py").write_bytes(STUB_SOURCE)
        self.listing = {"success": True, "projects": [{"projectId": 17}]}
        self.store = MemoryArtifactStore()
        limits = {name: {"total": 10, "normal": 8, "reserve": 2}
                  for name in ("configurations", "research", "lean")}
        self.registry = Registry(self.store, limits)
        raw = joint_document() if version == 2 else deepcopy(context("research")[0]["plan"])
        raw["deployment_hash"] = content_hash(MANIFEST)
        self.plan = EngineeringTaskPlan.from_dict(raw, discovered_project_ids=[17])
        self.bridge = EngineeringTaskBridge(self.registry, self.plan)
        self.bridge.register()
        self.attempt = self.bridge.claim("research").attempt_id
        self.dump("config/quantconnect.json", {"active_project_id": 17})
        self.dump("audit/deployment.json", {"source_files": MANIFEST})
        self.dump("synthetic-plan.json", self.plan.to_dict())
        plan_key = "engineering/frozen-plans/" + self.plan.hash + ".json"
        listing_key = "engineering/project-listings/" + content_hash(self.listing) + ".json"
        self.store.write_once(plan_key, canonical_json(self.plan.to_dict()))
        self.store.write_once(listing_key, canonical_json(self.listing))
        self.dump("audit/engineering_current.json", {"plan_key": plan_key, "plan_hash": self.plan.hash,
                  "project_listing_ref": {"key": listing_key, "sha256": content_hash(self.listing)}})
        self.patches = [patch.object(cli, "ROOT", self.root),
                        patch.object(cli, "open_registry", return_value=self.registry),
                        patch.object(cli, "export_usage", return_value=None),
                        patch.object(cli, "source_manifest", return_value={"source_hash": SOURCE}),
                        patch.object(collection_task_cli, "execution_source_manifest", return_value={"source_hash": SOURCE}),
                        patch.object(collection_cli, "catalog", return_value=deepcopy(CATALOG))]
        for item in self.patches:
            item.start()
        try:
            self.admission = cli.prepare(self.bridge, self.attempt) if prepare else None
        except BaseException:
            self.close()
            raise

    def close(self):
        for item in reversed(self.patches):
            item.stop()
        self.directory.cleanup()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def dump(self, relative, value):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((json.dumps(value) + "\n").encode("utf-8"))
        return path

    def command(self, name, *, attempt=None, tool=None, logs=None, extra=()):
        argv = ["stage2.py", name]
        if attempt is not None:
            argv += ["--attempt", attempt]
        if tool is not None:
            argv += ["--tool-file", str(self.dump("synthetic-tool.json", tool))]
        if logs is not None:
            argv += ["--logs-file", str(self.dump("synthetic-logs.json", logs))]
        argv += list(extra)
        output = io.StringIO()
        with patch.object(sys, "argv", argv), contextlib.redirect_stdout(output):
            cli.main()
        return json.loads(output.getvalue())

    def research_observation(self):
        payload = self.admission["payload"]
        value = wrapper(payload) if self.plan.to_dict()["schema_version"] == 2 else report(payload)
        return research_tool(payload, value)

    def settle_research(self):
        # Model an actual new-entry dispatch before its synthetic successful
        # result; legacy fixtures with no first-admission marker stay legacy.
        self.pin_research_dispatch()
        return self.command("research-result", attempt=self.attempt, tool=self.research_observation())

    def pin_research_dispatch(self):
        entry_key = "engineering/research-entry-protocol/" + self.attempt + ".json"
        dispatch_key = "engineering/research-dispatch/" + self.attempt + ".json"
        if self.store.exists(entry_key) and not self.store.exists(dispatch_key):
            from qresearch.engineering_receipts import research_cell_source
            source = research_cell_source(self.admission["payload"], self.admission["deployment"])
            self.command("research-dispatch", attempt=self.attempt,
                tool=envelope("jupyter_read_cell", {"projectId": 17, "index": 0},
                    {"cellType": "code", "source": source.splitlines(keepends=True)}))

    def alter_current_context(self, *, pointer=True):
        if pointer:
            self.dump("audit/engineering_current.json", {"plan_key": "foreign/unavailable-plan.json", "plan_hash": "0" * 64})
        else:
            (self.root / "audit/engineering_current.json").unlink()
        self.dump("audit/deployment.json", {"source_files": {"new.py": "f" * 64}})


class WR17EngineeringRecoveryTests(unittest.TestCase):
    def test_v1_and_v2_freeze_preserve_pointer_and_store_under_pending_project(self):
        for version in (1, 2):
            with self.subTest(version=version), SyntheticFixture(version) as fixture:
                pointer = fixture.root / "audit/engineering_current.json"
                original = pointer.read_bytes()
                before = fixture.registry.snapshot()
                saved = dict(fixture.store._data)
                with self.assertRaises((ValueError, RegistryError)):
                    cli.freeze(fixture.listing, plan_file=fixture.root / "synthetic-plan.json")
                self.assertEqual(pointer.read_bytes(), original)
                self.assertEqual(fixture.store._data, saved)
                self.assertEqual(fixture.registry.snapshot(), before)

    def test_readonly_preview_remains_available_with_pending_project(self):
        for version in (1, 2):
            with self.subTest(version=version), SyntheticFixture(version) as fixture:
                pointer = fixture.root / "audit/engineering_current.json"
                original = pointer.read_bytes()
                saved = dict(fixture.store._data)
                before = fixture.registry.snapshot()
                value = cli.freeze(fixture.listing, plan_file=fixture.root / "synthetic-plan.json", preview=True)
                self.assertFalse(value["configuration_registered"])
                self.assertFalse(value["execution_started"])
                self.assertEqual(pointer.read_bytes(), original)
                self.assertEqual(fixture.store._data, saved)
                self.assertEqual(fixture.registry.snapshot(), before)

    def test_prepare_original_attempt_survives_pointer_source_catalog_and_deployment_changes(self):
        for version in (1, 2):
            with self.subTest(version=version), SyntheticFixture(version) as fixture:
                original = (fixture.root / fixture.admission["input_path"]).read_bytes()
                fixture.alter_current_context()
                before = fixture.registry.snapshot()
                saved = dict(fixture.store._data)
                with patch.object(cli, "source_manifest", side_effect=AssertionError("No current source on recovery")), \
                     patch.object(collection_task_cli, "execution_source_manifest", side_effect=AssertionError("No current source on recovery")), \
                     patch.object(collection_cli, "catalog", side_effect=AssertionError("No current catalog on recovery")):
                    observed = fixture.command("prepare", attempt=fixture.attempt)
                self.assertEqual(observed, fixture.admission)
                self.assertEqual((fixture.root / fixture.admission["input_path"]).read_bytes(), original)
                self.assertEqual(fixture.store._data, saved)
                self.assertEqual(fixture.registry.snapshot(), before)

    def test_original_research_receipt_settles_without_current_pointer_or_extra_charge(self):
        for version in (1, 2):
            with self.subTest(version=version), SyntheticFixture(version) as fixture:
                fixture.pin_research_dispatch()
                fixture.alter_current_context(pointer=False)
                before = fixture.registry.snapshot()["usage"]
                with patch.object(collection_cli, "catalog", side_effect=AssertionError("No current catalog on settlement")):
                    result = fixture.settle_research()
                    again = fixture.settle_research()
                self.assertEqual(result["status"], "completed")
                self.assertEqual(again["status"], "completed")
                self.assertEqual(result["config_id"], fixture.bridge.config_id)
                self.assertEqual(fixture.registry.snapshot()["usage"], before)

    def test_original_lean_submission_and_completion_use_original_admitted_identity(self):
        for version in (1, 2):
            with self.subTest(version=version), SyntheticFixture(version) as fixture:
                fixture.settle_research()
                attempt = fixture.bridge.claim("lean").attempt_id
                admission = cli.prepare(fixture.bridge, attempt)
                payload = admission["payload"]
                tool = envelope("create_backtest", {"projectId": 17, "backtestName": "synthetic-wr17"},
                                {"success": True, "backtestId": "native-backtest-id"})
                fixture.alter_current_context()
                before = fixture.registry.snapshot()["usage"]
                submitted = fixture.command("backtest-submission", attempt=attempt, tool=tool)
                self.assertEqual(submitted["status"], "pending")
                result = fixture.command("backtest-result", attempt=attempt, tool=completed_tool(), logs=log_tools(payload))
                self.assertEqual(result["status"], "completed")
                self.assertEqual(result["config_id"], fixture.bridge.config_id)
                self.assertEqual(fixture.registry.snapshot()["usage"], before)

    def test_missing_local_original_input_recovers_metadata_without_recreation(self):
        for version in (1, 2):
            with self.subTest(version=version), SyntheticFixture(version) as fixture:
                path = fixture.root / fixture.admission["input_path"]
                path.unlink()
                fixture.alter_current_context(pointer=False)
                before = fixture.registry.snapshot()
                saved = dict(fixture.store._data)
                self.assertEqual(fixture.command("prepare", attempt=fixture.attempt), fixture.admission)
                self.assertFalse(path.exists())
                self.assertEqual(fixture.registry.snapshot(), before)
                self.assertEqual(fixture.store._data, saved)

    def test_admitted_input_tampering_is_rejected_before_any_transition(self):
        mutations = (lambda item: item["deployment"].update(input_hash="0" * 64),
                     lambda item: item["payload"]["deployment_manifest"].update(**{"stub.py": "e" * 64}),
                     lambda item: item.update(input_path="audit/task_inputs/foreign.py"))
        for version in (1, 2):
            for index, mutation in enumerate(mutations):
                with self.subTest(version=version, mutation=index), SyntheticFixture(version) as fixture:
                    key = "engineering/admitted-inputs/" + fixture.attempt + ".json"
                    bad = deepcopy(fixture.admission)
                    mutation(bad)
                    fixture.store._data[key] = canonical_json(bad)
                    before = fixture.registry.snapshot()
                    saved = dict(fixture.store._data)
                    with self.assertRaises((ValueError, RegistryError)):
                        fixture.command("research-result", attempt=fixture.attempt, tool=fixture.research_observation())
                    self.assertEqual(fixture.registry.snapshot(), before)
                    self.assertEqual(fixture.store._data, saved)

    def test_local_original_input_tampering_is_rejected_and_never_overwritten(self):
        for version in (1, 2):
            with self.subTest(version=version), SyntheticFixture(version) as fixture:
                path = fixture.root / fixture.admission["input_path"]
                path.write_bytes(b"SYNTHETIC_TAMPERED_INPUT\n")
                before = fixture.registry.snapshot()
                saved = dict(fixture.store._data)
                with self.assertRaises((ValueError, RegistryError)):
                    fixture.command("prepare", attempt=fixture.attempt)
                self.assertEqual(path.read_bytes(), b"SYNTHETIC_TAMPERED_INPUT\n")
                self.assertEqual(fixture.registry.snapshot(), before)
                self.assertEqual(fixture.store._data, saved)

    def test_finalized_attempt_cannot_create_a_fresh_remote_input(self):
        for version in (1, 2):
            with self.subTest(version=version), SyntheticFixture(version, prepare=False) as fixture:
                fixture.registry.fail(fixture.attempt, "SYNTHETIC observed failure")
                before = fixture.registry.snapshot()
                saved = dict(fixture.store._data)
                with self.assertRaises((ValueError, RegistryError)):
                    fixture.command("prepare", attempt=fixture.attempt)
                self.assertFalse((fixture.root / "audit/task_inputs").exists())
                self.assertEqual(fixture.registry.snapshot(), before)
                self.assertEqual(fixture.store._data, saved)

    def test_attempt_status_and_unknown_attempt_are_independent_of_pointer(self):
        for version in (1, 2):
            with self.subTest(version=version), SyntheticFixture(version) as fixture:
                fixture.alter_current_context(pointer=False)
                observed = fixture.command("status", attempt=fixture.attempt)
                self.assertEqual(observed["attempts"][0]["attempt_id"], fixture.attempt)
                before = fixture.registry.snapshot()
                saved = dict(fixture.store._data)
                with self.assertRaises((ValueError, RegistryError)):
                    fixture.command("prepare", attempt="0" * 32)
                self.assertEqual(fixture.registry.snapshot(), before)
                self.assertEqual(fixture.store._data, saved)

    def test_new_joint_registration_rechecks_current_source_without_charge(self):
        with SyntheticFixture(2) as fixture:
            before = fixture.registry.snapshot()
            saved = dict(fixture.store._data)
            with patch.object(collection_task_cli, "execution_source_manifest", return_value={"source_hash": "f" * 64}):
                with self.assertRaises(ValueError):
                    fixture.command("register")
            self.assertEqual(fixture.registry.snapshot(), before)
            self.assertEqual(fixture.store._data, saved)


if __name__ == "__main__":
    unittest.main()
