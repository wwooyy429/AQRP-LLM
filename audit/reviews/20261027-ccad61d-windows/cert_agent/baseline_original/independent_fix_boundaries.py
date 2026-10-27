"""Additional independent WR20 fix boundaries, including old mapping/history interaction."""
from cert_fixture import *
import hashlib,io,socket,time,unittest
O=Path(__file__).parent;SCENARIOS=[];NETWORK=[]
FLAGS=('vendor_provenance_authenticated','full_historical_US200_certified','actual_availability_certified','financial_vintage_certified','research_certified','row_values_exported','financial_evidence')
def denied(*a,**k):NETWORK.append(True);raise AssertionError('Network is forbidden')
socket.socket.connect=denied;socket.create_connection=denied
def note(name):SCENARIOS.append(name)
def ipo(raw,stamp,*,available=None,claimed=None,drop_pre=False):
 listing=ts(stamp);available=ts(available) if available else listing
 for r in raw['liquid']:
  if r['sid']=='SID200':r.update(dollar_volume=2000,listing_effective_at=iso(listing),listing_available_at=iso(available),classification_effective_at=iso(listing),classification_available_at=iso(available))
 for r in raw['tables']['security_master']:
  if r['sid']=='SID200':r.update(effective_from=iso(listing),available_at=iso(available))
 if drop_pre:raw['liquid']=[r for r in raw['liquid'] if r['sid']!='SID200' or pd.Timestamp(r['session'])>=listing]
 expected=[];post_counts=[]
 for index,row in enumerate(raw['tables']['membership']):
  formation,close=[p for p in raw['pairs'] if iso(p[0])==row['formation_at']][0]
  sessions=[c for _,c in raw['pairs'] if c<=close][-20:]
  count=sum(c>=listing for c in sessions);post_counts.append(count)
  use=(count==20 and available<=formation) if claimed is None else claimed[index]
  row['sids']=['SID200']+raw['sids'][:199] if use else list(raw['members'])
  expected.append([row['formation_at'],row['sids']])
 return expected,post_counts
def master_update(raw,*,rename=True):
 old=raw['tables']['security_master'][0];old['effective_to']='2018-01-25T00:00:00-05:00'
 new=deepcopy(old);new.update(effective_from='2018-01-25T00:00:00-05:00',effective_to=None,available_at='2018-01-25T00:00:00-05:00')
 if rename:new['ticker']='RENAMED000'
 raw['tables']['security_master'].append(new)
def assert_false(test,r):test.assertTrue(all(r[k] is False for k in FLAGS))
class Boundaries(unittest.TestCase):
 def test_listing_intraday_exact_close_and_one_microsecond_after(self):
  for stamp,counts in [('2018-01-04 12:00:00',[19,20]),('2018-01-04 16:00:00',[19,20]),('2018-01-04 16:00:00.000001',[18,19])]:
   with self.subTest(stamp=stamp):
    note('IPO_clock_'+stamp);raw=raw_fixture();expected,got=ipo(raw,stamp);self.assertEqual(got,counts)
    f=make(raw=raw);r=run(f);self.assertEqual(r['status'],'observations_passed');self.assertEqual(r['ranked_membership_hash'],content_hash(expected));assert_false(self,r)

 def test_invalid_membership_after_close_and_young_IPO_is_rejected(self):
  for stamp,claim in [('2018-01-04 16:00:00',[True,True]),('2018-01-04 16:00:00.000001',[False,True]),('2018-01-25 12:00:00',[True,True])]:
   with self.subTest(stamp=stamp):
    note('invalid_IPO_claim_'+stamp);raw=raw_fixture();ipo(raw,stamp,claimed=claim);f=make(raw=raw);r=run(f)
    self.assertEqual(r['status'],'insufficient_evidence');self.assertFalse(r['checks']['ranked_membership_matches']);self.assertGreater(r['counts']['membership_mismatch_formations'],0);self.assertEqual(r['counts']['liquidity_record_count'],4221);assert_false(self,r)

 def test_listing_information_is_available_only_at_or_before_formation(self):
  for available in ('2018-02-01 09:00:00','2018-02-01 09:00:00.000001','2018-02-02 09:00:00.000001'):
   with self.subTest(available=available):
    note('listing_available_'+available);raw=raw_fixture();expected,_=ipo(raw,'2018-01-03 12:00:00',available=available);r=run(make(raw=raw))
    self.assertEqual(r['status'],'observations_passed');self.assertEqual(r['ranked_membership_hash'],content_hash(expected));assert_false(self,r)

 def test_unknown_listing_and_availability_are_not_silently_filtered(self):
  for field in ('listing_effective_at','listing_available_at'):
   with self.subTest(field=field):
    note('unknown_'+field)
    def change(raw):raw['liquid'][0][field]=None
    r=run(make(change));self.assertEqual(r['status'],'insufficient_evidence');self.assertGreater(r['counts']['unavailable_liquidity_formations'],0);assert_false(self,r)

 def test_recent_classification_and_mapping_do_not_reset_old_listing(self):
  for variant in ('classification','mapping','both'):
   with self.subTest(variant=variant):
    note('recent_'+variant)
    def change(raw):
     if variant in ('classification','both'):
      for row in raw['liquid']:
       row.update(classification_effective_at='2018-01-25T00:00:00-05:00',classification_available_at='2018-01-25T00:00:00-05:00')
     if variant in ('mapping','both'):master_update(raw)
    r=run(make(change));self.assertEqual(r['status'],'observations_passed');self.assertEqual(r['counts']['known_eligible_candidate_expected_cells'],8040);assert_false(self,r)

 def test_old_eligible_missing_history_after_mapping_must_not_fill_rank201(self):
  for variant in ('one_session_missing','all_sessions_missing','all_missing_same_ticker_new_interval'):
   with self.subTest(variant=variant):
    note('old_eligible_mapping_'+variant)
    def change(raw):
     master_update(raw,rename=variant!='all_missing_same_ticker_new_interval')
     if variant=='one_session_missing':raw['liquid']=[x for x in raw['liquid'] if not(x['sid']=='SID200' and x['session']==iso(raw['pairs'][0][1]))]
     else:
      raw['liquid']=[x for x in raw['liquid'] if x['sid']!='SID000']
      for row in raw['tables']['membership']:row['sids']=raw['sids'][1:201]
    r=run(make(change));self.assertEqual(r['status'],'insufficient_evidence','A retained old listed master interval cannot be treated as a young IPO because the current mapping is new');self.assertFalse(r['checks']['all_known_eligible_candidate_histories_complete']);self.assertGreater(r['counts']['missing_candidate_session_cells'],0);assert_false(self,r)

 def test_ranking_view_does_not_delete_original_rows_refs_or_counts(self):
  results=[]
  for drop in (False,True):
   note('young_IPO_refs_drop_pre_'+str(drop));raw=raw_fixture();expected,_=ipo(raw,'2018-01-25 12:00:00',drop_pre=drop);f=make(raw=raw)
   before={k:bytes(v) for k,v in f['store']._data.items()};refs=deepcopy(f['refs']);r=run(f)
   self.assertEqual(r['status'],'observations_passed');self.assertEqual(r['evidence_refs'],refs);self.assertEqual(r['counts']['liquidity_record_count'],len(raw['liquid']));self.assertEqual(r['ranked_membership_hash'],content_hash(expected))
   self.assertTrue(all(f['store'].read_bytes(k)==v for k,v in before.items()));self.assertEqual(len(f['ingestor']._combined_records(refs['liquidity'],'liquidity')),len(raw['liquid']));assert_false(self,r);results.append(r)
  self.assertEqual(results[0]['ranked_membership_hash'],results[1]['ranked_membership_hash']);self.assertGreater(results[0]['counts']['liquidity_record_count'],results[1]['counts']['liquidity_record_count'])

 def test_summary_reopens_IPO_private_inputs_and_rejects_forgery(self):
  for variant in ('private_batch_tamper','fake_count','empty_refs'):
   with self.subTest(variant=variant):
    note('IPO_summary_'+variant);raw=raw_fixture();ipo(raw,'2018-01-25 12:00:00');f=make(raw=raw);r=run(f);m=scope(f,r)
    if variant=='private_batch_tamper':f['store']._data[f['refs']['liquidity'][0]['key']]=b'{}'
    else:
     fake=deepcopy(r);fake.pop('report_ref')
     if variant=='fake_count':fake['counts']['liquidity_record_count']-=15
     else:fake['evidence_refs']={k:[] for k in fake['evidence_refs']}
     h=content_hash(fake);key='data-certification/v1/reports/'+h+'.json';f['store'].write_once(key,canonical_json(fake));m['partitions'][0]['report_ref']={'key':key,'sha256':h}
    with self.assertRaises(DataCertificationError):summarize_certification_scope(f['store'],m,content_hash(m),calendar=f['kwargs']['calendar'],synthetic=True)

 def test_fixed_IPO_observations_and_summary_never_authenticate_vendor(self):
  note('IPO_observed_summary_false_flags');raw=raw_fixture();ipo(raw,'2018-01-04 16:00:00');f=make(raw=raw);r=run(f);m=scope(f,r);s=summarize_certification_scope(f['store'],m,content_hash(m),calendar=f['kwargs']['calendar'],synthetic=True)
  self.assertEqual(s['status'],'observations_passed');self.assertTrue(s['raw_rows_recomputed_here']);assert_false(self,r);assert_false(self,s);self.assertFalse(s['declared_full_development_interval'])

class Result(unittest.TextTestResult):
 def __init__(self,*a,**k):super().__init__(*a,**k);self.successes=[]
 def addSuccess(self,t):self.successes.append(t.id());super().addSuccess(t)
if __name__=='__main__':
 before={p.relative_to(SOURCE).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in SOURCE.rglob('*') if p.is_file()};out=io.StringIO();start=time.perf_counter();r=unittest.TextTestRunner(stream=out,verbosity=2,resultclass=Result).run(unittest.defaultTestLoader.loadTestsFromTestCase(Boundaries))
 failures={t.id().split(' (')[0] for t,_ in r.failures};errors={t.id().split(' (')[0] for t,_ in r.errors}
 report={'fixed_commit':'ea6053e3e9ef4be17db246daf18a4cf9b2e5be58','methods':r.testsRun,'passed_methods':len(r.successes),'failed_methods':len(failures),'error_methods':len(errors),'failure_records':len(r.failures),'error_records':len(r.errors),'scenario_checks':len(SCENARIOS),'scenario_checks_not_unittest_subcases':True,'scenarios':SCENARIOS,'failures':[{'method':t.id(),'traceback':tb} for t,tb in r.failures],'errors':[{'method':t.id(),'traceback':tb} for t,tb in r.errors],'seconds':time.perf_counter()-start,'source_unchanged':before=={p.relative_to(SOURCE).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in SOURCE.rglob('*') if p.is_file()},'network_attempts':len(NETWORK),'actual_QC_market_model_or_authoritative_budget_calls':0,'original_independent_fixture':True}
 (O/'boundaries_first_results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');(O/'boundaries_first_unittest.txt').write_text(out.getvalue(),encoding='utf-8');print(out.getvalue());print(json.dumps({k:v for k,v in report.items() if k not in ('failures','errors','scenarios')},ensure_ascii=False,indent=2));raise SystemExit(0 if r.wasSuccessful() else 1)
