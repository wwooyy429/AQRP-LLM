"""Synthetic occurrence-preserving workers and receipts; no provider access."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "cloud"), str(ROOT / "tests")]
from qresearch.artifacts import MemoryArtifactStore, content_hash
from qresearch.collection_execution import run_collection_task, stdout_marker, collection_research_observation
from qresearch.collection_tasks import CollectionTaskBridge, CollectionTaskPlan
from qresearch.engineering_receipts import ReceiptParseError, research_observation
from qresearch.historical_source import HistoricalSourceError, observed_liquidity_record
from qresearch.registry import Registry
from test_collection_tasks import CAT, raw_plan, manifest
from test_engineering_receipts import research_tool
import test_phase2_joint_plan as joint_fixture


def occurrence_joint():
    raw = joint_fixture.joint_raw()
    raw["collection_probe"]["collection_plan"].update(schema_version=2,
        observation_policy="retain_source_occurrences", data_version="SYNTHETIC-occurrence-v2")
    return raw


class OccurrenceTaskChainTests(unittest.TestCase):
    def setup_joint(self, directory):
        helper = joint_fixture.JointWorkerTests()
        with patch("test_phase2_joint_plan.joint_raw", return_value=occurrence_joint()):
            setup = helper.build(directory)
        qb = setup[-1]
        native = qb.universe_history

        def duplicates(*args, **kwargs):
            response = native(*args, **kwargs)
            for objects in response.values:
                same = deepcopy(objects[0])
                conflict = deepcopy(objects[0]); conflict.dollar_volume += 1
                objects.extend([same, conflict])
            return response

        qb.universe_history = duplicates
        return helper, setup

    def test_joint_retains_all_observations_reports_ambiguity_and_binds_same_plan_lean(self):
        with tempfile.TemporaryDirectory() as directory:
            helper, setup = self.setup_joint(directory)
            _, local, reg, bridge, attempt, payload, api, qb = setup
            wrapper = helper.run_worker(setup)
            summary = wrapper["cloud_report"]["evidence"]["collection_probe"]
            self.assertEqual((summary["schema_version"], summary["record_count"],
                summary["duplicate_projection_records"], summary["conflicting_projection_records"]), (2, 160, 80, 40))
            self.assertEqual(summary["observation_policy"], "retain_source_occurrences")
            self.assertEqual(summary["cache_only_source_fetch_calls"], 0)
            for name in ("research_certified", "full_historical_US200_certified", "financial_vintage_certified"):
                self.assertIs(summary[name], False)
            deployment = dict(source_manifest_hash=payload["identity"]["source_manifest_hash"],
                deployment_hash=payload["identity"]["deployment_hash"], input_hash="f" * 64)
            parsed = research_observation(payload, deployment, research_tool(payload, wrapper))
            bridge.record_submission(attempt, parsed["submission"])
            self.assertEqual(bridge.consume_completion(attempt, completion_source=lambda _: parsed["completion"]).status, "completed")
            self.assertTrue(bridge.claim("lean").should_execute)
            self.assertNotIn(b'"source_record_index"', b"".join(local._data.values()))
            self.assertNotIn(b"SYNTHETIC-AAPL", b"".join(local._data.values()))
            self.assertEqual(qb.universe_calls, 40)

    def test_joint_replay_cannot_drop_ambiguities_or_fetch_again(self):
        import qresearch.engineering_data as worker
        with tempfile.TemporaryDirectory() as directory:
            helper, setup = self.setup_joint(directory)
            _, _, _, bridge, _, payload, api, qb = setup
            result = helper.run_worker(setup)
            summary = result["cloud_report"]["evidence"]["collection_probe"]
            calls = qb.universe_calls
            self.assertEqual(worker._run_collection_probe(qb, worker._cloud_store(qb.object_store), bridge.plan,
                payload, api=api), summary)
            self.assertEqual(qb.universe_calls, calls)

    def test_joint_receipt_rejects_schema_downgrade_policy_and_ambiguity_tamper(self):
        with tempfile.TemporaryDirectory() as directory:
            helper, setup = self.setup_joint(directory)
            _, _, reg, _, _, payload, _, _ = setup
            wrapper = helper.run_worker(setup)
            deployment = dict(source_manifest_hash=payload["identity"]["source_manifest_hash"],
                deployment_hash=payload["identity"]["deployment_hash"], input_hash="f" * 64)

            def downgrade(summary):
                summary["schema_version"] = 1
                for name in ("observation_policy", "duplicate_projection_records", "conflicting_projection_records"):
                    summary.pop(name)

            for mutate in (downgrade, lambda s: s.update(observation_policy="deduplicate"),
                    lambda s: s.update(duplicate_projection_records=True),
                    lambda s: s.update(conflicting_projection_records=81),
                    lambda s: s.update(duplicate_projection_records=160),
                    lambda s: s.update(financial_vintage_certified=True),
                    lambda s: s.update(source_record_index=[1])):
                changed = deepcopy(wrapper)
                mutate(changed["cloud_report"]["evidence"]["collection_probe"])
                changed["report_ref"]["sha256"] = content_hash(changed["cloud_report"])
                before = reg.snapshot()
                with self.assertRaises(ReceiptParseError):
                    research_observation(payload, deployment, research_tool(payload, changed))
                self.assertEqual(reg.snapshot(), before)

    def test_standalone_occurrence_collection_keeps_counts_in_native_metadata_and_replays(self):
        raw = raw_plan()
        raw["collection_plan"].update(schema_version=2, observation_policy="retain_source_occurrences")
        plan = CollectionTaskPlan.from_dict(raw, discovered_project_ids=[17], field_catalog=CAT)
        local, cloud = MemoryArtifactStore(), MemoryArtifactStore()
        reg = Registry(local, {name: dict(normal=3, reserve=1, total=4)
            for name in ("configurations", "research", "lean")})
        bridge = CollectionTaskBridge(reg, plan); bridge.register()
        attempt = bridge.claim()
        payload = dict(bridge.payload(attempt), deployment_manifest=manifest())

        class Source:
            calls = 0

            def fetch(self, start, end, fields):
                self.calls += 1
                for index, value in enumerate((1, 1, 2)):
                    yield dict(sid="SYNTHETIC-DUPLICATE", snapshot_at=(start + pd.Timedelta(hours=9)).isoformat(),
                        source_record_index=index, values={"dollar_volume": value})

        source = Source()
        wrapper = run_collection_task(payload, field_catalog=CAT, store=cloud, source=source, synthetic=True)
        counts = wrapper["cloud_report"]["statistics"]
        self.assertEqual((counts["record_count"], counts["duplicate_projection_records"], counts["conflicting_projection_records"]), (6, 4, 2))
        marker = stdout_marker(wrapper, payload=payload, field_catalog=CAT)
        native = dict(tool_name="mcp__quantconnect__jupyter_execute_cell", arguments=dict(projectId=17, index=0),
            result=dict(structuredContent=dict(outputs=[dict(output_type="stream", name="stdout", text=marker)])))
        deployment = dict(source_manifest_hash=payload["identity"]["source_manifest_hash"],
            deployment_hash=payload["identity"]["deployment_hash"], input_hash="f" * 64)
        parsed = collection_research_observation(payload, deployment, native, field_catalog=CAT)
        self.assertEqual(parsed["completion"]["cloud_report"], wrapper["cloud_report"])
        self.assertEqual(run_collection_task(payload, field_catalog=CAT, store=cloud, synthetic=True), wrapper)
        self.assertEqual(source.calls, 2)
        self.assertNotIn("SYNTHETIC-DUPLICATE", json.dumps(parsed))

    def test_occurrence_projection_cannot_silently_enter_unique_observation_ingestion(self):
        row = dict(sid="SYNTHETIC-SID", snapshot_at="2018-01-03T00:00:00-05:00",
            source_record_index=0, values={"dollar_volume": 1})
        with self.assertRaises(HistoricalSourceError):
            observed_liquidity_record(row, session_close="2018-01-02T16:00:00-05:00")


if __name__ == "__main__":
    unittest.main()
