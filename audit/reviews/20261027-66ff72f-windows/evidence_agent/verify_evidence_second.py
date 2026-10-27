"""Independent saved-terminal/source/evidence/ledger verification; offline only."""
from pathlib import Path
import ast,copy,hashlib,io,json,re,subprocess,tarfile,zipfile
R=Path(__file__).resolve().parents[1];O=Path(__file__).resolve().parent;S=R/'source'
G=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\repo')
OLD=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-84414ab-20261027');B=Path(r'B:\BaiduSyncdisk\学习\投资\量化\量化交易比赛\LLM审核\review-84414ab-20261027')
SHA='66ff72ffaaff8c91c008898e6527c91131176c2a';BASE='84414ab49c39e25cb50ece1c1debeefa3993c874';EIGHTYONE='81fbe5294055423e88ee5aeae48ca6223e7971da'
ATTEMPT='bfd00f2611fd4496b9498d4597618a8e';EXTERNAL='39cafa1e9b11f91b27e396b66d033a6d';checks=[]
def canon(v):return json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def norm(b):return b.decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n').encode()
def check(n,ok,detail=None):checks.append({'check':n,'passed':bool(ok),'detail':detail})
def gitfiles(rev):
 raw=subprocess.check_output(['git','-C',str(G),'archive',rev])
 with tarfile.open(fileobj=io.BytesIO(raw)) as t:return {m.name:t.extractfile(m).read() for m in t.getmembers() if m.isfile()}
files=gitfiles(SHA);base=gitfiles(BASE);old81=gitfiles(EIGHTYONE);doc=lambda p:json.loads(files[p])
disk={p.relative_to(S).as_posix():p.read_bytes() for p in S.rglob('*') if p.is_file()};bad=[p for p in set(files)|set(disk) if files.get(p)!=disk.get(p)]
check('3178_fixed_Git_source_file_set',len(files)==3178 and set(files)==set(disk));check('all3178_raw_source_bytes_equal_fixed_Git',not bad,bad)
manifest={p:sha(norm(b)) for p,b in files.items() if ((Path(p).parts[0] in ('cloud','config','templates','tests','tools','docs','.github') and Path(p).suffix in ('.py','.json','.md','.yml','.yaml') and '__pycache__' not in Path(p).parts) or p in ('requirements-test.txt','.gitattributes','.gitignore','AGENTS.md'))}
stage=doc('audit/stage_verification.json');review_hash=sha(canon(manifest));check('130_review_sources_and_hash_recomputed',len(manifest)==130 and manifest==stage['source_files'] and review_hash==stage['source_hash'])
check('current530_developer_log_saved_not_rerun',stage['local_tests_passed'] is True and 'Ran 530 tests' in stage['test_output'])
def assigns(data):return {n.targets[0].id:ast.literal_eval(n.value) for n in ast.parse(data).body if isinstance(n,ast.Assign)}
generated=assigns(files['cloud/research_config.py']);priorconfig=assigns(base['cloud/research_config.py'])
impl={Path(p).name:sha(norm(b)) for p,b in files.items() if p.startswith('cloud/qresearch/') and p.endswith('.py')};deploy={p[6:]:sha(norm(b)) for p,b in files.items() if p.startswith('cloud/') and p.endswith('.py')};dep=doc('audit/deployment.json')
check('29_current_deployment_source_map_recomputed',len(deploy)==29 and dep['source_files']==deploy)
check('current_implementation_hash_recomputed',generated['IMPLEMENTATION_SHA256']==dep['implementation_hash']==sha(canon(impl)))
check('active_research_configuration_unchanged',generated['CONFIGURATION']==priorconfig['CONFIGURATION'] and generated['SOURCE_SHA256']==priorconfig['SOURCE_SHA256']==dep['configuration_hash'])
budget=doc('config/budget.json');policy=copy.deepcopy(budget);policy.pop('usage');exmap=dict(manifest);exmap['config/budget.json']=sha(canon(policy));exhash=sha(canon({'schema':'collection_execution_sources_v1','source_files':exmap}))
old_evidence=[p for p in base if p.startswith(('audit/reviews/','audit/review_packages/'))];oldbad=[p for p in old_evidence if files.get(p)!=base[p]]
check('all_old_review_packages_and_failed_originals_raw_unchanged',not oldbad,{'files':len(old_evidence),'changed':oldbad})
diff=[{'path':p,'change':'added' if p not in base else 'removed' if p not in files else 'modified','old_raw_sha256':sha(base[p]) if p in base else None,'new_raw_sha256':sha(files[p]) if p in files else None} for p in sorted(set(files)|set(base)) if files.get(p)!=base.get(p)]

developer_rows=[];package_counts={}
for name,manifest_file,entries_key in [('native_runtime_failure','original_files_manifest.json','files'),('native_rejection','original_files_manifest.json','files'),('deployment_integrity','developer_outputs_manifest.json','entries')]:
 prefix='audit/review_packages/'+name+'/';m=doc(prefix+manifest_file);rows=m[entries_key];package_counts[name]=len(rows)
 for row in rows:
  p=row['path'] if entries_key=='entries' else prefix+row['path'];b=files[p];ok=sha(b)==row['raw_sha256'] and len(b)==row['bytes'];check('developer_raw_'+name+'_'+p,ok);developer_rows.append({'path':p,'raw_sha256':sha(b),'bytes':len(b),'passed':ok})
 if entries_key=='files':
  dev=doc(prefix+'developer_verification.json');check('developer_'+name+'_manifest_declarations',m['file_count']==len(rows)==dev['original_files'] and sha(files[prefix+manifest_file])==dev['original_files_manifest_raw_sha256'])
check('184_developer_originals_three_groups',package_counts=={'native_runtime_failure':65,'native_rejection':41,'deployment_integrity':78} and len(developer_rows)==184)
def transcript(p):
 text=files[p].decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n');f=re.findall(r'^FAIL: (test_\w+)',text,re.M);e=re.findall(r'^ERROR: (test_\w+)',text,re.M);ran=re.search(r'^Ran (\d+) tests? in ',text,re.M)
 return {'methods':int(ran.group(1)) if ran else None,'failed_methods':len(set(f)),'failure_records':len(f),'error_methods':len(set(e)),'error_records':len(e),'OK':bool(re.search(r'^OK$',text,re.M))}
raw_counts={}
for label,p in [('runtime_before','native_runtime_failure/original_developer_final_baseline.stderr'),('runtime_after','native_runtime_failure/original_developer_final_candidate.stderr'),('rejection_before','native_rejection/original_developer_final_baseline.stderr'),('rejection_after','native_rejection/original_developer_final_candidate.stderr'),('diagnostics_before','deployment_integrity/diagnostics/final_baseline.stderr'),('diagnostics_after','deployment_integrity/diagnostics/final_candidate.stderr'),('current530','deployment_integrity/verification/verify.stderr')]:raw_counts[label]=transcript('audit/review_packages/'+p)
check('runtime_developer_raw15_before13failed49records_then_OK',raw_counts['runtime_before']=={'methods':15,'failed_methods':13,'failure_records':49,'error_methods':0,'error_records':0,'OK':False} and raw_counts['runtime_after']['methods']==15 and raw_counts['runtime_after']['OK'])
check('rejection_developer_raw25_before67fails6errors_then_OK',raw_counts['rejection_before']['methods']==25 and raw_counts['rejection_before']['failure_records']==67 and raw_counts['rejection_before']['error_records']==6 and raw_counts['rejection_after']['methods']==25 and raw_counts['rejection_after']['OK'])
check('diagnostics_developer_raw15_before28fails2errors_then_OK',raw_counts['diagnostics_before']['methods']==15 and raw_counts['diagnostics_before']['failure_records']==28 and raw_counts['diagnostics_before']['error_records']==2 and raw_counts['diagnostics_after']['methods']==15 and raw_counts['diagnostics_after']['OK'])
check('current530_full_stderr_raw_transcript_OK',raw_counts['current530']['methods']==530 and raw_counts['current530']['OK'])
check('earlier_developer_fixture_and_reader_corrections_retained',all('audit/review_packages/deployment_integrity/'+p in files for p in ('diagnostics/initial_fixture_before.stderr','diagnostics/pre_reader_isolation_final_replay.json','diagnostics/initial_reserved_probe_reserved_before.stderr','peer/probe-initial.txt','peer/probe-DEL-before.txt')) and 'initial_preflight_helper_failure' in doc('audit/review_packages/native_rejection/developer_verification.json'))

A='audit/reviews/20261027-84414ab-windows/';am=doc(A+'archive_manifest.json');archive_rows=[]
for row in am['files']:
 b=files[A+row['archive_path']];origins=[str(p) for p in (B/row['origin_relative_path'],OLD/row['origin_relative_path']) if p.is_file() and p.read_bytes()==b];ok=sha(b)==row['raw_sha256'] and len(b)==row['bytes'] and bool(origins)
 check('844_original_'+row['archive_path'],ok);archive_rows.append({'path':row['archive_path'],'raw_sha256':sha(b),'bytes':len(b),'matching_originals':origins,'passed':ok})
check('82_original_review_files_and_byte_total',len(archive_rows)==82==am['file_count'] and sum(v['bytes'] for v in archive_rows)==am['total_original_bytes'])
reused=[]
for row in am['reused_existing_evidence']:
 b=files[row['existing_archive_path']];origin=B/row['origin_relative_path'];ok=origin.is_file() and origin.read_bytes()==b and sha(b)==row['raw_sha256'] and len(b)==row['bytes'];check('844_reused_'+row['origin_relative_path'],ok);reused.append({'path':row['existing_archive_path'],'origin':str(origin),'passed':ok})
check('3_original_deduplicated_refs',len(reused)==3)
artifact=doc(A+'artifact_manifest.json');artifactbad=[p for p,h in artifact.items() if not (B/p).is_file() or sha((B/p).read_bytes())!=h]
check('all5349_original_artifact_entries_equal_B_root',len(artifact)==5349==am['full_original_artifact_manifest_hash_checks'] and artifact==json.loads((B/'artifact_manifest.json').read_text(encoding='utf-8-sig')) and not artifactbad,artifactbad)
for label,path,mapping in [('candidate',B/'source',base),('baseline81',B/'baselines/81fbe52/source',old81)]:
 actual={p.relative_to(path).as_posix():p.read_bytes() for p in path.rglob('*') if p.is_file()};mismatch=[p for p in set(actual)|set(mapping) if actual.get(p)!=mapping.get(p)];check('original844_'+label+'_raw_source_equals_Git',not mismatch and len(mapping)==am['source_Git_blob_checks'][label]['files'],{'files':len(mapping),'mismatches':mismatch})
zp=Path(am['review_zip']['path'])
with zipfile.ZipFile(zp) as z:
 check('844_final_ZIP_raw_SHA_CRC_unique_paths',sha(zp.read_bytes())==am['review_zip']['raw_sha256'] and z.testzip() is None and len(z.namelist())==len(set(z.namelist())))
 zipbad=[p for p,h in artifact.items() if sha(z.read(B.name+'/'+p))!=h];check('all5349_final_ZIP_entries_match_manifest',not zipbad and am['review_zip']['verified_entries']==5349,zipbad)
for p in am['sidecar_sha256_checks']:check('844_sidecar_'+p,sha(files[A+p.removesuffix('.sha256')])==files[A+p].decode('utf-8-sig').split()[0])
check('844_reader_error_and591_correction_kept',doc(A+'evidence_agent/metadata_verification_first.json')['passed_checks']==589 and doc(A+'evidence_agent/metadata_verification.json')['passed_checks']==591)

terminal=doc('audit/stage2_terminal_reconciliation.json');rawpath='audit/tool_observations/'+ATTEMPT+'-terminal-runtime-error.json';raw=files[rawpath];packet=json.loads(raw);parser=json.loads((O/'parser_replay.json').read_text(encoding='utf-8'));replay=json.loads((O/'old_bridge_replay.json').read_text(encoding='utf-8'));observed=json.loads((O/'parsed_observation.json').read_bytes())
check('native_packet_raw_and_parser_hash_bound',sha(raw)==terminal['native_tool_receipt_raw_sha256']==parser['native_original_raw_sha256'] and sha(files['cloud/qresearch/engineering_receipts.py'])==terminal['parser_source_raw_sha256']==parser['parser_raw_sha256'])
check('native_carriers_equal_strict_failure_marker',packet['tool_name']=='mcp__quantconnect__read_backtest' and packet['arguments']=={'projectId':38436695,'backtestId':EXTERNAL} and packet['result']['isError'] is True and packet['result']['structuredContent']==json.loads(packet['result']['content'][0]['text']) and packet['result']['structuredContent']['success'] is False and packet['result']['structuredContent']['errors'][0]=='The backtest ended with a runtime error.')
admitted=doc('audit/runtime/engineering/admitted-inputs/'+ATTEMPT+'.json');submission=doc('audit/runtime/engineering/submissions/'+ATTEMPT+'.json')
check('observation_bound_to_original_attempt_input_source_deployment_submission',observed['platform']['deployment']==admitted['deployment']==submission['deployment'] and observed['platform']['identity']==dict(admitted['payload']['identity'],external_id=EXTERNAL) and sha(files[admitted['input_path']])==admitted['deployment']['input_hash'] and submission['external_id']==EXTERNAL)
check('canonical_parsed_failure_evidence_matches_actual_saved_reference',sha(canon(observed))==terminal['parsed_observation_sha256']==parser['observation_sha256'] and files['audit/runtime/engineering/evidence/'+ATTEMPT+'/completion/'+parser['observation_sha256']+'.json']==canon(observed))
check('real_packet_has_no_native_orders_progress_completed_or_backtest_object',set(packet['result']['structuredContent'])=={'success','errors'} and terminal['orders_count'] is None and terminal['progress'] is None and terminal['completed_flag'] is None)
check('parser_and_old81_mirror_replay_actually_passed',parser['production_parser_calls']==2 and replay['production_consume_completion_calls']==4 and replay['event_counts']=={'before':12,'after':13,'same_receipt_replay':13} and replay['actual13_event_semantics_match_mirror_ignoring_recorded_at'] is True and replay['success_result_created'] is False and replay['actual_registry_writes']==0)
check('two_diagnostics_one_failure_not_order_or_success_evidence',len(packet['result']['structuredContent']['errors'])-1==terminal['specific_failure_diagnostic_strings']==2 and terminal['diagnostic_strings_are_not_distinct_failures'] is True and observed['platform']['raw_receipt']['diagnostic_count']==2)
raw_events=files['audit/runtime/registry/events.jsonl'];old_events=base['audit/runtime/registry/events.jsonl'];events=[];prev=None;check('original12_event_prefix_preserved_raw',len(old_events.splitlines())==12 and len(raw_events.splitlines())==13 and raw_events.startswith(old_events))
for i,line in enumerate(raw_events.splitlines(),1):
 env=json.loads(line);body={k:v for k,v in env.items() if k!='hash'};check('event_'+str(i)+'_sequence_hash_chain',env['sequence']==i and env['previous_hash']==prev and sha(canon(body))==env['hash']);events.append(env['event']);prev=env['hash']
usage=copy.deepcopy(events[0]['initial_usage']);attempts={}
for ev in events[1:]:
 if ev['kind'] in ('config_registered','attempt_started'):
  st='configurations' if ev['kind']=='config_registered' else ev['stage'];usage[st]['total']+=1;usage[st][ev['allocation']]+=1
 if ev['kind']=='attempt_started':attempts[ev['attempt_id']]=dict(ev,status='started')
 if ev['kind'] in ('pending','ambiguous','failed','completed'):attempts[ev['attempt_id']].update(ev,status=ev['kind'])
totals={k:usage[k]['total'] for k in ('configurations','research','lean')};record=attempts[ATTEMPT]
check('13events_replay6_9_1_failed_once_no_refund',totals=={'configurations':6,'research':9,'lean':1} and usage==terminal['usage_before']==terminal['usage_after']==replay['usage_before']==replay['usage_after'] and record['status']=='failed' and record['external_id']==EXTERNAL and sum(e['kind']=='failed' and e['attempt_id']==ATTEMPT for e in events if 'attempt_id' in e)==1)
check('last_event_only_old_attempt_runtime_failure',events[-1]['kind']=='failed' and events[-1]['attempt_id']==ATTEMPT and events[-1]['error']['platform_status']=='runtime_error' and events[-1]['error']['evidence_ref']==replay['evidence_ref'] and events[-1]['reconciliation']==parser['observation_sha256'])
protected=[p for p in base if p.startswith(('config/','templates/','audit/runtime/','audit/task_inputs/','audit/tool_observations/')) and p!='audit/runtime/registry/events.jsonl' or p in ('audit/data_exposure.json','audit/engineering_current.json','AGENTS.md','docs/research_charter.md')]
protectedbad=[p for p in protected if files.get(p)!=base[p]];check('all_old_authority_input_submission_pointer_budget_exposure_raw_unchanged_except_explicit_event_append',not protectedbad,{'paths':len(protected),'changed':protectedbad})
newruntime=sorted(p for p in set(files)-set(base) if p.startswith('audit/runtime/'));check('only_one_new_runtime_completion_artifact',newruntime==['audit/runtime/engineering/evidence/'+ATTEMPT+'/completion/'+parser['observation_sha256']+'.json'],newruntime)
check('no_new_success_result_for_old_attempt',not any(ATTEMPT in p and '/results/' in p for p in files))
flags=doc('config/development.json')['execution'];check('all_four_execution_flags_false',all(flags[k] is False for k in ('market_research_enabled','llm_runtime_enabled','final_test_enabled','live_trading_enabled')))
rootcause=doc('audit/stage2_deployment_root_cause.json');synthetic=doc('audit/review_packages/deployment_integrity/root_cause/documented_import_emulation.json');summary=doc('audit/review_packages/deployment_integrity/root_cause/summary.json')
check('source_projection_is_not_archived_native_tool_or_worker_snapshot',rootcause['original_tool_envelope_not_rewritten_or_archived'] is True and rootcause['notebook_content_persisted'] is False and rootcause['worker_file_bytes_or_hashes_observed'] is False and rootcause['runtime_transform_root_cause_proven'] is False and rootcause['original_runtime_failure_repaired'] is False)
check('frozen25_source_projection_metadata_has_exact_bound_hashes',rootcause['known_implementation_files']==25 and len(rootcause['records'])==25 and all(v['expected_sha256']==v['observed_sha256'] and v['matches'] is True for v in rootcause['records']) and rootcause['expected_manifest_hash']==admitted['deployment']['deployment_hash'] and rootcause['separately_bound_input_hash']==admitted['deployment']['input_hash'])
check('synthetic_import_emulation_is_not_real_worker_root_cause',synthetic['kind']=='synthetic_offline_emulation_not_actual_worker_evidence' and synthetic['assumption_not_confirmed_from_actual_backtest_files'] is True and summary['root_cause_certified'] is False and summary['synthetic_emulation_proves_worker_behavior'] is False)
preflight=doc('audit/stage2_next_preflight.json');check('preflight_has_separate_older_observation_identity_not_terminal_refresh',preflight['read_python_files']==26 and preflight['known_old_implementation_paths']==25 and preflight['old_backtest_terminal_confirmed'] is False and preflight['full_cloud_inventory_certified'] is False and preflight['separate_fixed_candidate_comparison']['candidate_commit']=='268f420e9d066e7e7859566a65c0ce65523bec82')
afterdisk={p.relative_to(S).as_posix():p.read_bytes() for p in S.rglob('*') if p.is_file()};check('all3178_source_bytes_unchanged_after_replay_and_static_checks',afterdisk==disk)
report={'fixed_candidate':SHA,'baseline':BASE,'scope':'Independent saved-native parser replay and fixed81 isolated Bridge/Registry replay plus Git/hash/archive/ledger checks; no preflight function execution or large suite',
 'check_count':len(checks),'passed_checks':sum(v['passed'] for v in checks),'failed_checks':sum(not v['passed'] for v in checks),'software_unit_methods':0,'software_suite_runs':0,'production_replays':{'current_native_parser_calls':2,'old81_Bridge_consume_completion_calls':4,'negative_bindings':2,'failure_transition':1,'idempotent_receipt_replay':1},'actual_registry_writes':0,'new_QC_market_model_calls':0,
 'source':{'raw_files':len(files),'equal_fixed_Git':not bad,'review_files':len(manifest),'review_hash':review_hash,'execution_hash':exhash,'local_deployment_hash':sha(canon(deploy)),'implementation_hash':generated['IMPLEMENTATION_SHA256'],'active_configuration_hash':generated['SOURCE_SHA256'],'unchanged_after_checks':afterdisk==disk},
 'first_static_reader_error':{'exception':'KeyError: identity','cause':'Reviewer assumed admitted-input identity at top level; actual immutable schema stores it in payload.identity. Corrected only reviewer reading path. First script and raw stdout/stderr retained; first static attempt ended before writing summary. Both production parser/old81 mirror replay first runs already passed.','product_or_evidence_defect':False},
 'complete_diff':diff,'old_evidence_files_unchanged':len(old_evidence),'developer_originals':developer_rows,'developer_package_counts':package_counts,'developer_saved_raw_counts':raw_counts,
 'developer_evidence_boundary':'All184 package scripts/output bytes retained. Developer/peer original_independent_* names are delivery labels, not current GPT acceptance; their source commits differ from final66. Saved530 is developer log, not run by this agent. Current final software acceptance belongs to root review.',
 'prior_independent_archive':{'originals':archive_rows,'reused':reused,'artifact_entries_verified':len(artifact),'ZIP_sha256':sha(zp.read_bytes())},
 'terminal':{'native_original_raw_sha256':sha(raw),'parsed_observation_sha256':parser['observation_sha256'],'current_parser_raw_sha256':parser['parser_raw_sha256'],'replay_report':'old_bridge_replay.json','native_receipt_original_vs_projection_vs_synthetic_mechanism_distinguished':True},
 'protected_metadata':{'paths':len(protected),'changed':protectedbad},'budget':{'events':len(events),'original12_prefix_byte_preserved':True,'usage':usage,'limits':events[0]['limits'],'original_attempt':{k:record[k] for k in ('attempt_id','stage','status','external_id')}},'checks':checks,'financial_evidence':False,
 'boundaries':['Archived RuntimeError is one failed old execution; no new scientific execution or refund.','No independent platform retrieval by this agent; trust/provenance is the retained native wrapper plus exact original submission context.','Projection metadata cannot independently replay absent original read_project envelope or diagnose actual worker file mismatch.','Synthetic import insertion supports possible mechanism only.','Full stage2/system and data/financial validity are unaccepted.']}
p=O/'evidence_verification.json';p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');(O/'evidence_verification.json.sha256').write_text(sha(p.read_bytes())+'  evidence_verification.json\n',encoding='utf-8')
print(json.dumps({k:report[k] for k in ('fixed_candidate','check_count','passed_checks','failed_checks','software_unit_methods','source','developer_package_counts','protected_metadata','budget','production_replays')},ensure_ascii=False,indent=2))
for c in checks:
 if not c['passed']:print('FAILED',c)
raise SystemExit(0 if all(v['passed'] for v in checks) else 1)
