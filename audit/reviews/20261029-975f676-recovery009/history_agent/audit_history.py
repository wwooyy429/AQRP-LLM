from pathlib import Path
from contextlib import contextmanager
from hashlib import sha256, sha1
import json, sys, subprocess, ast, socket
sys.dont_write_bytecode=True
O=Path(__file__).resolve().parent;S=O.parent/'source';M=O.parent/'materials'
G=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\repo')
sys.path.insert(0,str(S/'cloud'))
from qresearch.artifacts import canonical_json, decode_events
from qresearch.registry import Registry
from qresearch.engineering_receipts import research_dispatch_binding,research_observation,backtest_observation
def deny(*a,**k):raise AssertionError('No network in independent historical audit')
socket.socket.connect=deny;socket.create_connection=deny
checks=[]
def check(name,value,details=None):
    checks.append({'name':name,'passed':bool(value),'details':details})
    if not value: raise AssertionError(name)
def load(path):return json.loads((S/path).read_bytes())
before={p.relative_to(S).as_posix():sha256(p.read_bytes()).hexdigest() for p in S.rglob('*') if p.is_file()}
history=load('docs/review/current/history.json')
check('WR01_through_WR28_complete_unique_ids', sorted(int(x['id'].split('-')[1]) for x in history['findings'])==list(range(1,29)))
for report in history['reports']:
    raw=(S/report['report_path']).read_bytes();j=json.loads(raw)
    check('original_report_raw_hash:'+report['report_path'],sha256(raw).hexdigest()==report['report_raw_sha256'])
    check('index_quotes_original_top_fields:'+report['report_path'],all(j[k]==v for k,v in report['reported_fields'].items()))
    check('index_no_complete_bundle_inference:'+report['report_path'],not report['archive_scope']['complete_original_review_bundle_asserted'])
for finding in history['findings']:
    check(finding['id']+'_no_current_automatic_acceptance',finding['current_source_acceptance_inferred'] is False)
    check(finding['id']+'_original_and_confirmation_reports_exist',(S/finding['first_report_path']).is_file() and (S/finding['repair_confirmation_report_path']).is_file())
for name in history['local_index_validation']['verified_repository_paths']:
    check('indexed_path_exists:'+name,(S/name).is_file())
selected=[]
for selection_path in (S/'audit/reviews').glob('*/developer_archive_selection.json'):
    selection=json.loads(selection_path.read_bytes());entries=selection.get('selected_originals',[])
    rows=[]
    for item in entries:
        dest=selection_path.parent/item['path'];raw=dest.read_bytes()
        check('selected_original_raw:'+selection_path.parent.name+'/'+item['path'],sha256(raw).hexdigest()==item['raw_sha256'])
        rows.append(item['path'])
    selected.append({'archive':selection_path.parent.name,'selected_files_verified':len(rows),'complete_original_bundle_asserted':False,'original_zip':selection.get('original_zip'),'original_zip_sha256':selection.get('original_zip_sha256')})
journal=(S/'audit/runtime/registry/events.jsonl').read_bytes();envelopes=[json.loads(x) for x in journal.splitlines()]
previous=None
for seq,item in enumerate(envelopes,1):
    unsigned={k:v for k,v in item.items() if k!='hash'}
    check('independent_journal_record_'+str(seq),item['sequence']==seq and item['previous_hash']==previous and sha256(json.dumps(unsigned,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()==item['hash'])
    previous=item['hash']
check('71_events_and_production_decoder',len(envelopes)==71 and decode_events(journal)==envelopes)
prefix69=b''.join(journal.splitlines(keepends=True)[:69]);prior69=subprocess.check_output(['git','-C',str(G),'show','4a1bd3549d443d49f6ddd46820e3f807d00924ee:audit/runtime/registry/events.jsonl'])
check('original_69_event_prefix_raw_unchanged',prefix69==prior69)
class ReadOnlyStore:
    def __init__(self):self.accessed={}
    def read_bytes(self,key):
        p=(S/'audit/runtime'/key).resolve()
        if not p.is_relative_to((S/'audit/runtime').resolve()):raise ValueError(key)
        raw=p.read_bytes();self.accessed[key]=sha256(raw).hexdigest();return raw
    def exists(self,key):return (S/'audit/runtime'/key).is_file()
    @contextmanager
    def locked(self,key):yield
    def write_once(self,*a,**k):raise AssertionError('Read-only store disallows write')
    def append_event(self,*a,**k):raise AssertionError('Read-only store disallows append')
store=ReadOnlyStore();reg=Registry(store,load('audit/runtime/registry/baseline.json'));snapshot=reg.snapshot();rounds=reg.engineering_rounds_snapshot();cycle=reg.configuration_cycle_snapshot()
budget=load('config/budget.json')
check('replayed_lifetime_usage_16_17_3',{k:v['total'] for k,v in snapshot['usage'].items()}=={'configurations':16,'research':17,'lean':3})
check('cycle_3_of_13_with_original_lifetime',cycle['usage']['total']==3 and cycle['capacity']['total']==13 and cycle['lifetime_usage']['total']==16 and cycle==budget['configuration_cycle'])
check('008_round_closed',rounds['stage2-storage-repair-round-008']['status']=='closed')
check('all_existing_attempts_resolved',all(x['status'] in ('completed','failed') for x in snapshot['attempts']))
research_admission=load('audit/review_packages/storage-repair008/research_admission.json')
lean_admission=load('audit/review_packages/storage-repair008/lean_admission.json')
terminal=Path('audit/review_packages/storage-repair008/terminal')
binding=research_dispatch_binding(research_admission['payload'],research_admission['deployment'],load('audit/review_packages/storage-repair008/research_cell_readback.json'))
research=research_observation(research_admission['payload'],research_admission['deployment'],load('audit/review_packages/storage-repair008/research_execute_cell_observation.json'),dispatch_binding=binding,dispatch_required=True)
lean=backtest_observation(lean_admission['payload'],lean_admission['deployment'],'8a45b6c62d55521033e9cc5b9b9d3950',load(terminal/'backtest_terminal_observation.json'),load(terminal/'backtest_logs_observations.json'))
check('lean_native_reparse_exact_stored_observation',lean==load(terminal/'parsed_native_observation.json'))
research_report=research['completion']['cloud_report'];lean_report=lean['cloud_report']
check('old_native_research_13_checks',len(research_report['checks'])==13 and all(research_report['checks'].values()))
check('old_native_lean_7_checks_zero_orders',len(lean_report['checks'])==7 and all(lean_report['checks'].values()) and lean_report['statistics']['orders_submitted']==0 and lean['platform']['raw_receipt']['orders_count']==0)
check('old_same_plan_and_config',research_report['identity']['plan_hash']==lean_report['identity']['plan_hash'] and research_report['identity']['config_id']==lean_report['identity']['config_id'])
check('research_worker_zero_EOF_normalization',research_report['evidence']['deployment_verification']['eof_normalized_file_count']==0 and research_report['evidence']['deployment_verification']['original_source_identity_match'] is True)
check('lean_all43_EOF_normalization_no_raw_match',lean_report['evidence']['deployment_verification']['eof_normalized_file_count']==43 and lean_report['evidence']['deployment_verification']['original_source_identity_match'] is False)
source_readback=load('audit/review_packages/storage-repair008/source_readback.json')
for item in source_readback['checks']:
    raw=subprocess.check_output(['git','-C',str(G),'show','b1a4041ce98867047294b8f0830292af5d7ec56e:cloud/'+item['path']])
    check('original_PROJECT43_source_git:'+item['path'],sha256(raw).hexdigest()==item['expected_sha256'] and item['matches_original'] is True)
diagnosis=load(terminal/'notification_diagnosis.json')
check('historical_terminal_no_push_observed',diagnosis['automatic_completion_push_observed'] is False and 'historical' in diagnosis['terminal_observed_via'])
for admission,stage in ((research_admission,'research'),(lean_admission,'lean')):
    ident=admission['payload']['identity'];record=next(x for x in snapshot['attempts'] if x['attempt_id']==ident['attempt_id'])
    raw=(S/'audit/task_inputs'/(ident['attempt_id']+'.py')).read_bytes()
    check(stage+'_frozen_input_sha_and_ledger_completed',sha256(raw).hexdigest()==admission['deployment']['input_hash'] and record['status']=='completed')
    assignment=ast.parse(raw.decode('utf-8-sig')).body[0];payload=json.loads(ast.literal_eval(assignment.value))
    check(stage+'_input_payload_exact_identity',payload==admission['payload'])
exposure=load('audit/data_exposure.json')
check('exposure_2024_2025_retained',exposure['whole_window_uncontaminated'] is False and exposure['year2026_independence']=='requires independent review')
for finding in history['findings']:
    key=finding['id'];n=int(key.split('-')[1]);names=[]
    for path in (S/'tests').glob('*.py'):
        text=path.read_text(encoding='utf-8-sig')
        import re
        if re.search(r'(?i)wr[-_]?0?'+str(n)+r'(?![0-9])',text):names.append(path.relative_to(S).as_posix())
    finding['current_repository_related_test_files']=names
    finding['current_independent_execution']='see explicit historical_execution.json and repository run; historical confirmation is not automatic current acceptance'
after={p.relative_to(S).as_posix():sha256(p.read_bytes()).hexdigest() for p in S.rglob('*') if p.is_file()}
check('all_original_source_files_raw_unchanged',before==after)
out={'reviewed_source_commit':'975f676d62b561689909744f9e7236290e3f5fcb','materials_commit':'a6a5a165d87c172535cdea6cf495e3c1a850e6e4','static_checks':checks,'static_logical_checks':len(checks),'unit_methods':0,'history_report_count':len(history['reports']),'WR_count':len(history['findings']),'selected_archives':selected,'budget':{'events':len(envelopes),'journal_sha256':sha256(journal).hexdigest(),'prior69_prefix_sha256':sha256(prefix69).hexdigest(),'snapshot':snapshot,'cycles':reg.configuration_cycles_snapshot(),'cycle':cycle,'rounds':rounds,'readonly_metadata_files_accessed':store.accessed,'new_events':0,'new_debits':0,'refunds':0},'old_platform':{'evidence_level':'developer_archived_native_metadata_independently_reparsed_offline_not_live_QC','runtime_source_commit':'b1a4041ce98867047294b8f0830292af5d7ec56e','terminal_materials_commit':'ca5e4f3f68a58297cf02d97629346e10306ebcf0','research_checks':research_report['checks'],'lean_checks':lean_report['checks'],'orders':0,'research_worker_eof_normalized_count':0,'lean_worker_eof_normalized_count':43,'lean_original_source_identity_match':False,'automatic_push_observed':False,'new_source_cloud_execution_verified':False},'findings':[],'financial_evidence':False,'all_source_unchanged':before==after}
(O/'history_static_results.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
(O/'WR_matrix.json').write_text(json.dumps(history['findings'],ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'static_logical_checks':len(checks),'all_passed':all(x['passed'] for x in checks),'WRs':len(history['findings']),'old_native_research_checks':len(research_report['checks']),'old_native_lean_checks':len(lean_report['checks']),'journal_sha256':sha256(journal).hexdigest(),'all_source_unchanged':before==after}),flush=True)
