"""Offline WR-08 follow-on collection delivery identity and history verifier.

No unit methods, market/platform requests or candidate-source writes.
"""
from pathlib import Path
import ast, hashlib, io, json, subprocess, tarfile

ROOT=Path(__file__).resolve().parents[1]
OUT=Path(__file__).resolve().parent
GIT=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\repo')
OLD=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-d0b9c98-20261026')
DURABLE=Path(r'B:\BaiduSyncdisk\学习\投资\量化\量化交易比赛\LLM审核\review-d0b9c98-20261026')
SHA='fbe2454e6ea10aa59211c01f236c54bb251527be'
BASE='d0b9c98ae9490b977d62f3e9742d854146d298b4'
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
check('313_git_files_in_read_only_source',len(files)==313 and set(files)==set(disk))
check('all_source_bytes_equal_fixed_Git_archive',not disk_changed,disk_changed)
manifest=source_map(files);mh=sha(canon(manifest));base_manifest=source_map(base);base_mh=sha(canon(base_manifest))
verification=doc('audit/stage_verification.json');developer=doc('audit/stage2_snapshot_development.json')
check('independent_manifest_matches_stage_verification_map',manifest==verification['source_files'])
check('independent_manifest_matches_declared_hashes',mh==verification['source_hash']==developer['candidate_source_manifest_hash'],mh)
check('94_source_files',len(manifest)==94==developer['candidate_source_file_count'])
check('developer_evidence_is_not_independent_acceptance',developer['new_candidate_independently_accepted'] is False and developer['stage2_status']=='pending_acceptance' and developer['financial_evidence'] is False)
check('developer_322_test_output_recorded_as_developer_evidence','Ran 322 tests' in verification['test_output'] and verification['local_tests_passed'] is True and verification['external_review_status']=='pending_GPT_Work')

all_diff=[{'path':p,'kind':'added' if p not in base else 'removed' if p not in files else 'modified','baseline_raw_sha256':sha(base[p]) if p in base else None,'candidate_raw_sha256':sha(files[p]) if p in files else None}
    for p in sorted(set(files)|set(base)) if files.get(p)!=base.get(p)]
prod_diff=[d for d in all_diff if d['path'].startswith(('cloud/','config/','tools/','templates/'))]
expected={'cloud/qresearch/collection.py','cloud/qresearch/historical_source.py','cloud/research_config.py','config/source_catalog.json','templates/historical_collection.json','tools/stage2_collection.py'}
check('complete_production_diff_exact_expected_paths',{d['path'] for d in prod_diff}==expected,prod_diff)
old_production=[p for p in base if p.startswith(('cloud/','config/','tools/','templates/')) and p!='cloud/research_config.py']
check('all_existing_d0_production_bytes_unchanged',all(files.get(p)==base[p] for p in old_production),{'count':len(old_production)})
check('all_existing_d0_tests_bytes_unchanged',all(files.get(p)==base[p] for p in base if p.startswith('tests/')))
config_ast=ast.parse(files['cloud/research_config.py']);base_config_ast=ast.parse(base['cloud/research_config.py'])
def assignments(tree):return {n.targets[0].id:ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign)}
assigns,base_assigns=assignments(config_ast),assignments(base_config_ast)
check('generated_active_configuration_unchanged',assigns['CONFIGURATION']==base_assigns['CONFIGURATION'] and assigns['SOURCE_SHA256']==base_assigns['SOURCE_SHA256'])
check('generated_config_diff_only_implementation_digest',{k for k in assigns if assigns[k]!=base_assigns[k]}=={'IMPLEMENTATION_SHA256'})
implementation={Path(p).name:sha(norm(b)) for p,b in files.items() if p.startswith('cloud/qresearch/') and p.endswith('.py')}
check('implementation_digest_recomputed',assigns['IMPLEMENTATION_SHA256']==sha(canon(implementation))==developer['implementation_hash'])
deploy=doc('audit/deployment.json');depfiles=deployment_map(files);basedep=deployment_map(base)
check('deployment_file_map_recomputed',depfiles==deploy['source_files'])
check('deployment_27_python_files',len(depfiles)==27==developer['deployment_python_file_count'])
check('deployment_implementation_and_configuration_hashes',deploy['implementation_hash']==assigns['IMPLEMENTATION_SHA256'] and deploy['configuration_hash']==assigns['SOURCE_SHA256']==developer['configuration_hash'])

catalog=doc('config/source_catalog.json');template=doc('templates/historical_collection.json')
check('catalog_in_normalized_source_manifest',manifest['config/source_catalog.json']==sha(norm(files['config/source_catalog.json'])))
check('catalog_15_observation_fields_no_certification',len(catalog['fields'])==15 and catalog['purpose']=='engineering_source_observation_only' and all(catalog[k] is False for k in ('factor_fields_enabled','vendor_revision_certified','actual_availability_certified')))
check('template_requires_four_frozen_explicit_values',all(template[k] is None for k in ('plan_id','data_version','start','end_exclusive','source_manifest_hash')) and set(template['fields'])==set(catalog['fields']))
research_ast=ast.parse(files['tools/research.py'])
configfun=next(n for n in research_ast.body if isinstance(n,ast.FunctionDef) and n.name=='configuration')
check('catalog_not_in_existing_generated_active_configuration',b'source_catalog' not in files['tools/research.py'] and 'source_catalog' not in assigns['CONFIGURATION'])
collection_ast=ast.parse(files['cloud/qresearch/collection.py'])
planclass=next(n for n in collection_ast.body if isinstance(n,ast.ClassDef) and n.name=='HistoricalCollectionPlan')
plan_from=next(n for n in planclass.body if isinstance(n,ast.FunctionDef) and n.name=='from_dict')
plan_identity=next(n for n in ast.walk(plan_from) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='identity' for t in n.targets))
check('plan_identity_explicitly_binds_selected_catalog_definition_AST',isinstance(plan_identity.value,ast.Dict) and [ast.literal_eval(k) for k in plan_identity.value.keys]==['plan','field_catalog'] and isinstance(plan_identity.value.values[1],ast.DictComp))
cli=files['tools/stage2_collection.py'].decode('utf-8-sig')
check('metadata_CLI_checks_current_manifest_and_catalog','HistoricalCollectionPlan.from_dict(raw, field_catalog=catalog())' in cli and 'source_manifest()["source_hash"]' in cli and 'Plan does not pin the current source manifest' in cli)
check('metadata_CLI_discloses_no_dispatch_or_admission','"dispatch_supported": False' in cli and '"budget_admission_performed": False' in cli)

archive='audit/reviews/20261026-d0b9c98-windows/';am=doc(archive+'archive_manifest.json');originals=[]
for name,h in am['files'].items():
    sources=[OLD/name,DURABLE/name]
    matches=[str(p) for p in sources if p.is_file() and p.read_bytes()==files[archive+name]]
    check('archived_d0_original_'+name,sha(files[archive+name])==h and bool(matches))
    originals.append({'name':name,'sha256':sha(files[archive+name]),'exact_matching_original_paths':matches})
check('archived_complete_d0_bundle_hash',sha((DURABLE/'independent_review_bundle.zip').read_bytes())==am['complete_original_bundle_sha256'])
formal=doc(archive+'formal_report.json')
check('d0_formal_acceptance_bound_to_original_version',formal['reviewed_source_commit']==BASE and formal['source_manifest_hash']==base_mh and formal['software_acceptance']['status']=='passed_after_fix' and formal['software_acceptance']['whole_system']=='not_accepted')
first=doc(archive+'numeric_agent/exact_summary_results_first.json')
check('d0_first_reviewer_errors_preserved',first['methods']==11 and first['passed_methods']==9 and first['error_methods']==2 and first['failed_methods']==0 and first['error_records']==8 and first['exit_code']==1)
relative=doc(archive+'numeric_agent/relative_tolerance_results.json')
check('d0_strict_relative_failures_preserved',relative['methods']==11 and relative['passed_methods']==9 and relative['failed_methods']==2 and relative['failure_records']==4 and relative['error_methods']==0 and relative['exit_code']==1)
corrected=doc(archive+'numeric_agent/exact_summary_results.json')
check('d0_corrected_mixed_tolerance_result_preserved',corrected['methods']==11 and corrected['passed_methods']==11 and corrected['failed_methods']==corrected['error_methods']==0 and corrected['exit_code']==0)
older=[p for p in base if p.startswith(('audit/reviews/','audit/review_packages/'))]
older_changed=[p for p in older if files.get(p)!=base[p]]
check('all_older_pass_and_failure_evidence_bytes_unchanged',not older_changed,{'files':len(older),'changed':older_changed})
archive_check=doc('audit/d0_acceptance_archive_check.json')
check('archive_integrity_record_matches_original_manifest',archive_check['archive_originals_raw_bytes_verified']==am['files'])
check('archive_check_is_explicit_historical_no_new_tests',archive_check['reviewed_source_commit']==BASE and archive_check['repository_tests_rerun_this_turn'] is False and archive_check['whole_system_accepted'] is False)

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
        a=attempts[event['attempt_id']];a.update(event,status=kind)
        if kind=='completed':check('completed_result_'+event['attempt_id'],sha(files['audit/runtime/'+a['result_key']])==event['result_sha256'])
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
check('readiness_binds_old_d0_acceptance',ready['accepted_offline_source_commit']==BASE and ready['accepted_source_manifest_hash']==base_mh and ready['independent_offline_accepted_stages']==[0,1])
old_runtime=json.loads(runtime['audit/stage2_cloud_deployment.json']);olddep=old_runtime['source_files']
expected_diff=[p for p in sorted(set(olddep)|set(basedep)) if olddep.get(p)!=basedep.get(p)]
check('readiness_deployment_scope_explicitly_historical_d0','Accepted d0' in ready['deployment_comparison_scope'] and 'not a new QC readback' in ready['deployment_comparison_scope'] and ready['deployment_file_count']==25)
check('readiness_historical_deployment_differences_match',[d['path'] for d in ready['deployment_differences']]==expected_diff and all(d['accepted_candidate_sha256']==basedep[d['path']] and d['archived_cloud_sha256']==olddep[d['path']] for d in ready['deployment_differences']))
check('readiness_does_not_accept_or_deploy_new_candidate',ready['new_candidate_independently_accepted'] is False and ready['candidate_cloud_deployed'] is False and ready['stage2_status']=='pending_acceptance')
check('readiness_budget_and_active_research_unchanged',ready['global_usage']==totals and ready['authoritative_budget_changed'] is False and ready['active_research_configuration_changed'] is False)
check('readiness_preserves_pending_task',ready['terminal_received'] is False and ready['pending_source_or_task_input_changed'] is False and ready['pending_backtest_id']==pending['external_id'])
check('readiness_preserves_remote_protocol_missing','remote_collection_task_protocol_and_atomic_budget_admission' in ready['unimplemented_collection_scope'])
check('tracking_scopes_acceptance_to_old_d0',tracking['reviewed_source_commit']==BASE and tracking['source_manifest_hash']==base_mh and tracking['accepted_stages']==[0,1] and tracking['whole_system_acceptance']=='not_accepted' and 'pending_fixed_commit' in tracking['new_candidate_acceptance'])
check('tracking_precision_diagnostic_records_preserved',any(d.get('id')=='exploratory_pure_relative_ICIR' and d.get('failed')==2 and d.get('failure_records')==4 for d in tracking['numerical_diagnostics']))

report={'candidate_source_commit':SHA,'previous_independently_reviewed_commit':BASE,
    'actually_executed':'Read-only Git/raw byte hashes, AST and metadata/journal parsing',
    'unit_test_methods_executed_by_this_script':0,'platform_calls_by_this_script':0,'delivery_ZIP_supplied':False,
    'check_count':len(checks),'passed_checks':sum(c['passed'] for c in checks),'failed_checks':sum(not c['passed'] for c in checks),
    'Git':{'tracked_source_files':len(files),'exact_disk_byte_match':not disk_changed,'entire_raw_file_hash_map_sha256':sha(canon({p:sha(b) for p,b in files.items()}))},
    'source_manifest':{'count':len(manifest),'hash':mh,'previous_accepted_count':len(base_manifest),'previous_accepted_hash':base_mh},
    'complete_d0_to_candidate_diff':all_diff,'complete_production_diff':prod_diff,
    'new_catalog_identity':{'source_manifest_includes_catalog':True,'plan_identity_binds_selected_definitions':True,'generated_active_CONFIGURATION_includes_catalog':False,'generated_configuration_hash_unchanged':True,'Python_only_deployment_does_not_include_catalog_JSON':True,'field_count':len(catalog['fields']),
        'interpretation':'New observation catalog and inactive template change the source/plan identity. They do not register an active configuration, consume quota, activate factor fields, or constitute remote admission/deployment. Remote collection protocol/admission remains unimplemented.'},
    'old_d0_original_files':originals,'older_evidence_file_count':len(older),'protected_prior_runtime_files':{'count':len(protected),'changed':pdiff},
    'budget_replay':{'events':len(events),'usage':usage,'limits':limits,'pending_lean':{k:pending.get(k) for k in ('attempt_id','stage','status','external_id')},'initial_usage_is_historical_aggregate':True},
    'deployment':{'local_candidate_hash':sha(canon(depfiles)),'local_files':len(depfiles),'configuration_hash':assigns['SOURCE_SHA256'],'implementation_hash':assigns['IMPLEMENTATION_SHA256'],'previous_d0_hash':sha(canon(basedep)),'historical_runtime_source':old_runtime['source_commit'],'historical_runtime_hash':old_runtime['deployment_hash']},
    'readiness_note':'Its deployment comparison is d0 versus archived old75, not candidate fbe versus current cloud. source_configuration_budget_changed=true is a broad source-additions marker, qualified by active_research_configuration_changed=false and authoritative_budget_changed=false; it is not a debit.',
    'acceptance_boundary':'Old d0 accepted stage0/1 tested offline scope is retained; these checks alone do not accept the new collection implementation or stage2.',
    'unverified':['No unit-suite rerun by this evidence script; developer 322 remains developer evidence','No deployment, platform compile/run, source collection or pending LEAN terminal/log read','No full historical universe, financial vintage/delivery or independent financial test'],
    'checks':checks,'financial_evidence':False}
path=OUT/'delivery_evidence_report.json';path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(OUT/'delivery_evidence_report.sha256').write_text(sha(path.read_bytes())+'  delivery_evidence_report.json\n',encoding='utf-8')
print(json.dumps({k:report[k] for k in ('candidate_source_commit','check_count','passed_checks','failed_checks','Git','source_manifest','complete_production_diff','budget_replay','deployment')},ensure_ascii=False,indent=2))
for c in checks:
    if not c['passed']:print('FAILED',c)
raise SystemExit(0 if all(c['passed'] for c in checks) else 1)
