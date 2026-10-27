"""Joint pilot worker/receipt tests use invented snapshots and a fake SDK only."""
import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "cloud"), str(ROOT / "tests")]
from qresearch.artifacts import canonical_json, content_hash
from qresearch.engineering_tasks import EngineeringTaskBridge, EngineeringTaskPlan, JOINT_PROBE_FIELDS, JOINT_PROBE_CHECKS
from qresearch.engineering_receipts import research_observation, ReceiptParseError
import qresearch.engineering_data as worker
from test_engineering_receipts import context, research_tool
from test_wr13_annotations import ToyQuantBook, ToySymbol, registry


CATALOG = {name: value for name, value in json.loads((ROOT / "config/source_catalog.json").read_text(encoding="utf-8-sig"))["fields"].items()
           if name in JOINT_PROBE_FIELDS}


def joint_raw():
    raw = context("research")[0]["plan"]
    raw["schema_version"] = 2
    raw["required_checks"]["research"] += sorted(JOINT_PROBE_CHECKS)
    raw["collection_probe"] = {"collection_plan": {
        "schema_version": 1, "plan_id": "SYNTHETIC-joint-40day", "scope": "engineering",
        "source": "quantconnect_fundamental_universe", "data_version": "SYNTHETIC-joint-v1",
        "start": "2018-01-01T00:00:00-05:00", "end_exclusive": "2018-02-10T00:00:00-05:00",
        "timezone": "America/New_York", "fields": sorted(JOINT_PROBE_FIELDS), "calendar_days_per_request": 1,
        "max_batch_records": 1000, "max_records_per_window": 50000, "source_manifest_hash": raw["source_manifest_hash"]},
        "field_catalog": deepcopy(CATALOG)}
    return raw


class JointQuantBook(ToyQuantBook):
    """Invented daily universe even on weekends; not an exchange-calendar test."""
    def __init__(self):
        super().__init__()
        self.universe_settings = NS()
        self.universe_calls = 0

    def add_universe(self, selector):
        self.selector = selector
        return NS(symbol=ToySymbol("ALL"))

    def universe_history(self, universe, start, end, flatten=False):
        self.universe_calls += 1
        candidates = pd.date_range(pd.Timestamp(start).normalize(), pd.Timestamp(end).normalize(), freq="D")
        days = [day for day in candidates if pd.Timestamp(start) < day <= pd.Timestamp(end)]
        index = pd.MultiIndex.from_tuples([(universe.symbol, day) for day in days], names=["symbol", "time"])
        values = [[NS(symbol=ToySymbol(ticker), dollar_volume=123., has_fundamental_data=ticker == "AAPL",
                      time=day.to_pydatetime(), end_time=day.to_pydatetime()) for ticker in ("AAPL", "MSFT")] for day in days]
        return pd.Series(values, index=index, dtype=object)


class JointWorkerTests(unittest.TestCase):
    def build(self, directory):
        root = Path(directory)
        code = "SYNTHETIC = True\n"
        (root / "worker_stub.py").write_text(code, encoding="utf-8")
        manifest = {"worker_stub.py": hashlib.sha256(code.encode()).hexdigest()}
        raw = joint_raw(); raw["deployment_hash"] = content_hash(manifest)
        plan = EngineeringTaskPlan.from_dict(raw, discovered_project_ids=[17], probe_field_catalog=CATALOG)
        local, reg = registry()
        bridge = EngineeringTaskBridge(reg, plan); bridge.register()
        attempt = bridge.claim("research")
        payload = dict(bridge.payload(attempt), deployment_manifest=manifest)
        api = NS(Resolution=NS(DAILY="synthetic_daily"), DataNormalizationMode=NS(RAW="synthetic_raw"),
                 Globals=NS(version="synthetic_joint"))
        qb = JointQuantBook()
        return root, local, reg, bridge, attempt, payload, api, qb

    def run_worker(self, setup):
        root, local, reg, bridge, attempt, payload, api, qb = setup
        original = worker._context
        with patch.object(worker, "_context", side_effect=lambda value, stage: original(value, stage, source_root=root)):
            return worker.run_research_task(payload, api=api, quantbook_factory=lambda: qb)

    def test_actual_joint_worker_native_receipt_one_parent_debit_and_lean_dependency(self):
        with tempfile.TemporaryDirectory() as directory:
            setup = self.build(directory)
            root, local, reg, bridge, attempt, payload, api, qb = setup
            before = reg.snapshot()["usage"]
            wrapper = self.run_worker(setup)
            summary = wrapper["cloud_report"]["evidence"]["collection_probe"]
            self.assertEqual(summary["window_count"], 40)
            self.assertEqual(summary["record_count"], 80)
            self.assertEqual(qb.universe_calls, 40)
            self.assertEqual(summary["cache_only_source_fetch_calls"], 0)
            self.assertEqual(summary["missing_values"], dict.fromkeys(JOINT_PROBE_FIELDS, 0))
            deployment = {"source_manifest_hash": payload["identity"]["source_manifest_hash"],
                          "deployment_hash": payload["identity"]["deployment_hash"], "input_hash": "f" * 64}
            parsed = research_observation(payload, deployment, research_tool(payload, wrapper))
            bridge.record_submission(attempt, parsed["submission"])
            self.assertEqual(bridge.consume_completion(attempt, completion_source=lambda _: parsed["completion"]).status, "completed")
            self.assertEqual(reg.snapshot()["usage"], before)
            self.assertEqual(len(reg.snapshot()["attempts"]), 1)
            self.assertEqual(len(reg.snapshot()["config_ids"]), 1)
            self.assertNotIn(b"SYNTHETIC-AAPL", b"".join(local._data.values()))
            lean = bridge.claim("lean")
            self.assertTrue(lean.should_execute)
            self.assertEqual(bridge.payload(lean)["research_resolution"], wrapper["cloud_report"]["resolution"])

    def test_saved_probe_replay_has_no_new_source_and_keeps_original_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            setup = self.build(directory)
            root, local, reg, bridge, attempt, payload, api, qb = setup
            wrapper = self.run_worker(setup)
            original = wrapper["cloud_report"]["evidence"]["collection_probe"]
            calls = qb.universe_calls
            store = worker._cloud_store(qb.object_store)
            self.assertEqual(worker._run_collection_probe(qb, store, bridge.plan, payload, api=api), original)
            self.assertEqual(qb.universe_calls, calls)

    def test_probe_exception_is_not_a_manufactured_native_failure_or_completion(self):
        with tempfile.TemporaryDirectory() as directory:
            setup = self.build(directory)
            root, local, reg, bridge, attempt, payload, api, qb = setup
            before = reg.snapshot()
            with patch.object(qb, "universe_history", side_effect=RuntimeError("SYNTHETIC-SENSITIVE-SOURCE")):
                with self.assertRaises(ValueError) as caught:
                    self.run_worker(setup)
            self.assertNotIn("SYNTHETIC-SENSITIVE-SOURCE", str(caught.exception))
            self.assertEqual(reg.snapshot(), before)
            self.assertEqual(bridge._record(attempt)["status"], "started")
            self.assertNotIn(b"SYNTHETIC-SENSITIVE-SOURCE", b"".join(local._data.values()))

    def test_native_summary_rows_certification_and_parent_reference_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            setup = self.build(directory)
            root, local, reg, bridge, attempt, payload, api, qb = setup
            wrapper = self.run_worker(setup)
            deployment = {"source_manifest_hash": payload["identity"]["source_manifest_hash"],
                          "deployment_hash": payload["identity"]["deployment_hash"], "input_hash": "f" * 64}
            for mutate in (lambda x: x.update(rows=["SYNTHETIC-ROW"]),
                           lambda x: x.update(financial_vintage_certified=True),
                           lambda x: x.update(record_count=True),
                           lambda x: x.update(cache_only_source_fetch_calls=1),
                           lambda x: x["receipt_ref"].update(key="wrong/parent.json"),
                           lambda x: x.update(plan_hash="0" * 64)):
                with self.subTest(mutation=mutate):
                    altered = deepcopy(wrapper)
                    mutate(altered["cloud_report"]["evidence"]["collection_probe"])
                    altered["report_ref"]["sha256"] = content_hash(altered["cloud_report"])
                    before = reg.snapshot()
                    with self.assertRaises(ReceiptParseError):
                        research_observation(payload, deployment, research_tool(payload, altered))
                    self.assertEqual(reg.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
