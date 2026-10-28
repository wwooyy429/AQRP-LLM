"""Versioned local/admitted/project identity boundaries; synthetic stores only.

These tests never read the authoritative ledger, call QC or certify market data.
"""
from contextlib import ExitStack, contextmanager
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "cloud"), str(ROOT / "tools"), str(ROOT / "tests")]
import stage2
import collection_task_cli as collection_cli
import deployment_preflight
from qresearch.artifacts import MemoryArtifactStore, canonical_json, content_hash
from qresearch.registry import Registry
from test_deployment_preflight import LocalFixture, project_tool, projects, SOURCE, MANIFEST, SECRET
from test_collection_tasks import raw_plan, CAT

POLICY = "utf8_sig_universal_newlines_terminal_lf_v1"


def v2_manifest(raw=SOURCE):
    """Independent known-answer construction for this simple ASCII fixture."""
    return {"schema_version": 2, "source_identity_policy": POLICY, "files": {
        "stub.py": {"source_sha256": hashlib.sha256(raw).hexdigest(),
                    "canonical_sha256": hashlib.sha256(raw.rstrip(b"\n") + b"\n").hexdigest(),
                    "terminal_lf_count": len(raw) - len(raw.rstrip(b"\n"))}}}


def build_record(manifest):
    return {"source_files": deepcopy(MANIFEST), "deployment_manifest": deepcopy(manifest)}


@contextmanager
def collection_fixture(manifest=None):
    with tempfile.TemporaryDirectory() as folder, ExitStack() as stack:
        root = Path(folder)
        (root / "audit").mkdir()
        (root / "cloud").mkdir()
        (root / "cloud/stub.py").write_bytes(SOURCE)
        record = {"source_files": MANIFEST} if manifest is None else build_record(manifest)
        (root / "audit/deployment.json").write_bytes(canonical_json(record))
        store = MemoryArtifactStore()
        registry = Registry(store, {name: {"normal": 8, "reserve": 2, "total": 10}
                                    for name in ("configurations", "research", "lean")})
        stack.enter_context(patch.object(collection_cli, "ROOT", root))
        stack.enter_context(patch.object(collection_cli, "open_registry", return_value=registry))
        stack.enter_context(patch.object(collection_cli, "execution_source_manifest", return_value={"source_hash": "a" * 64}))
        stack.enter_context(patch.object(collection_cli, "export_usage", return_value=None))
        yield root, store, registry


def freeze_collection():
    return collection_cli.freeze_task(raw_plan(), {"success": True, "projects": [{"projectId": 17}]}, field_catalog=CAT)


class VersionedLocalCLITests(unittest.TestCase):
    def test_new_freeze_preview_binds_full_v2_wrapper_for_both_plan_versions(self):
        wrapper = v2_manifest()
        for version in (1, 2):
            with self.subTest(plan_version=version), LocalFixture(version) as f:
                f.dump("audit/deployment.json", build_record(wrapper))
                before = dict(f.store._data)
                result = stage2.freeze({"success": True, "projects": [{"projectId": 17}]}, plan_file=f.root / "plan.json", preview=True)
                self.assertEqual(result["deployment_hash"], content_hash(wrapper))
                self.assertNotEqual(result["deployment_hash"], content_hash(MANIFEST))
                self.assertEqual(stage2.local_deployment_preflight(), wrapper)
                self.assertEqual(f.store._data, before)
                self.assertFalse(result["budget_admission_performed"])

    def test_v2_local_source_eof_change_cannot_pass_worker_policy(self):
        for raw in (SOURCE.rstrip(b"\n"), SOURCE + b"\n", SOURCE.replace(b"1", b"2")):
            with self.subTest(source=raw), LocalFixture(2) as f:
                f.dump("audit/deployment.json", build_record(v2_manifest()))
                (f.root / "cloud/stub.py").write_bytes(raw)
                before = dict(f.store._data)
                with self.assertRaises(ValueError):
                    stage2.local_deployment_preflight()
                self.assertEqual(f.store._data, before)

    def test_v2_complete_inventory_excludes_both_fixed_inputs_but_no_other_file(self):
        with LocalFixture(2) as f:
            wrapper = v2_manifest()
            f.dump("audit/deployment.json", build_record(wrapper))
            for name in ("_engineering_task_input.py", "_collection_task_input.py"):
                (f.root / "cloud" / name).write_bytes(b'TASK_INPUT_JSON = "synthetic"\n')
            self.assertEqual(stage2.local_deployment_preflight(), wrapper)
            (f.root / "cloud/extra.py").write_bytes(b"extra = 1\n")
            with self.assertRaises(ValueError):
                stage2.local_deployment_preflight()

    def test_legacy_inventory_policy_and_strict_eof_remain_unchanged(self):
        with LocalFixture(1) as f:
            self.assertEqual(stage2.local_deployment_preflight(), MANIFEST)
            (f.root / "cloud/_collection_task_input.py").write_bytes(b'x = 1\n')
            with self.assertRaises(ValueError):
                stage2.local_deployment_preflight()
            (f.root / "cloud/_collection_task_input.py").unlink()
            (f.root / "cloud/stub.py").write_bytes(SOURCE + b"\n")
            with self.assertRaises(ValueError):
                stage2.local_deployment_preflight()

    def test_original_engineering_admissions_restore_without_upgrade_or_live_build(self):
        for deployment_version in (1, 2):
            with self.subTest(deployment_version=deployment_version), LocalFixture(2) as f:
                expected = MANIFEST
                if deployment_version == 2:
                    expected = v2_manifest()
                    f.dump("audit/deployment.json", build_record(expected))
                    stage2.freeze({"success": True, "projects": [{"projectId": 17}]}, plan_file=f.root / "plan.json")
                    bridge = stage2.current_bridge()
                else:
                    bridge = f.bridge
                bridge.register()
                attempt = bridge.claim("research").attempt_id
                admission = stage2.prepare(bridge, attempt)
                self.assertEqual(admission["payload"]["deployment_manifest"], expected)
                before = dict(f.store._data)
                usage = f.registry.snapshot()["usage"]
                original = (f.root / admission["input_path"]).read_bytes()
                (f.root / "audit/deployment.json").unlink()
                (f.root / "cloud/stub.py").unlink()
                with patch.object(stage2, "joint_preflight", side_effect=AssertionError("Do not read today's sources")):
                    self.assertEqual(stage2.prepare(bridge, attempt), admission)
                self.assertEqual((f.root / admission["input_path"]).read_bytes(), original)
                self.assertEqual(f.store._data, before)
                self.assertEqual(f.registry.snapshot()["usage"], usage)

    def test_invalid_new_manifest_never_falls_back_to_legacy_map(self):
        for change in ({"schema_version": True}, {"source_identity_policy": "unapproved"}, {"files": {}}):
            with self.subTest(change=change), LocalFixture(2) as f:
                wrapper = v2_manifest()
                wrapper.update(change)
                f.dump("audit/deployment.json", build_record(wrapper))
                before = dict(f.store._data)
                with self.assertRaises(ValueError):
                    stage2.local_deployment_preflight()
                self.assertEqual(f.store._data, before)


class VersionedCollectionCLITests(unittest.TestCase):
    def test_v2_stale_EOF_or_body_blocks_freeze_without_writes_or_charge(self):
        for raw in (SOURCE + b"\n", SOURCE.replace(b"1", b"2")):
            with self.subTest(raw=raw), collection_fixture(v2_manifest()) as (root, store, registry):
                (root / "cloud/stub.py").write_bytes(raw)
                before = registry.snapshot()
                saved = dict(store._data)
                with self.assertRaises(ValueError):
                    freeze_collection()
                self.assertFalse((root / "audit/collection_current.json").exists())
                self.assertEqual(registry.snapshot(), before)
                self.assertEqual(store._data, saved)

    def test_v2_stale_source_blocks_precharge_and_first_prepare_without_writes(self):
        for operation in ("register-task", "claim-task", "prepare-task"):
            for raw in (SOURCE + b"\n", SOURCE.replace(b"1", b"2")):
                with self.subTest(operation=operation, raw=raw), collection_fixture(v2_manifest()) as (root, store, registry):
                    freeze_collection()
                    bridge = collection_cli.current_bridge(field_catalog=CAT)
                    if operation in {"claim-task", "prepare-task"}:
                        bridge.register()
                    if operation == "prepare-task":
                        attempt = bridge.claim().attempt_id
                    (root / "cloud/stub.py").write_bytes(raw)
                    before = registry.snapshot()
                    saved = dict(store._data)
                    with self.assertRaises(ValueError):
                        args = NS(command=operation, attempt=attempt if operation == "prepare-task" else None,
                                  allocation="normal", retry_of=None, reason=None)
                        collection_cli.execute_metadata_command(args, field_catalog=CAT)
                    self.assertEqual(registry.snapshot(), before)
                    self.assertEqual(store._data, saved)
                    self.assertFalse((root / "audit/collection_task_inputs").exists())

    def test_new_freeze_and_prepare_share_the_v2_wrapper_hash(self):
        wrapper = v2_manifest()
        with collection_fixture(wrapper) as (root, store, registry):
            frozen = freeze_collection()
            bridge = collection_cli.current_bridge(field_catalog=CAT)
            self.assertEqual(bridge.plan.to_dict()["deployment_hash"], content_hash(wrapper))
            self.assertEqual(registry.snapshot()["usage"]["configurations"]["total"], 0)
            self.assertFalse(frozen["configuration_registered"])
            collection_cli.verify_current_source(bridge)
            bridge.register()
            attempt = bridge.claim().attempt_id
            admission = collection_cli.prepare_task(bridge, attempt)
            self.assertEqual(admission["payload"]["deployment_manifest"], wrapper)
            self.assertEqual(admission["deployment"]["deployment_hash"], content_hash(wrapper))
            self.assertEqual(collection_cli.admitted_input(bridge, attempt), admission)
            before = dict(store._data)
            usage = registry.snapshot()["usage"]
            (root / "audit/deployment.json").unlink()
            with patch.object(collection_cli, "execution_source_manifest", side_effect=AssertionError("Recovery cannot refreeze")):
                self.assertEqual(collection_cli.prepare_task(bridge, attempt), admission)
            self.assertEqual(store._data, before)
            self.assertEqual(registry.snapshot()["usage"], usage)

    def test_legacy_admission_keeps_original_bytes_after_new_wrapper_build(self):
        with collection_fixture() as (root, store, registry):
            freeze_collection()
            bridge = collection_cli.current_bridge(field_catalog=CAT)
            bridge.register()
            attempt = bridge.claim().attempt_id
            admission = collection_cli.prepare_task(bridge, attempt)
            self.assertEqual(admission["payload"]["deployment_manifest"], MANIFEST)
            original = (root / admission["input_path"]).read_bytes()
            (root / "audit/deployment.json").write_bytes(canonical_json(build_record(v2_manifest())))
            before = dict(store._data)
            with self.assertRaises(ValueError):
                collection_cli.verify_current_source(bridge)
            self.assertEqual(collection_cli.prepare_task(bridge, attempt), admission)
            self.assertEqual((root / admission["input_path"]).read_bytes(), original)
            self.assertEqual(store._data, before)

    def test_malformed_new_wrapper_rejects_before_frozen_pointer_or_debit(self):
        invalid = v2_manifest()
        invalid["files"]["stub.py"]["terminal_lf_count"] = True
        with collection_fixture(invalid) as (root, store, registry):
            before = registry.snapshot()
            with self.assertRaises(ValueError):
                freeze_collection()
            self.assertFalse((root / "audit/collection_current.json").exists())
            self.assertEqual(registry.snapshot(), before)

    def test_v2_admission_tampering_cannot_be_rebound_to_current_wrapper(self):
        with collection_fixture(v2_manifest()) as (root, store, registry):
            freeze_collection()
            bridge = collection_cli.current_bridge(field_catalog=CAT)
            bridge.register()
            attempt = bridge.claim().attempt_id
            admission = collection_cli.prepare_task(bridge, attempt)
            key = "collection/admitted-inputs/" + attempt + ".json"
            modified = deepcopy(admission)
            modified["payload"]["deployment_manifest"]["files"]["stub.py"]["source_sha256"] = "e" * 64
            store._data[key] = canonical_json(modified)
            before = dict(store._data)
            with self.assertRaises(ValueError):
                collection_cli.admitted_input(bridge, attempt)
            self.assertEqual(store._data, before)


class VersionedProjectReadbackTests(unittest.TestCase):
    def check(self, files=None, manifest=None, input_hash=None):
        manifest = v2_manifest() if manifest is None else manifest
        return deployment_preflight.read_project_preflight(project_tool(files), projects(), manifest,
            content_hash(manifest), project_id=17, input_sha256=input_hash)

    def test_v2_native_match_rebuilds_wrapper_and_keeps_only_metadata(self):
        result = self.check()
        self.assertTrue(result["preflight_passed"])
        self.assertEqual(result["observed_source_reference_hash"], content_hash(v2_manifest()))
        self.assertEqual(result["deployment_manifest_schema_version"], 2)
        self.assertEqual(result["source_identity_policy"], POLICY)
        self.assertEqual(result["files"], [{"path": "stub.py", "expected_sha256": MANIFEST["stub.py"], "observed_sha256": MANIFEST["stub.py"]}])
        self.assertFalse(result["ready_to_dispatch"])
        self.assertFalse(result["worker_source_verified"])
        self.assertNotIn(SECRET, json.dumps(result))
        self.assertNotIn(SOURCE.decode().strip(), json.dumps(result))

    def test_v2_project_eof_is_strict_even_when_canonical_hash_is_unchanged(self):
        for raw in (SOURCE.rstrip(b"\n"), SOURCE + b"\n"):
            with self.subTest(raw=raw):
                observed = v2_manifest(raw)
                self.assertEqual(observed["files"]["stub.py"]["canonical_sha256"], v2_manifest()["files"]["stub.py"]["canonical_sha256"])
                result = self.check([{"filePath": "stub.py", "content": raw.decode()}])
                self.assertFalse(result["preflight_passed"])
                self.assertEqual(result["different_paths"], ["stub.py"])
                self.assertEqual(result["observed_source_reference_hash"], content_hash(observed))
                self.assertNotEqual(result["observed_source_reference_hash"], result["expected_manifest_hash"])

    def test_v2_project_BOM_line_endings_and_notebook_contents_remain_nonsemantic(self):
        files = [{"filePath": "stub.py", "content": "\ufeffvalue = 1\r\n"},
                 {"filePath": "research.ipynb", "content": "OTHER_SYNTHETIC_NOTEBOOK_ROWS"}]
        self.assertEqual(self.check(files), self.check())

    def test_v2_collection_input_is_excluded_without_exporting_or_hashing_contents(self):
        baseline = self.check()
        for contents in (SECRET, 'TASK_INPUT_JSON = "OTHER_SYNTHETIC_PRIVATE_INPUT"\n', "INVALID SYNTAX '''"):
            with self.subTest(contents_kind=type(contents).__name__):
                files = [{"filePath": "stub.py", "content": SOURCE.decode()},
                         {"filePath": "research.ipynb", "content": SECRET},
                         {"filePath": "_collection_task_input.py", "content": contents}]
                result = self.check(files)
                self.assertTrue(result["preflight_passed"])
                self.assertEqual(result["files"], baseline["files"])
                self.assertEqual(result["observed_implementation_count"], 1)
                self.assertEqual(result["observed_source_reference_hash"], baseline["observed_source_reference_hash"])
                self.assertEqual(result["ignored_generated_input_file_count"], 1)
                self.assertNotIn(SECRET, json.dumps(result))
                self.assertNotIn("OTHER_SYNTHETIC_PRIVATE_INPUT", json.dumps(result))
                self.assertFalse(result["ready_to_dispatch"])
                self.assertFalse(result["budget_admission_performed"])

    def test_collection_input_cannot_satisfy_engineering_input_and_v1_policy_is_unchanged(self):
        text = 'TASK_INPUT_JSON = "synthetic"\n'
        digest = hashlib.sha256(text.encode()).hexdigest()
        files = [{"filePath": "stub.py", "content": SOURCE.decode()},
                 {"filePath": "_collection_task_input.py", "content": text}]
        result = self.check(files, input_hash=digest)
        self.assertTrue(result["source_reference_matches"])
        self.assertIsNone(result["input_observed_sha256"])
        self.assertFalse(result["input_binding_verified"])
        self.assertFalse(result["preflight_passed"])
        legacy = self.check(files, manifest=MANIFEST)
        self.assertFalse(legacy["preflight_passed"])
        self.assertEqual(legacy["unexpected_in_returned_reference"], ["_collection_task_input.py"])
        self.assertNotIn("ignored_generated_input_file_count", legacy)

    def test_v2_invalid_frozen_canonical_record_cannot_approve_matching_source_hash(self):
        wrapper = v2_manifest()
        wrapper["files"]["stub.py"]["canonical_sha256"] = "e" * 64
        result = self.check(manifest=wrapper)
        self.assertFalse(result["preflight_passed"])
        self.assertEqual(result["different_paths"], ["stub.py"])

    def test_v2_empty_reference_reports_missing_without_inventing_valid_manifest(self):
        result = self.check([])
        self.assertFalse(result["preflight_passed"])
        self.assertEqual(result["missing_from_returned_reference"], ["stub.py"])
        self.assertIsNone(result["observed_source_reference_hash"])

    def test_v2_input_hash_remains_exact_and_legacy_report_shape_is_unchanged(self):
        text = 'TASK_INPUT_JSON = "synthetic"\n'
        digest = hashlib.sha256(text.encode()).hexdigest()
        files = [{"filePath": "stub.py", "content": SOURCE.decode()},
                 {"filePath": "_engineering_task_input.py", "content": text + "\n"}]
        result = self.check(files, input_hash=digest)
        self.assertTrue(result["source_reference_matches"])
        self.assertFalse(result["input_binding_verified"])
        self.assertFalse(result["preflight_passed"])
        legacy = self.check(manifest=MANIFEST)
        self.assertNotIn("deployment_manifest_schema_version", legacy)
        self.assertNotIn("source_identity_policy", legacy)
        self.assertEqual(legacy["observed_source_reference_hash"], content_hash(MANIFEST))

    def test_v2_cli_prefers_wrapper_from_built_record_without_writes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            inputs = {"project.json": project_tool(), "projects.json": projects(), "manifest.json": build_record(v2_manifest())}
            for name, value in inputs.items():
                (root / name).write_bytes(canonical_json(value))
            before = {p.name: p.read_bytes() for p in root.iterdir()}
            argv = ["deployment_preflight.py", "--project-tool-file", str(root / "project.json"),
                    "--projects-file", str(root / "projects.json"), "--manifest-file", str(root / "manifest.json"),
                    "--deployment-hash", content_hash(v2_manifest()), "--project-id", "17"]
            output = io.StringIO()
            with patch.object(sys, "argv", argv), patch("sys.stdout", output), self.assertRaises(SystemExit) as status:
                deployment_preflight.main()
            self.assertEqual(status.exception.code, 0)
            self.assertTrue(json.loads(output.getvalue())["preflight_passed"])
            self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()}, before)
            self.assertNotIn(SECRET, output.getvalue())


if __name__ == "__main__":
    unittest.main()
