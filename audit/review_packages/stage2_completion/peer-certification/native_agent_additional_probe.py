"""Extra native-agent developer probes; synthetic only, no provider or ledger."""
from pathlib import Path
from copy import deepcopy
from hashlib import sha256
import json,sys,unittest
import pandas as pd
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'cloud'),str(ROOT/'tests')]
import qresearch.data_certification as cert
from qresearch.artifacts import canonical_json,content_hash
import test_data_certification as fixture

class NativeAgentAdditionalCertificationProbe(unittest.TestCase):
 @classmethod
 def setUpClass(cls):fixture.DataCertificationTests.setUpClass()
 def setUp(self):
  self.c=fixture.DataCertificationTests('test_known_answer_201_candidates_21_sessions_200_members_and_no_approval');self.c.setUp()
 def manifest(self,r):
  m={n:r[n] for n in ('source_manifest_hash','ingestion_namespace','data_version_hash','financial_catalog_hash')};m.update(schema_version=1,start=r['scope_start'],end_exclusive=r['scope_end_exclusive'],partitions=[{'plan_hash':r['plan_hash'],'start':r['scope_start'],'end_exclusive':r['scope_end_exclusive'],'report_ref':r['report_ref']}]);return m
 def summary(self,m,calendar=None):return cert.summarize_certification_scope(self.c.store,m,content_hash(m),calendar=calendar or self.c.calendar,synthetic=True)
 def altered(self,r,mutate):
  b={k:deepcopy(v) for k,v in r.items() if k!='report_ref'};mutate(b);raw=canonical_json(b);digest=sha256(raw).hexdigest();ref={'key':'data-certification/v1/reports/'+digest+'.json','sha256':digest};self.c.store.write_once(ref['key'],raw);m=self.manifest(r);m['partitions'][0]['report_ref']=ref;return m
 def test_complete_declared_rows_do_not_authenticate_or_export_values(self):
  r=self.c.audit();self.assertEqual(r['status'],'observations_passed')
  for k in ('vendor_provenance_authenticated','full_historical_US200_certified','actual_availability_certified','financial_vintage_certified','research_certified','row_values_exported','financial_evidence'):self.assertIs(r[k],False)
  for secret in (fixture.SID[-1],'88888.12345','123456.78901','synthetic-original-v1'):self.assertNotIn(secret,json.dumps(r))
 def test_zero_counts_with_all_true_checks_are_rejected(self):
  r=self.c.audit()
  with self.assertRaises(cert.DataCertificationError):self.summary(self.altered(r,lambda b:b.update(counts={k:0 for k in b['counts']})))
 def test_empty_refs_with_all_true_checks_are_rejected(self):
  r=self.c.audit()
  with self.assertRaises(cert.DataCertificationError):self.summary(self.altered(r,lambda b:b.update(evidence_refs={k:[] for k in b['evidence_refs']})))
 def test_changed_price_counter_and_impossible_warmup_are_rejected(self):
  r=self.c.audit()
  for mutate in (lambda b:b['counts'].update(price_expected_cells=0),lambda b:b.update(warmup_start=b['scope_end_exclusive'])):
   with self.subTest(mutate=mutate),self.assertRaises(cert.DataCertificationError):self.summary(self.altered(r,mutate))
 def replace_candidate(self,late=False):
  rows=deepcopy(self.c.liquid);first=self.c.calendar.sessions[0].isoformat();sid=fixture.SID[-1]
  if late:
   row=next(r for r in rows if r['sid']==sid and r['session']==first);row.update(vendor_available_at=fixture.ts('2018-01-31 10:00').isoformat(),historical_ingested_at=fixture.ts('2018-01-31 10:05').isoformat())
  else:rows=[r for r in rows if not(r['sid']==sid and r['session']==first)]
  self.c.change_source('liquidity',rows);members=deepcopy(self.c.table_rows['membership']);members[0]['sids']=list(reversed(fixture.SID[:-1]));self.c.change_table('membership',members);prices=deepcopy(self.c.table_rows['prices']);old=next(r for r in prices if r['sid']==sid);prices.remove(old);old['sid']=fixture.SID[0];prices.append(old);self.c.change_table('prices',prices)
 def test_missing_known_candidate_cannot_be_hidden_by_rank201(self):
  self.replace_candidate();r=self.c.audit();self.assertEqual(r['counts']['observed_member_cells'],400);self.assertEqual(r['status'],'insufficient_evidence');self.assertGreater(r['counts']['missing_candidate_session_cells'],0)
 def test_late_known_candidate_cannot_be_hidden_by_rank201(self):
  self.replace_candidate(late=True);r=self.c.audit();self.assertEqual(r['counts']['observed_member_cells'],400);self.assertEqual(r['status'],'insufficient_evidence');self.assertGreater(r['counts']['missing_candidate_session_cells'],0)
 def test_empty_calendar_never_vacuously_passes(self):
  cal=fixture.Calendar();cal.frame=cal.frame.iloc[:0];r=cert.audit_data_certification(self.c.store,self.c.frozen_plan,calendar=cal,synthetic=True);self.assertEqual(r['status'],'insufficient_evidence');self.assertEqual(r['counts']['formation_count'],0);self.assertFalse(r['checks']['ranked_membership_matches'])
 def test_changed_calendar_duplicate_scope_and_foreign_source_are_rejected(self):
  r=self.c.audit();m=self.manifest(r);cal=fixture.Calendar();cal.frame=cal.frame.iloc[:-1]
  with self.assertRaises(cert.DataCertificationError):self.summary(m,calendar=cal)
  for altered in (dict(m,partitions=m['partitions']*2),dict(m,source_manifest_hash='b'*64)):
   with self.assertRaises(cert.DataCertificationError):self.summary(altered)
 def test_private_context_corruption_fails_without_disclosure(self):
  r=self.c.audit();m=self.manifest(r);self.c.store._data[r['context_ref']['key']]=b'{"private":"NEVER_EXPORT_CORRUPTION"}'
  with self.assertRaises(cert.DataCertificationError) as caught:self.summary(m)
  self.assertNotIn('NEVER_EXPORT_CORRUPTION',str(caught.exception))
 def scoped(self,start,end):
  p=fixture.plan(self.c.ingestor,start=fixture.ts(start).isoformat(),end_exclusive=fixture.ts(end).isoformat(),plan_id='synthetic-peer-'+start);refs={k:deepcopy(v) for k,v in self.c.refs.items() if k in ('liquidity_refs','financial_refs')}
  for component,arg in {'membership':'membership_refs','prices':'price_refs','security_master':'security_master_refs','corporate_actions':'corporate_action_refs'}.items():
   rows=deepcopy(self.c.table_rows[component])
   if component=='membership':rows=[r for r in rows if fixture.ts(start)<=pd.Timestamp(r['formation_at'])<fixture.ts(end)]
   refs[arg]=[cert.store_certification_table(self.c.store,p,component,rows,synthetic=True)]
  return cert.audit_data_certification(self.c.store,p,calendar=self.c.calendar,ingestor=self.c.ingestor,synthetic=True,**refs)
 def two_scope(self):
  first=self.scoped('2018-01-31','2018-02-01');second=self.scoped('2018-02-01','2018-02-02');m=self.manifest(first);m['end_exclusive']=second['scope_end_exclusive'];m['partitions'].append(self.manifest(second)['partitions'][0]);return m
 def test_two_contiguous_partitions_recompute_and_do_not_certify_full_history(self):
  r=self.summary(self.two_scope());self.assertEqual(r['status'],'observations_passed');self.assertEqual(r['counts']['formation_count'],2);self.assertEqual(r['counts']['expected_member_cells'],400);self.assertTrue(r['raw_rows_recomputed_here']);self.assertTrue(r['counts_are_partition_sums_not_unique_rows']);self.assertFalse(r['full_historical_US200_certified'])
 def test_missing_second_partition_stays_insufficient(self):
  m=self.two_scope();m['partitions'][1]['report_ref']=None;r=self.summary(m);self.assertEqual(r['status'],'insufficient_evidence');self.assertEqual(r['missing_report_count'],1);self.assertEqual(r['counts']['formation_count'],1)
 def test_full_target_cannot_be_inferred_from_two_small_partitions(self):
  m=self.two_scope();m.update(start=fixture.ts('2010-01-01').isoformat(),end_exclusive=fixture.ts('2024-01-01').isoformat());r=self.summary(m);self.assertEqual(r['status'],'insufficient_evidence');self.assertFalse(r['partition_intervals_cover_target']);self.assertTrue(r['declared_full_development_interval']);self.assertFalse(r['full_historical_US200_certified'])
 def test_real_local_residency_and_truthy_synthetic_aliases_are_rejected(self):
  before=dict(self.c.store._data)
  for synthetic in (False,0,1,'true'):
   with self.subTest(synthetic=synthetic),self.assertRaises(cert.DataCertificationError):cert.audit_data_certification(self.c.store,self.c.frozen_plan,calendar=self.c.calendar,synthetic=synthetic)
  self.assertEqual(self.c.store._data,before)
 def test_future_financial_delivery_never_changes_membership(self):
  old=self.c.audit();rows=deepcopy(self.c.financial)
  for r in rows:r.update(vendor_available_at=fixture.ts('2018-02-01 10:00').isoformat(),historical_ingested_at=fixture.ts('2018-02-01 10:01').isoformat())
  self.c.change_source('financial',rows);r=self.c.audit();self.assertEqual(r['counts']['financial_missing_cells'],400);self.assertEqual(r['ranked_membership_hash'],old['ranked_membership_hash']);self.assertFalse(r['financial_vintage_certified'])

if __name__=='__main__':unittest.main(verbosity=2,defaultTest='NativeAgentAdditionalCertificationProbe')
