"""Independent historical SID, interval, knowledge-time and classification tests."""
from cert_fixture import *
import hashlib,io,socket,time,unittest
O=Path(__file__).parent;SCENARIOS=[];NETWORK=[]
FLAGS=('vendor_provenance_authenticated','full_historical_US200_certified','actual_availability_certified','financial_vintage_certified','research_certified','row_values_exported','financial_evidence')
def denied(*a,**k):NETWORK.append(True);raise AssertionError('Network forbidden')
socket.socket.connect=denied;socket.create_connection=denied
def note(s):SCENARIOS.append(s)
def history(raw,*,rename=True,segments=2,old_end=None,old_available=None,new_available=None,new_type='common_stock',new_listed=True,include_current=True):
 old=raw['tables']['security_master'][0];old['effective_to']=old_end or ('2018-01-15T00:00:00-05:00' if segments==3 else '2018-01-25T00:00:00-05:00')
 if old_available:old['available_at']=old_available
 if segments==3:
  middle=deepcopy(old);middle.update(effective_from='2018-01-15T00:00:00-05:00',effective_to='2018-01-25T00:00:00-05:00',available_at='2018-01-15T00:00:00-05:00',ticker='MID000' if rename else old['ticker']);raw['tables']['security_master'].append(middle)
 if include_current:
  new=deepcopy(old);new.update(effective_from='2018-01-25T00:00:00-05:00',effective_to=None,available_at=new_available or '2018-01-25T00:00:00-05:00',ticker='RENAMED000' if rename else old['ticker'],instrument_type=new_type,listed=new_listed);raw['tables']['security_master'].append(new)
def missing(raw,sid='SID000'):
 raw['liquid']=[r for r in raw['liquid'] if r['sid']!=sid]
 if sid=='SID000':
  for row in raw['tables']['membership']:row['sids']=raw['sids'][1:201]
def false(test,r):test.assertTrue(all(r[k] is False for k in FLAGS))
def audit(test,raw,expected):
 f=make(raw=raw);r=run(f);test.assertEqual(r['status'],expected);false(test,r);return f,r
class History(unittest.TestCase):
 def test_continuous_two_and_three_mapping_versions_independently_prove_age(self):
  for segments,rename in ((2,False),(2,True),(3,True)):
   for absent in (False,True):
    with self.subTest(segments=segments,rename=rename,absent=absent):
     note('continuous_'+str((segments,rename,absent)));raw=raw_fixture();history(raw,segments=segments,rename=rename)
     if absent:missing(raw)
     _,r=audit(self,raw,'insufficient_evidence' if absent else 'observations_passed');self.assertEqual(r['counts']['known_eligible_candidate_expected_cells'],8040);self.assertEqual(r['counts']['missing_candidate_session_cells'],40 if absent else 0)

 def test_half_open_interval_adjacency_gap_and_overlap_microsecond(self):
  for mode,end in [('adjacent','2018-01-25T00:00:00-05:00'),('gap','2018-01-24T23:59:59.999999-05:00'),('overlap','2018-01-25T00:00:00.000001-05:00')]:
   with self.subTest(mode=mode):
    note('interval_'+mode);raw=raw_fixture();history(raw,old_end=end);_,r=audit(self,raw,'observations_passed' if mode=='adjacent' else 'insufficient_evidence')
    if mode!='adjacent':self.assertGreater(r['counts']['inconsistent_classification_cells'],0)

 def test_old_interval_knowledge_at_formation_equality_and_future(self):
  for available,expected_missing in [('2018-02-01T09:00:00-05:00',40),('2018-02-01T09:00:00.000001-05:00',20),('2018-02-02T09:00:00.000001-05:00',0)]:
   with self.subTest(available=available):
    note('old_available_'+available);raw=raw_fixture();history(raw,old_available=available);missing(raw);_,r=audit(self,raw,'insufficient_evidence');self.assertEqual(r['counts']['missing_candidate_session_cells'],expected_missing)

 def test_WR26_no_then_known_current_is_not_affirmative_exclusion(self):
  for mode in ('future_current','missing_current'):
   with self.subTest(mode=mode):
    note('WR26_'+mode);raw=raw_fixture();history(raw,new_available='2018-02-02T09:00:00.000001-05:00',include_current=mode!='missing_current');missing(raw)
    _,r=audit(self,raw,'insufficient_evidence');self.assertGreater(r['counts']['inconsistent_classification_cells'],0)

 def test_unknown_current_states_and_explicit_exclusions(self):
  for code,listed,expected in [(None,True,'insufficient_evidence'),('common_stock',None,'insufficient_evidence'),('etf',True,'observations_passed'),('common_stock',False,'observations_passed')]:
   with self.subTest(code=code,listed=listed):
    note('current_state_'+str((code,listed)));raw=raw_fixture();history(raw,new_type=code,new_listed=listed);missing(raw);audit(self,raw,expected)

 def test_WR25_unknown_text_classifications_must_not_be_known_exclusions(self):
  for code in ('UNMAPPED_VENDOR_CODE','unknown','common_stok'):
   with self.subTest(code=code):
    note('WR25_'+code);raw=raw_fixture();history(raw,new_type=code);missing(raw)
    try:r=run(make(raw=raw))
    except DataCertificationError:continue
    self.assertEqual(r['status'],'insufficient_evidence','A string outside the registered taxonomy is unknown, not ETF/other known exclusion');false(self,r)

 def test_genuine_young_IPO_with_declared_clock_and_without_any_history(self):
  for mode in ('some_post_IPO_history','no_history','unknown_listing'):
   with self.subTest(mode=mode):
    note('young_IPO_'+mode);raw=raw_fixture();stamp='2018-01-25T00:00:00-05:00'
    for row in raw['liquid']:
     if row['sid']=='SID200':row.update(dollar_volume=2000,listing_effective_at=stamp,listing_available_at=stamp,classification_effective_at=stamp,classification_available_at=stamp)
    raw['tables']['security_master'][-1].update(effective_from=stamp,available_at=stamp)
    raw['liquid']=[r for r in raw['liquid'] if r['sid']!='SID200' or pd.Timestamp(r['session'])>=pd.Timestamp(stamp)]
    if mode=='no_history':missing(raw,'SID200')
    if mode=='unknown_listing':
     for row in raw['liquid']:
      if row['sid']=='SID200':row['listing_effective_at']=None
    audit(self,raw,'observations_passed' if mode=='some_post_IPO_history' else 'insufficient_evidence')

 def test_IPO_history_across_mapping_boundary_nineteen_twenty_sessions(self):
  for stamp,allow_last in [('2018-01-04T12:00:00-05:00',True),('2018-01-04T16:00:00-05:00',True),('2018-01-04T16:00:00.000001-05:00',False)]:
   with self.subTest(stamp=stamp):
    note('IPO_mapping_'+stamp);raw=raw_fixture();old=raw['tables']['security_master'][-1];old.update(effective_from=stamp,available_at=stamp,effective_to='2018-01-25T00:00:00-05:00');new=deepcopy(old);new.update(ticker='NEWIPO200',effective_from='2018-01-25T00:00:00-05:00',available_at='2018-01-25T00:00:00-05:00',effective_to=None);raw['tables']['security_master'].append(new)
    for row in raw['liquid']:
     if row['sid']=='SID200':row.update(dollar_volume=2000,listing_effective_at=stamp,listing_available_at=stamp,classification_effective_at=stamp,classification_available_at=stamp)
    if allow_last:raw['tables']['membership'][-1]['sids']=['SID200']+raw['sids'][:199]
    audit(self,raw,'observations_passed')

 def test_fixed_missing_old_history_preserves_raw_refs_and_summary_reopens(self):
  note('history_refs_raw_and_summary');raw=raw_fixture();history(raw);missing(raw);f=make(raw=raw);before=dict(f['store']._data);r=run(f);self.assertEqual(r['status'],'insufficient_evidence');self.assertEqual(r['counts']['liquidity_record_count'],4200);self.assertEqual(r['evidence_refs'],f['refs']);self.assertTrue(all(f['store'].read_bytes(k)==v for k,v in before.items()));false(self,r)
  m=scope(f,r);s=summarize_certification_scope(f['store'],m,content_hash(m),calendar=f['kwargs']['calendar'],synthetic=True);self.assertEqual(s['status'],'insufficient_evidence');self.assertTrue(s['raw_rows_recomputed_here']);false(self,s)
  note('history_private_master_tamper');f['store']._data[f['refs']['security_master'][0]['key']]=b'{}'
  with self.assertRaises(DataCertificationError):summarize_certification_scope(f['store'],m,content_hash(m),calendar=f['kwargs']['calendar'],synthetic=True)

class Result(unittest.TextTestResult):
 def __init__(self,*a,**k):super().__init__(*a,**k);self.successes=[]
 def addSuccess(self,t):self.successes.append(t.id());super().addSuccess(t)
if __name__=='__main__':
 before={p.relative_to(SOURCE).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in SOURCE.rglob('*') if p.is_file()};out=io.StringIO();start=time.perf_counter();r=unittest.TextTestRunner(stream=out,verbosity=2,resultclass=Result).run(unittest.defaultTestLoader.loadTestsFromTestCase(History))
 fail={t.id().split(' (')[0] for t,_ in r.failures};err={t.id().split(' (')[0] for t,_ in r.errors}
 report={'fixed_commit':'ccad61d03ccf17bf2bdc2d7ffc88dfd11b6d3ca6','methods':r.testsRun,'passed_methods':len(r.successes),'failed_methods':len(fail),'error_methods':len(err),'failure_records':len(r.failures),'error_records':len(r.errors),'scenario_checks':len(SCENARIOS),'scenario_checks_not_unittest_subcase_count':True,'scenarios':SCENARIOS,'failures':[{'method':t.id(),'traceback':tb} for t,tb in r.failures],'errors':[{'method':t.id(),'traceback':tb} for t,tb in r.errors],'seconds':time.perf_counter()-start,'source_unchanged':before=={p.relative_to(SOURCE).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in SOURCE.rglob('*') if p.is_file()},'network_attempts':len(NETWORK),'actual_QC_market_model_or_authoritative_budget_calls':0,'independent_original_fixture':True}
 (O/'history_first_results.json').write_bytes((json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode());(O/'history_first_unittest.txt').write_bytes(out.getvalue().encode());print(out.getvalue());print(json.dumps({k:v for k,v in report.items() if k not in ('scenarios','failures','errors')},ensure_ascii=False,indent=2));raise SystemExit(0 if r.wasSuccessful() else 1)
