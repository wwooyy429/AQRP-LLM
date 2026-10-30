"""Independent read-only collection-bridge evidence and identity checks.

No unittest methods, platform/SDK/market calls, ledger changes or candidate writes.
Execution identity probes run the exact extracted function with in-memory readers.
"""
from pathlib import Path
import ast, copy, hashlib, io, json, subprocess, tarfile, zipfile

ROOT=Path(__file__).resolve().parents[1]
OUT=Path(__file__).resolve().parent
GIT=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\repo')
OLD=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-dc49f0f-20261027')
DURABLE=Path(r'B:\BaiduSyncdisk\学习\投资\量化\量化交易比赛\LLM审核\review-dc49f0f-20261027')
SHA='4a94430144cd3d9e4b5469bd2b6e4a48d80d5fc7'
BASE='dc49f0f3037918f3ce4413665c59b164a8d6e2b7'
RUNTIME='1f7c0c0ab4640a825fd317684f854158ad5d2193'
checks=[]
def canon(v):return json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def norm(b):return b.decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n').encode()
def check(name,result,details=None):checks.append({'check':name,'passed':bool(result),'details':details})
def gitfiles(rev):
    raw=subprocess.check_output(['git','-C',str(GIT),'archive',rev])
    with tarfile.open(fileobj=io.BytesIO(raw)) as tf:return {m.name:tf.extractfile(m).read() for m in tf.getmembers() if m.isfile()}
files=gitfiles(SHA);base=gitfiles(BASE);runtime=gitfiles(RUNTIME)
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
check('1331_git_files_in_read_only_source',len(files)==1331 and set(files)==set(disk))
check('all_source_bytes_equal_fixed_Git_archive',not disk_changed,disk_changed)
manifest=source_map(files);mh=sha(canon(manifest));base_manifest=source_map(base);base_mh=sha(canon(base_manifest))
verification=doc('audit/stage_verification.json');developer=doc('audit/review_packages/wr14/developer_verification.json')
check('independent_full_review_manifest_map',manifest==verification['source_files'])
check('independent_full_review_manifest_hash',mh==verification['source_hash']==developer['candidate_source_manifest_hash'],mh)
check('112_review_source_files',len(manifest)==112==developer['candidate_source_files'])
check('developer_407_method_output_has_developer_role','Ran 407 tests' in verification['test_output'] and verification['external_review_status']=='pending_GPT_Work' and developer['new_candidate_independently_accepted'] is False and developer['financial_evidence'] is False)
all_diff=[{'path':p,'kind':'added' if p not in base else 'removed' if p not in files else 'modified','baseline_raw_sha256':sha(base[p]) if p in base else None,'candidate_raw_sha256':sha(files[p]) if p in files else None}
    for p in sorted(set(files)|set(base)) if files.get(p)!=base.get(p)]
prod_diff=[d for d in all_diff if d['path'].startswith(('cloud/','config/','tools/','templates/'))]
expected={'cloud/qresearch/engineering_receipts.py','cloud/research_config.py'}
check('complete_production_diff_exact_two_paths',{d['path'] for d in prod_diff}==expected,prod_diff)
check('other_existing_production_bytes_unchanged',all(files.get(p)==base[p] for p in base if p.startswith(('cloud/','config/','tools/','templates/')) and p not in expected))
check('WR12_CLI_source_unchanged_this_repair',files['tools/collection_task_cli.py']==base['tools/collection_task_cli.py'] and files['tools/stage2_collection.py']==base['tools/stage2_collection.py'])
check('Registry_code_unchanged_this_repair',files['cloud/qresearch/registry.py']==base['cloud/qresearch/registry.py'])
check('all_config_documents_unchanged',all(files.get(p)==base[p] for p in base if p.startswith('config/')))
check('WR09_WR10_source_and_collection_fixes_unchanged',files['cloud/qresearch/collection.py']==base['cloud/qresearch/collection.py'] and files['cloud/qresearch/historical_source.py']==base['cloud/qresearch/historical_source.py'])
def assignments(code):return {n.targets[0].id:ast.literal_eval(n.value) for n in ast.parse(code).body if isinstance(n,ast.Assign)}
assigns,base_assigns=assignments(files['cloud/research_config.py']),assignments(base['cloud/research_config.py'])
check('generated_active_configuration_unchanged',assigns['CONFIGURATION']==base_assigns['CONFIGURATION'] and assigns['SOURCE_SHA256']==base_assigns['SOURCE_SHA256'])
check('generated_config_diff_only_implementation_digest',{k for k in assigns if assigns[k]!=base_assigns[k]}=={'IMPLEMENTATION_SHA256'})
implementation={Path(p).name:sha(norm(b)) for p,b in files.items() if p.startswith('cloud/qresearch/') and p.endswith('.py')}
check('generated_implementation_digest',assigns['IMPLEMENTATION_SHA256']==sha(canon(implementation))==developer['implementation_hash'])
deploy=doc('audit/deployment.json');depfiles=deployment_map(files)
check('deployment_file_map_recomputed',depfiles==deploy['source_files'])
check('deployment_29_python_files',len(depfiles)==29==developer['deployment_python_files'])
check('deployment_configuration_and_implementation_hashes',deploy['implementation_hash']==assigns['IMPLEMENTATION_SHA256'] and deploy['configuration_hash']==assigns['SOURCE_SHA256']==developer['configuration_hash_unchanged'])

# Run only the exact pure identity function. File reads and source scanning are
# replaced by independent deterministic dictionaries. No production module import.
cli_tree=ast.parse(files['tools/collection_task_cli.py'])
identity_fn=next(n for n in cli_tree.body if isinstance(n,ast.FunctionDef) and n.name=='execution_source_manifest')
identity_module=ast.fix_missing_locations(ast.Module(body=[identity_fn],type_ignores=[]))
def execution_identity(source_files,budget):
    space={'hashlib':hashlib,'canonical_json':canon,'content_hash':lambda x:sha(canon(x)),
           'ROOT':Path('IN_MEMORY_ONLY'),'source_manifest':lambda:{'source_files':copy.deepcopy(source_files)},
           'read_json':lambda _:copy.deepcopy(budget)}
    exec(compile(identity_module,'candidate:tools/collection_task_cli.py:execution_source_manifest','exec'),space)
    return space['execution_source_manifest']()
budget=doc('config/budget.json');policy=copy.deepcopy(budget);policy.pop('usage')
exec_expected_map=dict(manifest);exec_expected_map['config/budget.json']=sha(canon(policy))
exec_expected_hash=sha(canon({'schema':'collection_execution_sources_v1','source_files':exec_expected_map}))
actual=execution_identity(manifest,budget)
check('execution_identity_exact_full_file_map_except_budget_usage',actual['source_files']==exec_expected_map)
check('execution_identity_domain_and_hash',actual['source_hash']==exec_expected_hash,exec_expected_hash)
base_identity_fn=next(n for n in ast.parse(base['tools/collection_task_cli.py']).body if isinstance(n,ast.FunctionDef) and n.name=='execution_source_manifest')
check('execution_identity_policy_function_AST_unchanged',ast.dump(identity_fn,include_attributes=False)==ast.dump(base_identity_fn,include_attributes=False))
check('execution_and_full_review_identity_separate',actual['source_hash']!=mh and manifest['config/budget.json']!=actual['source_files']['config/budget.json'])
exec_paths=[p for p in files if p.startswith(('cloud/','config/','tools/','templates/'))]
omitted=[p for p in exec_paths if p not in manifest]
check('all_current_execution_code_config_template_files_included',not omitted,{'count':len(exec_paths),'omitted':omitted})
source_sensitivity=[]
for p in manifest:
    if p=='config/budget.json':continue
    mutated=dict(manifest);mutated[p]=sha((manifest[p]+'independent_change').encode())
    changed=execution_identity(mutated,budget)['source_hash']!=exec_expected_hash
    check('execution_identity_source_sensitivity_'+p,changed)
    source_sensitivity.append({'path':p,'changed':changed})
usage_cases=[{'case':'all_usage_counters_incremented','usage':{k:(v+1 if isinstance(v,int) else v) for k,v in budget['usage'].items()}},
    {'case':'usage_projection_removed','remove':True},{'case':'usage_projection_replaced','usage':{'arbitrary_new_counter':999}}]
usage_probes=[]
for case in usage_cases:
    value=copy.deepcopy(budget)
    if case.get('remove'):value.pop('usage')
    else:value['usage']=case['usage']
    full_map=dict(manifest);full_map['config/budget.json']=sha(canon(value))
    outcome=execution_identity(full_map,value)
    unchanged=outcome['source_hash']==exec_expected_hash
    full_changes=sha(canon(full_map))!=mh
    check('usage_only_'+case['case']+'_keeps_execution_identity_and_changes_full_review',unchanged and full_changes)
    usage_probes.append({'case':case['case'],'execution_hash_unchanged':unchanged,'full_review_hash_changes':full_changes})
def leaves(value,path=()):
    if isinstance(value,dict):
        for k,v in value.items():yield from leaves(v,path+(k,))
    elif isinstance(value,list):
        for k,v in enumerate(value):yield from leaves(v,path+(k,))
    else:yield path,value
policy_probes=[]
for path,value in leaves(policy):
    mutated=copy.deepcopy(budget);target=mutated
    for key in path[:-1]:target=target[key]
    target[path[-1]]=not value if isinstance(value,bool) else value+1 if isinstance(value,(int,float)) else str(value)+'__changed__'
    full_map=dict(manifest);full_map['config/budget.json']=sha(canon(mutated))
    changed=execution_identity(full_map,mutated)['source_hash']!=exec_expected_hash
    check('budget_policy_leaf_'+'.'.join(map(str,path))+'_changes_identity',changed)
    policy_probes.append({'path':list(path),'execution_hash_changes':changed})
for key in policy:
    mutated=copy.deepcopy(budget);mutated.pop(key)
    changed=execution_identity(manifest,mutated)['source_hash']!=exec_expected_hash
    check('budget_policy_top_level_delete_'+key+'_changes_identity',changed)
    policy_probes.append({'deleted_top_level_key':key,'execution_hash_changes':changed})
extra=copy.deepcopy(budget);extra['new_budget_policy']={'guard':'independent'}
check('new_unknown_budget_policy_is_also_bound',execution_identity(manifest,extra)['source_hash']!=exec_expected_hash)
probe_result={'probe_type':'Exact extracted pure candidate function executed with in-memory readers; no unittest methods or source writes',
    'execution_source_hash':exec_expected_hash,'full_review_source_hash':mh,'file_count':len(actual['source_files']),
    'source_hash_sensitivity_cases':source_sensitivity,'usage_only_cases':usage_probes,'policy_mutation_cases':policy_probes,
    'new_unknown_budget_policy_also_bound':True,'independent_function_AST_sha256':sha(ast.dump(identity_fn,include_attributes=False).encode()),
    'no_ledger_or_config_modified':True}
probe_path=OUT/'execution_identity_probes.json';probe_path.write_text(json.dumps(probe_result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

archive='audit/reviews/20261027-dc49f0f-windows/';am=doc(archive+'archive_manifest.json');originals=[]
for entry in am['files']:
    name=entry['archive_path'];data=files[archive+name]
    sources=[OLD/entry['origin_relative_path'],DURABLE/entry['origin_relative_path']]
    matches=[str(p) for p in sources if p.is_file() and p.read_bytes()==data]
    check('archived_dc_original_'+name,sha(data)==entry['raw_sha256'] and len(data)==entry['bytes'] and bool(matches))
    originals.append({'name':name,'sha256':sha(data),'bytes':len(data),'exact_matching_original_paths':matches})
check('archive_exact_188_entries',len(am['files'])==188==am['file_count'] and sum(x['bytes'] for x in originals)==am['total_original_bytes'])
reused=[]
for item in am['reused_existing_evidence']:
    data=files[item['existing_archive_path']];origin=DURABLE/item['origin_relative_path']
    equal=origin.is_file() and origin.read_bytes()==data
    check('reused_dc_original_'+item['origin_relative_path'],equal and sha(data)==item['raw_sha256'] and len(data)==item['bytes'])
    reused.append({'path':item['existing_archive_path'],'origin':str(origin),'sha256':sha(data),'same_original_bytes':equal})
check('8_duplicate_script_references_preserved',len(reused)==8)
artifact_manifest=json.loads((DURABLE/'artifact_manifest.json').read_text(encoding='utf-8-sig'))
all_original_entries=am['files']+am['reused_existing_evidence']
check('196_selected_original_artifact_manifest_hash_bindings',len(all_original_entries)==196==am['selected_original_artifact_manifest_hash_checks'] and all(artifact_manifest[e['origin_relative_path']]==e['raw_sha256'] for e in all_original_entries))
full_original_bad=[];full_original_matches={}
for p,h in artifact_manifest.items():
    candidates=[DURABLE/p,OLD/p]
    matching=[str(x) for x in candidates if x.is_file() and sha(x.read_bytes())==h]
    if not matching:full_original_bad.append(p)
    else:full_original_matches[p]=matching[0]
check('3579_full_original_artifact_hashes_recomputed',len(artifact_manifest)==3579==am['full_original_artifact_manifest_hash_checks'] and not full_original_bad,{'files':len(artifact_manifest),'mismatches':full_original_bad})
receipt_manifest=doc(archive+'receipt_agent/manifest.json')
by_origin={e['origin_relative_path']:e['raw_sha256'] for e in all_original_entries}
check('22_original_receipt_manifest_hash_bindings',len(receipt_manifest)==22==am['receipt_manifest_hash_checks'] and all(by_origin['receipt_agent/'+p]==h for p,h in receipt_manifest.items()))
for sidecar in am['sidecar_sha256_checks']:
    expected=files[archive+sidecar].decode('utf-8-sig').split()[0]
    target=sidecar.removesuffix('.sha256')
    check('archived_sidecar_'+sidecar,sha(files[archive+target])==expected)
formal=doc(archive+'formal_report.json')
check('original_dc_WR14_failure_bound_to_old_version',formal['reviewed_source_commit']==BASE and formal['source_manifest_hash']==base_mh and formal['software_acceptance']['overall']=='failed' and formal['software_acceptance']['blocking_findings']==['WR-14'] and formal['software_acceptance']['whole_system']=='not_accepted')
check('original_WR13_and_prior_pass_scopes_preserved',formal['software_acceptance']['WR13_original_scope']=='passed_after_fix' and formal['software_acceptance']['shared_budget_tested_scope']=='passed' and formal['software_acceptance']['stage0_1_prior_scope']=='retained')
receipt_first=doc(archive+'receipt_agent/first_run_summary.json');receipt_corrected=doc(archive+'receipt_agent/role_corrected_summary.json')
check('Role_first_measurement_failure_and_product_errors_retained',receipt_first['methods']==12 and receipt_first['subcases']==160 and receipt_first['failure_records']==1 and receipt_first['error_records']==2 and receipt_first['success'] is False)
check('Role_corrected_measurement_retains_product_errors',receipt_corrected['methods']==12 and receipt_corrected['subcases']==160 and receipt_corrected['failure_records']==0 and receipt_corrected['error_records']==2 and receipt_corrected['success'] is False and files[archive+'receipt_agent/reviewer_role_correction.diff'])
fraction_current=doc(archive+'receipt_agent/candidate_fractional_clock.json');fraction_old=doc(archive+'receipt_agent/baseline_be94426_fractional_clock.json')
check('original_WR14_14_case_6pass_8wrong_rejection_kept',fraction_current['variants']==14 and fraction_current['actually_completed']==6 and fraction_current['incorrect_rejections']==8 and fraction_current['receipt_source_sha256']==sha(norm(base['cloud/qresearch/engineering_receipts.py'])))
check('original_be944_14_case_positive_control_kept',fraction_old['variants']==14 and fraction_old['actually_completed']==14 and fraction_old['incorrect_rejections']==0)
revision=doc(archive+'report_revision.json');revision_first=doc(archive+'report_revision.initial.json')
check('initial_intermediate_final_report_text_hashes_match_revision_records',sha(files[archive+'formal_report.initial.txt'])==revision_first['initial_report_sha256'] and sha(files[archive+'formal_report.wording_revision_raw.txt'])==revision_first['final_report_sha256'] and sha(files[archive+'formal_report.txt'])==revision['final_report_sha256'])
check('revision_records_limit_changes_to_wording_and_format',revision['conclusions_and_test_inputs_unchanged'] is True and revision_first['conclusions_or_test_inputs_changed'] is False)
prior_zip_records=[]
zip_phases=[('review-dc49f0f-20261027.zip','formal_report.initial.txt'),('review-dc49f0f-20261027-final.zip','formal_report.wording_revision_raw.txt'),('review-dc49f0f-20261027-verified.zip','formal_report.txt')]
for name,report in zip_phases:
    path=DURABLE.parent/name
    with zipfile.ZipFile(path) as z:
        candidates=[p for p in z.namelist() if p==DURABLE.name+'/formal_report.txt']
        equal=len(candidates)==1 and z.read(candidates[0])==files[archive+report]
        good=z.testzip() is None and len(z.namelist())==len(set(z.namelist()))
    check('preserved_prior_ZIP_'+name,equal and good)
    prior_zip_records.append({'path':str(path),'raw_sha256':sha(path.read_bytes()),'formal_report_phase':report,'formal_report_bytes_match':equal,'CRC_and_unique_entries_ok':good})
older=[p for p in base if p.startswith(('audit/reviews/','audit/review_packages/'))]
older_changed=[p for p in older if files.get(p)!=base[p]]
check('all_previous_pass_failure_precision_evidence_bytes_unchanged',not older_changed,{'files':len(older),'changed':older_changed})
precision=doc('audit/reviews/20261026-d0b9c98-windows/numeric_agent/relative_tolerance_results.json')
check('old_pure_relative_precision_failures_still_present',precision['methods']==11 and precision['failed_methods']==2 and precision['failure_records']==4 and precision['exit_code']==1)
official_root='audit/reviews/20261026-fbe2454-windows/';official=doc(official_root+'source_agent/official_sdk_static_manifest.json');sdk=[]
for item in official['files']:
    p=official_root+'source_agent/'+item['saved_file'];data=files[p]
    check('official_fixed_SDK_'+item['saved_file'],sha(data)==item['sha256'] and data==base[p] and len(data.splitlines())==item['lines'])
    sdk.append({'path':p,'raw_sha256':sha(data)})
factory=doc(official_root+'upstream_factory_extension.json');factory_path=official_root+factory['saved_file']
check('official_fixed_HistoryRequestFactory_20th',sha(files[factory_path])==factory['sha256'] and files[factory_path]==base[factory_path])
sdk.append({'path':factory_path,'raw_sha256':sha(files[factory_path])})
check('20_fixed_SDK_contract_originals_preserved',len(sdk)==20 and official['sha']=='f3d841e60dfd010ee5fc293ea893e56952484108')
check('developer_archive_identity_and_pending_status',developer['original_archive_files']==188 and developer['original_archive_manifest_raw_sha256']==sha(files[archive+'archive_manifest.json']) and developer['known_open_findings_pending_independent_verification']==['WR-14'])
devoutputs=doc('audit/review_packages/wr14/developer_outputs_manifest.json')
check('48_developer_raw_output_file_bytes',len(devoutputs['files'])==48==devoutputs['file_count'] and all(sha(files['audit/review_packages/wr14/'+e['archive_path']])==e['raw_sha256'] and len(files['audit/review_packages/wr14/'+e['archive_path']])==e['bytes'] for e in devoutputs['files']))
check('developer_outputs_manifest_raw_identity',sha(files['audit/review_packages/wr14/developer_outputs_manifest.json'])==developer['developer_outputs_manifest_raw_sha256'])
manifest_raw=files['audit/review_packages/wr14/developer_outputs_manifest.json']
manifest_CRLF=norm(manifest_raw).replace(b'\n',b'\r\n')
check('developer_outputs_manifest_declared_digest_identifies_CRLF_equivalent',sha(manifest_CRLF)==developer['developer_outputs_manifest_raw_sha256'])
metadata_hash_discrepancy={'file':'audit/review_packages/wr14/developer_outputs_manifest.json',
    'declared_raw_sha256':developer['developer_outputs_manifest_raw_sha256'],'actual_fixed_Git_raw_sha256':sha(manifest_raw),
    'equivalent_CRLF_sha256':sha(manifest_CRLF),'actual_Git_raw_matches_declaration':sha(manifest_raw)==developer['developer_outputs_manifest_raw_sha256'],
    'all48_listed_output_raw_hashes_match':True,
    'interpretation':'Raw digest declaration corresponds to a CRLF original representation; committed manifest is LF. Exact raw identity is false, while listed output content and all archived independent originals match. This is a metadata representation discrepancy, not a production test result.'}
phases={d['phase']:d for d in devoutputs['phase_execution_identity']}
check('developer_pre_edit_parser_hash_accurate',phases['before']['parser_normalized_sha256']==sha(norm(base['cloud/qresearch/engineering_receipts.py'])))
check('developer_all_post_edit_parser_hashes_accurate',all(phases[p]['parser_normalized_sha256']==sha(norm(files['cloud/qresearch/engineering_receipts.py'])) for p in ('after','after-built','after-ready')))
check('developer_initial_preparation_failures_preserved',phases['after']['exit_codes']=={'minimal':0,'fractional':1,'annotations':1} and phases['after-built']['exit_codes']=={'minimal':0,'fractional':0,'annotations':1} and phases['after-ready']['exit_codes']=={'minimal':0,'fractional':0,'annotations':0})
fixture=devoutputs['supporting_fixture_reused']
check('developer_original_official_schema_fixture_reused_unchanged',sha(files[fixture['archive_path']])==fixture['raw_sha256'] and len(files[fixture['archive_path']])==fixture['bytes'])
protected_dev=doc('audit/review_packages/wr14/protected_files_check.json')
check('966_developer_protected_paths_unchanged_in_Git',len(protected_dev['files'])==966==developer['protected_files_checked'] and all(files.get(p)==base.get(p) for p in protected_dev['files']))
check('developer_baseline_6_methods_4_error_methods_not_124_methods',developer['baseline_new_tests']['methods']==6 and developer['baseline_new_tests']['error_methods']==4 and developer['baseline_new_tests']['error_records']==124)

protected=[p for p in runtime if p.startswith(('config/','templates/','audit/runtime/','audit/task_inputs/','audit/tool_observations/'))
    or p in ('audit/data_exposure.json','audit/engineering_current.json','audit/stage2_cloud_deployment.json','audit/stage2_real_execution.json','docs/research_charter.md','AGENTS.md')]
pdiff=[p for p in protected if files.get(p)!=runtime[p]]
check('37_prior_protected_runtime_files_unchanged',len(protected)==37 and not pdiff,{'count':len(protected),'changed':pdiff})
check('no_real_collection_configuration_or_input_persisted',not any(p.startswith(('audit/collection_current.json','audit/collection_task_inputs/','audit/runtime/collection/')) for p in files))
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
projection=budget['usage']
check('usage_projection_matches_registry',list(totals.values())==[projection['configuration_budget_charges'],projection['research_execution_attempts'],projection['lean_submission_attempts']])
check('no_new_charge_totals_still_6_9_1',list(totals.values())==[6,9,1])
pending=attempts['bfd00f2611fd4496b9498d4597618a8e']
check('same_archived_pending_lean',pending['status']=='pending' and pending['external_id']=='39cafa1e9b11f91b27e396b66d033a6d')
ex=doc('config/development.json')['execution']
check('all_execution_flags_false',all(ex[p] is False for p in ('market_research_enabled','llm_runtime_enabled','final_test_enabled','live_trading_enabled')))
ready=doc('audit/stage2_current_readiness.json');tracking=doc('audit/review_tracking.json')
accepted7bf='7bf716f45fd6183951a492f0201012af717070f0'
accepted7bf_hash='8200262e31fba80d57888474c0980f22a15b8a1bfa59261a334a67ef87c11381'
check('readiness_prior_7bf_acceptance_identity',ready['accepted_offline_source_commit']==accepted7bf and ready['accepted_source_manifest_hash']==accepted7bf_hash and ready['candidate_source_manifest_hash']==mh)
check('repair_not_independently_accepted_or_cloud_deployed',ready['new_candidate_independently_accepted'] is False and ready['candidate_cloud_deployed'] is False and ready['known_open_findings']==['WR-14'])
check('readiness_budget_and_active_configuration_unchanged',ready['global_usage']==totals and developer['budget']['used']==totals and ready['active_research_configuration_changed'] is False and ready['authoritative_budget_changed'] is False)
check('readiness_pending_identity_preserved',ready['pending_backtest_id']==pending['external_id'] and ready['terminal_received'] is False and ready['pending_source_or_task_input_changed'] is False)
check('prior_cloud_comparison_explicitly_prior_dc49',ready['platform_comparison_from_independent_review']['candidate_commit']==BASE and ready['platform_comparison_from_independent_review']['runtime_source_commit']=='75f24629d3b7f94ff3aa906c3ce8a2b8b9a8d3c4' and ready['platform_comparison_from_independent_review']['this_archival_turn_new_QC_read'] is False)
check('real_platform_and_data_certification_still_missing','actual_cloud_dispatch_and_runtime_validation' in ready['unimplemented_collection_scope'] and 'actual_vendor_receipt_and_vintage_certification' in ready['unimplemented_collection_scope'])
check('tracking_keeps_old_failure_and_new_candidate_separate',tracking['reviewed_source_commit']==BASE and tracking['source_manifest_hash']==base_mh and tracking['known_open_findings']==['WR-14'] and tracking['current_candidate']['source_manifest_hash']==mh and tracking['current_candidate']['independently_accepted'] is False and tracking['shared_admission_review_scope']['source_commit']=='be9442603a31481a9a71e51ca794df77650c7411')

report={'candidate_source_commit':SHA,'previous_independently_reviewed_commit':BASE,
    'actually_executed':'Read-only Git/prior artifact hashes, AST, JSON and exact extracted identity function with independent in-memory readers',
    'archive_deduplication_note':'188 selected original files plus8 raw-hash references preserve196 original paths; duplicate source trees, generated cache stores and existing same-byte scripts are intentionally not recopied.',
    'unit_test_methods_executed_by_this_script':0,'platform_calls_by_this_script':0,'delivery_ZIP_supplied':False,
    'check_count':len(checks),'passed_checks':sum(c['passed'] for c in checks),'failed_checks':sum(not c['passed'] for c in checks),
    'Git':{'tracked_source_files':len(files),'exact_disk_byte_match':not disk_changed,'entire_raw_file_hash_map_sha256':sha(canon({p:sha(b) for p,b in files.items()}))},
    'source_manifest':{'count':len(manifest),'hash':mh,'previous_dc_count':len(base_manifest),'previous_dc_hash':base_mh},
    'execution_source_manifest':{'hash':exec_expected_hash,'file_count':len(actual['source_files']),'exact_policy':'Only budget usage removed; all remaining budget fields canonicalized, every other complete source hash retained','executed_identity_function_probe_artifact':'execution_identity_probes.json','source_sensitivity_cases':len(source_sensitivity),'usage_only_cases':len(usage_probes),'policy_leaf_or_delete_cases':len(policy_probes),'additional_new_policy_key_case':1},
    'complete_dc_to_candidate_diff':all_diff,'complete_production_diff':prod_diff,
    'full_previous_artifact_files_verified':len(full_original_matches),'prior_report_ZIPs':prior_zip_records,'old_dc_original_files':originals,'reused_original_files':reused,'older_evidence_file_count':len(older),
    'official_static_contracts':{'files':sdk,'count':len(sdk),'upstream_commit':official['sha'],'new_downloads':0,'real_SDK_executed':False},
    'protected_prior_runtime_files':{'count':len(protected),'changed':pdiff},
    'budget_replay':{'events':len(events),'usage':usage,'limits':limits,'pending_lean':{k:pending.get(k) for k in ('attempt_id','stage','status','external_id')},'initial_usage_is_historical_aggregate':True},
    'deployment':{'local_candidate_hash':sha(canon(depfiles)),'local_files':len(depfiles),'configuration_hash':assigns['SOURCE_SHA256'],'implementation_hash':assigns['IMPLEMENTATION_SHA256'],'previous_dc_hash':sha(canon(deployment_map(base))),'historical_runtime_source':json.loads(runtime['audit/stage2_cloud_deployment.json'])['source_commit'],'historical_runtime_hash':json.loads(runtime['audit/stage2_cloud_deployment.json'])['deployment_hash']},
    'acceptance_boundary':'Prior accepted scopes including dc49 original WR13 bypass fix retained; dc49 WR14 compatibility failure remains the baseline. New fractional-clock repair needs independent review. Local preparation is not cloud execution or actual data certification.',
    'unverified':['No unit-suite or CLI lifecycle rerun by this evidence script; Registry/worker/CLI behavioral tests belong to other review tasks','No SDK, cloud source collection/deployment/compile/run or pending LEAN terminal/log read','No full historical universe, financial vintage/delivery or independent financial test'],
    'metadata_hash_discrepancy':metadata_hash_discrepancy,
    'checks':checks,'financial_evidence':False}
path=OUT/'delivery_evidence_report.json';path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for artifact in ('delivery_evidence_report.json','execution_identity_probes.json'):(OUT/(artifact+'.sha256')).write_text(sha((OUT/artifact).read_bytes())+'  '+artifact+'\n',encoding='utf-8')
print(json.dumps({k:report[k] for k in ('candidate_source_commit','check_count','passed_checks','failed_checks','Git','source_manifest','execution_source_manifest','complete_production_diff','budget_replay','deployment')},ensure_ascii=False,indent=2))
for c in checks:
    if not c['passed']:print('FAILED',c)
raise SystemExit(0 if all(c['passed'] for c in checks) else 1)
