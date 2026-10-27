"""Independent source, developer evidence and historical package verification.

Read-only checks and pure identity evaluation; no software suites or QC calls.
"""
from pathlib import Path
import ast, copy, hashlib, io, json, subprocess, tarfile, zipfile
ROOT=Path(__file__).resolve().parents[1];OUT=Path(__file__).resolve().parent
GIT=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\repo')
OLD=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-8f7236e-20261027')
DURABLE=Path(r'B:\BaiduSyncdisk\学习\投资\量化\量化交易比赛\LLM审核\review-8f7236e-20261027')
SHA='ae2b8985f3799c246e90341370f86d80483f63ed'
BASE='8f7236ecbafcb514f07a6af4150a5afdbc1fd474'
DD='dd094f345f45b9d9cb78dd9295a6aefd587f4c68'
checks=[]
def canon(v):return json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def norm(b):return b.decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n').encode()
def check(n,ok,detail=None):checks.append({'check':n,'passed':bool(ok),'detail':detail})
def gitfiles(rev):
    raw=subprocess.check_output(['git','-C',str(GIT),'archive',rev])
    with tarfile.open(fileobj=io.BytesIO(raw)) as tf:return {m.name:tf.extractfile(m).read() for m in tf.getmembers() if m.isfile()}
files=gitfiles(SHA);base=gitfiles(BASE);dd=gitfiles(DD)
def doc(p):return json.loads(files[p])
def source_map(mapping):
    result={}
    for p,b in mapping.items():
        parts=Path(p).parts
        if ((parts[0] in ('cloud','config','templates','tests','tools','docs','.github') and Path(p).suffix in ('.py','.json','.md','.yml','.yaml') and '__pycache__' not in parts) or p in ('requirements-test.txt','.gitattributes','.gitignore','AGENTS.md')):result[p]=sha(norm(b))
    return result
disk={p.relative_to(ROOT/'source').as_posix():p.read_bytes() for p in (ROOT/'source').rglob('*') if p.is_file()}
bad=[p for p in set(files)|set(disk) if files.get(p)!=disk.get(p)]
check('1843_source_files_equal_fixed_Git_set',len(files)==1843 and set(files)==set(disk))
check('all_source_bytes_equal_fixed_Git',not bad,bad)
manifest=source_map(files);review_hash=sha(canon(manifest));old_review_hash=sha(canon(source_map(base)))
devroot='audit/review_packages/wr16_wr17/';dev=doc(devroot+'developer_verification.json');stage=doc('audit/stage_verification.json')
check('120_normalized_review_source_files',len(manifest)==120==dev['candidate_source_files'])
check('review_source_map_and_hash_recomputed',manifest==stage['source_files'] and review_hash==stage['source_hash']==dev['candidate_source_manifest_hash'])
diff=[{'path':p,'kind':'added' if p not in base else 'removed' if p not in files else 'modified','old_raw_sha256':sha(base[p]) if p in base else None,'new_raw_sha256':sha(files[p]) if p in files else None} for p in sorted(set(base)|set(files)) if base.get(p)!=files.get(p)]
prod=[d for d in diff if d['path'].startswith(('cloud/','config/','tools/','templates/'))]
check('three_runtime_diff_paths_only',{d['path'] for d in prod}=={'cloud/qresearch/registry.py','cloud/research_config.py','tools/stage2.py'},prod)
check('all_existing_configs_templates_and_tests_unchanged',all(files.get(p)==base[p] for p in base if p.startswith(('config/','templates/','tests/'))))
check('shared_parser_calculation_source_unchanged',all(files.get(p)==base[p] for p in base if p.startswith('cloud/qresearch/') and p!='cloud/qresearch/registry.py'))
old_evidence=[p for p in base if p.startswith(('audit/reviews/','audit/review_packages/'))]
oldbad=[p for p in old_evidence if files.get(p)!=base[p]]
check('all_old_failure_acceptance_precision_evidence_unchanged',not oldbad,{'files':len(old_evidence),'changed':oldbad})
check('current_review_instructions_exist_and_keep_pending_findings',dev['documentation']=='docs/review/wr16-wr17.md' and dev['known_open_findings_pending_independent_retest']==['WR-16','WR-17'] and dev['purpose']=='WR16_WR17_developer_repair_not_independent_or_financial_acceptance')

rawmanifest=doc(devroot+'original_outputs_manifest.json');raw_rows=[]
for e in rawmanifest['files']:
    p=devroot+e['archive_path'];b=files[p];ok=sha(b)==e['raw_sha256'] and len(b)==e['bytes']
    check('developer_original_'+e['archive_path'],ok)
    raw_rows.append({'path':p,'actual_raw_sha256':sha(b),'claimed_raw_sha256':e['raw_sha256'],'bytes':len(b),'passed':ok})
check('65_original_outputs_and_byte_total',len(raw_rows)==65==rawmanifest['file_count']==dev['developer_originals']['files'] and sum(e['bytes'] for e in raw_rows)==rawmanifest['total_original_bytes']==dev['developer_originals']['bytes'])
check('developer_original_manifest_raw_declaration_matches',sha(files[devroot+'original_outputs_manifest.json'])==dev['developer_originals']['manifest_raw_sha256'])
for e in rawmanifest['reused_existing_evidence']:
    b=files[e['existing_archive_path']]
    check('developer_reused_original_quick_script',sha(b)==e['raw_sha256'] and len(b)==e['bytes'])
check('developer_raw_attributes_present','audit/review_packages/wr16_wr17/** -text' in files['.gitattributes'].decode('utf-8-sig'))
check('old_registry_and_stage2_inputs_identify_8f_source',norm(files[devroot+'original_wr16-before__registry_input.py'])==norm(base['cloud/qresearch/registry.py']) and norm(files[devroot+'original_wr17_baseline_stage2_input.py'])==norm(base['tools/stage2.py']))
check('WR17_original_before_after_test_input_same_content',norm(files[devroot+'original_wr17_baseline_test_input.py'])==norm(files['tests/test_wr17_engineering_recovery.py']) and dev['WR17']['baseline_and_after']['test_input_identical'] is True)
check('developer_WR16_initial_product_failures_retained',dev['WR16']['baseline_methods']==6 and dev['WR16']['baseline_passed_methods']==2 and dev['WR16']['baseline_failed_methods']==4 and dev['WR16']['baseline_failure_records']==10)
wr17before=dev['WR17']['baseline_and_after']['results']['baseline']
check('developer_WR17_missing_recovery_product_errors_not_relabelled_harness',wr17before['methods']==11 and wr17before['passed_methods']==2 and wr17before['failed_methods']==4 and wr17before['error_methods']==5 and wr17before['failure_records']==9 and wr17before['error_records']==10)
check('developer_MRE_before_fail_after_pass_kept',dev['WR16']['original_full_MRE_before_exit']==1 and dev['WR16']['original_full_MRE_after_exit']==0 and dev['WR17']['baseline_and_after']['original_MRE']['before_exit']==1 and dev['WR17']['baseline_and_after']['original_MRE']['after_exit']==0)
full=doc(devroot+'original_final_repository_verification.json')
check('442_developer_record_source_identity_matches_candidate',full['source_files']==manifest and full['source_hash']==review_hash and full['local_tests_passed'] is True and 'Ran 442 tests' in full['test_output'])
check('prior_preview_saved_without_silent_current_identity',json.loads(files[devroot+'original_prior_joint_preview.json'])==json.loads(base['audit/stage2_joint_preview.json']))

archive='audit/reviews/20261027-8f7236e-windows/';am=doc(archive+'archive_manifest.json');archive_rows=[]
for e in am['files']:
    b=files[archive+e['archive_path']];origins=[str(p) for p in (DURABLE/e['origin_relative_path'],OLD/e['origin_relative_path']) if p.is_file() and p.read_bytes()==b]
    ok=sha(b)==e['raw_sha256'] and len(b)==e['bytes'] and bool(origins)
    check('8f_independent_original_'+e['archive_path'],ok)
    archive_rows.append({'path':e['archive_path'],'sha256':sha(b),'bytes':len(b),'matching_originals':origins,'passed':ok})
check('208_independent_originals_and_total',len(am['files'])==208==am['file_count']==dev['independent_original_files'] and sum(x['bytes'] for x in archive_rows)==am['total_original_bytes']==dev['independent_original_bytes'])
check('independent_archive_manifest_raw_declarations',sha(files[archive+'archive_manifest.json'])==dev['independent_archive_manifest_raw_sha256']==doc('audit/8f7236e_review_archive_check.json')['archive_manifest_raw_sha256'])
reused=[]
for e in am['reused_existing_evidence']:
    b=files[e['existing_archive_path']];original=DURABLE/e['origin_relative_path'];ok=original.is_file() and original.read_bytes()==b and sha(b)==e['raw_sha256'] and len(b)==e['bytes']
    check('independent_reused_'+e['origin_relative_path'],ok);reused.append({'path':e['existing_archive_path'],'origin':str(original),'passed':ok})
check('11_independent_duplicate_refs',len(reused)==11)
artifact=doc(archive+'artifact_manifest.json');actual_artifact=json.loads((DURABLE/'artifact_manifest.json').read_text(encoding='utf-8-sig'))
artifactbad=[p for p,h in artifact.items() if not (DURABLE/p).is_file() or sha((DURABLE/p).read_bytes())!=h]
check('final3328_original_artifact_manifest_raw_entries',artifact==actual_artifact and len(artifact)==3328==am['full_original_artifact_manifest_hash_checks'] and not artifactbad,artifactbad)
source_proofs=[]
for label,path,mapping in [('candidate',DURABLE/'source',base),('baseline_dd094f3',DURABLE/'baselines/dd094f3/source',dd)]:
    diskmap={p.relative_to(path).as_posix():p.read_bytes() for p in path.rglob('*') if p.is_file()}
    mismatch=[p for p in set(mapping)|set(diskmap) if mapping.get(p)!=diskmap.get(p)]
    check('old_package_'+label+'_full_source_equals_Git',not mismatch and len(mapping)==am['source_Git_blob_checks'][label]['files'],{'files':len(mapping),'mismatches':mismatch})
    source_proofs.append({'label':label,'files':len(mapping),'all_equal':not mismatch})
package_first=doc(archive+'package_attempt_1.json')
check('first_packaging_six_omissions_remain_explicit',package_first['packaging_attempt']==1 and len(package_first['missing'])==6 and package_first['extra']==[] and package_first['changed']==[] and 'not a production' in package_first['cause'])
zipinfo=am['review_zip'];zip_path=Path(zipinfo['path']);prune_corrections=[]
with zipfile.ZipFile(zip_path) as z:
    check('corrected_final_package_raw_SHA_CRC_and_unique_entries',sha(zip_path.read_bytes())==zipinfo['raw_sha256'] and z.testzip() is None and len(z.namelist())==len(set(z.namelist())))
    zipbad=[p for p,h in artifact.items() if sha(z.read(DURABLE.name+'/'+p))!=h]
    check('corrected_final_ZIP_all3328_entries_equal_final_manifest',not zipbad and zipinfo['verified_entries']==3328,zipbad)
    for p in package_first['missing']:
        expected=base[p];member=DURABLE.name+'/source/'+p
        ok=z.read(member)==expected and (DURABLE/'source'/p).read_bytes()==expected and files[p]==expected
        check('previously_pruned_source_recovered_'+p,ok);prune_corrections.append({'path':p,'raw_sha256':sha(expected),'final_ZIP_member':member,'current_and_old_source_and_ZIP_equal':ok})
for rm in am['receipt_manifests']:
    m=doc(archive+rm['path']);parent=str(Path(rm['path']).parent).replace('\\','/')+'/'
    actual_by_origin={e['origin_relative_path']:e['raw_sha256'] for e in am['files']+am['reused_existing_evidence']}
    check('independent_receipt_manifest_'+rm['path'],len(m)==rm['references'] and all(actual_by_origin[parent+p]==h for p,h in m.items()))
for p in am['sidecar_sha256_checks']:check('independent_sidecar_'+p,sha(files[archive+p.removesuffix('.sha256')])==files[archive+p].decode('utf-8-sig').split()[0])
formal=doc(archive+'formal_report.json');findings=doc(archive+'findings.json')
check('8f_failed_findings_and_scopes_not_rewritten',formal['software_acceptance']=='failed_stage2_joint_candidate_WR16_WR17; prior_stage0_1_scope_preserved' and [f['id'] for f in findings]==['WR-16','WR-17'] and formal['reviewed_source_commit']==BASE)
check('8f_fraction_schema_helper_setup_errors_preserved',len(formal['tests']['fraction_auditor_setup_errors'])==2 and all(e['methods']==10 and e['passed']==9 and e['errors']==1 for e in formal['tests']['fraction_auditor_setup_errors']) and formal['tests']['fraction_final']['passed']==10)

def assigns(data):return {n.targets[0].id:ast.literal_eval(n.value) for n in ast.parse(data).body if isinstance(n,ast.Assign)}
generated=assigns(files['cloud/research_config.py']);prior_generated=assigns(base['cloud/research_config.py'])
impl={Path(p).name:sha(norm(b)) for p,b in files.items() if p.startswith('cloud/qresearch/') and p.endswith('.py')}
deploy={p[len('cloud/'):]:sha(norm(b)) for p,b in files.items() if p.startswith('cloud/') and p.endswith('.py')};deployment=doc('audit/deployment.json')
check('implementation_hash_recomputed',sha(canon(impl))==generated['IMPLEMENTATION_SHA256']==deployment['implementation_hash']==dev['implementation_hash'])
check('active_research_configuration_and_hash_unchanged',generated['CONFIGURATION']==prior_generated['CONFIGURATION'] and generated['SOURCE_SHA256']==prior_generated['SOURCE_SHA256']==deployment['configuration_hash'])
check('29_deployment_source_files_recomputed',len(deploy)==29 and deploy==deployment['source_files'])
budget=doc('config/budget.json');policy=copy.deepcopy(budget);policy.pop('usage');exmap=dict(manifest);exmap['config/budget.json']=sha(canon(policy));exhash=sha(canon({'schema':'collection_execution_sources_v1','source_files':exmap}))
fn=next(n for n in ast.parse(files['tools/collection_task_cli.py']).body if isinstance(n,ast.FunctionDef) and n.name=='execution_source_manifest')
priorfn=next(n for n in ast.parse(base['tools/collection_task_cli.py']).body if isinstance(n,ast.FunctionDef) and n.name=='execution_source_manifest')
check('pure_execution_identity_policy_AST_unchanged',ast.dump(fn,include_attributes=False)==ast.dump(priorfn,include_attributes=False))
ns={'ROOT':Path('IN_MEMORY_ONLY'),'hashlib':hashlib,'canonical_json':canon,'content_hash':lambda v:sha(canon(v)),'source_manifest':lambda:{'source_files':copy.deepcopy(manifest)},'read_json':lambda _:copy.deepcopy(budget)}
exec(compile(ast.fix_missing_locations(ast.Module(body=[fn],type_ignores=[])),'candidate:execution_identity','exec'),ns)
check('execution_identity_only_excludes_budget_usage',ns['execution_source_manifest']()=={'source_files':exmap,'source_hash':exhash})
preview=doc('audit/stage2_joint_preview.json')
check('preview_matches_saved_raw_stdout',json.loads(files[devroot+'original_current_preview.stdout'])==preview)
check('preview_binds_new_source_and_deployment',preview['source_manifest_hash']==preview['plan']['source_manifest_hash']==exhash==dev['preview']['execution_source_hash'] and preview['deployment_hash']==sha(canon(deploy)) and preview['plan_hash']==sha(canon(preview['plan']))==dev['preview']['plan_hash'])
check('preview_still_not_admission_dispatch_or_registration',all(preview[k] is False for k in ('configuration_registered','execution_started','ready_to_dispatch','budget_admission_performed')))
protected=[p for p in base if p.startswith(('config/','templates/','audit/runtime/','audit/task_inputs/','audit/tool_observations/')) or p in ('audit/data_exposure.json','audit/engineering_current.json','audit/stage2_cloud_deployment.json','audit/stage2_live_preflight.json','audit/stage2_live_project_listing.json','audit/stage2_real_execution.json','docs/research_charter.md','AGENTS.md')]
protectedbad=[p for p in protected if files.get(p)!=base[p]]
check('all_authoritative_budget_old_attempt_pointer_data_exposure_and_flags_unchanged',not protectedbad,{'paths':len(protected),'changed':protectedbad})
new_runtime=[p for p in set(files)-set(base) if p.startswith(('audit/runtime/','audit/task_inputs/'))]
check('no_new_real_attempt_configuration_or_task_input',not new_runtime,new_runtime)
raw=files['audit/runtime/registry/events.jsonl'];events=[];previous=None;check('journal_tail_complete',raw.endswith(b'\n'))
for i,line in enumerate(raw.splitlines(),1):
    envelope=json.loads(line);body={k:v for k,v in envelope.items() if k!='hash'}
    check('journal_event_'+str(i)+'_chain',envelope['sequence']==i and envelope['previous_hash']==previous and sha(canon(body))==envelope['hash']);events.append(envelope['event']);previous=envelope['hash']
usage=copy.deepcopy(events[0]['initial_usage']);attempts={}
for e in events[1:]:
    if e['kind'] in ('config_registered','attempt_started'):
        s='configurations' if e['kind']=='config_registered' else e['stage'];usage[s]['total']+=1;usage[s][e['allocation']]+=1
    if e['kind']=='attempt_started':attempts[e['attempt_id']]=dict(e,status='started')
    if e['kind'] in ('pending','ambiguous','failed','completed'):attempts[e['attempt_id']].update(e,status=e['kind'])
totals={s:usage[s]['total'] for s in ('configurations','research','lean')};pending=attempts['bfd00f2611fd4496b9498d4597618a8e']
check('12_events_independently_replay6_9_1',len(events)==12 and list(totals.values())==[6,9,1] and totals==dev['budget_used'])
check('old_pending_attempt_external_identity_unchanged',pending['status']=='pending' and pending['external_id']=='39cafa1e9b11f91b27e396b66d033a6d')
flags=doc('config/development.json')['execution'];check('all_four_execution_flags_still_false',all(flags[k] is False for k in ('market_research_enabled','llm_runtime_enabled','final_test_enabled','live_trading_enabled')))
report={'fixed_candidate':SHA,'baseline':BASE,'scope':'Independent source/evidence/package/identity and budget verification; no software suites or platform execution',
 'actually_executed':'Raw bytes/AST/JSON/ZIP/hash checks; independent event replay; pure identity function in memory',
 'check_count':len(checks),'passed_checks':sum(c['passed'] for c in checks),'failed_checks':sum(not c['passed'] for c in checks),'unit_test_methods_executed':0,'software_442_suite_rerun':False,'QC_market_model_calls':0,
 'source':{'files':len(files),'raw_bytes_equal_Git':not bad,'review_files':len(manifest),'review_hash':review_hash,'execution_hash':exhash,'previous_review_hash':old_review_hash},
 'deployment':{'Python_files':len(deploy),'local_deployment_hash':sha(canon(deploy)),'implementation_hash':generated['IMPLEMENTATION_SHA256'],'active_configuration_hash':generated['SOURCE_SHA256'],'does_not_certify_cloud_deployment':True},
 'complete_diff':diff,'production_diff':prod,'old_evidence_files_unchanged':len(old_evidence),
 'developer_originals':raw_rows,'developer_failure_boundary':'WR16 baseline6 methods2pass4fail/10failure records; final8 includes2 added methods. WR17 same11-method input2pass4fail5product errors, not reviewer errors; repair11pass. Developer records remain developer evidence.',
 'review_instructions':dev['documentation'],'prior_independent_archive':{'originals':archive_rows,'reused':reused,'full_artifact_entries_verified':len(artifact),'fixed_source_checks':source_proofs,'first_packaging_attempt_six_omissions':package_first,'recovered_paths':prune_corrections,'final_package_sha256':sha(zip_path.read_bytes())},
 'protected_metadata':{'paths':len(protected),'changed':protectedbad},'budget':{'events':len(events),'usage':usage,'limits':events[0]['limits'],'pending_attempt':{k:pending[k] for k in ('attempt_id','stage','status','external_id')}},
 'preview':{'plan_hash':preview['plan_hash'],'no_registration_or_dispatch':True,'independent_replay':'build_preview_verification.json'},
 'boundary':'Old pending is archived evidence only, current terminal unknown. No QC/task/log read or new real source/Research/LEAN/model operation. Source/build/preview integrity does not independently accept the repairs or certify data.',
 'checks':checks,'financial_evidence':False}
p=OUT/'evidence_verification.json';p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');(OUT/'evidence_verification.json.sha256').write_text(sha(p.read_bytes())+'  evidence_verification.json\n',encoding='utf-8')
print(json.dumps({k:report[k] for k in ('fixed_candidate','check_count','passed_checks','failed_checks','unit_test_methods_executed','source','deployment','budget')},ensure_ascii=False,indent=2))
for c in checks:
    if not c['passed']:print('FAILED',c)
raise SystemExit(0 if all(c['passed'] for c in checks) else 1)
