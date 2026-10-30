"""Independent known answers for observed-scope diagnostics. No market data."""
from cert_fixture import *
import hashlib,io,os,socket,subprocess,time,unittest
O=Path(__file__).resolve().parent;PY=r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\venv\Scripts\python.exe'
SCENARIOS=[];NETWORK=[]
def denied(*a,**k):NETWORK.append(True);raise AssertionError('No external provider call is allowed')
socket.socket.connect=denied;socket.create_connection=denied
FALSE_FLAGS=('vendor_provenance_authenticated','full_historical_US200_certified','actual_availability_certified','financial_vintage_certified','research_certified','row_values_exported','financial_evidence')
def note(name):SCENARIOS.append(name)
def synthetic_ipo(raw,listing,*,drop_pre=False,turnover=False):
 sid='SID200'
 for row in raw['liquid']:
  if row['sid']==sid:row.update(dollar_volume=2000,listing_effective_at=listing,listing_available_at=listing,classification_effective_at=listing,classification_available_at=listing)
 for row in raw['tables']['security_master']:
  if row['sid']==sid:row.update(effective_from=listing,available_at=listing)
 if drop_pre:raw['liquid']=[x for x in raw['liquid'] if x['sid']!=sid or pd.Timestamp(x['session'])>=pd.Timestamp(listing)]
 for index,row in enumerate(raw['tables']['membership']):
  row['sids']=list(raw['members']) if drop_pre and (not turnover or index==0) else [sid]+raw['sids'][:199]

class Certification(unittest.TestCase):
 def test_known_answer_all_counts_and_permanent_authentication_gaps(self):
  note('201names21sessions_two_formations_known_answer');f=make();r=run(f)
  self.assertEqual(r['status'],'observations_passed');self.assertTrue(all(r['checks'].values()))
  self.assertEqual({k:r['counts'][k] for k in ('formation_count','expected_member_cells','observed_member_cells','liquidity_record_count','financial_record_count','price_record_count','known_eligible_candidate_expected_cells')},
   {'formation_count':2,'expected_member_cells':400,'observed_member_cells':400,'liquidity_record_count':4221,'financial_record_count':201,'price_record_count':402,'known_eligible_candidate_expected_cells':8040})
  self.assertTrue(all(r[k] is False for k in FALSE_FLAGS));self.assertEqual(len(r['gap_codes']),4)
  m=scope(f,r);s=summarize_certification_scope(f['store'],m,content_hash(m),calendar=f['kwargs']['calendar'],synthetic=True)
  self.assertEqual(s['status'],'observations_passed');self.assertTrue(s['raw_rows_recomputed_here']);self.assertTrue(all(s[k] is False for k in FALSE_FLAGS));self.assertFalse(s['declared_full_development_interval'])

 def test_known_old_eligible_missing_history_cannot_be_hidden_by_spare_rank(self):
  for variant in ('tail_one_missing','top_all_missing'):
   with self.subTest(variant=variant):
    note('eligible_history_'+variant)
    def change(raw):
     if variant=='tail_one_missing':raw['liquid']=[x for x in raw['liquid'] if not(x['sid']=='SID200' and x['session']==iso(raw['pairs'][0][1]))]
     else:
      raw['liquid']=[x for x in raw['liquid'] if x['sid']!='SID000']
      for row in raw['tables']['membership']:row['sids']=raw['sids'][1:201]
    r=run(make(change));self.assertEqual(r['status'],'insufficient_evidence');self.assertFalse(r['checks']['all_known_eligible_candidate_histories_complete']);self.assertTrue(r['checks']['ranked_membership_matches']);self.assertGreater(r['counts']['missing_candidate_session_cells'],0)

 def test_unknown_classification_master_and_mapping_remain_incomplete(self):
  for variant in ('unknown_liquidity_type','missing_master','ambiguous_ticker'):
   with self.subTest(variant=variant):
    note(variant)
    def change(raw):
     if variant=='unknown_liquidity_type':raw['liquid'][0]['instrument_type']=None
     elif variant=='missing_master':raw['tables']['security_master']=[x for x in raw['tables']['security_master'] if x['sid']!='SID000']
     else:raw['tables']['security_master'][1]['ticker']='T000'
    r=run(make(change));self.assertEqual(r['status'],'insufficient_evidence');self.assertFalse(all(r['checks'].values()))

 def test_legitimate_ipo_without_twenty_post_listing_sessions_is_excluded(self):
  note('legitimate_young_ipo_excluded');f=make(lambda raw:synthetic_ipo(raw,'2018-01-25T00:00:00-05:00',drop_pre=True));r=run(f)
  self.assertEqual(r['status'],'observations_passed');self.assertEqual(r['counts']['known_eligible_candidate_expected_cells'],8000);self.assertEqual(r['counts']['observed_member_cells'],400)

 def test_listing_date_boundary_with_only_post_listing_history_and_turnover(self):
  note('IPO19_then20_post_listing_sessions');f=make(lambda raw:synthetic_ipo(raw,'2018-01-04T00:00:00-05:00',drop_pre=True,turnover=True));r=run(f)
  self.assertEqual(r['status'],'observations_passed');self.assertEqual(r['counts']['observed_member_cells'],400)
  note('old_listing_with20_real_sessions');r=run(make(lambda raw:synthetic_ipo(raw,'2017-12-01T00:00:00-05:00')));self.assertEqual(r['status'],'observations_passed')

 def test_WR20_pre_listing_rows_must_not_supply_twenty_session_ipo_history(self):
  for listing in ('2018-01-04T00:00:00-05:00','2018-01-25T00:00:00-05:00'):
   with self.subTest(listing=listing):
    note('WR20_pre_listing_rows_'+listing)
    f=make(lambda raw:synthetic_ipo(raw,listing));r=run(f)
    self.assertEqual(r['status'],'insufficient_evidence','Pre-listing liquidity must not turn a19-session or young IPO into a complete20-session candidate')

 def test_date_only_publication_waits_for_next_exchange_close(self):
  note('date_only_Jan31_gates_at_Feb1close')
  def change(raw):raw['financial'][0].update(public_at=None,public_date='2018-01-31',public_precision='date',vendor_available_at='2018-01-31T12:00:00-05:00',historical_ingested_at='2018-01-31T13:00:00-05:00')
  r=run(make(change));self.assertEqual(r['counts']['financial_available_cells'],399);self.assertEqual(r['counts']['financial_missing_cells'],1);self.assertTrue(r['checks']['ranked_membership_matches']);self.assertEqual(r['status'],'insufficient_evidence')

 def test_later_financial_revision_never_backfills_and_actual_receipt_is_required(self):
  note('later_vintage_not_backfilled')
  def add_revision(raw):
   row=deepcopy(raw['financial'][0]);row.update(source_revision='financial_v2',value=999,public_at='2018-02-02T12:00:00-05:00',vendor_available_at='2018-02-02T12:01:00-05:00',historical_ingested_at='2018-02-02T12:02:00-05:00');raw['financial'].append(row)
  f=make(add_revision);r=run(f);self.assertEqual(r['status'],'observations_passed')
  early=f['ingestor'].financial_records_asof(f['refs']['financial'],ts('2018-02-02 09:00'))
  self.assertEqual(early[early.sid=='SID000'].value.tolist(),[10.0])
  late=f['ingestor'].financial_records_asof(f['refs']['financial'],ts('2018-02-03 09:00'))
  self.assertEqual(late[late.sid=='SID000'].sort_values('available_time').iloc[-1].value,999)
  for variant in ('modeled_receipt','missing_vendor','missing_value'):
   with self.subTest(variant=variant):
    note(variant)
    def change(raw):
     row=raw['financial'][0]
     if variant=='modeled_receipt':row['availability_basis']='modeled_lean_frontier'
     elif variant=='missing_vendor':row['vendor_available_at']=None
     else:row['value']=None
    rr=run(make(change));self.assertEqual(rr['status'],'insufficient_evidence');self.assertTrue(rr['checks']['ranked_membership_matches']);self.assertGreater(rr['counts']['financial_missing_cells'],0)

 def test_raw_prices_and_actions_are_exact_causal_registered_components(self):
  for variant in ('adjusted','bad_ohlc','action_before_event','unknown_action','duplicate_action'):
   with self.subTest(variant=variant):
    note(variant)
    def change(raw):
     if variant=='adjusted':raw['tables']['prices'][0]['normalization']='adjusted'
     elif variant=='bad_ohlc':raw['tables']['prices'][0]['high']=1
     else:
      action={'sid':'SID000','event_time':'2018-01-20T12:00:00-05:00','available_at':'2018-01-20T13:00:00-05:00','kind':'split','source_revision':'action_v1'}
      if variant=='action_before_event':action['available_at']='2018-01-19T13:00:00-05:00'
      elif variant=='unknown_action':action['kind']='spin_off_unmapped'
      raw['tables']['corporate_actions']=[action,deepcopy(action)] if variant=='duplicate_action' else [action]
    with self.assertRaises(DataCertificationError):run(make(change))
  note('unknown_action_SID_not_covered')
  def unknown_sid(raw):raw['tables']['corporate_actions']=[{'sid':'NOT_IN_MASTER','event_time':'2018-01-20T12:00:00-05:00','available_at':'2018-01-20T13:00:00-05:00','kind':'split','source_revision':'action_v1'}]
  r=run(make(unknown_sid));self.assertFalse(r['checks']['corporate_action_sids_known']);self.assertEqual(r['status'],'insufficient_evidence')

 def test_exact_calendar_membership_and_fixed_plan_bounds(self):
  for variant in ('wrong200','wrong20','future_scope','unknown_override','future_field'):
   with self.subTest(variant=variant):
    note(variant);change={'wrong200':{'universe_size':199},'wrong20':{'liquidity_lookback_sessions':19},'future_scope':{'end_exclusive':'2024-01-02T00:00:00-05:00'},'unknown_override':{'approved':True},'future_field':{'financial_catalog':{'future_return':{'unit':'USD','period_accessor':'value'}}}}[variant]
    with self.assertRaises(DataCertificationError):make(plan_change=change)
  for variant in ('duplicate_member','bad_formation_hour','duplicate_calendar'):
   with self.subTest(variant=variant):
    note(variant)
    def change(raw):
     if variant=='duplicate_member':raw['tables']['membership'][0]['sids'][-1]=raw['tables']['membership'][0]['sids'][0]
     elif variant=='bad_formation_hour':raw['pairs'][0]=(raw['pairs'][0][0]+pd.Timedelta(minutes=1),raw['pairs'][0][1])
     else:raw['pairs'].append(raw['pairs'][-1])
    with self.assertRaises(DataCertificationError):run(make(change))
  note('short_warmup_not_compliant')
  def short(raw):raw['pairs']=raw['pairs'][2:]
  r=run(make(short));self.assertFalse(r['checks']['complete_twenty_session_warmup']);self.assertEqual(r['status'],'insufficient_evidence')

 def test_partition_summary_recomputes_private_input_and_refuses_forged_report(self):
  for variant in ('private_table_tamper','fake_counts','empty_refs_free_true','certification_true'):
   with self.subTest(variant=variant):
    note(variant);f=make();r=run(f);m=scope(f,r)
    if variant=='private_table_tamper':f['store']._data[f['refs']['prices'][0]['key']]=b'{}'
    else:
     forged=deepcopy(r);forged.pop('report_ref')
     if variant=='fake_counts':forged['counts']['liquidity_record_count']+=1
     elif variant=='empty_refs_free_true':forged['evidence_refs']={key:[] for key in forged['evidence_refs']}
     else:forged['research_certified']=True
     h=content_hash(forged);key='data-certification/v1/reports/'+h+'.json';f['store'].write_once(key,canonical_json(forged));m['partitions'][0]['report_ref']={'key':key,'sha256':h}
    with self.assertRaises(DataCertificationError):summarize_certification_scope(f['store'],m,content_hash(m),calendar=f['kwargs']['calendar'],synthetic=True)

 def test_partition_overlap_missing_report_and_full_scope_expansion_not_certified(self):
  note('overlapping_partitions');f=make();r=run(f);m=scope(f,r);part=deepcopy(m['partitions'][0]);part['plan_hash']='2'*64;part['report_ref']=None;m['partitions'].append(part)
  with self.assertRaises(DataCertificationError):summarize_certification_scope(f['store'],m,content_hash(m),calendar=f['kwargs']['calendar'],synthetic=True)
  note('missing_partition_report');m=scope(f,r);m['partitions'][0]['report_ref']=None;s=summarize_certification_scope(f['store'],m,content_hash(m),calendar=f['kwargs']['calendar'],synthetic=True);self.assertEqual(s['missing_report_count'],1);self.assertEqual(s['status'],'insufficient_evidence')
  note('cannot_expand_two_days_into_full_history');m=scope(f,r);m.update(start='2010-01-01T00:00:00-05:00',end_exclusive='2024-01-01T00:00:00-05:00');s=summarize_certification_scope(f['store'],m,content_hash(m),calendar=f['kwargs']['calendar'],synthetic=True)
  self.assertFalse(s['partition_intervals_cover_target']);self.assertEqual(s['status'],'insufficient_evidence');self.assertTrue(all(s[k] is False for k in FALSE_FLAGS))

 def test_real_rows_cannot_enter_local_store_and_CLI_cannot_approve(self):
  note('local_real_store_rejected');f=make()
  with self.assertRaises(DataCertificationError):audit_data_certification(f['store'],f['plan'],calendar=f['kwargs']['calendar'],synthetic=False)
  commands=[]
  for variant in ('capabilities','valid_plan','duplicate_JSON_key','unknown_override'):
   note('CLI_'+variant)
   cmd=[PY,'-B',str(SOURCE/'tools/data_certification.py')]
   if variant=='capabilities':cmd+=['capabilities']
   else:
    p=O/(variant+'.json');value=f['plan'].to_dict()
    if variant=='unknown_override':value['approve']=True
    b=canonical_json(value)
    if variant=='duplicate_JSON_key':b=b'{"schema_version":1,'+b[1:]
    p.write_bytes(b);cmd+=['validate-plan','--plan-file',str(p)]
   got=subprocess.run(cmd,cwd=O,env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1'),capture_output=True);(O/(variant+'.stdout')).write_bytes(got.stdout);(O/(variant+'.stderr')).write_bytes(got.stderr)
   commands.append({'variant':variant,'command':cmd,'exit_code':got.returncode,'stdout_raw_sha256':hashlib.sha256(got.stdout).hexdigest(),'stderr_raw_sha256':hashlib.sha256(got.stderr).hexdigest()})
   obj=json.loads(got.stdout);self.assertFalse(obj['ready_to_dispatch'])
   if variant in ('duplicate_JSON_key','unknown_override'):self.assertEqual(got.returncode,2);self.assertFalse(obj['plan_valid'])
   else:self.assertEqual(got.returncode,0);self.assertFalse(obj['research_certified']);self.assertFalse(obj['budget_admission_performed'])
  (O/'cli_command_log.json').write_text(json.dumps(commands,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

class Result(unittest.TextTestResult):
 def __init__(self,*a,**k):super().__init__(*a,**k);self.successes=[]
 def addSuccess(self,test):self.successes.append(test.id());super().addSuccess(test)
if __name__=='__main__':
 before={p.relative_to(SOURCE).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in SOURCE.rglob('*') if p.is_file()}
 stream=io.StringIO();start=time.perf_counter();result=unittest.TextTestRunner(stream=stream,verbosity=2,resultclass=Result).run(unittest.defaultTestLoader.loadTestsFromTestCase(Certification));text=stream.getvalue();(O/'first_unittest.txt').write_text(text,encoding='utf-8')
 failnames={t.id().split(' (')[0] for t,_ in result.failures};errornames={t.id().split(' (')[0] for t,_ in result.errors}
 report={'fixed_commit':'deb85d9f27441b275ab8b108f0232ecd2707a1e8','methods':result.testsRun,'passed_methods':len(result.successes),'failed_methods':len(failnames),'error_methods':len(errornames),'failure_records':len(result.failures),'error_records':len(result.errors),'scenario_checks':len(SCENARIOS),'scenarios':SCENARIOS,'failures':[{'method':t.id(),'traceback':tb} for t,tb in result.failures],'errors':[{'method':t.id(),'traceback':tb} for t,tb in result.errors],'elapsed_seconds':time.perf_counter()-start,'actual_market_model_QC_calls':len(NETWORK),'actual_registry_writes':0,'synthetic_memory_inputs_only':True,'author_fixture_imports':False,'source_unchanged':before=={p.relative_to(SOURCE).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in SOURCE.rglob('*') if p.is_file()},'source_module_raw_sha256':{n:hashlib.sha256((SOURCE/n).read_bytes()).hexdigest() for n in ('cloud/qresearch/data_certification.py','cloud/qresearch/ingestion.py','cloud/qresearch/universe.py','tools/data_certification.py')},'financial_evidence':False}
 (O/'first_results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(text);print(json.dumps({k:v for k,v in report.items() if k not in ('failures','errors','scenarios')},ensure_ascii=False,indent=2));raise SystemExit(0 if result.wasSuccessful() else 1)
