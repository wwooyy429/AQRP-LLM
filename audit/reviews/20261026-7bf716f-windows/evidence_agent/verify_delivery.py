"""Read-only metadata evidence verification for fixed WR-09/WR-10 repair.

No unit methods, SDK execution, market/platform request or candidate write.
"""
from pathlib import Path
import ast, copy, hashlib, io, json, subprocess, tarfile

ROOT=Path(__file__).resolve().parents[1]
OUT=Path(__file__).resolve().parent
GIT=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\repo')
OLD=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-fbe2454-20261026')
DURABLE=Path(r'B:\BaiduSyncdisk\学习\投资\量化\量化交易比赛\LLM审核\review-fbe2454-20261026')
SHA='7bf716f45fd6183951a492f0201012af717070f0'
BASE='fbe2454e6ea10aa59211c01f236c54bb251527be'
D0='d0b9c98ae9490b977d62f3e9742d854146d298b4'
RUNTIME='1f7c0c0ab4640a825fd317684f854158ad5d2193'
checks=[]
def canon(v):return json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def norm(b):return b.decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n').encode()
def check(name,result,details=None):checks.append({'check':name,'passed':bool(result),'details':details})
def gitfiles(rev):
    raw=subprocess.check_output(['git','-C',str(GIT),'archive',rev])
    with tarfile.open(fileobj=io.BytesIO(raw)) as tf:return {m.name:tf.extractfile(m).read() for m in tf.getmembers() if m.isfile()}
files=gitfiles(SHA);base=gitfiles(BASE);runtime=gitfiles(RUNTIME);d0=gitfiles(D0)
def doc(p):return json.loads(files[p])
def source_map(mapping):
    result={}
    for p,b in mapping.items():
        parts=Path(p).parts
        if ((parts[0] in ('cloud','config','templates','tests','tools','docs','.github') and Path(p).suffix in ('.py','.json','.md','.yml','.yaml') and '__pycache__' not in parts)
            or p in ('requirements-test.txt','.gitattributes','.gitignore','AGENTS.md')):result[p]=sha(norm(b))
    return result
def deployment_map(mapping):return {p[len('cloud/'):]:sha(norm(b)) for p,b in mapping.items() if p.startswith('cloud/') and p.endswith('.py')}
disk={p.relative_to(ROOT/'source').as_posix():p.read_bytes() for p in (ROOT/'source').rglob('*') if p.is_file()}
disk_changed=[p for p in set(files)|set(disk) if disk.get(p)!=files.get(p)]
check('451_git_files_in_read_only_source',len(files)==451 and set(files)==set(disk))
check('all_source_bytes_equal_fixed_Git_archive',not disk_changed,disk_changed)
manifest=source_map(files);mh=sha(canon(manifest));base_manifest=source_map(base);base_mh=sha(canon(base_manifest));d0_mh=sha(canon(source_map(d0)))
verification=doc('audit/stage_verification.json');developer=doc('audit/review_packages/wr09_wr10/developer_verification.json')
check('independent_manifest_matches_stage_verification_map',manifest==verification['source_files'])
check('independent_manifest_matches_declared_hashes',mh==verification['source_hash']==developer['candidate_source_manifest_hash'],mh)
check('97_source_files',len(manifest)==97==developer['candidate_source_files'])
check('developer_336_method_output_recorded_only_as_developer_evidence','Ran 336 tests' in verification['test_output'] and verification['external_review_status']=='pending_GPT_Work' and developer['real_SDK_executed'] is False and developer['financial_evidence'] is False)
all_diff=[{'path':p,'kind':'added' if p not in base else 'removed' if p not in files else 'modified','baseline_raw_sha256':sha(base[p]) if p in base else None,'candidate_raw_sha256':sha(files[p]) if p in files else None}
    for p in sorted(set(files)|set(base)) if files.get(p)!=base.get(p)]
prod_diff=[d for d in all_diff if d['path'].startswith(('cloud/','config/','tools/','templates/'))]
expected={'cloud/qresearch/collection.py','cloud/qresearch/historical_source.py','cloud/research_config.py'}
check('complete_production_diff_exact_three_paths',{d['path'] for d in prod_diff}==expected,prod_diff)
check('all_other_existing_production_bytes_unchanged',all(files.get(p)==base[p] for p in base if p.startswith(('cloud/','config/','tools/','templates/')) and p not in expected))
check('source_catalog_and_inactive_template_unchanged',files['config/source_catalog.json']==base['config/source_catalog.json'] and files['templates/historical_collection.json']==base['templates/historical_collection.json'])
check('previous_d0_evaluation_and_budget_code_unchanged',all(files[p]==d0[p] for p in ('cloud/qresearch/evaluation.py','cloud/qresearch/registry.py','cloud/qresearch/engineering_tasks.py','cloud/qresearch/contracts.py','cloud/qresearch/runtime.py','tools/research.py','tools/stages.py')))
def assignments(code):return {n.targets[0].id:ast.literal_eval(n.value) for n in ast.parse(code).body if isinstance(n,ast.Assign)}
assigns,base_assigns=assignments(files['cloud/research_config.py']),assignments(base['cloud/research_config.py'])
check('generated_active_configuration_unchanged',assigns['CONFIGURATION']==base_assigns['CONFIGURATION'] and assigns['SOURCE_SHA256']==base_assigns['SOURCE_SHA256'])
check('generated_config_diff_only_implementation_digest',{k for k in assigns if assigns[k]!=base_assigns[k]}=={'IMPLEMENTATION_SHA256'})
implementation={Path(p).name:sha(norm(b)) for p,b in files.items() if p.startswith('cloud/qresearch/') and p.endswith('.py')}
check('implementation_digest_recomputed',assigns['IMPLEMENTATION_SHA256']==sha(canon(implementation))==developer['implementation_hash'])
deploy=doc('audit/deployment.json');depfiles=deployment_map(files)
check('deployment_file_map_recomputed',depfiles==deploy['source_files'])
check('deployment_27_python_files',len(depfiles)==27==developer['deployment_python_files'])
check('deployment_implementation_configuration_and_source_hashes',deploy['implementation_hash']==assigns['IMPLEMENTATION_SHA256'] and deploy['configuration_hash']==assigns['SOURCE_SHA256']==developer['configuration_hash_unchanged'] and sha(norm(files['cloud/qresearch/historical_source.py']))==developer['historical_source_normalized_sha256'])

def class_functions(code,classname):
    cls=next(n for n in ast.parse(code).body if isinstance(n,ast.ClassDef) and n.name==classname)
    return {n.name:ast.dump(n,include_attributes=False) for n in cls.body if isinstance(n,ast.FunctionDef)}
old_col,new_col=class_functions(base['cloud/qresearch/collection.py'],'HistoricalSnapshotCollector'),class_functions(files['cloud/qresearch/collection.py'],'HistoricalSnapshotCollector')
check('collector_all_methods_except_row_AST_unchanged',set(old_col)==set(new_col) and all(old_col[k]==new_col[k] for k in old_col if k!='_row'))
new_row=new_col['_row'];row_code=files['cloud/qresearch/collection.py'].decode('utf-8-sig')
check('legacy_min_date_rejected_by_shared_read_write_row_validation','parsed == date.min' in row_code and 'self._row(raw, start, end)' in row_code and 'Stored source rows violate the frozen projection' in row_code)
check('cache_identity_still_binds_plan_catalog_and_source_manifest','"source_manifest_hash"' in row_code and 'identity = {"plan": value, "field_catalog":' in row_code and '"plan_hash": self.plan.hash' in row_code)
check('legacy_read_validation_does_not_rewrite_or_refetch',all(old_col[k]==new_col[k] for k in ('_document','_load_window','read_window','_collect_window','collect')))
history=files['cloud/qresearch/historical_source.py'].decode('utf-8-sig')
check('history_dates_resolve_value_then_exact_min_sentinel','return None if result == date.min else result.isoformat()' in history and 'return None if result == date.min else value' in history and 'has_value' not in history.lower())
check('history_endpoint_absolute_UTC_microsecond_mapping','value.tz_convert("UTC") - pd.Timedelta(microseconds=1)' in history and '_history_endpoint(start), _history_endpoint(end)' in history and 'arbitrary custom 100ns' in history)

archive='audit/reviews/20261026-fbe2454-windows/';am=doc(archive+'archive_manifest.json');originals=[]
for entry in am['files']:
    name=entry['archive_path'];data=files[archive+name]
    sources=[OLD/entry['origin_relative_path'],DURABLE/entry['origin_relative_path']]
    matches=[str(p) for p in sources if p.is_file() and p.read_bytes()==data]
    check('archived_fbe_original_'+name,sha(data)==entry['raw_sha256'] and len(data)==entry['bytes'] and bool(matches))
    originals.append({'name':name,'sha256':sha(data),'bytes':len(data),'exact_matching_original_paths':matches})
check('archive_exact_129_entries',len(am['files'])==129==am['file_count'] and sum(x['bytes'] for x in originals)==am['total_original_bytes'])
check('developer_archive_manifest_identity',sha(files[archive+'archive_manifest.json'])==developer['original_archive_manifest_raw_sha256'])
official=doc(archive+'source_agent/official_sdk_static_manifest.json');sdk=[]
for item in official['files']:
    p=archive+'source_agent/'+item['saved_file'];data=files[p]
    check('official_fixed_SDK_'+item['saved_file'],sha(data)==item['sha256'] and len(data.splitlines())==item['lines'] and ('/'+official['sha']+'/') in item['url'])
    sdk.append({'archive_path':p,'sha256':sha(data),'upstream_url':item['url'],'source_kind':'19-file original static SDK capture'})
factory=doc(archive+'upstream_factory_extension.json');factory_data=files[archive+factory['saved_file']]
check('official_fixed_HistoryRequestFactory_20th_file',sha(factory_data)==factory['sha256'] and ('/'+official['sha']+'/') in factory['url'])
sdk.append({'archive_path':archive+factory['saved_file'],'sha256':sha(factory_data),'upstream_url':factory['url'],'source_kind':'Additional original static factory hop'})
check('official_fixed_SDK_20_distinct_files',len(sdk)==20==am['official_static_contract_files_verified']==developer['official_static_contract_files'] and len({d['archive_path'] for d in sdk})==20)
check('official_static_commit_is_historical_frozen_LEAN',official['repository']=='QuantConnect/Lean' and official['sha']=='f3d841e60dfd010ee5fc293ea893e56952484108' and official['public_static_source_only'] is True)
formal=doc(archive+'formal_report.json')
check('original_fbe_formal_failure_bound_to_original_source',formal['reviewed_source_commit']==BASE and formal['source_manifest_hash']==base_mh and formal['software_acceptance']['overall']=='failed' and formal['software_acceptance']['blocking_findings']==['WR-09','WR-10'])
first_source=doc(archive+'source_agent/source_review_results_first.json');first_secondary=doc(archive+'source_agent/secondary_source_results_first.json');counted=doc(archive+'source_agent/secondary_source_results_counted.json')
check('original_WR09_failure_not_overwritten',first_source['methods']==8 and first_source['passed_methods']==7 and first_source['failure_records']==2)
check('original_secondary_harness_error_preserved',first_secondary['error_records']==1 and first_secondary['failed_or_error_methods']==2)
check('final_corrected_method_counts_preserve_two_failing_methods',counted['methods']==3 and counted['passed_methods']==1 and counted['failed_or_error_methods']==2 and counted['error_records']==0 and counted['failure_records']==4)
collection_first=doc(archive+'collection_agent/first_results.json');collection_final=doc(archive+'collection_agent/verification_results.json')
check('first_and_fixed_collection_harness_pass_records_separate',collection_first['methods']==collection_final['methods']==19 and collection_first['passed_methods']==collection_final['passed_methods']==19)
check('reviewer_harness_and_count_correction_diffs_retained',all(files[archive+p] for p in ('source_agent/secondary_harness_correction.diff','source_agent/secondary_counting_correction.diff')))
older=[p for p in base if p.startswith(('audit/reviews/','audit/review_packages/'))]
older_changed=[p for p in older if files.get(p)!=base[p]]
check('all_older_pass_and_failure_evidence_bytes_unchanged',not older_changed,{'files':len(older),'changed':older_changed})
replays=doc('audit/review_packages/wr09_wr10/developer_archive_replays.json')
check('developer_replays_explicit_role_and_actual_manifest',replays['is_new_GPT_Work_acceptance'] is False and replays['actual_current_source_manifest_hash']==mh and replays['real_SDK_executed'] is False and replays['counts_are_overlapping_not_unique'] is True)
check('historical_script_literals_explicit_not_actual_identity',replays['reviewed_source_literal_in_original_scripts']==BASE and 'source_commit' in files['docs/review/wr09-wr10.md'].decode('utf-8-sig'))
check('developer_replay_scripts_exist_as_original_unchanged_bytes',all(archive+r['script'] in files for r in replays['runs']))
public=doc('audit/review_packages/wr09_wr10/original_public_reproductions.json')
check('developer_old_public_failures_preserved_as_negative_control',public['source_commit']==BASE and len(public['runs'])==2 and all(r['exit_code']==1 for r in public['runs']))
check('developer_marks_findings_pending_independent_verification',developer['known_open_findings_pending_independent_verification']==['WR-09','WR-10'] and developer['candidate_deployed'] is False and developer['real_SDK_executed'] is False)

protected=[p for p in runtime if p.startswith(('config/','templates/','audit/runtime/','audit/task_inputs/','audit/tool_observations/'))
    or p in ('audit/data_exposure.json','audit/engineering_current.json','audit/stage2_cloud_deployment.json','audit/stage2_real_execution.json','docs/research_charter.md','AGENTS.md')]
pdiff=[p for p in protected if files.get(p)!=runtime[p]]
check('37_prior_protected_runtime_files_unchanged',len(protected)==37 and not pdiff,{'count':len(protected),'changed':pdiff})
raw=files['audit/runtime/registry/events.jsonl'];check('journal_complete_tail',raw.endswith(b'\n'))
events=[];prior=None
for i,line in enumerate(raw.splitlines(),1):
    env=json.loads(line);body={k:v for k,v in env.items() if k!='hash'}
    check('event_'+str(i)+'_chain',env['sequence']==i and env['previous_hash']==prior and sha(canon(body))==env['hash'])
    events.append(env['event']);prior=env['hash']
check('journal_has_12_events',len(events)==12)
usage=json.loads(json.dumps(events[0]['initial_usage']));attempts={};configs=set()
for event in events[1:]:
    kind=event['kind']
    if kind in ('config_imported','config_registered'):
        cid=event['config_id'];payload=files['audit/runtime/configurations/'+cid+'.json']
        check('configuration_'+cid+'_identity',sha(payload)==cid and canon(json.loads(payload))==payload)
        check('configuration_'+cid+'_single_registration',cid not in configs);configs.add(cid)
    if kind in ('config_registered','attempt_started'):
        stage='configurations' if kind=='config_registered' else event['stage'];usage[stage]['total']+=1;usage[stage][event['allocation']]+=1
    if kind=='attempt_started':attempts[event['attempt_id']]=dict(event,status='started')
    if kind in ('pending','ambiguous','failed','completed'):
        attempt=attempts[event['attempt_id']];attempt.update(event,status=kind)
        if kind=='completed':check('completed_result_'+event['attempt_id'],sha(files['audit/runtime/'+attempt['result_key']])==event['result_sha256'])
limits=events[0]['limits'];totals={s:usage[s]['total'] for s in ('configurations','research','lean')}
check('all_global_limits_respected',all(usage[s][p]<=limits[s][p] for s in usage for p in usage[s]))
budget=doc('config/budget.json')['usage']
check('usage_projection_matches_registry',list(totals.values())==[budget['configuration_budget_charges'],budget['research_execution_attempts'],budget['lean_submission_attempts']])
check('no_new_charge_totals_still_6_9_1',list(totals.values())==[6,9,1])
pending=attempts['bfd00f2611fd4496b9498d4597618a8e']
check('same_archived_pending_lean',pending['status']=='pending' and pending['external_id']=='39cafa1e9b11f91b27e396b66d033a6d')
ex=doc('config/development.json')['execution']
check('all_execution_flags_false',all(ex[p] is False for p in ('market_research_enabled','llm_runtime_enabled','final_test_enabled','live_trading_enabled')))
ready=doc('audit/stage2_current_readiness.json');tracking=doc('audit/review_tracking.json')
check('readiness_and_tracking_keep_original_d0_scope',ready['accepted_offline_source_commit']==D0 and ready['accepted_source_manifest_hash']==d0_mh and tracking['prior_stage0_stage1_acceptance_source']['commit']==D0 and tracking['prior_stage0_stage1_acceptance_source']['source_manifest_hash']==d0_mh)
check('new_repair_not_accepted_in_metadata',ready['new_candidate_independently_accepted'] is False and ready['candidate_cloud_deployed'] is False and ready['known_open_findings']==['WR-09','WR-10'] and tracking['known_open_findings']==['WR-09','WR-10'])
check('latest_metadata_preserves_original_fbe_failed_review',tracking['reviewed_source_commit']==BASE and tracking['source_manifest_hash']==base_mh and 'failed' in tracking['software_acceptance'] and tracking['whole_system_acceptance']=='not_accepted')
check('readiness_and_developer_usage_matches_registry',ready['global_usage']==totals and developer['budget']['used']==totals and ready['active_research_configuration_changed'] is False and ready['authoritative_budget_changed'] is False)
check('readiness_preserves_pending_identity',ready['pending_backtest_id']==pending['external_id'] and ready['terminal_received'] is False and ready['pending_source_or_task_input_changed'] is False)
check('actual_collection_admission_and_certification_still_missing','remote_collection_task_protocol_and_atomic_budget_admission' in ready['unimplemented_collection_scope'] and 'actual_vendor_receipt_and_vintage_certification' in ready['unimplemented_collection_scope'])

report={'candidate_source_commit':SHA,'previous_independently_reviewed_commit':BASE,
    'actually_executed':'Read-only raw Git/previous artifact byte hashes, AST and journal/metadata parsing',
    'unit_test_methods_executed_by_this_script':0,'platform_calls_by_this_script':0,'delivery_ZIP_supplied':False,
    'check_count':len(checks),'passed_checks':sum(c['passed'] for c in checks),'failed_checks':sum(not c['passed'] for c in checks),
    'Git':{'tracked_source_files':len(files),'exact_disk_byte_match':not disk_changed,'entire_raw_file_hash_map_sha256':sha(canon({p:sha(b) for p,b in files.items()}))},
    'source_manifest':{'count':len(manifest),'hash':mh,'previous_fbe_count':len(base_manifest),'previous_fbe_hash':base_mh,'original_d0_acceptance_hash':d0_mh},
    'complete_fbe_to_candidate_diff':all_diff,'complete_production_diff':prod_diff,
    'old_fbe_original_files':originals,'official_static_contracts':{'files':sdk,'count':len(sdk),'upstream_commit':official['sha'],'new_downloads_this_subtask':0,'real_SDK_executed':False},
    'older_evidence_file_count':len(older),'protected_prior_runtime_files':{'count':len(protected),'changed':pdiff},
    'new_cache_behavior_identity':{'projected_exact_min_date_sentinel_becomes_null':True,'stored_exact_min_date_sentinel_is_rejected':True,'row_validation_shared_by_write_and_read':True,'existing_cache_helpers_AST_unchanged':True,'cache_identity_unchanged_and_binds_frozen_plan_with_source_manifest_and_selected_catalog':True,'old_bytes_not_migrated_or_overwritten':True,
        'interpretation':'Repair changes source projection and validity checks, not stored historical facts. A legacy sentinel row is now invalid; refusal does not certify actual data coverage or receipt/vintage and does not authorize automatic source refetch.'},
    'budget_replay':{'events':len(events),'usage':usage,'limits':limits,'pending_lean':{k:pending.get(k) for k in ('attempt_id','stage','status','external_id')},'initial_usage_is_historical_aggregate':True},
    'deployment':{'local_candidate_hash':sha(canon(depfiles)),'local_files':len(depfiles),'configuration_hash':assigns['SOURCE_SHA256'],'implementation_hash':assigns['IMPLEMENTATION_SHA256'],'previous_fbe_hash':sha(canon(deployment_map(base))),'historical_runtime_source':json.loads(runtime['audit/stage2_cloud_deployment.json'])['source_commit'],'historical_runtime_hash':json.loads(runtime['audit/stage2_cloud_deployment.json'])['deployment_hash']},
    'acceptance_boundary':'d0 tested stage0/1 scope retained; prior fbe WR09/WR10 failures retained; candidate repair awaiting independent review. Developer replay literals are historical, outer metadata claims must not be mistaken for this subtask execution.',
    'unverified':['No unit-suite rerun by this evidence script; developer 336/replays remain developer records','No SDK, source collection, deployment, platform compile/run or pending LEAN terminal/log read','No full historical universe, financial vintage/delivery or independent financial test'],
    'checks':checks,'financial_evidence':False}
path=OUT/'delivery_evidence_report.json';path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(OUT/'delivery_evidence_report.sha256').write_text(sha(path.read_bytes())+'  delivery_evidence_report.json\n',encoding='utf-8')
print(json.dumps({k:report[k] for k in ('candidate_source_commit','check_count','passed_checks','failed_checks','Git','source_manifest','complete_production_diff','budget_replay','deployment')},ensure_ascii=False,indent=2))
for c in checks:
    if not c['passed']:print('FAILED',c)
raise SystemExit(0 if all(c['passed'] for c in checks) else 1)
