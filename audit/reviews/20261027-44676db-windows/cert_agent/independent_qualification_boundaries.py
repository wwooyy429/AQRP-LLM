"""Independent public-API known answers for qualification and knowledge coverage."""
from cert_fixture import *
import hashlib,io,socket,time,unittest
O=Path(__file__).parent;SCENARIOS=[];NETWORK=[]
FLAGS=('vendor_provenance_authenticated','full_historical_US200_certified','actual_availability_certified','financial_vintage_certified','research_certified','row_values_exported','financial_evidence')
def denied(*a,**k):NETWORK.append(True);raise AssertionError('No network/provider allowed')
socket.socket.connect=denied;socket.create_connection=denied
def note(s):SCENARIOS.append(s)
def set_current(raw,*,kind='common_stock',listed=True,available='2018-01-25T00:00:00-05:00',exchange='NYSE',future_only=False):
 old=raw['tables']['security_master'][0];old['effective_to']='2018-01-25T00:00:00-05:00'
 new=deepcopy(old);new.update(ticker='RENAMED000',effective_from='2018-01-25T00:00:00-05:00',effective_to=None,available_at=available,instrument_type=kind,listed=listed,exchange=exchange)
 if future_only:raw['tables']['security_master']=[r for r in raw['tables']['security_master'] if r['sid']!='SID000']
 raw['tables']['security_master'].append(new)
def liquid(raw,mode):
 if mode=='all_missing':
  raw['liquid']=[r for r in raw['liquid'] if r['sid']!='SID000']
  for r in raw['tables']['membership']:r['sids']=raw['sids'][1:201]
 elif mode=='single_missing':
  raw['liquid']=[r for r in raw['liquid'] if not(r['sid']=='SID000' and r['session']==iso(raw['pairs'][0][1]))]
  raw['tables']['membership'][0]['sids']=raw['sids'][1:201]
def run_checked(test,raw,status):
 f=make(raw=raw);r=run(f);test.assertEqual(r['status'],status);test.assertTrue(all(r[k] is False for k in FLAGS));return f,r
class Qualification(unittest.TestCase):
 def test_closed_included_excluded_unknown_semantics_via_public_API(self):
  kinds=[(x,'insufficient_evidence') for x in ('common_stock','adr','reit_common')]+[(x,'observations_passed') for x in ('etf','etn','closed_end_fund','preferred_stock','unit','warrant','otc')]+[(x,'insufficient_evidence') for x in (None,'UNMAPPED_VENDOR_CODE','common_stok')]
  for kind,status in kinds:
   with self.subTest(kind=kind):
    note('classification_'+str(kind));raw=raw_fixture();set_current(raw,kind=kind);liquid(raw,'all_missing');_,r=run_checked(self,raw,status)
    if kind in ('common_stock','adr','reit_common'):self.assertEqual(r['counts']['missing_candidate_session_cells'],40)
    elif status=='insufficient_evidence':self.assertGreater(r['counts']['inconsistent_classification_cells'],0)

 def test_finite_known_exclusion_does_not_survive_its_expiry(self):
  for typ in ('etf','unlisted'):
   for mode in ('expired','ends_at_last_formation','covers_both'):
    with self.subTest(typ=typ,mode=mode):
     note('finite_'+typ+'_'+mode);raw=raw_fixture();row=raw['tables']['security_master'][0]
     if typ=='etf':row['instrument_type']='etf'
     else:row['listed']=False
     row['effective_to']={'expired':'2018-01-25T00:00:00-05:00','ends_at_last_formation':'2018-02-02T09:00:00-05:00','covers_both':'2018-02-02T09:00:00.000001-05:00'}[mode];liquid(raw,'all_missing')
     _,r=run_checked(self,raw,'observations_passed' if mode=='covers_both' else 'insufficient_evidence')
     self.assertEqual(r['counts']['inconsistent_classification_cells'],{'expired':2,'ends_at_last_formation':1,'covers_both':0}[mode])

 def test_current_knowledge_equality_microsecond_delay_and_future(self):
  for kind in ('common_stock','etf'):
   for clock in ('2018-02-01T09:00:00-05:00','2018-02-01T09:00:00.000001-05:00','2018-02-02T09:00:00.000001-05:00'):
    with self.subTest(kind=kind,clock=clock):
     note('current_available_'+kind+'_'+clock);raw=raw_fixture();set_current(raw,kind=kind,available=clock)
     if kind=='etf':liquid(raw,'all_missing')
     status='observations_passed' if clock=='2018-02-01T09:00:00-05:00' else 'insufficient_evidence'
     _,r=run_checked(self,raw,status);self.assertEqual(r['counts']['inconsistent_classification_cells'],0 if status=='observations_passed' else (1 if clock.startswith('2018-02-01') else 2))

 def test_future_only_inventory_does_not_create_then_unknown_past_SID(self):
  for kind in ('common_stock','etf','UNMAPPED_VENDOR_CODE'):
   with self.subTest(kind=kind):
    note('future_only_'+kind);raw=raw_fixture();set_current(raw,kind=kind,available='2018-02-02T09:00:00.000001-05:00',future_only=True);liquid(raw,'all_missing');_,r=run_checked(self,raw,'observations_passed')
    self.assertEqual(r['counts']['known_eligible_candidate_expected_cells'],8000);self.assertEqual(r['counts']['inconsistent_classification_cells'],0)

 def test_empty_and_conflicting_current_evidence_remains_unresolved(self):
  for mode in ('empty_all_masters','two_conflicting_current','exact_duplicate_current'):
   with self.subTest(mode=mode):
    note('master_evidence_'+mode);raw=raw_fixture()
    if mode=='empty_all_masters':raw['tables']['security_master']=[]
    else:
     set_current(raw);extra=deepcopy(raw['tables']['security_master'][-1])
     if mode=='two_conflicting_current':extra['ticker']='CONFLICT000'
     raw['tables']['security_master'].append(extra)
    if mode=='exact_duplicate_current':
     with self.assertRaises(DataCertificationError):run(make(raw=raw))
    else:run_checked(self,raw,'insufficient_evidence')

 def test_liquidity_complete_one_missing_and_whole_missing_by_current_state(self):
  for state in ('included','unknown','excluded'):
   for mode in ('complete','single_missing','all_missing'):
    with self.subTest(state=state,mode=mode):
     note('liquidity_'+state+'_'+mode);raw=raw_fixture();set_current(raw,kind={'included':'common_stock','unknown':None,'excluded':'etf'}[state]);liquid(raw,mode)
     if state=='excluded':
      for row in raw['liquid']:
       if row['sid']=='SID000':row['instrument_type']='etf'
      for row in raw['tables']['membership']:row['sids']=raw['sids'][1:201]
     status='observations_passed' if state=='excluded' or state=='included' and mode=='complete' else 'insufficient_evidence'
     _,r=run_checked(self,raw,status)
     if state=='included':self.assertEqual(r['counts']['missing_candidate_session_cells'],{'complete':0,'single_missing':1,'all_missing':40}[mode])

 def test_IPO_continuity_keeps_nineteen_twenty_and_close_microsecond_boundary(self):
  for stamp,allow_last in [('2018-01-04T12:00:00-05:00',True),('2018-01-04T16:00:00-05:00',True),('2018-01-04T16:00:00.000001-05:00',False)]:
   with self.subTest(stamp=stamp):
    note('IPO_continuity_'+stamp);raw=raw_fixture();old=raw['tables']['security_master'][-1];old.update(effective_from=stamp,available_at=stamp,effective_to='2018-01-25T00:00:00-05:00');new=deepcopy(old);new.update(ticker='RENAMED_IPO200',effective_from='2018-01-25T00:00:00-05:00',available_at='2018-01-25T00:00:00-05:00',effective_to=None);raw['tables']['security_master'].append(new)
    for row in raw['liquid']:
     if row['sid']=='SID200':row.update(dollar_volume=2000,listing_effective_at=stamp,listing_available_at=stamp,classification_effective_at=stamp,classification_available_at=stamp)
    if allow_last:raw['tables']['membership'][-1]['sids']=['SID200']+raw['sids'][:199]
    run_checked(self,raw,'observations_passed')

 def test_raw_refs_counts_and_summary_recompute_false_certification(self):
  note('fixed_unknown_raw_refs_and_summary');raw=raw_fixture();set_current(raw,kind='UNMAPPED_VENDOR_CODE');liquid(raw,'all_missing');f=make(raw=raw);before=dict(f['store']._data);r=run(f)
  self.assertEqual(r['status'],'insufficient_evidence');self.assertEqual(r['counts']['liquidity_record_count'],4200);self.assertEqual(r['evidence_refs'],f['refs']);self.assertTrue(all(f['store'].read_bytes(k)==v for k,v in before.items()));self.assertTrue(all(r[k] is False for k in FLAGS))
  m=scope(f,r);s=summarize_certification_scope(f['store'],m,content_hash(m),calendar=f['kwargs']['calendar'],synthetic=True);self.assertEqual(s['status'],'insufficient_evidence');self.assertTrue(s['raw_rows_recomputed_here']);self.assertTrue(all(s[k] is False for k in FLAGS))
  note('private_master_tamper_rejected');f['store']._data[f['refs']['security_master'][0]['key']]=b'{}'
  with self.assertRaises(DataCertificationError):summarize_certification_scope(f['store'],m,content_hash(m),calendar=f['kwargs']['calendar'],synthetic=True)

 def test_observed_zero_is_complete_but_missing_below_rank_is_still_gap(self):
  for gap in (False,True):
   with self.subTest(gap=gap):
    note('observed_zero_with_missing_'+str(gap));raw=raw_fixture();set_current(raw)
    for row in raw['liquid']:
     if row['sid']=='SID000':row['dollar_volume']=0
    if gap:raw['liquid']=[r for r in raw['liquid'] if not(r['sid']=='SID000' and r['session']==iso(raw['pairs'][0][1]))]
    for row in raw['tables']['membership']:row['sids']=raw['sids'][1:201]
    _,r=run_checked(self,raw,'insufficient_evidence' if gap else 'observations_passed');self.assertEqual(r['counts']['known_eligible_candidate_expected_cells'],8040);self.assertEqual(r['counts']['missing_candidate_session_cells'],1 if gap else 0)

class Result(unittest.TextTestResult):
 def __init__(self,*a,**k):super().__init__(*a,**k);self.successes=[]
 def addSuccess(self,t):self.successes.append(t.id());super().addSuccess(t)
if __name__=='__main__':
 before={p.relative_to(SOURCE).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in SOURCE.rglob('*') if p.is_file()};out=io.StringIO();start=time.perf_counter();r=unittest.TextTestRunner(stream=out,verbosity=2,resultclass=Result).run(unittest.defaultTestLoader.loadTestsFromTestCase(Qualification))
 fail={t.id().split(' (')[0] for t,_ in r.failures};err={t.id().split(' (')[0] for t,_ in r.errors}
 report={'fixed_commit':'44676db609b3b7c2175fa7fa4f19c8ccf8165458','methods':r.testsRun,'passed_methods':len(r.successes),'failed_methods':len(fail),'error_methods':len(err),'failure_records':len(r.failures),'error_records':len(r.errors),'scenario_checks':len(SCENARIOS),'scenario_checks_not_unittest_subcase_count':True,'scenarios':SCENARIOS,'failures':[{'method':t.id(),'traceback':tb} for t,tb in r.failures],'errors':[{'method':t.id(),'traceback':tb} for t,tb in r.errors],'seconds':time.perf_counter()-start,'source_unchanged':before=={p.relative_to(SOURCE).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in SOURCE.rglob('*') if p.is_file()},'network_attempts':len(NETWORK),'actual_QC_market_model_or_authoritative_budget_calls':0,'independent_original_fixture':True}
 (O/'qualification_first_results.json').write_bytes((json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode());(O/'qualification_first_unittest.txt').write_bytes(out.getvalue().encode());print(out.getvalue());print(json.dumps({k:v for k,v in report.items() if k not in ('scenarios','failures','errors')},ensure_ascii=False,indent=2));raise SystemExit(0 if r.wasSuccessful() else 1)
