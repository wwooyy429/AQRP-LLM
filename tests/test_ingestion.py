"""Synthetic historical source projections; no external service or market data."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cloud"))
from qresearch.artifacts import ArtifactConflict, MemoryArtifactStore
from qresearch.ingestion import (HistoricalBatchIngestor, IngestionError, MissingPITEvidence,
                                 extract_qc_records, resolve_historical_sid)
from qresearch.point_in_time import causal_window
from qresearch.universe import select_liquid_universe


def ts(value):
    return pd.Timestamp(value, tz="America/New_York")


def liquid(sid="A", day="2018-01-02", revision="v1", **changes):
    row = dict(sid=sid, source_revision=revision, session=ts(day + " 16:00"), dollar_volume=100,
        dollar_volume_field="dollar_volume", availability_basis="actual_historical_receipt",
        vendor_available_at=ts(day + " 16:01"), historical_ingested_at=ts(day + " 16:02"),
        instrument_type="common_stock", listed=True,
        classification_effective_at=ts("2017-01-01"), classification_available_at=ts("2017-01-01"),
        listing_effective_at=ts("2017-01-01"), listing_available_at=ts("2017-01-01"))
    return row | changes


def financial(revision="v1", **changes):
    return dict(sid="A", source_revision=revision, field_path="financials.revenue", unit="USD",
        period_accessor="three_months", report_period_end=ts("2017-12-31 16:00"), value=20,
        public_at=ts("2018-02-01 12:00"), public_date=None, public_precision="timestamp",
        vendor_available_at=ts("2018-02-01 13:00"), historical_ingested_at=ts("2018-02-01 13:05"),
        availability_basis="actual_historical_receipt") | changes


class IngestionTests(unittest.TestCase):
    def setUp(self):
        self.store = MemoryArtifactStore()
        self.catalog = {"financials.revenue": {"unit": "USD", "period_accessor": "three_months"}}
        self.ingestor = HistoricalBatchIngestor(self.store, source="independent-synthetic",
            data_version="pinned-v1", origin="historical_declared_fixture", synthetic=True,
            financial_catalog=self.catalog)

    def ingest(self, rows, kind="liquidity"):
        return self.ingestor.ingest(kind, rows, partition="2018/fixed-chunk")

    def test_real_rows_require_cloud_and_current_universe_is_rejected(self):
        with self.assertRaises(IngestionError):
            HistoricalBatchIngestor(self.store, source="qc", data_version="v", origin="historical_all_market")
        with self.assertRaises(IngestionError):
            HistoricalBatchIngestor(self.store, source="qc", data_version="v", origin="current_constituents", synthetic=True)

    def test_batch_reordering_is_idempotent_and_receipt_has_no_values(self):
        first = self.ingest([liquid("A"), liquid("B")])
        second = self.ingest([liquid("B"), liquid("A")])
        self.assertEqual(first["batch_ref"], second["batch_ref"])
        self.assertTrue(second["reused_batch"])
        self.assertEqual(second["new_vintages"], 0)
        self.assertNotIn('"dollar_volume":', json.dumps(first))
        self.assertNotIn('"sid":', json.dumps(first))
        self.assertFalse(first["full_historical_universe_certified"])
        self.assertFalse(first["actual_source_timing_certified"])

    def test_same_vintage_correction_conflicts_but_revision_is_retained(self):
        first = self.ingest([financial()], "financial")
        with self.assertRaises(ArtifactConflict):
            self.ingest([financial(value=99)], "financial")
        revised = self.ingest([financial(revision="v2", value=30,
            vendor_available_at=ts("2018-02-05 13:00"), historical_ingested_at=ts("2018-02-05 13:05"))], "financial")
        self.assertNotEqual(first["batch_ref"], revised["batch_ref"])
        self.assertEqual(revised["new_vintages"], 1)
        self.assertTrue(self.store.exists(first["batch_ref"]["key"]))

    def test_unknown_timestamps_and_classification_preserved_not_backfilled(self):
        receipt = self.ingest([liquid(vendor_available_at=None, historical_ingested_at=None,
            classification_available_at=None, instrument_type=None, availability_basis="modeled_lean_frontier")])
        self.assertEqual(receipt["gaps"]["actual_availability_unverified"], 1)
        self.assertEqual(receipt["gaps"]["instrument_type_missing"], 1)
        raw = json.loads(self.store.read_bytes(receipt["batch_ref"]["key"]))["records"][0]
        self.assertIsNone(raw["vendor_available_at"])
        with self.assertRaises(MissingPITEvidence):
            self.ingestor.liquidity_rows_asof(receipt["batch_ref"], ts("2018-01-03 09:00"), [ts("2018-01-02 16:00")])

    def test_liquidity_rank_uses_supplied_dollar_volume_and_keeps_ADR(self):
        rows = [liquid(sid, day, dollar_volume=value, instrument_type=kind)
            for sid, value, kind in (("ADR", 300, "adr"), ("A", 200, "common_stock"), ("B", 100, "common_stock"))
            for day in ("2018-01-02", "2018-01-03")]
        receipt = self.ingest(rows)
        sessions = [ts("2018-01-02 16:00"), ts("2018-01-03 16:00")]
        formation = ts("2018-01-04 09:00")
        frame = self.ingestor.liquidity_rows_asof(receipt["batch_ref"], formation, sessions)
        self.assertEqual(select_liquid_universe(frame, formation, sessions, size=2, lookback=2), ("ADR", "A"))
        # Missing financial values never enter or change the liquidity selection.
        missing = self.ingest([financial(sid="ADR", value=None)], "financial")
        self.assertEqual(missing["gaps"]["value_missing"], 1)
        known = self.ingestor.financial_records_asof(missing["batch_ref"], ts("2018-02-02 09:00"))
        self.assertEqual(tuple(known.sid), ("ADR",))
        self.assertTrue(known.value.isna().all())

    def test_financial_asof_keeps_late_revision_out_and_mature_revision_in(self):
        rows = [financial(), financial(revision="v2", value=99,
            vendor_available_at=ts("2018-02-05 13:00"), historical_ingested_at=ts("2018-02-05 13:05"))]
        receipt = self.ingest(rows, "financial")
        early = self.ingestor.financial_records_asof(receipt["batch_ref"], ts("2018-02-02 09:00"))
        self.assertEqual(list(early.value), [20])
        all_known = self.ingestor.financial_records_asof(receipt["batch_ref"], ts("2018-02-06 09:00"))
        decisions = [ts("2018-02-02 09:00"), ts("2018-02-06 09:00")]
        window = causal_window(all_known, decisions, ("A",), {"financials.revenue": "latest_available"},
            {time: time - pd.Timedelta(days=1) for time in decisions}, {"financials.revenue": pd.Timedelta(days=100)})
        self.assertEqual(list(window.matrices["financials.revenue"].A), [20, 99])

    def test_streamed_vintages_combine_without_double_count_or_cross_partition_conflict(self):
        original = self.ingest([financial()], "financial")
        revised = self.ingest([financial(revision="v2", value=99,
            vendor_available_at=ts("2018-02-05 13:00"), historical_ingested_at=ts("2018-02-05 13:05"))], "financial")
        references = [original["batch_ref"], revised["batch_ref"], original["batch_ref"]]
        all_known = self.ingestor.financial_records_asof(references, ts("2018-02-06 09:00"))
        self.assertEqual(len(all_known), 2)
        conflict = self.ingestor.ingest("financial", [financial(value=100)], partition="2018/another-chunk")
        with self.assertRaises(ArtifactConflict):
            self.ingestor.financial_records_asof([original["batch_ref"], conflict["batch_ref"]], ts("2018-02-06 09:00"))

    def test_date_only_publication_requires_explicit_later_exchange_gate(self):
        receipt = self.ingest([financial(public_at=None, public_date="2018-02-01", public_precision="date")], "financial")
        before = ts("2018-02-02 09:00")
        with self.assertRaises(MissingPITEvidence):
            self.ingestor.financial_records_asof(receipt["batch_ref"], before)
        with self.assertRaises(IngestionError):
            self.ingestor.financial_records_asof(receipt["batch_ref"], before,
                date_release_gates={"2018-02-01": ts("2018-02-01 23:59")})
        gates = {"2018-02-01": ts("2018-02-02 16:00")}
        self.assertTrue(self.ingestor.financial_records_asof(receipt["batch_ref"], before, date_release_gates=gates).empty)
        self.assertEqual(len(self.ingestor.financial_records_asof(receipt["batch_ref"], ts("2018-02-05 09:00"), date_release_gates=gates)), 1)

    def test_future_missing_timezone_inconsistent_receipt_or_invalid_field_rejected(self):
        bad = [liquid(session=ts("2024-01-02")), liquid(session="2018-01-02 16:00"),
            liquid(vendor_available_at=ts("2018-01-02 15:00")),
            liquid(historical_ingested_at=ts("2018-01-02 16:00")),
            liquid(dollar_volume_field="close"), liquid(dollar_volume=float("inf")),
            liquid(instrument_type="unmapped-vendor-code")]
        for row in bad:
            with self.subTest(row=list(row)):
                with self.assertRaises(IngestionError):
                    self.ingest([row])
        for row in (financial(field_path="future_earnings"), financial(unit="ratio"), financial(public_date="2024-01-02"),
                    financial(public_at=ts("2017-01-01")), financial(public_at=None, public_precision="timestamp")):
            with self.assertRaises(IngestionError):
                self.ingest([row], "financial")

    def test_symbol_identity_and_exact_QC_field_mapping_no_fallback(self):
        obj = SimpleNamespace(symbol=SimpleNamespace(id="PERMANENT-ID"), dollar_volume=13,
                              close=200, volume=99999, session=ts("2018-01-02 16:00"))
        rows = list(extract_qc_records([obj], kind="liquidity",
            field_map={"dollar_volume": "dollar_volume", "session": "session", "vendor_available_at": "vendor_time"}))
        self.assertEqual(rows[0]["sid"], "PERMANENT-ID")
        self.assertEqual(rows[0]["dollar_volume"], 13)
        self.assertIsNone(rows[0]["vendor_available_at"])
        with self.assertRaises(IngestionError):
            list(extract_qc_records([obj], kind="liquidity", field_map={"dollar_volume": "close"}))
        with self.assertRaises(IngestionError):
            list(extract_qc_records([obj], kind="liquidity", field_map={"dollar_volume": "close*volume"}))
        with self.assertRaises(IngestionError):
            list(extract_qc_records([SimpleNamespace(symbol="AAPL")], kind="liquidity", field_map={"dollar_volume": "dollar_volume"}))

    def test_mapping_uses_effective_and_available_times_without_current_backfill(self):
        mappings = [dict(ticker="XYZ", sid="OLD", effective_from=ts("2010-01-01"), effective_to=ts("2018-01-01"), available_at=ts("2010-01-01")),
            dict(ticker="XYZ", sid="NEW", effective_from=ts("2018-01-01"), effective_to=None, available_at=ts("2018-01-02"))]
        self.assertEqual(resolve_historical_sid("XYZ", ts("2017-06-01"), mappings), "OLD")
        with self.assertRaises(IngestionError):
            resolve_historical_sid("XYZ", ts("2018-01-01 09:00"), mappings)
        self.assertEqual(resolve_historical_sid("XYZ", ts("2018-01-03"), mappings), "NEW")
        with self.assertRaises(IngestionError):
            resolve_historical_sid("XYZ", ts("2018-01-03"), mappings + [dict(mappings[-1], sid="OTHER")])

    def test_hash_tampering_duplicate_vintage_and_bounded_stream(self):
        with self.assertRaises(IngestionError):
            self.ingest([liquid(), liquid()])
        tiny = HistoricalBatchIngestor(self.store, source="fixture", data_version="v1",
            origin="historical_declared_fixture", synthetic=True, max_batch_records=1)
        with self.assertRaises(IngestionError):
            tiny.ingest("liquidity", [liquid("A"), liquid("B")], partition="2018/chunk")
        receipts = list(tiny.ingest_stream("liquidity", [[liquid("A")], [liquid("B")]], partition="2018/chunk"))
        self.assertEqual([item["rows"] for item in receipts], [1, 1])
        ref = receipts[0]["batch_ref"]
        self.store._data[ref["key"]] = b"{}"
        with self.assertRaises(IngestionError):
            tiny.liquidity_rows_asof(ref, ts("2018-01-03 09:00"), [ts("2018-01-02 16:00")])


if __name__ == "__main__":
    unittest.main()
