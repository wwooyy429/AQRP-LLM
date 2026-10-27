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
        self.assertEqual(result['declared_financial_value_field_count'],0)
        self.assertFalse(result['ready_to_dispatch'])
        self.assertIn('financial_value_catalog_not_available',result['gap_codes'])
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
