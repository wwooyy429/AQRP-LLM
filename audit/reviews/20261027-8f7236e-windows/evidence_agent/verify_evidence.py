"""Read-only source/evidence/ledger identity checks for joint pilot candidate."""
from pathlib import Path
import ast, copy, hashlib, io, json, subprocess, tarfile

ROOT=Path(__file__).resolve().parents[1];OUT=Path(__file__).resolve().parent
GIT=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\repo')
SHA='8f7236ecbafcb514f07a6af4150a5afdbc1fd474'
BASE='dd094f345f45b9d9cb78dd9295a6aefd587f4c68'
checks=[]
def canon(v):return json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def norm(b):return b.decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n').encode()
def check(n,ok,details=None):checks.append({'check':n,'passed':bool(ok),'details':details})
def gitfiles(rev):
    data=subprocess.check_output(['git','-C',str(GIT),'archive',rev])
    with tarfile.open(fileobj=io.BytesIO(data)) as tf:return {m.name:tf.extractfile(m).read() for m in tf.getmembers() if m.isfile()}
files=gitfiles(SHA);base=gitfiles(BASE)
def doc(p):return json.loads(files[p])
def source_map(mapping):
    result={}
    for p,b in mapping.items():
        parts=Path(p).parts
        if ((parts[0] in ('cloud','config','templates','tests','tools','docs','.github') and Path(p).suffix in ('.py','.json','.md','.yml','.yaml') and '__pycache__' not in parts) or p in ('requirements-test.txt','.gitattributes','.gitignore','AGENTS.md')):result[p]=sha(norm(b))
    return result
disk={p.relative_to(ROOT/'source').as_posix():p.read_bytes() for p in (ROOT/'source').rglob('*') if p.is_file()}
bad=[p for p in set(files)|set(disk) if files.get(p)!=disk.get(p)]
check('1563_file_set_equals_fixed_Git',len(files)==1563 and set(files)==set(disk))
check('all_source_raw_bytes_equal_fixed_Git',not bad,bad)
manifest=source_map(files);review_hash=sha(canon(manifest));old_review_hash=sha(canon(source_map(base)))
dev=doc('audit/review_packages/phase2_joint/developer_verification.json');stage=doc('audit/stage_verification.json')
check('117_normalized_source_manifest_files',len(manifest)==117==dev['source_files'])
check('complete_review_source_map_recomputed',manifest==stage['source_files'])
check('complete_review_source_hash_recomputed',review_hash==stage['source_hash']==dev['source_manifest_hash'])
diff=[{'path':p,'kind':'added' if p not in base else 'removed' if p not in files else 'modified','old_raw_sha256':sha(base[p]) if p in base else None,'new_raw_sha256':sha(files[p]) if p in files else None} for p in sorted(set(base)|set(files)) if base.get(p)!=files.get(p)]
prod=[d for d in diff if d['path'].startswith(('cloud/','config/','tools/','templates/'))]
expected={'cloud/qresearch/engineering_data.py','cloud/qresearch/engineering_receipts.py','cloud/qresearch/engineering_tasks.py','cloud/qresearch/registry.py','cloud/research_config.py','config/engineering_joint_pilot.json','tools/stage2.py'}
check('complete_seven_path_production_diff',{d['path'] for d in prod}==expected,prod)
check('all_previous_config_documents_raw_unchanged',all(files.get(p)==base[p] for p in base if p.startswith('config/')))
check('all_previous_tests_raw_unchanged',all(files.get(p)==base[p] for p in base if p.startswith('tests/')))
old_evidence=[p for p in base if p.startswith(('audit/reviews/','audit/review_packages/'))]
old_bad=[p for p in old_evidence if files.get(p)!=base[p]]
check('all_prior_failure_acceptance_precision_metadata_evidence_unchanged',not old_bad,{'files':len(old_evidence),'changed':old_bad})
wr14='audit/review_packages/wr14/';wm=doc(wr14+'developer_outputs_manifest.json')
check('WR15_corrected_Git_manifest_digest_kept',sha(files[wr14+'developer_outputs_manifest.json'])==doc(wr14+'developer_verification.json')['developer_outputs_manifest_raw_sha256']=='b8170f1c123ef3eb3991cb519206f7db8a700f6673f406121b5535f4411c8df5')
check('48_historical_output_hashes_still_match',len(wm['files'])==48 and all(sha(files[wr14+e['archive_path']])==e['raw_sha256'] and len(files[wr14+e['archive_path']])==e['bytes'] for e in wm['files']))

saved='audit/review_packages/phase2_joint/';rawmanifest=doc(saved+'original_outputs_manifest.json');raw_entries=[]
for entry in rawmanifest['files']:
    data=files[saved+entry['path']];ok=sha(data)==entry['raw_sha256'] and len(data)==entry['bytes']
    check('new_developer_raw_output_'+entry['path'],ok)
    raw_entries.append({'path':saved+entry['path'],'actual_raw_sha256':sha(data),'expected_raw_sha256':entry['raw_sha256'],'actual_bytes':len(data),'expected_bytes':entry['bytes'],'passed':ok})
check('nine_saved_original_outputs',len(raw_entries)==9)
check('new_original_output_attribute_minus_text','audit/review_packages/phase2_joint/** -text' in files['.gitattributes'].decode('utf-8-sig'))
original_full=doc(saved+'original_full_repository_verification.json')
check('developer423_record_matches_candidate_source',original_full['source_files']==manifest and original_full['source_hash']==review_hash and original_full['local_tests_passed'] is True and 'Ran 423 tests' in original_full['test_output'])
initial=doc(saved+'original_joint_boundary_initial10_summary.json');targeted=doc(saved+'original_joint_boundary_targeted_summary.json')
check('boundary_original_runs_not_replaced_by_worker_summary',initial['methods']==10 and targeted['methods']==12)
check('first_worker_failure_is_explicitly_summary_only',dev['own_worker_test_first_failure']['kind']=='developer_agent_reported_tool_transcript_summary_not_saved_raw_bytes' and dev['own_worker_test_first_failure']['methods']==4 and dev['own_worker_test_first_failure']['errors']==1 and 'not label' in dev['own_worker_test_first_failure']['evidence_limit'])
check('developer_evidence_not_independent_acceptance',dev['purpose']=='new_joint_protocol_developer_candidate_not_independent_or_financial_acceptance' and dev['financial_evidence'] is False and dev['cloud_source_changed'] is False)

def assignments(data):return {n.targets[0].id:ast.literal_eval(n.value) for n in ast.parse(data).body if isinstance(n,ast.Assign)}
generated=assignments(files['cloud/research_config.py']);old_generated=assignments(base['cloud/research_config.py'])
impl={Path(p).name:sha(norm(b)) for p,b in files.items() if p.startswith('cloud/qresearch/') and p.endswith('.py')}
deploy={p[len('cloud/'):]:sha(norm(b)) for p,b in files.items() if p.startswith('cloud/') and p.endswith('.py')};deployment=doc('audit/deployment.json')
check('implementation_hash_tracks_all_library_files',generated['IMPLEMENTATION_SHA256']==sha(canon(impl))==deployment['implementation_hash'])
check('generated_active_research_configuration_unchanged',generated['SOURCE_SHA256']==old_generated['SOURCE_SHA256']==deployment['configuration_hash'] and generated['CONFIGURATION']==old_generated['CONFIGURATION'])
check('local29file_deployment_hashes_recomputed',len(deploy)==29 and deployment['source_files']==deploy)
budget=doc('config/budget.json');policy=copy.deepcopy(budget);policy.pop('usage')
execution_map=dict(manifest);execution_map['config/budget.json']=sha(canon(policy));execution_hash=sha(canon({'schema':'collection_execution_sources_v1','source_files':execution_map}))
fn=next(n for n in ast.parse(files['tools/collection_task_cli.py']).body if isinstance(n,ast.FunctionDef) and n.name=='execution_source_manifest')
old_fn=next(n for n in ast.parse(base['tools/collection_task_cli.py']).body if isinstance(n,ast.FunctionDef) and n.name=='execution_source_manifest')
check('execution_manifest_policy_function_unchanged',ast.dump(fn,include_attributes=False)==ast.dump(old_fn,include_attributes=False))
namespace={'ROOT':Path('IN_MEMORY_ONLY'),'hashlib':hashlib,'canonical_json':canon,'content_hash':lambda v:sha(canon(v)),'source_manifest':lambda:{'source_files':copy.deepcopy(manifest)},'read_json':lambda _:copy.deepcopy(budget)}
exec(compile(ast.fix_missing_locations(ast.Module(body=[fn],type_ignores=[])),'candidate:execution_source_manifest','exec'),namespace)
check('execution_manifest_exactly_binds_source_and_budget_policy',namespace['execution_source_manifest']()=={'source_files':execution_map,'source_hash':execution_hash})

preview=doc('audit/stage2_joint_preview.json');plan=preview['plan'];pilot=doc('config/engineering_joint_pilot.json');catalog=doc('config/source_catalog.json')['fields']
check('preview_same_as_saved_raw_stdout',json.loads(files[saved+'original_preview.stdout'])==preview)
check('preview_plan_and_configuration_hashes',sha(canon(plan))==preview['plan_hash']==dev['preview_plan_hash'] and sha(canon({'engineering_task_schema_version':1,'plan':plan}))==preview['configuration_hash'])
check('preview_binds_current_execution_and_deployment',preview['source_manifest_hash']==plan['source_manifest_hash']==plan['collection_probe']['collection_plan']['source_manifest_hash']==execution_hash==dev['preview_source_hash'] and preview['deployment_hash']==plan['deployment_hash']==sha(canon(deploy)))
check('preview_explicit_not_registration_admission_dispatch',all(preview[k] is False for k in ('configuration_registered','execution_started','ready_to_dispatch','budget_admission_performed')) and dev['preview_is_registration_or_authorization'] is False)
check('unregistered_template_has_null_identity',all(pilot[k] is None for k in ('project_id','source_manifest_hash','deployment_hash')) and pilot['collection_probe']['collection_plan']['source_manifest_hash'] is None and pilot['collection_probe']['field_catalog'] is None)
selected=plan['collection_probe']['collection_plan']['fields']
check('joint_probe_four_explicit_observation_fields',set(selected)=={'dollar_volume','has_fundamental_data','time','end_time'} and plan['collection_probe']['field_catalog']=={k:catalog[k] for k in selected})
check('joint_probe_only_fixed40calendar_day_development_range',plan['collection_probe']['collection_plan']['start']=='2018-01-01T00:00:00-05:00' and plan['collection_probe']['collection_plan']['end_exclusive']=='2018-02-10T00:00:00-05:00')
check('joint_is_no_orders_no_financial_test_no_retry',plan['orders_enabled'] is False and plan['financial_metrics_enabled'] is False and plan['economic_factor'] is None and plan['economic_model'] is None and plan['max_retries']=={'research':0,'lean':0})
source_stage2=ast.parse(files['tools/stage2.py']);freeze=next(n for n in source_stage2.body if isinstance(n,ast.FunctionDef) and n.name=='freeze')
first_registry_index=next(i for i,n in enumerate(freeze.body) if isinstance(n,ast.Assign) and any(isinstance(v,ast.Call) and isinstance(v.func,ast.Name) and v.func.id=='open_registry' for v in ast.walk(n)))
preview_index=next(i for i,n in enumerate(freeze.body) if isinstance(n,ast.If) and isinstance(n.test,ast.Name) and n.test.id=='preview')
check('preview_returns_before_opening_registry_AST',preview_index<first_registry_index and isinstance(freeze.body[preview_index].body[-1],ast.Return))
preflight=doc('audit/stage2_live_preflight.json');listing=doc('audit/stage2_live_project_listing.json')
check('developer_preflight_is_metadata_read_only_not_runtime_claim',preflight['purpose']=='live_read_only_preflight_not_runtime_or_data_certification' and preflight['new_cloud_writes']==0 and all(v==0 for v in preflight['new_executions'].values()) and preflight['data_certification'] is False and preflight['financial_evidence'] is False)
check('preflight_preserves_pending_no_terminal_no_poll',preflight['pending_backtest_id']=='39cafa1e9b11f91b27e396b66d033a6d' and preflight['terminal_delivered'] is False and preflight['backtest_read_or_polled'] is False)
check('preflight_limits_readback_to_two_files_normalized_not_raw',preflight['source_commit_at_start']==BASE and [x['path'] for x in preflight['protected_cloud_source_checks']]==['main.py','_engineering_task_input.py'] and 'not all' in preflight['checked_source_scope'])
check('project_listing_metadata_consistent',preflight['project_listing']==listing and preflight['active_project']==plan['project_id'] and any(x['projectId']==plan['project_id'] for x in listing['projects']))

protected=[p for p in base if p.startswith(('audit/runtime/','audit/task_inputs/','audit/tool_observations/','templates/')) or p in ('config/budget.json','config/research.json','config/data.json','config/development.json','config/engineering.json','config/source_catalog.json','config/quantconnect.json','config/universe.json','config/workflow.json','audit/data_exposure.json','audit/engineering_current.json','audit/stage2_real_execution.json','audit/stage2_cloud_deployment.json','docs/research_charter.md','AGENTS.md')]
protected_bad=[p for p in protected if files.get(p)!=base[p]]
check('old_budget_pointer_inputs_partitions_exposure_and_protected_metadata_unchanged',not protected_bad,{'paths':len(protected),'changed':protected_bad})
new_runtime=[p for p in set(files)-set(base) if p.startswith(('audit/runtime/','audit/task_inputs/'))]
check('no_joint_config_registration_attempt_or_input_written',not new_runtime,new_runtime)
raw=files['audit/runtime/registry/events.jsonl'];events=[];previous=None
check('journal_complete_tail',raw.endswith(b'\n'))
for i,line in enumerate(raw.splitlines(),1):
    envelope=json.loads(line);body={k:v for k,v in envelope.items() if k!='hash'}
    check('event_'+str(i)+'_hash_chain',envelope['sequence']==i and envelope['previous_hash']==previous and sha(canon(body))==envelope['hash'])
    events.append(envelope['event']);previous=envelope['hash']
usage=copy.deepcopy(events[0]['initial_usage']);attempts={}
for e in events[1:]:
    kind=e['kind']
    if kind in ('config_registered','attempt_started'):
        stage_name='configurations' if kind=='config_registered' else e['stage'];usage[stage_name]['total']+=1;usage[stage_name][e['allocation']]+=1
    if kind=='attempt_started':attempts[e['attempt_id']]=dict(e,status='started')
    if kind in ('pending','ambiguous','failed','completed'):attempts[e['attempt_id']].update(e,status=kind)
totals={k:usage[k]['total'] for k in ('configurations','research','lean')};pending=attempts['bfd00f2611fd4496b9498d4597618a8e']
check('12_authoritative_events_replay_to6_9_1',len(events)==12 and list(totals.values())==[6,9,1] and totals==dev['budget_used']==preflight['budget_used'])
check('existing_pending_attempt_identity_unchanged',pending['status']=='pending' and pending['external_id']=='39cafa1e9b11f91b27e396b66d033a6d')
flags=doc('config/development.json')['execution'];check('all_four_production_execution_flags_false',all(flags[k] is False for k in ('market_research_enabled','llm_runtime_enabled','final_test_enabled','live_trading_enabled')))
check('all_data_certifications_and_final_evaluation_remain_false',all(dev[k] is False for k in ('native_failed_Research_receipt_certified','historical_US200_certified','financial_vintages_certified','actual_historical_availability_certified','final_test_enabled','financial_evidence')))
report={'fixed_candidate':SHA,'baseline':BASE,'scope':'Source/evidence identity and read-only preview preparation; no platform or financial acceptance',
    'actually_executed':'Read-only raw hashes, AST/JSON, independent event replay and pure identity function',
    'check_count':len(checks),'passed_checks':sum(c['passed'] for c in checks),'failed_checks':sum(not c['passed'] for c in checks),'unit_test_methods_executed':0,'new_QC_or_market_model_calls':0,
    'source':{'files':len(files),'all_raw_bytes_match_Git':not bad,'review_files':len(manifest),'review_hash':review_hash,'old_review_hash':old_review_hash,'execution_hash':execution_hash},
    'deployment':{'Python_files':len(deploy),'local_deployment_hash':sha(canon(deploy)),'implementation_hash':generated['IMPLEMENTATION_SHA256'],'active_configuration_hash':generated['SOURCE_SHA256'],'new_identity_does_not_prove_deployment':True},
    'complete_diff':diff,'production_diff':prod,'old_evidence_files_unchanged':len(old_evidence),'developer_original_output_rows':raw_entries,
    'developer_failure_boundary':'Initial4 worker-method error exists as reported tool-transcript summary only, not an original saved raw subprocess file; later saved boundary/423/preview files remain developer evidence.',
    'preview':{'archived_plan_hash':preview['plan_hash'],'source_and_deployment_hashes_match_current':True,'registration_admission_and_dispatch':False,'independent_replay':'See build_preview_verification.json'},
    'preflight_boundary':'Developer-recorded read-only project/main/input checks are not independently retrieved here; two normalized files do not certify full cloud source, runtime, terminal or licensed data. No QC tool called in this subtask.',
    'protected_metadata':{'paths':len(protected),'changed':protected_bad},'budget':{'events':len(events),'usage':usage,'limits':events[0]['limits'],'pending_attempt':{k:pending[k] for k in ('attempt_id','stage','status','external_id')}},
    'checks':checks,'financial_evidence':False}
p=OUT/'evidence_verification.json';p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');(OUT/'evidence_verification.json.sha256').write_text(sha(p.read_bytes())+'  evidence_verification.json\n',encoding='utf-8')
print(json.dumps({k:report[k] for k in ('fixed_candidate','check_count','passed_checks','failed_checks','unit_test_methods_executed','source','deployment','budget')},ensure_ascii=False,indent=2))
for c in checks:
    if not c['passed']:print('FAILED',c)
raise SystemExit(0 if all(c['passed'] for c in checks) else 1)
