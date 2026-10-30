"""Synthetic known answers for bounded evidence; no market provider or jobs."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cloud"))
from qresearch.artifacts import MemoryArtifactStore, canonical_json, content_hash
from qresearch.data_certification import (DataCertificationError, DataCertificationPlan,
    audit_data_certification, certification_capabilities, store_certification_table, summarize_certification_scope)
from qresearch.ingestion import HistoricalBatchIngestor


def ts(value):
    return pd.Timestamp(value, tz="America/New_York")


CATALOG = {"financials.revenue": {"unit": "USD", "period_accessor": "three_months"}}
SID = ["SYNTHETIC-SID-" + str(index).zfill(3) for index in range(201)]
RANKED = list(reversed(SID[1:]))


class Calendar:
    """Hand-listed 2018 US sessions, deliberately a synthetic calendar adapter."""
    def __init__(self):
        dates = [date for date in pd.bdate_range("2018-01-02", "2018-01-31") if date.date().isoformat() != "2018-01-15"]
        self.sessions = [ts(date.date().isoformat() + " 16:00") for date in dates]
        formations = [ts(date.date().isoformat() + " 09:00") for date in dates[1:]] + [ts("2018-02-01 09:00")]
        self.frame = pd.DataFrame({"formation_at": formations, "session_close": self.sessions})

    def decisions(self, start, end):
        return self.frame[(self.frame.formation_at >= start) & (self.frame.formation_at < end)].copy()


def ingestion(store):
    return HistoricalBatchIngestor(store, source="synthetic-vendor", data_version="synthetic-v1",
        origin="historical_all_market", financial_catalog=CATALOG, synthetic=True)


def plan(ingestor, **changes):
    raw = {"schema_version": 1, "plan_id": "synthetic-US200-certification", "start": ts("2018-01-31").isoformat(),
        "end_exclusive": ts("2018-02-02").isoformat(), "warmup_start": ts("2018-01-01").isoformat(),
        "timezone": "America/New_York", "source_manifest_hash": "a" * 64, "data_version": "synthetic-v1",
        "ingestion_namespace": ingestor.namespace, "financial_catalog": CATALOG,
        "universe_size": 200, "liquidity_lookback_sessions": 20}
    return DataCertificationPlan.from_dict(raw | changes)


def source_data(calendar):
    liquid = []
    for index, sid in enumerate(SID):
        for session in calendar.sessions:
            liquid.append({"sid": sid, "source_revision": "synthetic-original-v1", "session": session.isoformat(),
                "dollar_volume": 1000 + index, "dollar_volume_field": "dollar_volume",
                "vendor_available_at": (session + pd.Timedelta(minutes=1)).isoformat(),
                "historical_ingested_at": (session + pd.Timedelta(minutes=2)).isoformat(),
                "availability_basis": "actual_historical_receipt", "instrument_type": "common_stock", "listed": True,
                "classification_effective_at": ts("2010-01-01").isoformat(), "classification_available_at": ts("2010-01-01").isoformat(),
                "listing_effective_at": ts("2010-01-01").isoformat(), "listing_available_at": ts("2010-01-01").isoformat()})
    financial = [{"sid": sid, "source_revision": "synthetic-original-v1", "field_path": "financials.revenue",
        "unit": "USD", "period_accessor": "three_months", "report_period_end": ts("2017-12-31").isoformat(),
        "value": 123456.78901, "public_at": ts("2018-01-02 12:00").isoformat(), "public_date": None,
        "public_precision": "timestamp", "vendor_available_at": ts("2018-01-02 13:00").isoformat(),
        "historical_ingested_at": ts("2018-01-02 13:05").isoformat(), "availability_basis": "actual_historical_receipt"}
        for sid in SID]
    return liquid, financial


def tables(calendar):
    scored = calendar.frame[calendar.frame.formation_at >= ts("2018-01-31")]
    members = [{"formation_at": row.formation_at.isoformat(), "sids": RANKED} for row in scored.itertuples()]
    prices = [{"sid": sid, "session": row.session_close.isoformat(),
        "available_at": (row.session_close + pd.Timedelta(minutes=1)).isoformat(),
        "open": 88888.12345, "high": 90000, "low": 88000, "close": 89000, "volume": 100,
        "normalization": "raw", "source_revision": "synthetic-price-v1"} for row in scored.itertuples() for sid in RANKED]
    masters = [{"sid": sid, "ticker": "T" + str(index), "effective_from": ts("2010-01-01").isoformat(),
        "effective_to": None, "available_at": ts("2010-01-01").isoformat(), "instrument_type": "common_stock",
        "listed": True, "exchange": "synthetic-primary-exchange"} for index, sid in enumerate(SID)]
    actions = [{"sid": SID[-1], "event_time": ts("2018-01-30 16:00").isoformat(),
        "available_at": ts("2018-01-30 16:01").isoformat(), "kind": "dividend", "source_revision": "synthetic-action-v1"}]
    return {"membership": members, "prices": prices, "security_master": masters, "corporate_actions": actions}


class DataCertificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.calendar = Calendar()
        cls.liquid, cls.financial = source_data(cls.calendar)
        cls.table_rows = tables(cls.calendar)
        store = MemoryArtifactStore()
        ingest = ingestion(store)
        cls.frozen_plan = plan(ingest)
        cls.base_refs = {"liquidity_refs": [ingest.ingest("liquidity", cls.liquid, partition="2018/source")['batch_ref']],
                         "financial_refs": [ingest.ingest("financial", cls.financial, partition="2018/source")['batch_ref']]}
        for name, argument in (("membership", "membership_refs"), ("prices", "price_refs"),
                ("security_master", "security_master_refs"), ("corporate_actions", "corporate_action_refs")):
            cls.base_refs[argument] = [store_certification_table(store, cls.frozen_plan, name, cls.table_rows[name], synthetic=True)]
        cls.base_store = dict(store._data)

    def setUp(self):
        self.store = MemoryArtifactStore()
        self.store._data = dict(self.base_store)
        self.ingestor = ingestion(self.store)
        self.refs = deepcopy(self.base_refs)

    def audit(self, **changes):
        return audit_data_certification(self.store, self.frozen_plan, calendar=self.calendar,
            ingestor=self.ingestor, synthetic=True, **(self.refs | changes))

    def change_table(self, name, rows):
        argument = {"membership": "membership_refs", "prices": "price_refs", "security_master": "security_master_refs",
                    "corporate_actions": "corporate_action_refs"}[name]
        self.refs[argument] = [store_certification_table(self.store, self.frozen_plan, name, rows, synthetic=True)]

    def change_source(self, kind, rows):
        self.refs[kind + "_refs"] = [self.ingestor.ingest(kind, rows, partition="2018/altered")['batch_ref']]

    def test_known_answer_201_candidates_21_sessions_200_members_and_no_approval(self):
        result = self.audit()
        self.assertEqual(result['status'], 'observations_passed')
        self.assertTrue(all(result['checks'].values()))
        self.assertEqual(result['counts']['liquidity_record_count'], 201 * 21)
        self.assertEqual(result['counts']['formation_count'], 2)
        for name in ('expected_member_cells','observed_member_cells','price_observed_cells','financial_available_cells'):
            self.assertEqual(result['counts'][name], 400)
        self.assertEqual(result['counts']['financial_missing_cells'], 0)
        expected = [[row['formation_at'], RANKED] for row in self.table_rows['membership']]
        self.assertEqual(result['ranked_membership_hash'], content_hash(expected))
        for name in ('full_historical_US200_certified','actual_availability_certified','financial_vintage_certified',
                     'research_certified','vendor_provenance_authenticated','financial_evidence','row_values_exported'):
            self.assertIs(result[name], False)
        encoded = json.dumps(result)
        for private in ('123456.78901','88888.12345',SID[-1],'synthetic-price-v1'):
            self.assertNotIn(private, encoded)
        self.assertEqual(len(result['gap_codes']), 4)

    def test_missing_financials_never_replace_ranked_member_with_rank201(self):
        baseline = self.audit()
        self.change_source('financial', [row for row in self.financial if row['sid'] != SID[-1]])
        result = self.audit()
        self.assertEqual(result['ranked_membership_hash'], baseline['ranked_membership_hash'])
        self.assertEqual(result['counts']['observed_member_cells'], 400)
        self.assertEqual(result['counts']['financial_missing_cells'], 2)
        self.assertFalse(result['checks']['financial_scope_coverage_complete'])

    def test_latest_missing_restatement_does_not_backfill_older_nonmissing_value(self):
        row = deepcopy(self.financial[-1])
        row.update(source_revision='restatement-v2', value=None, public_at=ts('2018-01-29 12:00').isoformat(),
            vendor_available_at=ts('2018-01-29 13:00').isoformat(),historical_ingested_at=ts('2018-01-29 13:05').isoformat())
        self.change_source('financial', self.financial + [row])
        result = self.audit()
        self.assertEqual(result['counts']['financial_missing_cells'], 2)

    def test_future_delivery_cannot_be_used_at_earlier_formations(self):
        rows = deepcopy(self.financial)
        rows[-1].update(vendor_available_at=ts('2018-02-01 10:00').isoformat(),historical_ingested_at=ts('2018-02-01 10:05').isoformat())
        self.change_source('financial', rows)
        result = self.audit()
        self.assertEqual(result['counts']['financial_missing_cells'], 2)
        self.assertEqual(result['counts']['observed_member_cells'], 400)

    def test_missing_expected_liquidity_session_is_not_skipped(self):
        missing = self.calendar.sessions[10].isoformat()
        self.change_source('liquidity', [row for row in self.liquid if row['session'] != missing])
        result = self.audit()
        self.assertEqual(result['counts']['unavailable_liquidity_formations'], 2)
        self.assertEqual(result['counts']['observed_member_cells'], 0)
        self.assertEqual(result['status'], 'insufficient_evidence')

    def test_missing_old_candidate_history_cannot_hide_behind_rank201_replacement(self):
        rows=[row for row in self.liquid if not (row['sid']==SID[-1] and row['session']==self.calendar.sessions[0].isoformat())]
        self.change_source('liquidity',rows)
        members=deepcopy(self.table_rows['membership']);members[0]['sids']=list(reversed(SID[:-1]))
        self.change_table('membership',members)
        prices=deepcopy(self.table_rows['prices'])
        for row in prices:
            if row['sid']==SID[-1] and row['session']==ts('2018-01-30 16:00').isoformat():row['sid']=SID[0]
        self.change_table('prices',prices)
        result=self.audit()
        self.assertEqual(result['counts']['observed_member_cells'],400)
        self.assertEqual(result['counts']['price_missing_cells'],0)
        self.assertEqual(result['counts']['incomplete_candidate_histories'],1)
        self.assertEqual(result['counts']['missing_candidate_session_cells'],1)
        self.assertFalse(result['checks']['all_known_eligible_candidate_histories_complete'])
        self.assertEqual(result['status'],'insufficient_evidence')

    def configure_ipo(self, listing, *, drop_pre=False, available=None):
        """SID0 has highest liquidity but initially no mature listed history."""
        stamp = ts(listing)
        available_at = ts(available) if available else stamp
        rows = deepcopy(self.liquid)
        for row in rows:
            if row['sid'] == SID[0]:
                row.update(dollar_volume=1000000, listing_effective_at=stamp.isoformat(),
                    listing_available_at=available_at.isoformat(),
                    classification_effective_at=stamp.isoformat(),
                    classification_available_at=available_at.isoformat())
        if drop_pre:
            rows = [row for row in rows if row['sid'] != SID[0] or pd.Timestamp(row['session']) >= stamp]
        self.change_source('liquidity', rows)
        masters = deepcopy(self.table_rows['security_master'])
        masters[0].update(effective_from=stamp.isoformat(), available_at=available_at.isoformat())
        self.change_table('security_master', masters)

    def claim_ipo_on_last_formation(self):
        members = deepcopy(self.table_rows['membership'])
        members[-1]['sids'] = [SID[0]] + RANKED[:-1]
        self.change_table('membership', members)
        prices = deepcopy(self.table_rows['prices'])
        for row in prices:
            if row['sid'] == RANKED[-1] and row['session'] == self.calendar.sessions[-1].isoformat():
                row['sid'] = SID[0]
        self.change_table('prices', prices)

    def test_pre_listing_rows_cannot_admit_five_session_ipo(self):
        self.configure_ipo('2018-01-25')
        members = deepcopy(self.table_rows['membership'])
        for row in members:
            row['sids'] = [SID[0]] + RANKED[:-1]
        self.change_table('membership', members)
        result = self.audit()
        self.assertEqual(result['status'], 'insufficient_evidence')
        self.assertEqual(result['counts']['membership_mismatch_formations'], 2)
        self.assertFalse(result['checks']['ranked_membership_matches'])
        self.assertEqual(result['counts']['liquidity_record_count'], 201 * 21)
        self.assertEqual(result['ranked_membership_hash'], content_hash(
            [[row['formation_at'], RANKED] for row in self.table_rows['membership']]))
        self.assertFalse(result['research_certified'])

    def test_young_ipo_remains_excluded_with_or_without_declared_pre_listing_rows(self):
        self.configure_ipo('2018-01-25')
        with_pre_listing = self.audit()
        self.configure_ipo('2018-01-25', drop_pre=True)
        post_listing_only = self.audit()
        for result in (with_pre_listing, post_listing_only):
            self.assertEqual(result['status'], 'observations_passed')
            self.assertFalse(result['full_historical_US200_certified'])
        self.assertEqual(with_pre_listing['ranked_membership_hash'], post_listing_only['ranked_membership_hash'])
        self.assertGreater(with_pre_listing['counts']['liquidity_record_count'],
            post_listing_only['counts']['liquidity_record_count'])

    def test_ipo_nineteen_then_twenty_completed_session_known_answer(self):
        self.configure_ipo('2018-01-03')
        self.claim_ipo_on_last_formation()
        result = self.audit()
        self.assertEqual(result['status'], 'observations_passed')
        expected = [[self.table_rows['membership'][0]['formation_at'], RANKED],
            [self.table_rows['membership'][-1]['formation_at'], [SID[0]] + RANKED[:-1]]]
        self.assertEqual(result['ranked_membership_hash'], content_hash(expected))
        self.assertFalse(result['financial_evidence'])

    def test_listing_intraday_or_at_close_uses_inclusive_completed_close(self):
        for listing in ('2018-01-03 12:00', '2018-01-03 16:00'):
            with self.subTest(listing=listing):
                self.setUp()
                self.configure_ipo(listing)
                self.claim_ipo_on_last_formation()
                self.assertEqual(self.audit()['status'], 'observations_passed')

    def test_listing_after_session_close_cannot_count_that_session(self):
        self.configure_ipo('2018-01-03 16:01')
        result = self.audit()
        self.assertEqual(result['status'], 'observations_passed')
        self.assertEqual(result['ranked_membership_hash'], content_hash(
            [[row['formation_at'], RANKED] for row in self.table_rows['membership']]))

    def test_listing_announcement_after_formation_stays_unavailable(self):
        self.configure_ipo('2018-01-03', available='2018-01-31 10:00')
        self.claim_ipo_on_last_formation()
        self.assertEqual(self.audit()['status'], 'observations_passed')

    def test_unknown_listing_clock_is_not_removed_as_pre_listing_noise(self):
        rows = deepcopy(self.liquid)
        rows[0]['listing_effective_at'] = None
        self.change_source('liquidity', rows)
        result = self.audit()
        self.assertEqual(result['status'], 'insufficient_evidence')
        self.assertGreater(result['counts']['unavailable_liquidity_formations'], 0)

    def test_recent_classification_or_mapping_does_not_reset_old_listing_history(self):
        rows = deepcopy(self.liquid)
        for row in rows:
            row['classification_effective_at'] = ts('2018-01-25').isoformat()
            row['classification_available_at'] = ts('2018-01-25').isoformat()
        self.change_source('liquidity', rows)
        masters = deepcopy(self.table_rows['security_master'])
        for row in masters:
            row['effective_from'] = ts('2018-01-25').isoformat()
            row['available_at'] = ts('2018-01-25').isoformat()
        self.change_table('security_master', masters)
        self.assertEqual(self.audit()['status'], 'observations_passed')

    def mapping_history(self, *, rename=True, boundary='2018-01-25', old_available=None,
                        old_finish=None, old_listed=True):
        rows = deepcopy(self.table_rows['security_master'])
        old = rows[0]
        old['effective_to'] = ts(old_finish or boundary).isoformat()
        old['listed'] = old_listed
        if old_available:
            old['available_at'] = ts(old_available).isoformat()
        new = deepcopy(self.table_rows['security_master'][0])
        new.update(effective_from=ts(boundary).isoformat(), available_at=ts(boundary).isoformat())
        if rename:
            new['ticker'] = 'RENAMED-SYNTHETIC-SID0'
        rows.append(new)
        return rows

    def test_old_master_history_proves_missing_candidate_without_liquidity_clock(self):
        self.change_table('security_master', self.mapping_history())
        self.change_source('liquidity', [row for row in self.liquid if row['sid'] != SID[0]])
        result = self.audit()
        self.assertEqual(result['status'], 'insufficient_evidence')
        self.assertEqual(result['counts']['observed_member_cells'], 400)
        self.assertEqual(result['counts']['known_eligible_candidate_expected_cells'], 8040)
        self.assertEqual(result['counts']['missing_candidate_session_cells'], 40)
        self.assertEqual(result['counts']['incomplete_candidate_histories'], 2)
        self.assertFalse(result['checks']['all_known_eligible_candidate_histories_complete'])

    def test_same_ticker_version_boundary_does_not_hide_whole_missing_history(self):
        self.change_table('security_master', self.mapping_history(rename=False))
        self.change_source('liquidity', [row for row in self.liquid if row['sid'] != SID[0]])
        result = self.audit()
        self.assertEqual(result['status'], 'insufficient_evidence')
        self.assertEqual(result['counts']['known_eligible_candidate_expected_cells'], 8040)
        self.assertEqual(result['counts']['missing_candidate_session_cells'], 40)

    def test_mapping_complete_and_single_session_missing_have_separate_known_answers(self):
        self.change_table('security_master', self.mapping_history())
        complete = self.audit()
        self.assertEqual(complete['status'], 'observations_passed')
        self.assertEqual(complete['counts']['known_eligible_candidate_expected_cells'], 8040)
        self.change_source('liquidity', [row for row in self.liquid if not
            (row['sid'] == SID[0] and row['session'] == self.calendar.sessions[0].isoformat())])
        result = self.audit()
        self.assertEqual(result['status'], 'insufficient_evidence')
        self.assertEqual(result['counts']['missing_candidate_session_cells'], 1)
        self.assertEqual(result['counts']['incomplete_candidate_histories'], 1)

    def test_gap_overlap_and_unknown_state_cannot_create_continuous_master_history(self):
        for mode in ('gap', 'overlap', 'unknown', 'unlisted'):
            with self.subTest(mode=mode):
                self.setUp()
                rows = self.mapping_history(old_finish={'gap':'2018-01-24',
                    'overlap':'2018-01-26'}.get(mode),
                    old_listed=None if mode == 'unknown' else mode != 'unlisted')
                self.change_table('security_master', rows)
                self.change_source('liquidity', [row for row in self.liquid if row['sid'] != SID[0]])
                result = self.audit()
                self.assertEqual(result['status'], 'insufficient_evidence')
                self.assertGreater(result['counts']['inconsistent_classification_cells'], 0)
                self.assertFalse(result['checks']['historical_classification_and_mapping_consistent'])

    def test_late_known_old_master_cannot_be_used_as_prior_listing_proof(self):
        self.change_table('security_master', self.mapping_history(old_available='2018-01-31 10:00'))
        self.change_source('liquidity', [row for row in self.liquid if row['sid'] != SID[0]])
        result = self.audit()
        self.assertEqual(result['status'], 'insufficient_evidence')
        self.assertEqual(result['counts']['known_eligible_candidate_expected_cells'], 8020)
        self.assertEqual(result['counts']['missing_candidate_session_cells'], 20)
        self.assertGreater(result['counts']['inconsistent_classification_cells'], 0)

    def test_unknown_historical_master_state_is_not_overridden_by_liquidity_clock(self):
        self.change_table('security_master', self.mapping_history(old_listed=None))
        result = self.audit()
        self.assertEqual(result['status'], 'insufficient_evidence')
        self.assertGreater(result['counts']['inconsistent_classification_cells'], 0)

    def test_recent_mapping_without_old_master_or_listing_clock_is_unknown_not_ipo(self):
        rows = self.mapping_history()
        rows = [row for row in rows if row['sid'] != SID[0] or row['effective_to'] is None]
        self.change_table('security_master', rows)
        self.change_source('liquidity', [row for row in self.liquid if row['sid'] != SID[0]])
        result = self.audit()
        self.assertEqual(result['status'], 'insufficient_evidence')
        self.assertGreater(result['counts']['inconsistent_classification_cells'], 0)

    def test_unknown_current_eligibility_without_liquidity_is_not_an_exclusion(self):
        for field in ('listed', 'instrument_type'):
            with self.subTest(field=field):
                self.setUp()
                rows = self.mapping_history()
                rows[-1][field] = None
                self.change_table('security_master', rows)
                self.change_source('liquidity', [row for row in self.liquid if row['sid'] != SID[0]])
                result = self.audit()
                self.assertEqual(result['status'], 'insufficient_evidence')
                self.assertFalse(result['checks']['historical_classification_and_mapping_consistent'])
                self.assertGreater(result['counts']['inconsistent_classification_cells'], 0)

    def test_explicit_unlisted_or_excluded_type_without_liquidity_remains_excluded(self):
        for field, value in (('listed', False), ('instrument_type', 'etf')):
            with self.subTest(field=field):
                self.setUp()
                rows = self.mapping_history()
                rows[-1][field] = value
                self.change_table('security_master', rows)
                self.change_source('liquidity', [row for row in self.liquid if row['sid'] != SID[0]])
                result = self.audit()
                self.assertEqual(result['status'], 'observations_passed')
                self.assertEqual(result['counts']['known_eligible_candidate_expected_cells'], 8000)
                self.assertEqual(result['counts']['inconsistent_classification_cells'], 0)

    def test_unmapped_current_types_with_missing_liquidity_remain_unknown(self):
        for kind in ('UNMAPPED_VENDOR_CODE', 'unknown', 'Common_Stock'):
            with self.subTest(kind=kind):
                self.setUp()
                rows = self.mapping_history()
                rows[-1]['instrument_type'] = kind
                self.change_table('security_master', rows)
                self.change_source('liquidity', [row for row in self.liquid if row['sid'] != SID[0]])
                result = self.audit()
                self.assertEqual(result['status'], 'insufficient_evidence')
                self.assertGreater(result['counts']['inconsistent_classification_cells'], 0)
                self.assertFalse(result['checks']['historical_classification_and_mapping_consistent'])

    def test_expired_mapping_or_exclusion_without_current_coverage_is_unknown(self):
        for kind, listed in (('common_stock', True), ('etf', True), ('common_stock', False)):
            with self.subTest(kind=kind, listed=listed):
                self.setUp()
                rows = self.mapping_history()
                rows = rows[:-1]
                rows[0].update(instrument_type=kind, listed=listed)
                self.change_table('security_master', rows)
                self.change_source('liquidity', [row for row in self.liquid if row['sid'] != SID[0]])
                result = self.audit()
                self.assertEqual(result['status'], 'insufficient_evidence')
                self.assertGreater(result['counts']['inconsistent_classification_cells'], 0)

    def test_future_current_coverage_cannot_preemptively_exclude_historical_sid(self):
        for kind, listed in (('common_stock', True), ('etf', True), ('common_stock', False)):
            with self.subTest(kind=kind, listed=listed):
                self.setUp()
                rows = self.mapping_history()
                rows[-1].update(instrument_type=kind, listed=listed,
                    available_at=ts('2018-02-01 09:00:00.000001').isoformat())
                self.change_table('security_master', rows)
                self.change_source('liquidity', [row for row in self.liquid if row['sid'] != SID[0]])
                result = self.audit()
                self.assertEqual(result['status'], 'insufficient_evidence')
                self.assertEqual(result['counts']['inconsistent_classification_cells'], 2)

    def test_current_coverage_knowledge_equality_and_one_microsecond_delay(self):
        for available, expected, unknown in (('2018-01-31 09:00', 'observations_passed', 0),
                ('2018-01-31 09:00:00.000001', 'insufficient_evidence', 1)):
            with self.subTest(available=available):
                self.setUp()
                rows = self.mapping_history()
                rows[-1].update(instrument_type='etf', available_at=ts(available).isoformat())
                self.change_table('security_master', rows)
                self.change_source('liquidity', [row for row in self.liquid if row['sid'] != SID[0]])
                result = self.audit()
                self.assertEqual(result['status'], expected)
                self.assertEqual(result['counts']['inconsistent_classification_cells'], unknown)

    def test_explicit_current_exclusions_do_not_need_unrelated_unknown_fields(self):
        for changes in ({'listed': False, 'instrument_type': 'UNMAPPED_VENDOR_CODE'},
                {'listed': None, 'instrument_type': 'etf'},
                {'listed': True, 'instrument_type': 'etf', 'exchange': None}):
            with self.subTest(changes=changes):
                self.setUp()
                rows = self.mapping_history()
                rows[-1].update(changes)
                self.change_table('security_master', rows)
                self.change_source('liquidity', [row for row in self.liquid if row['sid'] != SID[0]])
                result = self.audit()
                self.assertEqual(result['status'], 'observations_passed')
                self.assertEqual(result['counts']['inconsistent_classification_cells'], 0)

    def test_future_only_master_does_not_leak_a_sid_into_historical_obligations(self):
        rows = self.mapping_history()
        rows = [row for row in rows if row['sid'] != SID[0] or row['effective_to'] is None]
        rows[-1]['available_at'] = ts('2018-02-01 09:00:00.000001').isoformat()
        self.change_table('security_master', rows)
        self.change_source('liquidity', [row for row in self.liquid if row['sid'] != SID[0]])
        result = self.audit()
        self.assertEqual(result['status'], 'observations_passed')
        self.assertEqual(result['counts']['known_eligible_candidate_expected_cells'], 8000)
        self.assertEqual(result['counts']['inconsistent_classification_cells'], 0)

    def test_known_liquidity_sid_without_any_master_coverage_is_unknown_even_below_cutoff(self):
        self.change_table('security_master', [row for row in self.table_rows['security_master'] if row['sid'] != SID[0]])
        result = self.audit()
        self.assertEqual(result['status'], 'insufficient_evidence')
        self.assertEqual(result['counts']['observed_member_cells'], 400)
        self.assertGreater(result['counts']['inconsistent_classification_cells'], 0)

    def test_closed_classification_semantics_never_infer_excluded_from_unknown(self):
        from qresearch.data_certification import _classification_kind, _master_qualification
        included = {'common_stock', 'adr', 'reit_common'}
        excluded = {'etf', 'etn', 'closed_end_fund', 'preferred_stock', 'unit', 'warrant', 'otc'}
        for kind in included | excluded | {None, 'unknown', 'UNMAPPED_VENDOR_CODE', 'Common_Stock'}:
            with self.subTest(kind=kind):
                expected = 'included' if kind in included else 'excluded' if kind in excluded else 'unknown'
                self.assertEqual(_classification_kind(kind), expected)
                self.assertEqual(_master_qualification({'instrument_type': kind, 'listed': True, 'exchange': 'NYSE'}), expected)
                self.assertEqual(_master_qualification({'instrument_type': kind, 'listed': False, 'exchange': None}), 'excluded')

    def test_old_candidate_history_audit_preserves_private_originals_and_no_certification(self):
        self.change_table('security_master', self.mapping_history())
        rows = [row for row in self.liquid if row['sid'] != SID[0]]
        self.change_source('liquidity', rows)
        before, refs = dict(self.store._data), deepcopy(self.refs)
        result = self.audit()
        self.assertEqual(result['status'], 'insufficient_evidence')
        self.assertEqual(result['counts']['liquidity_record_count'], len(rows))
        self.assertEqual(result['evidence_refs']['liquidity'], refs['liquidity_refs'])
        self.assertTrue(all(self.store.read_bytes(key) == value for key, value in before.items()))
        for name in ('vendor_provenance_authenticated','full_historical_US200_certified',
                     'actual_availability_certified','financial_vintage_certified','research_certified',
                     'row_values_exported','financial_evidence'):
            self.assertIs(result[name], False)

    def test_modeled_end_time_never_promoted_to_actual_receipt(self):
        rows = deepcopy(self.liquid)
        for row in rows:
            row['availability_basis'] = 'modeled_lean_frontier'
        self.change_source('liquidity', rows)
        result = self.audit()
        self.assertEqual(result['counts']['missing_actual_timing_rows'], 201 * 21)
        self.assertFalse(result['checks']['declared_actual_timing_complete'])
        self.assertFalse(result['research_certified'])

    def test_unknown_historical_classification_is_not_a_filter(self):
        rows = deepcopy(self.liquid)
        rows[-1]['instrument_type'] = None
        self.change_source('liquidity', rows)
        result = self.audit()
        # Only Jan31 has unknown classification. It belongs to the Feb1
        # formation's history, never to the earlier Jan31 formation.
        self.assertEqual(result['counts']['unavailable_liquidity_formations'], 1)
        self.assertEqual(result['counts']['observed_member_cells'], 200)

    def test_sid_aliases_and_late_mapping_evidence_are_detected(self):
        rows = deepcopy(self.table_rows['security_master'])
        rows[0]['ticker'] = rows[-1]['ticker']
        self.change_table('security_master', rows)
        self.assertEqual(self.audit()['counts']['ambiguous_mapping_cells'], 2)
        rows = deepcopy(self.table_rows['security_master'])
        rows[-1]['available_at'] = ts('2018-02-01 10:00').isoformat()
        self.change_table('security_master', rows)
        self.assertEqual(self.audit()['counts']['missing_or_ambiguous_security_master_cells'], 2)

    def test_truncated_warmup_cannot_silently_lower_twenty_sessions(self):
        calendar = Calendar()
        calendar.frame = calendar.frame.iloc[3:]
        result = audit_data_certification(self.store, self.frozen_plan, calendar=calendar,
            ingestor=self.ingestor, synthetic=True, **self.refs)
        self.assertEqual(result['counts']['incomplete_warmup_formations'], 2)
        self.assertFalse(result['checks']['complete_twenty_session_warmup'])

    def test_unknown_action_sid_is_counted_without_silent_identity_repair(self):
        rows = deepcopy(self.table_rows['corporate_actions'])
        rows[0]['sid'] = 'not-a-historical-SID'
        self.change_table('corporate_actions', rows)
        result = self.audit()
        self.assertFalse(result['checks']['corporate_action_sids_known'])

    def test_corrupted_content_and_free_approval_metadata_are_rejected(self):
        reference = self.refs['membership_refs'][0]
        self.store._data[reference['key']] = b'{"certified":true,"private":"NEVER_EXPORT"}'
        with self.assertRaises(DataCertificationError) as caught:
            self.audit()
        self.assertNotIn('NEVER_EXPORT', str(caught.exception))
        for extra in ('certified','passed','final_test_enabled'):
            with self.subTest(extra=extra),self.assertRaises(DataCertificationError):
                DataCertificationPlan.from_dict(self.frozen_plan.to_dict() | {extra:True})

    def test_reference_kind_plan_and_duplicates_are_bound(self):
        for change in ({'price_refs':self.refs['membership_refs']}, {'membership_refs':self.refs['membership_refs']*2}):
            with self.subTest(change=change),self.assertRaises(DataCertificationError):self.audit(**change)
        other = plan(self.ingestor, plan_id='other-scope')
        with self.assertRaises(DataCertificationError):
            audit_data_certification(self.store, other, calendar=self.calendar, ingestor=self.ingestor, synthetic=True, **self.refs)

    def test_final_naive_and_tunable_ranking_plans_are_rejected(self):
        for changes in ({'start':'2018-01-31'},{'end_exclusive':ts('2024-01-02').isoformat()},
                        {'warmup_start':ts('2018-01-31').isoformat()},{'universe_size':True},
                        {'universe_size':199},{'liquidity_lookback_sessions':19}):
            with self.subTest(changes=changes),self.assertRaises(DataCertificationError):plan(self.ingestor, **changes)

    def test_all_missing_evidence_reports_gaps_without_approval(self):
        result = audit_data_certification(self.store, self.frozen_plan, calendar=self.calendar, synthetic=True)
        self.assertEqual(result['status'], 'insufficient_evidence')
        self.assertEqual(result['counts']['formation_count'], 2)
        self.assertFalse(result['research_certified'])
        self.assertFalse(result['checks']['all_required_input_components_present'])

    def test_source_batches_read_once_then_shared_calculations_reuse_verified_rows(self):
        with patch.object(self.ingestor, '_records', wraps=self.ingestor._records) as read:
            result = self.audit()
        self.assertEqual(read.call_count, 2)
        self.assertEqual(result['status'], 'observations_passed')

    def test_real_rows_require_cloud_and_calendar_before_writes(self):
        before = dict(self.store._data)
        with self.assertRaises(DataCertificationError):
            audit_data_certification(self.store, self.frozen_plan, calendar=self.calendar, ingestor=self.ingestor, **self.refs)
        with self.assertRaises(DataCertificationError):
            store_certification_table(self.store, self.frozen_plan, 'membership', self.table_rows['membership'])
        self.assertEqual(self.store._data, before)

    def test_idempotent_report_and_mutated_catalog_identity(self):
        first = self.audit()
        count = len(self.store._data)
        self.assertEqual(self.audit(), first)
        self.assertEqual(len(self.store._data), count)
        self.ingestor.financial_catalog = {}
        with self.assertRaises(DataCertificationError):self.audit()

    def test_raw_price_identity_and_financial_ambiguity_fail_closed(self):
        rows = deepcopy(self.table_rows['prices'])
        rows[0]['normalization'] = 'adjusted'
        self.change_table('prices', rows)
        with self.assertRaises(DataCertificationError):self.audit()
        self.change_table('prices', self.table_rows['prices'])
        row = deepcopy(self.financial[-1]);row['source_revision']='simultaneous-v2';row['value']=1
        self.change_source('financial', self.financial + [row])
        result = self.audit()
        # The shared validate_records rejects the entire simultaneous-vintage
        # batch. Missing financial evidence still cannot alter membership.
        self.assertEqual(result['counts']['unavailable_financial_formations'],2)
        self.assertEqual(result['counts']['financial_missing_cells'],400)
        self.assertEqual(result['counts']['observed_member_cells'],400)

    def test_date_only_publication_waits_for_actual_next_exchange_close(self):
        rows = deepcopy(self.financial)
        rows[-1].update(public_at=None, public_date='2018-01-30', public_precision='date',
            vendor_available_at=ts('2018-01-30 17:00').isoformat(),historical_ingested_at=ts('2018-01-30 17:05').isoformat())
        self.change_source('financial',rows)
        result=self.audit()
        self.assertEqual(result['counts']['financial_available_cells'],399)
        self.assertEqual(result['counts']['financial_missing_cells'],1)
        self.assertEqual(result['counts']['observed_member_cells'],400)

    def test_frozen_partition_summary_cannot_expand_sample_or_accept_free_flags(self):
        observed=self.audit()
        manifest={name:observed[name] for name in ('source_manifest_hash','ingestion_namespace','data_version_hash','financial_catalog_hash')}
        manifest.update(schema_version=1,start=observed['scope_start'],end_exclusive=observed['scope_end_exclusive'],
            partitions=[{'plan_hash':observed['plan_hash'],'start':observed['scope_start'],
                'end_exclusive':observed['scope_end_exclusive'],'report_ref':observed['report_ref']}])
        result=summarize_certification_scope(self.store,manifest,content_hash(manifest),calendar=self.calendar,synthetic=True)
        self.assertEqual(result['status'],'observations_passed')
        self.assertEqual(result['counts']['expected_member_cells'],400)
        self.assertFalse(result['research_certified'])
        self.assertTrue(result['raw_rows_recomputed_here'])
        expanded=deepcopy(manifest);expanded.update(start=ts('2010-01-01').isoformat(),end_exclusive=ts('2024-01-01').isoformat())
        result=summarize_certification_scope(self.store,expanded,content_hash(expanded),calendar=self.calendar,synthetic=True)
        self.assertEqual(result['status'],'insufficient_evidence')
        self.assertFalse(result['partition_intervals_cover_target'])
        self.assertTrue(result['declared_full_development_interval'])
        self.assertFalse(result['full_historical_US200_certified'])
        absent=deepcopy(manifest);absent['partitions'][0]['report_ref']=None
        result=summarize_certification_scope(self.store,absent,content_hash(absent),calendar=self.calendar,synthetic=True)
        self.assertEqual(result['missing_report_count'],1)
        self.assertEqual(result['status'],'insufficient_evidence')
        for mutation in ('duplicate','changed_source','free_approval','changed_counts','empty_counts','empty_refs','future_warmup'):
            altered=deepcopy(manifest)
            if mutation=='duplicate':altered['partitions']*=2
            elif mutation=='changed_source':altered['source_manifest_hash']='b'*64
            else:
                body={key:value for key,value in observed.items() if key!='report_ref'}
                if mutation=='free_approval':body['research_certified']=True
                elif mutation=='changed_counts':body['counts']=dict(body['counts'],observed_member_cells=401)
                elif mutation=='empty_counts':body['counts']={name:0 for name in body['counts']}
                elif mutation=='empty_refs':body['evidence_refs']={name:[] for name in body['evidence_refs']}
                else:body['warmup_start']=ts('2026-01-01').isoformat()
                raw=canonical_json(body);digest=sha256(raw).hexdigest();ref={'key':'data-certification/v1/reports/'+digest+'.json','sha256':digest}
                self.store.write_once(ref['key'],raw);altered['partitions'][0]['report_ref']=ref
            with self.subTest(mutation=mutation),self.assertRaises(DataCertificationError):
                summarize_certification_scope(self.store,altered,content_hash(altered),calendar=self.calendar,synthetic=True)
        with self.assertRaises(DataCertificationError):
            summarize_certification_scope(self.store,manifest,'b'*64,calendar=self.calendar,synthetic=True)

    def test_capabilities_and_CLI_remain_metadata_only(self):
        catalog = json.loads((ROOT/'config/source_catalog.json').read_bytes())['fields']
        result = certification_capabilities(catalog)
        self.assertEqual(result['declared_financial_value_field_count'],1)
        self.assertFalse(result['ready_to_dispatch'])
        self.assertNotIn('financial_value_catalog_not_available',result['gap_codes'])
        with tempfile.TemporaryDirectory() as directory:
            file=Path(directory)/'plan.json';file.write_bytes(canonical_json(self.frozen_plan.to_dict()))
            command=[sys.executable,'-B',str(ROOT/'tools/data_certification.py'),'validate-plan','--plan-file',str(file)]
            complete=subprocess.run(command,capture_output=True,text=True,cwd=ROOT)
            self.assertEqual(complete.returncode,0,complete.stderr)
            self.assertFalse(json.loads(complete.stdout)['ready_to_dispatch'])
            file.write_bytes(b'{"certified":true,"rows":["NEVER_EXPORT"]}')
            complete=subprocess.run(command,capture_output=True,text=True,cwd=ROOT)
            self.assertEqual(complete.returncode,2)
            self.assertNotIn('NEVER_EXPORT',complete.stdout+complete.stderr)


if __name__ == '__main__':
    unittest.main()
