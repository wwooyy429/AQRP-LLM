"""Independent developer boundary probes for observed data certification."""
from pathlib import Path
from copy import deepcopy
from hashlib import sha256
import json,sys,unittest
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'cloud'),str(ROOT/'tests')]
from qresearch.artifacts import content_hash,canonical_json
from qresearch.data_certification import audit_data_certification,DataCertificationError,DataCertificationPlan,store_certification_table,summarize_certification_scope
import test_data_certification as fixture

FLAGS=('full_historical_US200_certified','actual_availability_certified','financial_vintage_certified','research_certified','vendor_provenance_authenticated','financial_evidence','row_values_exported')

def scope(report):
 value={k:report[k] for k in ('source_manifest_hash','ingestion_namespace','data_version_hash','financial_catalog_hash')}
 value.update(schema_version=1,start=report['scope_start'],end_exclusive=report['scope_end_exclusive'],partitions=[{'plan_hash':report['plan_hash'],'start':report['scope_start'],'end_exclusive':report['scope_end_exclusive'],'report_ref':report['report_ref']}])
 return value

class IndependentCertificationPeer(unittest.TestCase):
 @classmethod
 def setUpClass(cls):fixture.DataCertificationTests.setUpClass()
 def setUp(self):
  self.f=fixture.DataCertificationTests();self.f.setUp()
 def test_exact_hand_answer_remains_observation_only_and_metadata_private(self):
  r=self.f.audit();self.assertEqual(r['status'],'observations_passed');self.assertEqual(r['counts']['formation_count'],2)
  for key in ('expected_member_cells','observed_member_cells','financial_available_cells','price_observed_cells'):self.assertEqual(r['counts'][key],400)
  for key in FLAGS:self.assertIs(r[key],False)
  for secret in (fixture.SID[-1], '123456.78901','88888.12345','synthetic-original-v1'):self.assertNotIn(secret,json.dumps(r))
 def test_delayed_old_eligible_candidate_cannot_hide_behind_rank201(self):
  rows=deepcopy(self.f.liquid)
  for row in rows:
   if row['sid']==fixture.SID[-1] and row['session']==fixture.ts('2018-01-30 16:00').isoformat():row.update(vendor_available_at=fixture.ts('2018-01-31 10:00').isoformat(),historical_ingested_at=fixture.ts('2018-01-31 10:05').isoformat())
  self.f.change_source('liquidity',rows)
  members=deepcopy(self.f.table_rows['membership']);members[0]['sids']=list(reversed(fixture.SID[:-1]));self.f.change_table('membership',members)
  prices=deepcopy(self.f.table_rows['prices'])
  for row in prices:
   if row['sid']==fixture.SID[-1] and row['session']==fixture.ts('2018-01-30 16:00').isoformat():row['sid']=fixture.SID[0]
  self.f.change_table('prices',prices);r=self.f.audit()
  self.assertEqual(r['counts']['observed_member_cells'],400);self.assertEqual(r['counts']['price_missing_cells'],0)
  self.assertEqual(r['counts']['missing_candidate_session_cells'],1);self.assertFalse(r['checks']['all_known_eligible_candidate_histories_complete']);self.assertEqual(r['status'],'insufficient_evidence')
 def test_ambiguous_financial_vintage_never_changes_rank_or_picks_arbitrary_value(self):
  baseline=self.f.audit();row=deepcopy(self.f.financial[-1]);row.update(source_revision='simultaneous-peer-v2',value=7)
  self.f.change_source('financial',self.f.financial+[row]);r=self.f.audit()
  self.assertEqual(r['ranked_membership_hash'],baseline['ranked_membership_hash']);self.assertEqual(r['counts']['observed_member_cells'],400)
  self.assertEqual(r['counts']['unavailable_financial_formations'],2);self.assertEqual(r['counts']['financial_missing_cells'],400);self.assertEqual(r['status'],'insufficient_evidence')
 def test_future_raw_price_receipt_is_missing_and_unknown_action_SID_is_not_certified(self):
  baseline=self.f.audit();rows=deepcopy(self.f.table_rows['prices']);rows[-1]['available_at']=fixture.ts('2018-02-01 10:00').isoformat();self.f.change_table('prices',rows)
  actions=deepcopy(self.f.table_rows['corporate_actions']);actions[0]['sid']='UNKNOWN-PRIVATE-PEER-SID';self.f.change_table('corporate_actions',actions);r=self.f.audit()
  self.assertEqual(r['counts']['price_missing_cells'],1);self.assertEqual(r['ranked_membership_hash'],baseline['ranked_membership_hash']);self.assertFalse(r['checks']['corporate_action_sids_known']);self.assertEqual(r['status'],'insufficient_evidence');self.assertNotIn('UNKNOWN-PRIVATE-PEER-SID',json.dumps(r))
 def test_self_consistent_zero_counts_empty_refs_and_free_checks_are_recomputed(self):
  r=self.f.audit();m=scope(r);body={k:deepcopy(v) for k,v in r.items() if k!='report_ref'}
  body['counts']={key:0 for key in body['counts']};body['evidence_refs']={key:[] for key in body['evidence_refs']};self.assertTrue(all(body['checks'].values()))
  raw=canonical_json(body);digest=sha256(raw).hexdigest();ref={'key':'data-certification/v1/reports/'+digest+'.json','sha256':digest};self.f.store.write_once(ref['key'],raw);m['partitions'][0]['report_ref']=ref
  with self.assertRaises(DataCertificationError):summarize_certification_scope(self.f.store,m,content_hash(m),calendar=self.f.calendar,synthetic=True)
 def test_missing_private_source_cannot_be_replaced_by_a_valid_cached_report(self):
  r=self.f.audit();m=scope(r);key=r['evidence_refs']['liquidity'][0]['key'];del self.f.store._data[key];before=dict(self.f.store._data)
  with self.assertRaises(DataCertificationError):summarize_certification_scope(self.f.store,m,content_hash(m),calendar=self.f.calendar,synthetic=True)
  self.assertEqual(self.f.store._data,before)
 def test_small_scope_and_missing_partition_never_promote_complete_history(self):
  r=self.f.audit();m=scope(r);m.update(start=fixture.ts('2010-01-01').isoformat(),end_exclusive=fixture.ts('2024-01-01').isoformat())
  s=summarize_certification_scope(self.f.store,m,content_hash(m),calendar=self.f.calendar,synthetic=True)
  self.assertTrue(s['declared_full_development_interval']);self.assertFalse(s['partition_intervals_cover_target']);self.assertEqual(s['status'],'insufficient_evidence')
  for key in FLAGS:self.assertIs(s[key],False)
  missing=scope(r);missing['partitions'][0]['report_ref']=None;s=summarize_certification_scope(self.f.store,missing,content_hash(missing),calendar=self.f.calendar,synthetic=True)
  self.assertEqual(s['missing_report_count'],1);self.assertEqual(s['status'],'insufficient_evidence')
 def test_historical_ticker_alias_and_unknown_classification_do_not_pass(self):
  rows=deepcopy(self.f.table_rows['security_master']);rows[0]['ticker']=rows[-1]['ticker'];rows[-2]['instrument_type']=None;self.f.change_table('security_master',rows);r=self.f.audit()
  self.assertEqual(r['counts']['ambiguous_mapping_cells'],2);self.assertEqual(r['counts']['inconsistent_classification_cells'],2);self.assertEqual(r['counts']['observed_member_cells'],400);self.assertEqual(r['status'],'insufficient_evidence')
 def test_no_real_rows_can_enter_local_store_or_final_window_via_plan(self):
  before=dict(self.f.store._data)
  with self.assertRaises(DataCertificationError):store_certification_table(self.f.store,self.f.frozen_plan,'prices',self.f.table_rows['prices'])
  with self.assertRaises(DataCertificationError):audit_data_certification(self.f.store,self.f.frozen_plan,calendar=self.f.calendar,ingestor=self.f.ingestor,**self.f.refs)
  self.assertEqual(self.f.store._data,before)
  for changes in ({'end_exclusive':'2026-10-24T00:00:00-04:00'},{'universe_size':True},{'liquidity_lookback_sessions':19},{'research_certified':True}):
   with self.subTest(changes=changes),self.assertRaises(DataCertificationError):DataCertificationPlan.from_dict(self.f.frozen_plan.to_dict()|changes)

if __name__=='__main__':unittest.main(verbosity=2)
