"""Independent synthetic cloud-receiver boundaries, no QC SDK or market data."""
from copy import deepcopy
from datetime import datetime, time, timedelta
from hashlib import sha256
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cloud"))
from qresearch.artifacts import MemoryArtifactStore, canonical_json, content_hash
from qresearch.contracts import NY, aware
from qresearch.engineering_tasks import EngineeringTaskPlan
import qresearch.engineering_data as reception


class FakeObjectStore:
    def __init__(self):
        self.data = {}

    def contains_key(self, key):
        return key in self.data

    def save_bytes(self, key, value):
        self.data[key] = bytes(value)
        return True

    def read_bytes(self, key):
        return self.data[key]


class FakeHours:
    """Explicit toy weekday calendar; does not claim real exchange coverage."""
    def is_date_open(self, day):
        return day.weekday() < 5

    def get_next_market_close(self, day, extended):
        return datetime.combine(day.date(), time(16))

    def get_previous_trading_day(self, day):
        value = day - timedelta(days=1)
        while not self.is_date_open(value):
            value -= timedelta(days=1)
        return value

    def get_next_trading_day(self, day):
        value = day + timedelta(days=1)
        while not self.is_date_open(value):
            value += timedelta(days=1)
        return value


class FakeSymbol:
    def __init__(self, ticker, sid=None):
        self.value = ticker
        self.id = sid or "SID-" + ticker


class FakeAlgorithm:
    def __init__(self):
        self.object_store = FakeObjectStore()
        self.settings = SimpleNamespace()
        self.created = {}
        self.orders = []
        self.transactions = SimpleNamespace(get_orders=lambda: self.orders)
        self.time = datetime(2018, 2, 5, 16)

    def set_time_zone(self, value):
        self.zone = value

    def set_start_date(self, *value):
        self.start_date = value

    def set_end_date(self, *value):
        self.end_date = value

    def set_cash(self, value):
        self.cash = value

    def set_benchmark(self, value):
        self.benchmark = value

    def add_equity(self, ticker, resolution, **kwargs):
        security = SimpleNamespace(symbol=FakeSymbol(ticker), exchange=SimpleNamespace(hours=FakeHours()))
        self.created[ticker] = security
        return security


FAKE_API = SimpleNamespace(Resolution=SimpleNamespace(DAILY="Daily"),
    DataNormalizationMode=SimpleNamespace(RAW="Raw"), Globals=SimpleNamespace(version="synthetic-engine-v1"))


class EngineeringDataTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.code = "# synthetic receiver source\nVALUE = 1\n"
        (self.root / "receiver.py").write_text(self.code, encoding="utf-8")
        self.manifest = {"receiver.py": sha256(self.code.encode()).hexdigest()}
        raw = {"schema_version": 1, "plan_id": "independent-receiver-fixture", "scope": "engineering",
            "project_id": 17, "source_manifest_hash": "a" * 64, "deployment_hash": content_hash(self.manifest),
            "request_mode": "symbol_resolution", "request_template": {"dataset": "US Equities",
                "fields": ["close", "volume"], "start": "2018-01-01T00:00:00-05:00",
                "end": "2019-01-01T00:00:00-05:00", "data_version": "independent-fixture-v1",
                "universe_hash": "b" * 64, "normalization": "raw", "timezone": "America/New_York"},
            "symbol_resolution": {"tickers": ["AAPL", "MSFT"], "as_of": "2019-01-01T00:00:00-05:00",
                "method": "QuantBook.add_equity/as-of fixed fixture"},
            "observation_window": {"start": "2018-02-05T00:00:00-05:00", "end_exclusive": "2018-02-10T00:00:00-05:00"},
            "required_checks": {"research": ["source_snapshot_matches", "raw_data_received"],
                "lean": ["source_snapshot_matches", "raw_data_received", "complete_expected_bars", "no_orders",
                         "development_only", "symbol_registry_resolved", "corporate_action_received"]},
            "max_retries": {"research": 0, "lean": 0}, "report_namespace": "synthetic-receiver",
            "orders_enabled": False, "financial_metrics_enabled": False, "economic_factor": None, "economic_model": None}
        self.plan = EngineeringTaskPlan.from_dict(raw, discovered_project_ids=(17,))

    def payload(self, stage="lean"):
        document = self.plan.to_dict()
        attempt = "1" * 32 if stage == "research" else "2" * 32
        identity = {"plan_hash": self.plan.hash,
            "config_id": content_hash({"engineering_task_schema_version": 1, "plan": document}),
            "attempt_id": attempt, "stage": stage, "project_id": 17,
            "source_manifest_hash": document["source_manifest_hash"], "deployment_hash": document["deployment_hash"],
            "data_request_hash": self.plan.request_hash}
        return {"plan": document, "identity": identity, "deployment_manifest": self.manifest,
            "report_key": document["report_namespace"] + "/reports/" + self.plan.hash + "/" + stage + "/" + attempt + ".json",
            "external_identity_kind": "logical_research_execution_receipt" if stage == "research" else "quantconnect_backtest_id"}

    def init_receiver(self, algorithm=None):
        algorithm = algorithm or FakeAlgorithm()
        store = reception._cloud_store(algorithm.object_store)
        _, resolution = reception._resolution(store, self.plan,
            {ticker: FakeSymbol(ticker) for ticker in ("AAPL", "MSFT")})
        payload = self.payload()
        payload["research_resolution"] = resolution
        original = reception._context
        with patch.object(reception, "_context", side_effect=lambda data, stage, **kwargs: original(data, stage, source_root=self.root, **kwargs)):
            reception.initialize_receiver(algorithm, payload, api=FAKE_API)
        return algorithm

    def slice_for(self, algorithm, day, *, dividend=False):
        bars = {}
        for security in algorithm.created.values():
            bars[security.symbol] = SimpleNamespace(symbol=security.symbol, end_time=datetime(2018, 2, day, 16),
                open=430.0, high=432.0, low=429.0, close=431.25, volume=123456)
        dividends = {}
        if dividend:
            symbol = algorithm.created["AAPL"].symbol
            dividends[symbol] = SimpleNamespace(symbol=symbol, distribution=0.63)
        return SimpleNamespace(bars=bars, dividends=dividends, splits={}, delistings={}, symbol_changed_events={})

    def receive_all(self, algorithm, *, dividend=True):
        for day in range(5, 10):
            algorithm.time = datetime(2018, 2, day, 16)
            reception.receive_slice(algorithm, self.slice_for(algorithm, day, dividend=dividend and day == 9))

    def test_input_is_one_inert_string_literal_not_executable_python(self):
        path = self.root / "_engineering_task_input.py"
        expected = self.payload("research")
        path.write_text("TASK_INPUT_JSON = " + repr(json.dumps(expected)) + "\n", encoding="utf-8")
        self.assertEqual(reception.load_task_input(path), expected)
        marker = self.root / "must-not-exist"
        malicious = ["from pathlib import Path\nTASK_INPUT_JSON = '{}'\n",
            "TASK_INPUT_JSON = __import__('pathlib').Path(" + repr(str(marker)) + ").write_text('executed')\n",
            "TASK_INPUT_JSON = '{}'\nraise RuntimeError('executed')\n",
            "TASK_INPUT_JSON = SECOND = '{}'\n", "TASK_INPUT_JSON = {}\n"]
        for source in malicious:
            with self.subTest(source=source):
                path.write_text(source, encoding="utf-8")
                with self.assertRaises(ValueError):
                    reception.load_task_input(path)
                self.assertFalse(marker.exists())

    def test_deployment_bytes_and_paths_are_checked_before_execution(self):
        self.assertEqual(reception.verify_deployment(self.manifest, content_hash(self.manifest), source_root=self.root),
                         self.plan.to_dict()["deployment_hash"])
        (self.root / "receiver.py").write_text(self.code + "CHANGED = True\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            reception.verify_deployment(self.manifest, content_hash(self.manifest), source_root=self.root)
        for name in ("../receiver.py", "/receiver.py", "_engineering_task_input.py"):
            manifest = {name: "a" * 64}
            with self.subTest(path=name), self.assertRaises(ValueError):
                reception.verify_deployment(manifest, content_hash(manifest), source_root=self.root)

    def test_context_binds_stage_config_plan_destination_and_manifest(self):
        payload = self.payload("research")
        plan, _, identity = reception._context(payload, "research", source_root=self.root)
        self.assertEqual(plan.hash, self.plan.hash)
        self.assertEqual(identity, payload["identity"])
        for field, value in (("plan_hash", "c" * 64), ("config_id", "d" * 64),
                             ("deployment_hash", "e" * 64), ("stage", "lean")):
            changed = deepcopy(payload)
            changed["identity"][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                reception._context(changed, "research", source_root=self.root)
        changed = deepcopy(payload)
        changed["report_key"] = "synthetic-unrelated/report.json"
        with self.assertRaises(ValueError):
            reception._context(changed, "research", source_root=self.root)

    def test_context_rejects_extra_identity_rows_instead_of_echoing_them(self):
        payload = self.payload("research")
        payload["identity"]["rows"] = [[431.25]]
        with self.assertRaises(ValueError):
            reception._context(payload, "research", source_root=self.root)

    def test_resolution_validates_actual_hashes_and_frozen_template(self):
        store = MemoryArtifactStore()
        request, resolution = reception._resolution(store, self.plan, {ticker: FakeSymbol(ticker) for ticker in ("AAPL", "MSFT")})
        recovered, identities = reception._read_resolution(store, self.plan, resolution)
        self.assertEqual(recovered.identity(), request.identity())
        self.assertEqual(identities, {"AAPL": "SID-AAPL", "MSFT": "SID-MSFT"})
        changed = deepcopy(resolution)
        changed["resolved_request_ref"]["sha256"] = "f" * 64
        with self.assertRaises(ValueError):
            reception._read_resolution(store, self.plan, changed)
        raw = request.identity()
        raw["fields"] = ["open", "close", "volume"]
        ref = reception._save(store, "synthetic-tampering/changed-request.json", raw)
        changed = deepcopy(resolution)
        changed["resolved_request_ref"] = ref
        changed["resolved_request_hash"] = ref["sha256"]
        changed["resolution_artifact_hash"] = content_hash({key: changed[key] for key in ("resolved_registry_ref", "resolved_request_ref")})
        with self.assertRaises(ValueError):
            reception._read_resolution(store, self.plan, changed)

    def test_resolution_does_not_accept_unknown_tickers_or_duplicate_sids(self):
        for symbols in ({"AAPL": FakeSymbol("AAPL"), "EVIL": FakeSymbol("EVIL")},
                        {"AAPL": FakeSymbol("AAPL", "same"), "MSFT": FakeSymbol("MSFT", "same")}):
            with self.subTest(symbols=sorted(symbols)), self.assertRaises(ValueError):
                reception._resolution(MemoryArtifactStore(), self.plan, symbols)

    def test_finish_returns_completed_or_failed_metadata_without_values(self):
        store = MemoryArtifactStore()
        _, resolution = reception._resolution(store, self.plan, {ticker: FakeSymbol(ticker) for ticker in ("AAPL", "MSFT")})
        payload = self.payload("research")
        checks = {name: True for name in payload["plan"]["required_checks"]["research"]}
        result = reception._finish(store, payload, checks, {"record_count": 20, "history_calls_second": 0}, resolution)
        self.assertEqual(result["cloud_report"]["status"], "completed")
        self.assertFalse(result["cloud_report"]["market_values_exported"])
        self.assertNotIn("431.25", json.dumps(result))
        other = MemoryArtifactStore()
        checks["raw_data_received"] = False
        result = reception._finish(other, payload, checks, {"record_count": 0, "history_calls_second": 0}, resolution)
        self.assertEqual(result["cloud_report"]["status"], "failed")

    def test_finish_rejects_row_metadata_in_statistics_evidence_and_resolution(self):
        payload = self.payload("research")
        resolution_store = MemoryArtifactStore()
        _, resolution = reception._resolution(resolution_store, self.plan, {ticker: FakeSymbol(ticker) for ticker in ("AAPL", "MSFT")})
        checks = {name: True for name in payload["plan"]["required_checks"]["research"]}
        attacks = [({"record_count": [431.25]}, resolution, None),
            ({"record_count": True}, resolution, None),
            ({"record_count": 2, "close": 431.25}, resolution, None),
            ({"record_count": 2}, resolution, {"rows": [[431.25]]}),
            ({"record_count": 2}, resolution | {"rows": [[431.25]]}, None)]
        for stats, resolved, evidence in attacks:
            store = MemoryArtifactStore()
            with self.subTest(stats=stats, evidence=bool(evidence)), self.assertRaises(ValueError):
                reception._finish(store, payload, checks, stats, resolved, evidence=evidence)
            self.assertEqual(store._data, {})

    def test_receiver_initialization_uses_exact_research_ids_and_no_investment(self):
        algorithm = self.init_receiver()
        self.assertEqual(algorithm.zone, "America/New_York")
        self.assertEqual(algorithm.start_date, (2018, 2, 5))
        self.assertEqual(algorithm.end_date, (2018, 2, 9))
        self.assertTrue(algorithm.settings.daily_precise_end_time)
        self.assertEqual(algorithm.orders, [])
        self.assertEqual(algorithm._engineering_state["records"], [])

    def test_receiver_complete_actual_slices_and_dividend_have_no_value_export(self):
        algorithm = self.init_receiver()
        self.receive_all(algorithm)
        result = reception.finish_receiver(algorithm)
        report = result["cloud_report"]
        self.assertEqual(report["status"], "completed")
        self.assertTrue(report["checks"]["complete_expected_bars"])
        self.assertEqual(report["statistics"]["data_event_count"], 10)
        self.assertEqual(report["statistics"]["dividend_event_count"], 1)
        self.assertEqual(report["statistics"]["orders_submitted"], 0)
        self.assertNotIn("431.25", json.dumps(result))
        self.assertNotIn("0.63", json.dumps(result))
        self.assertTrue(all(type(value) is int for value in report["statistics"].values()))

    def test_empty_missing_duplicate_and_no_dividend_cannot_complete(self):
        algorithm = self.init_receiver()
        empty = reception.finish_receiver(algorithm)
        self.assertEqual(empty["cloud_report"]["status"], "failed")
        for mode in ("missing", "duplicate", "no-dividend"):
            algorithm = self.init_receiver()
            if mode == "missing":
                days = range(5, 9)
                for day in days:
                    algorithm.time = datetime(2018, 2, day, 16)
                    reception.receive_slice(algorithm, self.slice_for(algorithm, day, dividend=day == 8))
            else:
                self.receive_all(algorithm, dividend=mode != "no-dividend")
                if mode == "duplicate":
                    algorithm.time = datetime(2018, 2, 9, 16)
                    reception.receive_slice(algorithm, self.slice_for(algorithm, 9))
            result = reception.finish_receiver(algorithm)
            with self.subTest(mode=mode):
                self.assertEqual(result["cloud_report"]["status"], "failed")

    def test_actual_order_or_order_event_prevents_receiver_completion(self):
        for order_events in (False, True):
            algorithm = self.init_receiver()
            self.receive_all(algorithm)
            if order_events:
                algorithm._engineering_state["order_events"] = 1
            else:
                algorithm.orders.append(SimpleNamespace(id=1))
            result = reception.finish_receiver(algorithm)
            self.assertFalse(result["cloud_report"]["checks"]["no_orders"])
            self.assertEqual(result["cloud_report"]["status"], "failed")

    def test_wrong_bar_sid_and_foreign_bar_are_rejected(self):
        for wrong_key in (False, True):
            algorithm = self.init_receiver()
            algorithm.time = datetime(2018, 2, 5, 16)
            data = self.slice_for(algorithm, 5)
            symbol = algorithm.created["AAPL"].symbol
            foreign = FakeSymbol("EVIL")
            data.bars[symbol].symbol = foreign
            if wrong_key:
                data.bars[foreign] = data.bars.pop(symbol)
            with self.subTest(wrong_key=wrong_key), self.assertRaises(ValueError):
                reception.receive_slice(algorithm, data)

    def test_future_close_non_session_close_and_wrong_year_are_rejected(self):
        for mode in ("future", "not-close", "wrong-year"):
            algorithm = self.init_receiver()
            algorithm.time = datetime(2018, 2, 5, 16)
            data = self.slice_for(algorithm, 5)
            symbol = algorithm.created["AAPL"].symbol
            if mode == "future":
                data.bars[symbol].end_time = datetime(2018, 2, 6, 16)
            elif mode == "not-close":
                data.bars[symbol].end_time = datetime(2018, 2, 5, 15)
            else:
                algorithm.time = datetime(2024, 2, 5, 16)
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                reception.receive_slice(algorithm, data)


if __name__ == "__main__":
    unittest.main()
