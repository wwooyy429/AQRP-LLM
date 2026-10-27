"""Independent fixed-source, original evidence, identity and ledger verification.

No product suite, platform call or production mutation is performed here.
"""
from pathlib import Path
import ast,copy,hashlib,io,json,re,subprocess,tarfile,zipfile
ROOT=Path(__file__).resolve().parents[1];OUT=Path(__file__).resolve().parent;SOURCE=ROOT/'source'
GIT=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\repo')
OLD=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-ae2b898-20261027')
DURABLE=Path(r'B:\BaiduSyncdisk\学习\投资\量化\量化交易比赛\LLM审核\review-ae2b898-20261027')
SHA='81fbe5294055423e88ee5aeae48ca6223e7971da';BASE='ae2b8985f3799c246e90341370f86d80483f63ed';PRIOR='8f7236ecbafcb514f07a6af4150a5afdbc1fd474'
checks=[];discrepancies=[]
def canon(v):return json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def norm(b):return b.decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n').encode()
def check(name,ok,detail=None):checks.append({'check':name,'passed':bool(ok),'detail':detail})
def gitfiles(rev):
 raw=subprocess.check_output(['git','-C',str(GIT),'archive',rev])
 with tarfile.open(fileobj=io.BytesIO(raw)) as tf:return {m.name:tf.extractfile(m).read() for m in tf.getmembers() if m.isfile()}
def source_map(mapping):
 return {p:sha(norm(b)) for p,b in mapping.items() if ((Path(p).parts[0] in ('cloud','config','templates','tests','tools','docs','.github') and Path(p).suffix in ('.py','.json','.md','.yml','.yaml') and '__pycache__' not in Path(p).parts) or p in ('requirements-test.txt','.gitattributes','.gitignore','AGENTS.md'))}
files=gitfiles(SHA);base=gitfiles(BASE);prior=gitfiles(PRIOR)
doc=lambda p:json.loads(files[p])
disk={p.relative_to(SOURCE).as_posix():p.read_bytes() for p in SOURCE.rglob('*') if p.is_file()}
bad=[p for p in set(files)|set(disk) if files.get(p)!=disk.get(p)]
check('2374_fixed_Git_source_file_set',len(files)==2374 and set(files)==set(disk))
check('all2374_source_raw_bytes_equal_fixed_Git',not bad,bad)
manifest=source_map(files);review_hash=sha(canon(manifest));oldmanifest=source_map(base)
devroot='audit/review_packages/wr18/';dev=doc(devroot+'developer_verification.json');stage=doc('audit/stage_verification.json')
check('122_review_sources_hash_recomputed',len(manifest)==122==dev['candidate_source_files'] and manifest==stage['source_files'] and review_hash==stage['source_hash']==dev['candidate_source_manifest_hash'])
deltas=[{'path':p,'kind':'added' if p not in oldmanifest else 'removed' if p not in manifest else 'modified','old_normalized_sha256':oldmanifest.get(p),'new_normalized_sha256':manifest.get(p)} for p in sorted(set(manifest)|set(oldmanifest)) if oldmanifest.get(p)!=manifest.get(p)]
check('two_source_manifest_additions_only',set(manifest)-set(oldmanifest)=={'docs/review/wr18.md','tests/test_wr18_completion_dependency.py'} and not set(oldmanifest)-set(manifest))
diff=[{'path':p,'kind':'added' if p not in base else 'removed' if p not in files else 'modified','old_raw_sha256':sha(base[p]) if p in base else None,'new_raw_sha256':sha(files[p]) if p in files else None} for p in sorted(set(files)|set(base)) if files.get(p)!=base.get(p)]
prod=[r for r in diff if r['path'].startswith(('cloud/','tools/','config/','templates/'))]
check('runtime_diff_only_two_shared_implementations_and_generated_config',{r['path'] for r in prod}=={'cloud/qresearch/registry.py','cloud/qresearch/engineering_tasks.py','cloud/research_config.py'},prod)
check('all_existing_config_templates_tests_and_WR17_CLI_unchanged',all(files.get(p)==b for p,b in base.items() if p.startswith(('config/','templates/','tests/')) or p=='tools/stage2.py'))
old_evidence=[p for p in base if p.startswith(('audit/reviews/','audit/review_packages/'))]
oldbad=[p for p in old_evidence if files.get(p)!=base[p]]
check('all_prior_original_failures_reviews_precision_and_SDK_evidence_unchanged',not oldbad,{'files':len(old_evidence),'changed':oldbad})
check('WR18_document_and_pending_independent_boundary',dev['documentation']=='docs/review/wr18.md' and dev['purpose']=='WR18_developer_repair_not_independent_or_financial_acceptance' and dev['known_open_findings_pending_independent_retest']==['WR-18'] and dev['whole_system']=='not_accepted')

dm=doc(devroot+'original_outputs_manifest.json');developer_originals=[]
for e in dm['files']:
 b=files[devroot+e['archive_path']];ok=sha(b)==e['raw_sha256'] and len(b)==e['bytes'];check('developer_original_'+e['archive_path'],ok)
 developer_originals.append({'path':e['archive_path'],'raw_sha256':sha(b),'bytes':len(b),'passed':ok})
check('62_developer_raw_originals_byte_total_manifest_declaration',len(developer_originals)==62==dm['file_count']==dev['developer_originals']['files'] and sum(r['bytes'] for r in developer_originals)==dm['total_original_bytes']==dev['developer_originals']['bytes'] and sha(files[devroot+'original_outputs_manifest.json'])==dev['developer_originals']['manifest_raw_sha256'])
for i,e in enumerate(dm['reused_existing_evidence']):
 b=files[e['existing_archive_path']];check('developer_reused_script_'+str(i),sha(b)==e['raw_sha256'] and len(b)==e['bytes'])
check('developer_original_package_raw_attributes','audit/review_packages/wr18/** -text' in files['.gitattributes'].decode('utf-8-sig'))
target='tests/test_wr18_completion_dependency.py';testhash=sha(files[target])
check('same_final11_before_after_raw_test_input',files[devroot+'original_wr18-counted-before__test_input.py']==files[devroot+'original_wr18-counted-after__test_input.py']==files[target] and testhash==dev['targeted_and_original_regressions']['test_sha256'])
for name,source in [('registry','cloud/qresearch/registry.py'),('engineering_tasks','cloud/qresearch/engineering_tasks.py')]:
 check('developer_original_before_source_'+name,norm(files[devroot+'original_wr18-boundary-before__source_'+name+'.py'])==norm(base[source]))
 check('developer_original_after_source_'+name,norm(files[devroot+'original_wr18-boundary-after__source_'+name+'.py'])==norm(files[source]))
def transcript(p):
 text=files[devroot+p].decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n');f=re.findall(r'^FAIL: (test_\w+)',text,re.M);e=re.findall(r'^ERROR: (test_\w+)',text,re.M);ran=re.search(r'^Ran (\d+) tests? in ',text,re.M)
 return {'methods':int(ran.group(1)) if ran else None,'failed_methods':len(set(f)),'failure_records':len(f),'error_methods':len(set(e)),'error_records':len(e),'OK':bool(re.search(r'^OK$',text,re.M))}
raw_counts={k:transcript(p) for k,p in {'initial10_before':'original_wr18-boundary-before__new_tests.stderr','initial10_after':'original_wr18-boundary-after__new_tests.stderr','final11_before':'original_wr18-counted-before__stderr','final11_after':'original_wr18-counted-after__stderr'}.items()}
check('raw_initial10_before_failure_retained',raw_counts['initial10_before']=={'methods':10,'failed_methods':7,'failure_records':16,'error_methods':0,'error_records':0,'OK':False})
check('raw_final11_before8_failed18_records_retained',raw_counts['final11_before']=={'methods':11,'failed_methods':8,'failure_records':18,'error_methods':0,'error_records':0,'OK':False})
check('raw_final11_after_all_OK',raw_counts['final11_after']=={'methods':11,'failed_methods':0,'failure_records':0,'error_methods':0,'error_records':0,'OK':True})
for phase in ('before','after'):
 rec=doc(devroot+'original_wr18-counted-'+phase+'__execution.json');mapping=base if phase=='before' else files
 check('developer_counted_'+phase+'_source_bytes_and_test_identity',rec['test_raw_sha256']==testhash and all(rec['source_raw_sha256'][Path(p).name]==sha(mapping[p]) for p in ('cloud/qresearch/registry.py','cloud/qresearch/engineering_tasks.py')))
 full=doc(devroot+'original_wr18-full-'+phase+'__execution.json');check('developer_original_full_'+phase+'_exit_records',all(r['exit_code']==(1 if phase=='before' else 0) for r in full['records']) and full['scripts_byte_equal_original'] is True)
 compat=doc(devroot+'original_wr18-full-'+phase+'__admission_agent__new_first_results.json')
 check('developer_original9_'+phase+'_methods_count',compat['methods']==9 and compat['passed_methods']==(6 if phase=='before' else 9) and compat['failed_methods']==(3 if phase=='before' else 0) and compat['error_methods']==0 and compat['subcases']==4)
for rec in dev['targeted_and_original_regressions']['compatibility']['records']:
 counts=transcript('original_wr18-compat__'+rec['name']+'.stderr')
 check('raw_compatibility_'+rec['name'],counts['methods']==rec['methods'] and counts['OK'] and not counts['failure_records'] and not counts['error_records'])
full=doc(devroot+'original_final_repository_verification.json')
check('developer453_record_identity_matches_not_independent_rerun',full['source_files']==manifest and full['source_hash']==review_hash and full['local_tests_passed'] is True and 'Ran 453 tests' in full['test_output'])

archive='audit/reviews/20261027-ae2b898-windows/';am=doc(archive+'archive_manifest.json');archive_rows=[]
for e in am['files']:
 b=files[archive+e['archive_path']];origins=[str(p) for p in (DURABLE/e['origin_relative_path'],OLD/e['origin_relative_path']) if p.is_file() and p.read_bytes()==b]
 ok=sha(b)==e['raw_sha256'] and len(b)==e['bytes'] and bool(origins);check('ae_independent_original_'+e['archive_path'],ok)
 archive_rows.append({'path':e['archive_path'],'raw_sha256':sha(b),'bytes':len(b),'matching_originals':origins,'passed':ok})
check('463_original_files_byte_total_declaration',len(archive_rows)==463==am['file_count']==dev['independent_original_files'] and sum(r['bytes'] for r in archive_rows)==am['total_original_bytes']==dev['independent_original_bytes'])
check('original_independent_manifest_raw_declarations',sha(files[archive+'archive_manifest.json'])==dev['independent_archive_manifest_raw_sha256']==doc('audit/ae2b898_review_archive_check.json')['archive_manifest_raw_sha256'])
reused=[]
for e in am['reused_existing_evidence']:
 b=files[e['existing_archive_path']];origin=DURABLE/e['origin_relative_path'];ok=origin.is_file() and origin.read_bytes()==b and sha(b)==e['raw_sha256'] and len(b)==e['bytes']
 check('ae_independent_reused_'+e['origin_relative_path'],ok);reused.append({'path':e['existing_archive_path'],'origin':str(origin),'passed':ok})
check('21_deduplicated_original_refs',len(reused)==21)
artifact=doc(archive+'artifact_manifest.json');artifactbad=[p for p,h in artifact.items() if not (DURABLE/p).is_file() or sha((DURABLE/p).read_bytes())!=h]
check('3902_final_artifact_entries_equal_original_B_root',artifact==json.loads((DURABLE/'artifact_manifest.json').read_text(encoding='utf-8-sig')) and len(artifact)==3902==am['full_original_artifact_manifest_hash_checks'] and not artifactbad,artifactbad)
source_proofs=[]
for label,path,mapping in [('candidate',DURABLE/'source',base),('baseline8f',DURABLE/'baselines/8f7236e/source',prior)]:
 actual={p.relative_to(path).as_posix():p.read_bytes() for p in path.rglob('*') if p.is_file()};mismatch=[p for p in set(actual)|set(mapping) if actual.get(p)!=mapping.get(p)]
 check('ae_final_package_'+label+'_source_raw_equals_Git',not mismatch and len(mapping)==am['source_Git_blob_checks'][label]['files'],{'files':len(mapping),'mismatches':mismatch});source_proofs.append({'label':label,'files':len(mapping),'equal_Git':not mismatch})
zp=Path(am['review_zip']['path'])
with zipfile.ZipFile(zp) as z:
 check('ae_final_ZIP_raw_SHA_CRC_unique_members',sha(zp.read_bytes())==am['review_zip']['raw_sha256'] and z.testzip() is None and len(z.namelist())==len(set(z.namelist())))
 zipbad=[p for p,h in artifact.items() if sha(z.read(DURABLE.name+'/'+p))!=h]
 check('all3902_final_ZIP_entries_equal_manifest',not zipbad and am['review_zip']['verified_entries']==3902,zipbad)
for omitted in am['omitted']:
 p=DURABLE/omitted['path'];check('declared_omission_retains_original_hash_'+omitted['path'],p.is_file() and sha(p.read_bytes())==omitted['raw_sha256'])
refcounts=[]
for rm in am['receipt_manifests']:
 m=doc(archive+rm['path']);parent=str(Path(rm['path']).parent).replace('\\','/')+'/'
 originmap={e['origin_relative_path']:e['raw_sha256'] for e in am['files']+am['reused_existing_evidence']}
 ok=len(m)==rm['references'] and all(originmap[parent+p]==h for p,h in m.items());command_refs=sum(p.startswith('commands/') for p in m)
 check('mixed_recovery_manifest251_refs_with224_command_outputs',ok and len(m)==251 and command_refs==224)
 refcounts.append({'manifest':rm['path'],'all_references':len(m),'command_output_references':command_refs,'native_receipts_not_certified':True})
for p in am['sidecar_sha256_checks']:check('independent_sidecar_'+p,sha(files[archive+p.removesuffix('.sha256')])==files[archive+p].decode('utf-8-sig').split()[0])
formal=doc(archive+'formal_report.json');finding=doc(archive+'findings.json')
check('ae_original_failed_WR18_and_scoped_WR16_17_closure_preserved',formal['software_acceptance']=='failed_WR18; WR16_and_WR17_passed_in_retested_scope; prior_stage0_1_scope_preserved' and formal['reviewed_source_commit']==BASE and [f['id'] for f in finding]==['WR-18'])
check('ae_old_short_Registry_MRE_safe_refusal_explanation_kept',formal['tests']['original_short_inline_MRE']['registry_exit_code']==1 and '安全拒绝' in formal['tests']['original_short_inline_MRE']['registry_meaning'])
qa_required=['qa.txt','qa_first.txt','qa_report.py','qa_report_first.py','qa_measurement_first.txt','qa_report_measurement_first.py']
check('ae_QA_initial_and_measurement_correction_originals_kept',all(archive+'evidence_agent/'+p in files for p in qa_required) and b'ERROR:' in files[archive+'evidence_agent/qa_measurement_first.txt'] and '不是产品' in files[archive+'evidence_agent/qa.txt'].decode('utf-8-sig'))
check('ae_25source_plus1admitted_input_and18listed_scope_kept',formal['platform_evidence_level']['implementation_files']==25 and formal['platform_evidence_level']['task_input_files']==1 and formal['platform_evidence_level']['listing_python_files']==18 and formal['platform_evidence_level']['full_inventory_certified'] is False)

def assigns(data):return {n.targets[0].id:ast.literal_eval(n.value) for n in ast.parse(data).body if isinstance(n,ast.Assign)}
generated=assigns(files['cloud/research_config.py']);prior_generated=assigns(base['cloud/research_config.py'])
impl={Path(p).name:sha(norm(b)) for p,b in files.items() if p.startswith('cloud/qresearch/') and p.endswith('.py')};deploy={p[len('cloud/'):]:sha(norm(b)) for p,b in files.items() if p.startswith('cloud/') and p.endswith('.py')};deployment=doc('audit/deployment.json')
check('implementation_hash_recomputed',sha(canon(impl))==generated['IMPLEMENTATION_SHA256']==deployment['implementation_hash']==dev['implementation_hash'])
check('active_configuration_unchanged',generated['CONFIGURATION']==prior_generated['CONFIGURATION'] and generated['SOURCE_SHA256']==prior_generated['SOURCE_SHA256']==deployment['configuration_hash'])
check('29_deployment_sources_recomputed',len(deploy)==29 and deploy==deployment['source_files'])
budget=doc('config/budget.json');state={'budget':copy.deepcopy(budget),'manifest':copy.deepcopy(manifest)}
fn=next(n for n in ast.parse(files['tools/collection_task_cli.py']).body if isinstance(n,ast.FunctionDef) and n.name=='execution_source_manifest')
ns={'ROOT':Path('IN_MEMORY_ONLY'),'hashlib':hashlib,'canonical_json':canon,'content_hash':lambda v:sha(canon(v)),'source_manifest':lambda:{'source_files':copy.deepcopy(state['manifest'])},'read_json':lambda _:copy.deepcopy(state['budget'])}
exec(compile(ast.fix_missing_locations(ast.Module(body=[fn],type_ignores=[])),'candidate:identity_only','exec'),ns)
identity=lambda:ns['execution_source_manifest']()['source_hash'];exhash=identity();policy=copy.deepcopy(budget);policy.pop('usage');exmap=dict(manifest);exmap['config/budget.json']=sha(canon(policy))
check('execution_identity_recomputed_excludes_only_usage',exhash==sha(canon({'schema':'collection_execution_sources_v1','source_files':exmap})))
state['budget']['usage']={'audit_only':99999};check('usage_mutation_does_not_change_execution_identity',identity()==exhash)
policyprobes=[]
for key in sorted(set(budget)-{'usage'}):
 state['budget']=copy.deepcopy(budget);state['budget'][key]={'audit_only':True};policyprobes.append({'key':key,'identity_changed':identity()!=exhash})
check('all14_other_budget_policy_keys_change_identity',len(policyprobes)==14 and all(v['identity_changed'] for v in policyprobes));state['budget']=copy.deepcopy(budget)
sourceprobes=[]
for p in sorted(set(manifest)-{'config/budget.json'}):
 state['manifest']=copy.deepcopy(manifest);state['manifest'][p]='f'*64;sourceprobes.append({'path':p,'identity_changed':identity()!=exhash})
check('all121_nonbudget_manifest_files_affect_identity',len(sourceprobes)==121 and all(v['identity_changed'] for v in sourceprobes));state['manifest']=copy.deepcopy(manifest)
preview=doc('audit/stage2_joint_preview.json')
check('preview_matches_original_actual_stdout',json.loads(files[devroot+'original_current_preview.stdout'])==preview)
check('preview_new_identity_plan_and_deployment_hashes',preview['source_manifest_hash']==preview['plan']['source_manifest_hash']==exhash and preview['deployment_hash']==sha(canon(deploy)) and preview['plan_hash']==sha(canon(preview['plan'])))
check('preview_no_admission_dispatch_registration',all(preview[k] is False for k in ('configuration_registered','execution_started','ready_to_dispatch','budget_admission_performed')))
check('previous_preview_original_content_matches_fixed_ae',json.loads(files[devroot+'original_prior_joint_preview.json'])==json.loads(base['audit/stage2_joint_preview.json']))
protected=[p for p in base if p.startswith(('config/','templates/','audit/runtime/','audit/task_inputs/','audit/tool_observations/')) or p in ('audit/data_exposure.json','audit/engineering_current.json','audit/stage2_cloud_deployment.json','audit/stage2_live_preflight.json','audit/stage2_live_project_listing.json','audit/stage2_real_execution.json','docs/research_charter.md','AGENTS.md','tools/stage2.py')]
protectedbad=[p for p in protected if files.get(p)!=base[p]]
check('budget_old_attempt_input_pointer_switch_exposure_WR17_CLI_unchanged',not protectedbad,{'paths':len(protected),'changed':protectedbad})
check('no_new_authoritative_runtime_or_old_task_input',not [p for p in set(files)-set(base) if p.startswith(('audit/runtime/','audit/task_inputs/'))])
events=[];previous=None;raw=files['audit/runtime/registry/events.jsonl'];check('journal_tail_complete',raw.endswith(b'\n'))
for i,line in enumerate(raw.splitlines(),1):
 envelope=json.loads(line);body={k:v for k,v in envelope.items() if k!='hash'};check('journal_event_'+str(i)+'_chain',envelope['sequence']==i and envelope['previous_hash']==previous and sha(canon(body))==envelope['hash']);events.append(envelope['event']);previous=envelope['hash']
usage=copy.deepcopy(events[0]['initial_usage']);attempts={}
for e in events[1:]:
 if e['kind'] in ('config_registered','attempt_started'):
  st='configurations' if e['kind']=='config_registered' else e['stage'];usage[st]['total']+=1;usage[st][e['allocation']]+=1
 if e['kind']=='attempt_started':attempts[e['attempt_id']]=dict(e,status='started')
 if e['kind'] in ('pending','ambiguous','failed','completed'):attempts[e['attempt_id']].update(e,status=e['kind'])
totals={s:usage[s]['total'] for s in ('configurations','research','lean')};pending=attempts['bfd00f2611fd4496b9498d4597618a8e']
check('12_events_independent_replay6_9_1',len(events)==12 and list(totals.values())==[6,9,1] and totals==dev['budget_used'])
check('archived_pending_identity_unchanged_current_terminal_unknown',pending['status']=='pending' and pending['external_id']=='39cafa1e9b11f91b27e396b66d033a6d')
flags=doc('config/development.json')['execution'];check('all_four_execution_flags_false',all(flags[k] is False for k in ('market_research_enabled','llm_runtime_enabled','final_test_enabled','live_trading_enabled')))
ready=doc('audit/stage2_current_readiness.json')
check('readiness_keeps_WR18_pending_fullsystem_financial_limits',ready['stage2_status']=='failed_reviewed_ae_WR18_pending_repair_retest' and ready['known_open_findings']==['WR-18'] and ready['independent_offline_accepted_stages']==[0,1] and ready['candidate_cloud_deployed'] is False and ready['financial_evidence'] is False and ready['current_platform_lean_status'] is None)
comparison=doc(archive+'cloud_comparison.json');oldreference={v['path'] for v in comparison['files'] if v['path']!='_engineering_task_input.py'};different=[v['path'] for v in comparison['files'] if v['raw_equal_candidate'] is False];missing=sorted(set(deploy)-oldreference);declared=ready['platform_comparison_from_independent_review']['candidate_different_or_missing_paths'];actual=len(different)+len(missing)
check('readiness_ae_reference_different_or_absent_count_matches_saved_comparison',declared==actual,{'declared':declared,'computed':actual,'ae_existing_different_from_old25_reference':different,'ae_paths_absent_from_old25_reference':missing,'not_cloud_inventory_certification':True})
if declared!=actual:discrepancies.append({'id':'WR-19','severity':'P3_nonblocking_metadata','file':'audit/stage2_current_readiness.json','field':'platform_comparison_from_independent_review.candidate_different_or_missing_paths','declared':declared,'actual':actual,'basis':'Archived ae reference comparison:9 existing implementations differ plus4 ae paths absent from old25 reference. No new QC read; this does not prove actual current cloud absence. Top-level dc49 historical12 remains valid in its historical scope.'})
source_after={p.relative_to(SOURCE).as_posix():p.read_bytes() for p in SOURCE.rglob('*') if p.is_file()};check('candidate_source_unchanged_after_all_metadata_probes',source_after==disk)
report={'fixed_candidate':SHA,'baseline':BASE,'scope':'Independent raw Git/evidence/archive/ZIP/AST/identity/JSON checks and event replay; no software suite or QC',
 'check_count':len(checks),'passed_checks':sum(c['passed'] for c in checks),'failed_checks':sum(not c['passed'] for c in checks),'unit_test_methods_executed':0,'software_453_suite_rerun':False,'QC_market_model_calls':0,
 'source':{'files':len(files),'raw_bytes_equal_Git':not bad,'review_files':len(manifest),'review_hash':review_hash,'execution_hash':exhash,'identity_deltas':deltas},
 'deployment':{'Python_files':len(deploy),'local_deployment_hash':sha(canon(deploy)),'implementation_hash':generated['IMPLEMENTATION_SHA256'],'active_configuration_hash':generated['SOURCE_SHA256'],'not_cloud_deployment_certification':True},
 'complete_diff':diff,'runtime_diff':prod,'old_evidence_files_unchanged':len(old_evidence),'developer_originals':developer_originals,'developer_saved_raw_transcript_counts':raw_counts,
 'developer_replay_boundary':'62 developer outputs and7 existing-script refs are developer evidence, not independent software results. Original9 and full MRE raw before/after retained; short MRE safety exception documented; no remote provenance inferred from raw hashes.',
 'prior_independent_archive':{'originals':archive_rows,'reused':reused,'full_artifact_entries_verified':len(artifact),'fixed_source_checks':source_proofs,'ZIP_sha256':sha(zp.read_bytes()),'reference_manifests':refcounts},
 'protected_metadata':{'paths':len(protected),'changed':protectedbad},'budget':{'events':len(events),'usage':usage,'limits':events[0]['limits'],'pending_attempt':{k:pending[k] for k in ('attempt_id','stage','status','external_id')}},
 'preview':{'plan_hash':preview['plan_hash'],'read_only_no_admission':True,'independent_replay':'build_preview_verification.json'},'policy_influence_probes':policyprobes,'source_influence_probes':sourceprobes,
 'first_run_measurement_correction':{'first_checks':634,'first_passed':627,'first_nonconforming':7,'measurement_errors':6,'real_metadata_discrepancies':1,'cause':'CRLF final OK lines in six compatibility stderr transcripts were not normalized before regex parsing. Original raw byte/hash checks were correct. First script,report,stdout/stderr preserved; only reviewer parser corrected.'},
 'discrepancies':discrepancies,'checks':checks,'boundary':'No real market/model/platform operation, deployment or old terminal read. Financial certification and full-stage/system acceptance not implied.','financial_evidence':False}
p=OUT/'evidence_verification.json';p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');(OUT/'evidence_verification.json.sha256').write_text(sha(p.read_bytes())+'  evidence_verification.json\n',encoding='utf-8')
print(json.dumps({k:report[k] for k in ('fixed_candidate','check_count','passed_checks','failed_checks','unit_test_methods_executed','source','deployment','budget','discrepancies')},ensure_ascii=False,indent=2))
for c in checks:
 if not c['passed']:print('FAILED',c)
raise SystemExit(0 if all(c['passed'] for c in checks) else 1)
