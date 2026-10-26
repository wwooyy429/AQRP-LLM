"""WR-13 text annotation boundaries and complete synthetic receipt chains.

No market/provider/SDK calls occur. The old-worker test uses an invented weekday
calendar and constant history solely to exercise the existing Research worker.
"""
import base64
from copy import deepcopy
from datetime import datetime, time, timedelta
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
from qresearch.artifacts import MemoryArtifactStore, canonical_json, content_hash
from qresearch.collection_execution import run_collection_task, stdout_marker, collection_research_observation
from qresearch.collection_tasks import CollectionTaskPlan, CollectionTaskBridge
import qresearch.engineering_data as old_worker
from qresearch.engineering_receipts import ReceiptParseError, _native, _research_stdout, research_observation
from qresearch.engineering_tasks import EngineeringTaskPlan, EngineeringTaskBridge
from qresearch.registry import Registry
from test_engineering_receipts import context as legacy_context


MARKER = "AQRP_ENGINEERING_JSON e30="
SECRET = "WR13-SYNTHETIC-ANNOTATION-ROW"
MISSING = object()
STANDARD = {"audience": ["assistant"], "priority": 0.25, "lastModified": "2026-10-26T00:00:00Z"}
CATALOG = {"dollar_volume": {"kind": "number", "role": "synthetic", "unit": "USD", "period_accessor": None}}


def text_node(marker=MARKER, annotations=MISSING):
    result = {"type": "text", "text": marker}
    if annotations is not MISSING:
        result["annotations"] = deepcopy(annotations)
    return result


def shape(node, name):
    return node if name == "root" else {name: [node], "status": "completed", "success": True}


def envelope(native, *, mirror=True, outer=MISSING):
    result = {"structuredContent": native}
    if mirror:
        block = {"type": "text", "text": json.dumps(native, sort_keys=True, indent=2)}
        if outer is not MISSING:
            block["annotations"] = deepcopy(outer)
        result["content"] = [block]
    return result


def registry():
    store = MemoryArtifactStore()
    return store, Registry(store, {name: {"normal": 8, "reserve": 2, "total": 10}
                                  for name in ("configurations", "research", "lean")})


class FakeStore:
    def __init__(self):
        self.data = {}

    def contains_key(self, key):
        return key in self.data

    def save_bytes(self, key, value):
        self.data[key] = bytes(value)
        return True

    def read_bytes(self, key):
        return self.data[key]


class ToyHours:
    def is_date_open(self, day):
        return day.weekday() < 5

    def get_next_market_close(self, day, extended):
        return datetime.combine(day.date(), time(16))

    def get_previous_trading_day(self, day):
        result = day - timedelta(days=1)
        while not self.is_date_open(result):
            result -= timedelta(days=1)
        return result

    def get_next_trading_day(self, day):
        result = day + timedelta(days=1)
        while not self.is_date_open(result):
            result += timedelta(days=1)
        return result


class ToySymbol:
    def __init__(self, ticker):
        self.id, self.value = "SYNTHETIC-" + ticker, ticker


class ToyQuantBook:
    def __init__(self):
        self.object_store, self.settings, self.securities = FakeStore(), NS(), {}
        self.time, self.calls = datetime(2019, 1, 1), 0

    def set_time_zone(self, zone):
        self.zone = zone

    def set_start_date(self, year, month, day):
        self.time = datetime(year, month, day)

    def set_end_date(self, *args):
        pass

    def add_equity(self, ticker, resolution, **kwargs):
        symbol = ToySymbol(ticker)
        security = NS(symbol=symbol, exchange=NS(hours=ToyHours()))
        self.securities[symbol] = security
        return security

    def history(self, symbols, start, end, resolution, **kwargs):
        self.calls += 1
        index = pd.MultiIndex.from_tuples([(symbol, day.to_pydatetime().replace(hour=16))
                    for symbol in symbols for day in pd.bdate_range(start, end, inclusive="left")],
                    names=["symbol", "time"])
        return pd.DataFrame({"close": 1., "volume": 100.}, index=index)


class WR13AnnotationTests(unittest.TestCase):
    def extract(self, annotations=MISSING, *, wrapper="content", outer=MISSING):
        return _research_stdout(_native(envelope(shape(text_node(annotations=annotations), wrapper), outer=outer)))

    def test_absent_empty_none_and_standard_annotation_controls(self):
        values = [MISSING, None, {}, {"audience": []}, {"audience": ["user", "assistant", "user"]},
                  {"priority": 0}, {"priority": 1.0}, STANDARD,
                  {"lastModified": "2026-10-26T12:34:56.123456+05:30"}]
        for wrapper in ("content", "outputs", "root"):
            for value in values:
                with self.subTest(wrapper=wrapper, annotations=repr(value)):
                    self.assertEqual(self.extract(value, wrapper=wrapper), "e30=")

    def test_standard_annotations_on_outer_text_carrier_are_preserved(self):
        for value in ({}, None, STANDARD, {"audience": [], "priority": 0.0}):
            with self.subTest(annotations=value):
                self.assertEqual(self.extract(STANDARD, outer=value), "e30=")

    def test_unknown_row_error_and_output_annotations_rejected_at_every_entry(self):
        extras = [{"rows": [{"sid": SECRET, "close": 123.45}]}, {"error": SECRET},
                  {"outputs": [{"output_type": "error", "evalue": SECRET}]},
                  {"_meta": {"rows": [SECRET]}}, {"audience": ["assistant"], "unexpected": None}]
        for wrapper in ("content", "outputs", "root"):
            for annotation in extras:
                with self.subTest(wrapper=wrapper, keys=list(annotation)):
                    with self.assertRaises(ReceiptParseError) as caught:
                        self.extract(annotation, wrapper=wrapper)
                    self.assertNotIn(SECRET, str(caught.exception))

    def test_annotation_container_and_field_types_are_not_ignored(self):
        invalid = [[], "annotation", 0, False,
                   {"audience": "assistant"}, {"audience": ["system"]}, {"audience": [True]},
                   {"audience": [{"role": "assistant", "rows": [SECRET]}]},
                   {"priority": True}, {"priority": "0.25"}, {"priority": -0.01}, {"priority": 1.01},
                   {"priority": {"value": .25, "rows": [SECRET]}},
                   {"lastModified": None}, {"lastModified": 123}, {"lastModified": {"text": SECRET}}]
        for annotation in invalid:
            with self.subTest(annotations=annotation), self.assertRaises(ReceiptParseError):
                self.extract(annotation)

    def test_nonfinite_priority_is_rejected_even_in_direct_extractor(self):
        for value in (float("nan"), float("inf"), -float("inf")):
            with self.subTest(value=value), self.assertRaises(ReceiptParseError):
                _research_stdout(shape(text_node(annotations={"priority": value}), "content"))

    def test_obviously_invalid_modification_dates_are_rejected(self):
        for value in ("", "not-a-date", "2026-13-01T00:00:00Z", "2023-02-29T00:00:00Z", "2026-10-26T25:00:00Z"):
            with self.subTest(value=value), self.assertRaises(ReceiptParseError):
                self.extract({"lastModified": value})

    def test_annotations_inside_recursive_wrapper_and_json_text_are_checked(self):
        invalid = text_node(annotations={"rows": [SECRET]})
        variants = [{"results": [{"cells": [{"output": {"content": [invalid]}}]}]},
                    text_node(json.dumps({"outputs": [invalid]}), annotations=STANDARD)]
        for value in variants:
            with self.subTest(shape=list(value)), self.assertRaises(ReceiptParseError):
                _research_stdout(_native(envelope(value)))

    def test_text_content_is_string_not_a_recursive_object_or_array(self):
        for value in ({"outputs": [text_node()]}, [MARKER], None, True, 17):
            with self.subTest(value_type=type(value).__name__), self.assertRaises(ReceiptParseError):
                _research_stdout({"type": "text", "text": value, "annotations": {}})


class WR13ReceiptChainTests(unittest.TestCase):
    def build(self, kind, root):
        code = "SYNTHETIC = True\n"
        (root / "worker_stub.py").write_text(code, encoding="utf-8")
        manifest = {"worker_stub.py": hashlib.sha256(code.encode()).hexdigest()}
        local, reg = registry()
        if kind == "collection":
            cp = {"schema_version": 1, "plan_id": "WR13-SYNTHETIC-SNAPSHOT", "scope": "engineering",
                  "source": "quantconnect_fundamental_universe", "data_version": "SYNTHETIC-v1",
                  "start": "2018-01-03T00:00:00-05:00", "end_exclusive": "2018-01-04T00:00:00-05:00",
                  "timezone": "America/New_York", "fields": list(CATALOG), "calendar_days_per_request": 1,
                  "max_batch_records": 1, "max_records_per_window": 3, "source_manifest_hash": "a" * 64}
            raw = {"schema_version": 1, "task_kind": "historical_collection", "scope": "engineering",
                   "plan_id": "WR13-SYNTHETIC-TASK", "project_id": 17, "source_manifest_hash": "a" * 64,
                   "deployment_hash": content_hash(manifest), "collection_plan": cp, "field_catalog": CATALOG,
                   "report_namespace": "wr13/synthetic", "max_retries": 1}
            plan = CollectionTaskPlan.from_dict(raw, discovered_project_ids=[17], field_catalog=CATALOG)
            bridge = CollectionTaskBridge(reg, plan); bridge.register(); attempt = bridge.claim()
            payload = dict(bridge.payload(attempt), deployment_manifest=manifest)

            class SyntheticSource:
                def fetch(self, start, end, fields):
                    yield {"sid": "WR13-SYNTHETIC-CLOUD-SID", "snapshot_at": start.isoformat(), "values": {"dollar_volume": 0}}

            wrapper = run_collection_task(payload, field_catalog=CATALOG, source=SyntheticSource(),
                store=MemoryArtifactStore(), synthetic=True, source_root=root)
            marker = stdout_marker(wrapper, payload=payload, field_catalog=CATALOG)
        else:
            raw = legacy_context("research")[0]["plan"]
            raw["deployment_hash"] = content_hash(manifest)
            plan = EngineeringTaskPlan.from_dict(raw, discovered_project_ids=[17])
            bridge = EngineeringTaskBridge(reg, plan); bridge.register(); attempt = bridge.claim("research")
            payload = dict(bridge.payload(attempt), deployment_manifest=manifest)
            api = NS(Resolution=NS(DAILY="synthetic_daily"), DataNormalizationMode=NS(RAW="synthetic_raw"),
                     Globals=NS(version="synthetic_engine"))
            original = old_worker._context
            with patch.object(old_worker, "_context", side_effect=lambda value, stage: original(value, stage, source_root=root)):
                wrapper = old_worker.run_research_task(payload, api=api, quantbook_factory=ToyQuantBook)
            marker = "AQRP_ENGINEERING_JSON " + base64.b64encode(canonical_json(wrapper)).decode("ascii")
        deployment = {"source_manifest_hash": "a" * 64, "deployment_hash": content_hash(manifest), "input_hash": "f" * 64}
        return local, reg, bridge, attempt, payload, deployment, marker

    def exercise(self, kind):
        for name in ("content", "outputs", "root"):
            for annotations, accepted in ((MISSING, True), (STANDARD, True), ({"rows": [{"sid": SECRET, "close": 123.45}]}, False),
                                          ({"error": SECRET}, False)):
                with self.subTest(kind=kind, entry=name, accepted=accepted), tempfile.TemporaryDirectory() as directory:
                    local, reg, bridge, attempt, payload, deployment, marker = self.build(kind, Path(directory))
                    native = shape(text_node(marker, annotations), name)
                    tool = {"tool_name": "mcp__quantconnect__jupyter_execute_cell", "arguments": {"projectId": 17, "index": 2},
                            "result": envelope(native)}
                    before = reg.snapshot()["usage"]
                    parse = (lambda: collection_research_observation(payload, deployment, tool, field_catalog=CATALOG)) \
                            if kind == "collection" else (lambda: research_observation(payload, deployment, tool))
                    if accepted:
                        observed = parse()
                        bridge.record_submission(attempt, observed["submission"])
                        self.assertEqual(bridge.consume_completion(attempt, completion_source=lambda _: observed["completion"]).status, "completed")
                    else:
                        with self.assertRaises(ReceiptParseError) as caught:
                            parse()
                        self.assertNotIn(SECRET, str(caught.exception))
                        self.assertEqual(reg.snapshot()["attempts"][-1]["status"], "started")
                    self.assertEqual(reg.snapshot()["usage"], before)
                    self.assertNotIn(SECRET.encode(), b"".join(local._data.values()))

    def test_new_collection_worker_to_registry_chain(self):
        self.exercise("collection")

    def test_old_research_worker_to_registry_chain(self):
        self.exercise("legacy")


if __name__ == "__main__":
    unittest.main()
