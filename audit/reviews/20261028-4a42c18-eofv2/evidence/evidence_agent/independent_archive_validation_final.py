"""Independent offline archive verification; no provider or authoritative writes."""
from pathlib import Path
import argparse,ast,copy,hashlib,html,io,json,subprocess,sys,tarfile,tempfile
sys.dont_write_bytecode=True
p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--baseline',type=Path,required=True);p.add_argument('--archive',type=Path,required=True);p.add_argument('--git',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
S=a.source.resolve();B=a.baseline.resolve();A=a.archive.resolve();O=a.out.resolve();O.mkdir(parents=True,exist_ok=True)
sys.path[:0]=[str(S/'cloud'),str(S/'tools')]
from qresearch.artifacts import MemoryArtifactStore,content_hash,canonical_json
from qresearch.registry import Registry
from qresearch.engineering_receipts import backtest_runtime_failure,ReceiptParseError
from qresearch.engineering_data import verify_deployment,verify_deployment_observation,DeploymentVerificationError
from qresearch.deployment_sources import build_manifest
import stage2

def digest(b):return hashlib.sha256(b).hexdigest()
def canon(x):return json.dumps(x,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()
def read(root,name):return json.loads((root/name).read_bytes())
checks=[]
def check(name,condition,kind='static',detail=None):
 checks.append({'name':name,'kind':kind,'passed':bool(condition),'detail':detail})
 if not name.startswith('protected_raw_all_'):assert condition,name
 # Known protected-manifest mismatch remains false in results; continue other independent checks without changing expected bytes.
def guard(root):return{p.relative_to(root).as_posix():digest(p.read_bytes())for p in root.rglob('*')if p.is_file()}
before={name:guard(root)for name,root in [('candidate',S),('baseline',B),('archive',A)]}
protected=read(S,'audit/review_packages/deployment-eof-v2/protected_before.json')
check('protected_declares122',len(protected)==122)
for label,root in [('candidate',S),('baseline',B),('archive',A)]:
 check('protected_raw_all_'+label,all(digest((root/name).read_bytes())==d for name,d in protected.items()),detail={'files':122})
check('protected_actual_original_bytes_equal_baseline_archive',all((S/name).read_bytes()==(B/name).read_bytes()==(A/name).read_bytes()for name in protected))
pkg=S/'audit/review_packages/deployment-eof-v2';artifact=read(pkg,'artifact_manifest.json')
check('package_artifact_all10_raw_hashes',len(artifact['files'])==10 and all(digest((pkg/n).read_bytes())==d for n,d in artifact['files'].items()))
full=read(pkg,'full_offline_verification.json');ref=full['stage_verification_ref']
check('full_offline_stage_raw_reference',digest((S/ref['path']).read_bytes())==ref['sha256'])
check('full_offline_embedded_outputs_hashes',all(digest(full[n].encode())==full[n+'_sha256']for n in ['stdout','stderr']))
declared_maps=read(S.parents[0],'source_git_manifest.json')
for name in before:check('complete_raw_git_'+name,before[name]==declared_maps[name]['files'],detail={'count':len(before[name])})

book=(S/'audit/runtime/registry/events.jsonl').read_bytes();lines=book.splitlines(keepends=True)
check('journal48',len(lines)==48)
prefix=b''.join(lines[:46]);check('original46_exact_f50d',digest(prefix)=='f50d4cd8195428966484230adf0fd54ccf77f796159af61df748f37a7d1101b1')
prior=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-4520fd1-20261028\source')
check('original46_equals_prior_review',prefix==(prior/'audit/runtime/registry/events.jsonl').read_bytes())
check('offline_repair_book_unchanged_vs_baseline_archive',book==(B/'audit/runtime/registry/events.jsonl').read_bytes()==(A/'audit/runtime/registry/events.jsonl').read_bytes())
previous=None;events=[]
for seq,line in enumerate(lines,1):
 row=json.loads(line);unsigned={k:row[k]for k in ['sequence','previous_hash','event']}
 assert row['sequence']==seq and row['previous_hash']==previous and row['hash']==digest(canon(unsigned))
 previous=row['hash'];events.append(row['event'])
check('independent_full48_hash_chain',len(events)==48)
check('only_new_failed_and_close_not_debits',[x['kind']for x in events[46:]]==['failed','engineering_round_closed'])
check('failed_original_attempt47',events[46]['attempt_id']=='37dc855045e14ca49c88fd9d75f40cf7' and events[46]['error']['platform_status']=='runtime_error')
check('round_closed48',events[47]['round_id']=='stage2-normal-repair-round-004')
store=MemoryArtifactStore()
for pth in (S/'audit/runtime').rglob('*'):
 if pth.is_file():store._data[pth.relative_to(S/'audit/runtime').as_posix()]=pth.read_bytes()
memory_before=dict(store._data)
registry=Registry(store,read(S,'audit/runtime/registry/baseline.json'));snapshot=registry.snapshot()
totals={k:v['total']for k,v in snapshot['usage'].items()}
check('registry_usage12_15_2',totals=={'configurations':12,'research':15,'lean':2},'dynamic_Metadata')
round_data=registry._replay()['engineering_rounds']['stage2-normal-repair-round-004']
check('round_closed_no_refund',round_data['status']=='closed'and registry._round_usage(registry._replay(),round_data)=={'configurations':2,'research':2,'lean':1},'dynamic_Metadata')
attempt='37dc855045e14ca49c88fd9d75f40cf7';bridge=stage2.bridge_for_attempt(attempt,registry=registry)
admission=stage2.admitted_input(bridge,attempt);payload=admission['payload'];deployment=admission['deployment'];manifest=payload['deployment_manifest']
check('original_v1_manifest32',len(manifest)==32 and 'schema_version'not in manifest,'dynamic_Metadata')
check('original_input_exact',digest((S/admission['input_path']).read_bytes())==deployment['input_hash']=='8c9de804d671e13040a8aa765315937898ed8f9b1f28909606a5eff0a897dc03')
check('old_plan_and_deployment_identity',payload['plan']['required_checks']['lean']==['source_snapshot_matches','raw_data_received','complete_expected_bars','no_orders','development_only','symbol_registry_resolved','corporate_action_received']and len(payload['plan']['required_checks']['research'])==13 and deployment['deployment_hash']==digest(canon(manifest)))
recovered=stage2.prepare(bridge,attempt)
check('failed_original_input_prepare_recovery_no_reinterpretation',recovered==admission,'dynamic_Metadata')
packet_name='audit/tool_observations/'+attempt+'-backtest-result.json';packet_raw=(S/packet_name).read_bytes();packet=json.loads(packet_raw)
check('native_read_identity_exact',packet['tool_name']=='mcp__quantconnect__read_backtest'and packet['arguments']=={'projectId':38436695,'backtestId':'3e68866a46ca88ff16481c31b3c2c822'})
native=packet['result']['structuredContent'];texts=[json.loads(x['text'])for x in packet['result']['content']if x.get('type')=='text']
check('native_dual_carriers_exact',texts==[native]and packet['result']['isError']is True)
check('native_explicit_runtime_terminal',native['success']is False and native['errors'][0]=='The backtest ended with a runtime error.'and len(native['errors'])==3)
completion=backtest_runtime_failure(payload,deployment,'3e68866a46ca88ff16481c31b3c2c822',packet)
expected_ref=events[46]['error']['evidence_ref'];stored_completion=read(S,'audit/runtime/'+expected_ref['key'])
check('native_failure_equals_original_saved_completion',completion==stored_completion and digest(canon(completion))==expected_ref['sha256'],'dynamic_Metadata')
submission=bridge._recorded_submission(payload);status,passed=bridge._completion_contract(payload,submission,completion)
check('failure_contract_never_success',status=='runtime_error'and passed is False,'dynamic_Metadata')
check('raw_native_response_hash_bound',completion['platform']['raw_receipt']['response_sha256']==digest(canon(packet['result'])))
check('raw_native_completion_identity_bound',completion['platform']['deployment']==deployment and completion['platform']['identity']==dict(payload['identity'],external_id='3e68866a46ca88ff16481c31b3c2c822'))
calls=[]
def forbidden_reader(*args):calls.append(True);raise AssertionError('Already-failed original called completion reader')
terminal=bridge.consume_completion(attempt,completion_source=forbidden_reader)
check('failed_consume_idempotent_no_reader',terminal.status=='failed'and not calls,'dynamic_Metadata')
check('original_replay_no_metadata_writes',store._data==memory_before,'dynamic_Metadata')

logs=read(S,'audit/tool_observations/'+attempt+'-backtest-logs.json')
check('logs_search_identity',len(logs)==1 and logs[0]['arguments']=={'projectId':38436695,'backtestId':'3e68866a46ca88ff16481c31b3c2c822','query':'AQRP_ENGINEERING '+attempt,'page':1})
log_native=logs[0]['result']['structuredContent'];log_mirrors=[json.loads(x['text'])for x in logs[0]['result']['content']if x.get('type')=='text']
check('logs_empty_no_success_report',log_mirrors==[log_native]and log_native=={'success':True,'logs':[],'totalPages':0})

argv=['git','-C',str(a.git),'archive','662ccd876b67ca0949f921a53c4c33df37cfbbf1','cloud'];g=subprocess.run(argv,capture_output=True);assert g.returncode==0
with tarfile.open(fileobj=io.BytesIO(g.stdout))as t:frozen={m.name[6:]:t.extractfile(m).read()for m in t.getmembers()if m.isfile()and m.name.endswith('.py')}
norm=lambda b:b.decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n').encode()
check('original_frozen_Git32_deployment',len(frozen)==32 and {n:digest(norm(b))for n,b in frozen.items()}==manifest)
original=frozen['engineering_smoke.py'];changed=original+b'\n'
check('one_added_LF_raw_hash',digest(original)=='33ffa365d6b54d0a823574eaba5831c2f53c6aae7f2dff2c885b1d7ac0c9ca90'and digest(changed)=='5b7111b3806c2f4a8f93b85ffb8a54fa63cebdefb126bcc449c6020b95d3c4e5')
def parse_diagnostics(text):
 text=html.unescape(text);answer=[];offset=0
 while True:
  at=text.find('diagnostics=',offset)
  if at<0:return answer
  part=text[at+12:]
  try:obj,used=json.JSONDecoder().raw_decode(part)
  except json.JSONDecodeError:obj,used=json.JSONDecoder().raw_decode(part.replace('\\"','"'))
  answer.append(obj);offset=at+12+used
diag=parse_diagnostics(native['errors'][1])[0]
check('one_LF_matches_native_first_mismatch',diag['expected_sha256']==digest(original) and diag['observed_sha256']==digest(changed) and diag['path']=='engineering_smoke.py'and diag['failure_kind']=='source_hash_mismatch')
tree=ast.parse(changed);fmt={'byte_count':len(changed),'raw_sha256':digest(changed),'utf8_bom':changed.startswith(b'\xef\xbb\xbf'),'crlf_count':changed.count(b'\r\n'),'standalone_cr_count':changed.count(b'\r')-changed.count(b'\r\n'),'lf_count':changed.count(b'\n'),'normalized_trailing_lf_count':len(norm(changed))-len(norm(changed).rstrip(b'\n')),'syntax_status':'parsed','future_import_count':sum(isinstance(x,ast.ImportFrom)and x.module=='__future__'for x in ast.walk(tree)),'algorithm_import_count':sum(isinstance(x,ast.Import)and any(y.name=='AlgorithmImports'for y in x.names)for x in ast.walk(tree)),'algorithm_from_import_count':sum(isinstance(x,ast.ImportFrom)and x.module=='AlgorithmImports'for x in ast.walk(tree)),'algorithm_star_import_count':sum(isinstance(x,ast.ImportFrom)and x.module=='AlgorithmImports'and any(y.name=='*'for y in x.names)for x in ast.walk(tree))}
check('one_LF_matches_entire_reported_source_format',fmt==diag['worker_observation']['source_format'])
check('native_observation_scope_not_packaging_proof',diag['worker_observation']['coverage_scope']=='first_rejected_declared_source'and diag['worker_observation']['old_worker_root_cause_proven']is False and diag['worker_observation']['unlisted_worker_paths_scanned']is False and diag['worker_observation']['strict_identity_relaxed']is False)

mutants=[]
for label,alter in [('wrong_project',lambda x:x['arguments'].update(projectId=38436696)),('wrong_external',lambda x:x['arguments'].update(backtestId='0'*32)),('no_terminal_marker',lambda x:[x['result']['structuredContent']['errors'].__setitem__(0,'Request timed out.'),x['result']['content'].__setitem__(0,{'type':'text','text':json.dumps(x['result']['structuredContent'])})])]:
 wrong=copy.deepcopy(packet);alter(wrong)
 try:backtest_runtime_failure(payload,deployment,'3e68866a46ca88ff16481c31b3c2c822',wrong)
 except ReceiptParseError:mutants.append(label)
 else:raise AssertionError(label+' accepted')
check('failure_identity_and_nonterminal_mutants_rejected',len(mutants)==3,'dynamic_synthetic',mutants)

with tempfile.TemporaryDirectory(dir=O,prefix='one_file_')as temp:
 root=Path(temp);path=root/'engineering_smoke.py';path.write_bytes(changed);legacy={'engineering_smoke.py':digest(original)};v2=build_manifest({'engineering_smoke.py':original})
 try:verify_deployment(legacy,content_hash(legacy),source_root=root,worker_diagnostics=True)
 except DeploymentVerificationError as exc:check('v1_oneLF_still_rejected',exc.diagnostics['expected_sha256']==digest(original)and exc.diagnostics['observed_sha256']==digest(changed),'dynamic_synthetic')
 else:raise AssertionError('v1 weakened')
 observation=verify_deployment_observation(v2,content_hash(v2),source_root=root)
 check('v2_worker_oneLF_acceptance',observation['eof_normalized_file_count']==1 and observation['original_source_identity_match']is False,'dynamic_synthetic')
 try:verify_deployment(v2,content_hash(v2),source_root=root,require_source_bytes=True)
 except DeploymentVerificationError:check('v2_strict_preflight_oneLF_rejected',True,'dynamic_synthetic')
 else:raise AssertionError('v2 preflight weakened')
 path.write_bytes(original+b'\nCHANGED=True\n')
 try:verify_deployment_observation(v2,content_hash(v2),source_root=root)
 except DeploymentVerificationError:check('v2_body_change_rejected',True,'dynamic_synthetic')
 else:raise AssertionError('v2 body weakened')

check('actual_new_config_not_registered',read(S,'audit/stage2_deployment_source_fix.json')['repair']['candidate_configuration_hash']not in snapshot['config_ids'])
development=read(S,'config/development.json');check('all_declared_execution_gates_closed',all(development['execution'][k]is False for k in ['market_research_enabled','llm_runtime_enabled','final_test_enabled','live_trading_enabled']))
readiness=read(S,'audit/stage2_current_readiness.json');check('readiness_does_not_approve_new_candidate',readiness['new_candidate_independently_accepted']is False and readiness['stage2_status']=='not_accepted_native_LEAN_failed_and_data_gates_incomplete')
check('new_policy_has_no_cloud_runtime_evidence',read(S,'audit/stage2_deployment_source_fix.json')['original_failure']['new_successful_cloud_worker']is False)
for name,root in [('candidate',S),('baseline',B),('archive',A)]:check('final_source_guard_'+name,guard(root)==before[name])
result={'fixed_commit':'4a42c18f0b78bea2068d589bc12f1615712354c6','baseline_commit':'8d65c290773547c83549c098172f1eb8c3376cd7','archive_commit':'1cf26578da59eebd37e138ca5d6d076991386470','checks':checks,'unit_methods':0,'static_checks':sum(x['kind']=='static'for x in checks),'dynamic_Metadata_checks':sum(x['kind']=='dynamic_Metadata'for x in checks),'dynamic_synthetic_checks':sum(x['kind']=='dynamic_synthetic'for x in checks),'journal_sha256':digest(book),'prefix46_sha256':digest(prefix),'events':48,'global_usage':totals,'round_status':'closed','actual_original_LEAN_status':'runtime_error','actual_original_ledger_status':'failed','actual_seven_success_checks':None,'actual_orders':None,'protected_files':len(protected),'original_manifest_version':1,'old_runtime_source':'662ccd876b67ca0949f921a53c4c33df37cfbbf1','native_result_packet_sha256':digest(packet_raw),'native_logs_packet_sha256':digest((S/('audit/tool_observations/'+attempt+'-backtest-logs.json')).read_bytes()),'native_reported_source_format':fmt,'first_diagnostic':diag,'one_added_LF_exactly_reproduces_observation':True,'platform_packaging_step_proven':False,'other_worker_files_certified':False,'old39cafa_specific_cause_proven':False,'cloud_calls':0,'Research':0,'LEAN':0,'model_calls':0,'authoritative_budget_writes':0,'source_original_bytes_unchanged':True,'git_commands':[{'command':argv,'exit_code':g.returncode,'archive_sha256':digest(g.stdout)}],'findings':[{'id':'protected_Git_hash_mismatch','scope':'review_package_reproducibility','expected_protected_files':122,'actual_matching_protected_files':119,'mismatch_files':['audit/data_exposure.json','config/research.json','config/workflow.json'],'product_source_edited':False}]}
(O/'results.json').write_text(json.dumps(result,ensure_ascii=True,indent=2)+'\n',encoding='utf-8');print(json.dumps({k:v for k,v in result.items()if k not in ['checks','first_diagnostic','native_reported_source_format','git_commands']}))
