"""Independent synthetic joint-pilot boundaries; never calls a market provider.

These checks cover versioning, the one-parent budget contract and receipt
admission. The metadata fixtures are invented and do not certify cloud data.
"""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "cloud"), str(ROOT / "tests"), str(ROOT / "tools")]
from qresearch.artifacts import MemoryArtifactStore, content_hash
from qresearch.collection import HistoricalCollectionPlan
from qresearch.engineering_receipts import ReceiptParseError, research_observation
from qresearch.engineering_tasks import EngineeringTaskBridge, EngineeringTaskError, EngineeringTaskPlan
from qresearch.registry import Registry, RegistryError
from test_engineering_receipts import context as v1_context, report as metadata_report, research_tool, completed_tool, log_tools
from qresearch.engineering_receipts import backtest_observation
import stage2 as cli
import stage2_collection as collection_cli
import collection_task_cli as collection_task_cli


FIELDS = ("dollar_volume", "has_fundamental_data", "time", "end_time")
CATALOG = {key: value for key, value in json.loads(
    (ROOT / "config/source_catalog.json").read_text(encoding="utf-8-sig"))["fields"].items() if key in FIELDS}
SECRET = "JOINT-SYNTHETIC-ROW-MUST-NOT-ENTER-LEDGER"
FLAGS = ("full_historical_US200_certified", "actual_availability_certified", "research_certified",
         "row_values_exported", "financial_vintage_certified")


def joint_document():
    raw = deepcopy(v1_context("research")[0]["plan"])
    raw["schema_version"] = 2
    raw["plan_id"] = "synthetic-joint-boundary"
    raw["required_checks"]["research"] += ["collection_windows_completed", "collection_cache_only_replay", "collection_nonempty"]
    raw["collection_probe"] = {"collection_plan": {
        "schema_version": 1, "plan_id": "synthetic-joint-observation", "scope": "engineering",
        "source": "quantconnect_fundamental_universe", "data_version": "synthetic-joint-v1",
        "start": "2018-01-01T00:00:00-05:00", "end_exclusive": "2018-02-10T00:00:00-05:00",
        "timezone": "America/New_York", "fields": list(FIELDS), "calendar_days_per_request": 1,
        "max_batch_records": 1000, "max_records_per_window": 50000,
        "source_manifest_hash": raw["source_manifest_hash"]}, "field_catalog": deepcopy(CATALOG)}
    return raw


def freeze(raw=None, *, catalog=None):
    return EngineeringTaskPlan.from_dict(raw or joint_document(), discovered_project_ids=[17],
        probe_field_catalog=CATALOG if catalog is None else catalog)


def synthetic_registry():
    store = MemoryArtifactStore()
    limits = {key: {"normal": 8, "reserve": 2, "total": 10} for key in ("configurations", "research", "lean")}
    return store, Registry(store, limits)


def wrapper(payload):
    result = metadata_report(payload)
    plan = EngineeringTaskPlan.from_dict(payload["plan"], discovered_project_ids=[17])
    cp = HistoricalCollectionPlan.from_dict(payload["plan"]["collection_probe"]["collection_plan"], field_catalog=CATALOG)
    summary = {"schema_version": 1, "plan_hash": cp.hash,
        "receipt_ref": {"key": payload["plan"]["report_namespace"] + "/collection-probes/" + plan.hash + "/" + payload["identity"]["attempt_id"] + ".json",
                        "sha256": "e" * 64},
        "window_count": 40, "record_count": 40, "source_fetch_calls": 40, "reused_windows": 0,
        "empty_windows": 0, "cache_only_source_fetch_calls": 0, "missing_values": {key: 0 for key in FIELDS},
        **{key: False for key in FLAGS}}
    result["cloud_report"]["evidence"]["collection_probe"] = summary
    rehash(result)
    return result


def rehash(result):
    result["report_ref"]["sha256"] = content_hash(result["cloud_report"])


class JointPlanBoundaryTests(unittest.TestCase):
    def test_v1_known_answer_identity_and_exact_shape_retained(self):
        raw = v1_context("research")[0]["plan"]
        plan = EngineeringTaskPlan.from_dict(raw, discovered_project_ids=[17])
        self.assertEqual(plan.hash, "b9852d1dd435e395874f2b6b1e6da731498dd7c3367dfdeebc418e47af2ba48c")
        self.assertEqual(plan.request_hash, "dd5945668e98b176d6bc38388d46ca4076b817ad2c7aea84b41aa5b06219cc90")
        self.assertEqual(plan.to_dict(), raw)
        injected = deepcopy(raw)
        injected["collection_probe"] = joint_document()["collection_probe"]
        with self.assertRaises(ValueError):
            EngineeringTaskPlan.from_dict(injected, discovered_project_ids=[17])
        missing = joint_document()
        missing.pop("collection_probe")
        with self.assertRaises(ValueError):
            freeze(missing)

    def test_v2_canonical_immutable_and_probe_semantics_bind_request(self):
        raw = joint_document()
        plan = freeze(raw)
        before = plan.to_dict()
        raw["collection_probe"]["field_catalog"]["dollar_volume"]["unit"] = "mutated-after-freeze"
        raw["collection_probe"]["collection_plan"]["fields"].clear()
        copied = plan.to_dict()
        copied["collection_probe"]["field_catalog"].clear()
        self.assertEqual(plan.to_dict(), before)
        changed = joint_document()
        changed["collection_probe"]["collection_plan"]["data_version"] = "another-explicit-source-version"
        other = freeze(changed)
        self.assertNotEqual(plan.hash, other.hash)
        self.assertNotEqual(plan.request_hash, other.request_hash)

    def test_probe_cannot_widen_frozen_dates_clock_or_resource_bounds(self):
        mutations = [
            ("start", "2017-12-31T00:00:00-05:00"), ("end_exclusive", "2018-02-11T00:00:00-05:00"),
            ("end_exclusive", "2024-01-02T00:00:00-05:00"), ("start", "2018-01-01T01:00:00-05:00"),
            ("timezone", "UTC"), ("calendar_days_per_request", 2), ("max_batch_records", 1001),
            ("max_records_per_window", 50001), ("max_batch_records", True),
            ("max_records_per_window", 0), ("scope", "research"), ("source_manifest_hash", "0" * 64)]
        for key, value in mutations:
            with self.subTest(field=key, value=value):
                raw = joint_document()
                raw["collection_probe"]["collection_plan"][key] = value
                with self.assertRaises(ValueError):
                    freeze(raw)

    def test_catalog_fields_and_unknown_flags_cannot_be_self_authorized(self):
        mutations = [
            lambda x: x["collection_probe"].update(rows=[SECRET]),
            lambda x: x["collection_probe"]["collection_plan"].update(actual_availability_certified=True),
            lambda x: x["collection_probe"]["collection_plan"]["fields"].append("close"),
            lambda x: x["collection_probe"]["field_catalog"].update(close=deepcopy(CATALOG["dollar_volume"])),
            lambda x: x["collection_probe"]["collection_plan"]["fields"].remove("has_fundamental_data"),
            lambda x: x["collection_probe"]["field_catalog"]["dollar_volume"].update(unit="unreviewed-unit"),
            lambda x: x["required_checks"]["research"].remove("collection_cache_only_replay"),
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(case=index):
                raw = joint_document(); mutate(raw)
                with self.assertRaises(ValueError):
                    freeze(raw)

    def test_unresolved_project_prevents_joint_registration_without_charge(self):
        store, registry = synthetic_registry()
        old = EngineeringTaskBridge(registry, EngineeringTaskPlan.from_dict(v1_context("research")[0]["plan"], discovered_project_ids=[17]))
        old.register(); old.claim("research")
        before = registry.snapshot(); saved = dict(store._data)
        with self.assertRaises((ValueError, RegistryError)):
            EngineeringTaskBridge(registry, freeze()).register()
        self.assertEqual(registry.snapshot(), before)
        self.assertEqual(store._data, saved)

    def test_one_parent_configuration_and_research_attempt_no_child_debits(self):
        store, registry = synthetic_registry()
        bridge = EngineeringTaskBridge(registry, freeze())
        bridge.register()
        registered = registry.snapshot()
        self.assertEqual(registered["usage"]["configurations"]["total"], 1)
        self.assertEqual(len(registered["config_ids"]), 1)
        with self.assertRaises(EngineeringTaskError):
            bridge.claim("lean")
        self.assertEqual(registry.snapshot(), registered)
        attempt = bridge.claim("research")
        self.assertTrue(attempt.should_execute)
        used = registry.snapshot()
        self.assertEqual(used["usage"]["configurations"]["total"], 1)
        self.assertEqual(used["usage"]["research"]["total"], 1)
        self.assertEqual(used["usage"]["lean"]["total"], 0)
        self.assertEqual(bridge.claim("research").attempt_id, attempt.attempt_id)
        self.assertEqual(registry.snapshot(), used)

    def test_malformed_joint_package_is_rejected_before_registry_charge(self):
        for mutate in (lambda x: x["collection_probe"].update(rows=[SECRET]),
                       lambda x: x["collection_probe"]["collection_plan"].update(source_manifest_hash="0" * 64),
                       lambda x: x["collection_probe"]["collection_plan"].update(end_exclusive="2024-01-02T00:00:00-05:00")):
            with self.subTest(mutation=mutate):
                store, registry = synthetic_registry()
                before = registry.snapshot(); saved = dict(store._data)
                raw = joint_document(); mutate(raw)
                with self.assertRaises(ValueError):
                    registry.register_config({"engineering_task_schema_version": 1, "plan": raw})
                self.assertEqual(registry.snapshot(), before)
                self.assertEqual(store._data, saved)


class JointReceiptBoundaryTests(unittest.TestCase):
    def setup_context(self):
        store, registry = synthetic_registry()
        bridge = EngineeringTaskBridge(registry, freeze())
        bridge.register(); attempt = bridge.claim("research")
        payload = bridge.payload(attempt)
        deployment = {"source_manifest_hash": payload["identity"]["source_manifest_hash"],
            "deployment_hash": payload["identity"]["deployment_hash"], "input_hash": "f" * 64}
        return store, registry, bridge, attempt, payload, deployment

    def test_native_success_requires_bound_probe_summary_and_retains_parent_debit(self):
        store, registry, bridge, attempt, payload, deployment = self.setup_context()
        before = registry.snapshot()
        observed = research_observation(payload, deployment, research_tool(payload, wrapper(payload)))
        bridge.record_submission(attempt, observed["submission"])
        self.assertEqual(bridge.consume_completion(attempt, completion_source=lambda _: observed["completion"]).status, "completed")
        self.assertEqual(registry.snapshot()["usage"], before["usage"])
        self.assertNotIn(SECRET.encode(), b"".join(store._data.values()))
        next_attempt = bridge.claim("lean")
        self.assertTrue(next_attempt.should_execute)
        self.assertEqual(registry.snapshot()["usage"]["configurations"]["total"], 1)
        self.assertEqual(registry.snapshot()["usage"]["lean"]["total"], 1)

    def test_rehashed_invalid_probe_summaries_cannot_complete_or_write_rows(self):
        mutations = [
            lambda e: e.pop("collection_probe"),
            lambda e: e["collection_probe"].update(rows=[SECRET]),
            lambda e: e["collection_probe"].update(plan_hash="0" * 64),
            lambda e: e["collection_probe"]["receipt_ref"].update(key="wrong/probe.json"),
            lambda e: e["collection_probe"].update(window_count=41),
            lambda e: e["collection_probe"].update(source_fetch_calls=41),
            lambda e: e["collection_probe"].update(cache_only_source_fetch_calls=1),
            lambda e: e["collection_probe"].update(record_count=True),
            lambda e: e["collection_probe"].update(record_count=0),
            lambda e: e["collection_probe"].update(reused_windows=1),
            lambda e: e["collection_probe"]["missing_values"].update(dollar_volume=41),
        ] + [lambda e, name=name: e["collection_probe"].update({name: True}) for name in FLAGS]
        for index, mutate in enumerate(mutations):
            with self.subTest(case=index):
                store, registry, bridge, attempt, payload, deployment = self.setup_context()
                before = registry.snapshot(); saved = dict(store._data)
                result = wrapper(payload)
                mutate(result["cloud_report"]["evidence"]); rehash(result)
                with self.assertRaises((ValueError, ReceiptParseError)):
                    research_observation(payload, deployment, research_tool(payload, result))
                self.assertEqual(registry.snapshot(), before)
                self.assertEqual(store._data, saved)
                self.assertNotIn(SECRET.encode(), b"".join(store._data.values()))

    def test_probe_cannot_be_injected_into_legacy_or_lean_receipt(self):
        _, _, _, _, joint_research, _ = self.setup_context()
        summary = wrapper(joint_research)["cloud_report"]["evidence"]["collection_probe"]
        legacy_research, research_deployment = v1_context("research")
        legitimate = metadata_report(legacy_research)
        research_observation(legacy_research, research_deployment, research_tool(legacy_research, legitimate))
        legitimate["cloud_report"]["evidence"]["collection_probe"] = deepcopy(summary)
        rehash(legitimate)
        with self.assertRaises(ReceiptParseError):
            research_observation(legacy_research, research_deployment, research_tool(legacy_research, legitimate))
        for version in (1, 2):
            with self.subTest(version=version):
                payload, deployment = v1_context("lean")
                if version == 2:
                    plan = freeze()
                    document = plan.to_dict()
                    payload["plan"] = document
                    payload["identity"].update(plan_hash=plan.hash, data_request_hash=plan.request_hash,
                        config_id=content_hash({"engineering_task_schema_version": 1, "plan": document}))
                    payload["report_key"] = document["report_namespace"] + "/reports/" + plan.hash + "/lean/" + payload["identity"]["attempt_id"] + ".json"
                legitimate = metadata_report(payload)
                backtest_observation(payload, deployment, "native-backtest-id", completed_tool(), log_tools(payload, legitimate))
                legitimate["cloud_report"]["evidence"]["collection_probe"] = deepcopy(summary)
                rehash(legitimate)
                with self.assertRaises(ReceiptParseError):
                    backtest_observation(payload, deployment, "native-backtest-id", completed_tool(), log_tools(payload, legitimate))


class JointFreezeBoundaryTests(unittest.TestCase):
    def test_pending_project_freeze_preserves_old_pointer_and_preview_is_readonly(self):
        store, registry = synthetic_registry()
        old_plan = EngineeringTaskPlan.from_dict(v1_context("research")[0]["plan"], discovered_project_ids=[17])
        old = EngineeringTaskBridge(registry, old_plan)
        old.register(); old.claim("research")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config").mkdir(); (root / "audit").mkdir()
            (root / "config/quantconnect.json").write_text(json.dumps({"active_project_id": 17}), encoding="utf-8")
            (root / "audit/deployment.json").write_text(json.dumps({"source_files": {"stub.py": "b" * 64}}), encoding="utf-8")
            plan_file = root / "joint.json"
            plan_file.write_text(json.dumps(joint_document()), encoding="utf-8")
            pointer = root / "audit/engineering_current.json"
            original = (json.dumps({"schema_version": 1, "plan_hash": old_plan.hash,
                "note": "synthetic original pointer must survive a refused freeze"}) + "\n").encode()
            pointer.write_bytes(original)
            before = registry.snapshot(); saved = dict(store._data)
            projects = {"success": True, "projects": [{"projectId": 17}]}
            with patch.object(cli, "ROOT", root), patch.object(cli, "open_registry", return_value=registry), \
                 patch.object(cli, "source_manifest", return_value={"source_hash": "a" * 64}), \
                 patch.object(collection_task_cli, "execution_source_manifest", return_value={"source_hash": "a" * 64}), \
                 patch.object(collection_cli, "catalog", return_value=deepcopy(CATALOG)):
                preview = cli.freeze(projects, plan_file=plan_file, preview=True)
                self.assertFalse(preview["ready_to_dispatch"])
                self.assertEqual(pointer.read_bytes(), original)
                self.assertEqual(store._data, saved)
                with self.assertRaises((ValueError, RegistryError)):
                    cli.freeze(projects, plan_file=plan_file)
            self.assertEqual(pointer.read_bytes(), original)
            self.assertEqual(store._data, saved)
            self.assertEqual(registry.snapshot(), before)

    def test_freeze_cannot_replace_trusted_catalog_even_before_any_charge(self):
        store, registry = synthetic_registry()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config").mkdir(); (root / "audit").mkdir()
            (root / "config/quantconnect.json").write_text(json.dumps({"active_project_id": 17}), encoding="utf-8")
            (root / "audit/deployment.json").write_text(json.dumps({"source_files": {"stub.py": "b" * 64}}), encoding="utf-8")
            raw = joint_document()
            raw["collection_probe"]["field_catalog"]["dollar_volume"]["unit"] = "untrusted-injected-unit"
            plan_file = root / "joint.json"
            plan_file.write_text(json.dumps(raw), encoding="utf-8")
            before = registry.snapshot(); saved = dict(store._data)
            with patch.object(cli, "ROOT", root), patch.object(cli, "open_registry", return_value=registry), \
                 patch.object(cli, "source_manifest", return_value={"source_hash": "a" * 64}), \
                 patch.object(collection_task_cli, "execution_source_manifest", return_value={"source_hash": "a" * 64}), \
                 patch.object(collection_cli, "catalog", return_value=deepcopy(CATALOG)):
                with self.assertRaises(ValueError):
                    cli.freeze({"success": True, "projects": [{"projectId": 17}]}, plan_file=plan_file)
            self.assertFalse((root / "audit/engineering_current.json").exists())
            self.assertEqual(store._data, saved)
            self.assertEqual(registry.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
