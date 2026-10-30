"""Pure identity mutation, readiness and raw developer transcript accounting."""
from pathlib import Path
import ast,copy,hashlib,json,re
ROOT=Path(__file__).resolve().parents[1];OUT=Path(__file__).resolve().parent;S=ROOT/'source'
BASE=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-8f7236e-20261027\source')
D=S/'audit/review_packages/wr16_wr17'
def canon(v):return json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def hashes(root):return {p.relative_to(root).as_posix():sha(p.read_bytes()) for p in root.rglob('*') if p.is_file()}
before=hashes(S);checks=[]
def check(name,passed,detail=None):checks.append({'check':name,'passed':bool(passed),'detail':detail})
manifest=read(S/'audit/stage_verification.json')['source_files'];budget=read(S/'config/budget.json')
state={'manifest':copy.deepcopy(manifest),'budget':copy.deepcopy(budget)}
fn=next(n for n in ast.parse((S/'tools/collection_task_cli.py').read_bytes()).body if isinstance(n,ast.FunctionDef) and n.name=='execution_source_manifest')
ns={'ROOT':Path('IN_MEMORY_ONLY'),'hashlib':hashlib,'canonical_json':canon,'content_hash':lambda v:sha(canon(v)),
    'source_manifest':lambda:{'source_files':copy.deepcopy(state['manifest'])},'read_json':lambda _:copy.deepcopy(state['budget'])}
exec(compile(ast.fix_missing_locations(ast.Module(body=[fn],type_ignores=[])),'candidate:identity_mutation','exec'),ns)
identity=lambda:ns['execution_source_manifest']()['source_hash']
original=identity();state['budget']['usage']={'arbitrary_usage_probe':999999}
check('usage_only_mutation_does_not_change_execution_identity',identity()==original)
state['budget']=copy.deepcopy(budget);policy_probes=[]
for key in sorted(set(budget)-{'usage'}):
    state['budget']=copy.deepcopy(budget);state['budget'][key]={'audit_only_policy_probe':True}
    policy_probes.append({'top_level_policy_key':key,'identity_changed':identity()!=original})
check('every_other_budget_top_level_policy_key_changes_execution_identity',all(p['identity_changed'] for p in policy_probes),policy_probes)
state['budget']=copy.deepcopy(budget);source_probes=[]
for p in sorted(set(manifest)-{'config/budget.json'}):
    state['manifest']=copy.deepcopy(manifest);state['manifest'][p]='f'*64
    source_probes.append({'path':p,'identity_changed':identity()!=original})
check('all119_nonbudget_review_files_affect_execution_identity',len(source_probes)==119 and all(p['identity_changed'] for p in source_probes))
state['manifest']=copy.deepcopy(manifest)
oldmanifest=read(BASE/'audit/stage_verification.json')['source_files']
deltas=[{'path':p,'kind':'added' if p not in oldmanifest else 'removed' if p not in manifest else 'modified','old_normalized_sha256':oldmanifest.get(p),'new_normalized_sha256':manifest.get(p)} for p in sorted(set(oldmanifest)|set(manifest)) if oldmanifest.get(p)!=manifest.get(p)]
check('manifest_growth117_to120_is_exactly_new_review_doc_and_two_tests',len(oldmanifest)==117 and len(manifest)==120 and {p for p in manifest if p not in oldmanifest}=={'docs/review/wr16-wr17.md','tests/test_wr16_registry_admission.py','tests/test_wr17_engineering_recovery.py'})
ready=read(S/'audit/stage2_current_readiness.json')
check('readiness_keeps_repair_pending_and_only_prior0_1_stages',ready['stage2_status']=='failed_reviewed_8f_joint_candidate_pending_repair_retest' and ready['independent_offline_accepted_stages']==[0,1] and ready['known_open_findings']==['WR-16','WR-17'] and ready['new_candidate_independently_accepted'] is False)
check('readiness_does_not_treat_new_identity_as_actual_config_or_budget',ready['source_changed'] is True and ready['active_research_configuration_changed'] is False and ready['authoritative_budget_changed'] is False and ready['candidate_cloud_deployed'] is False)
check('readiness_retains_cloud_comparison_as_8f_archived_not_new_read',ready['platform_comparison_from_independent_review']['candidate_commit']=='8f7236ecbafcb514f07a6af4150a5afdbc1fd474' and ready['platform_comparison_from_independent_review']['this_archival_turn_new_QC_read'] is False)
check('readiness_retains_pending_unknown_terminal_and_financial_false',ready['last_archived_lean_status']=='pending' and ready['current_platform_lean_status'] is None and ready['financial_evidence'] is False and ready['read_or_polled_this_turn'] is False)
def transcript(name):
    text=(D/name).read_text(encoding='utf-8-sig');fails=re.findall(r'^FAIL: (test_\w+)',text,re.M);errors=re.findall(r'^ERROR: (test_\w+)',text,re.M)
    ran=re.search(r'^Ran (\d+) tests? in ',text,re.M)
    return {'path':name,'methods':int(ran.group(1)),'failure_records':len(fails),'failed_methods':len(set(fails)),'error_records':len(errors),'error_methods':len(set(errors)),'success':bool(re.search(r'^OK$',text,re.M)),'all_error_types':sorted(set(re.findall(r'^(\w+(?:Error|Exception)): ',text,re.M)))}
raw_counts={k:transcript(v) for k,v in {'WR16_before':'original_wr16-before__new_tests.stderr','WR16_final':'original_wr16-final8__new_tests.stderr','WR17_before':'original_wr17-tests-baseline__stderr','WR17_repair':'original_wr17-tests-repair__stderr'}.items()}
wr16=raw_counts['WR16_before'];wr17=raw_counts['WR17_before']
check('WR16_raw_transcript6methods4failed10failure_records',wr16['methods']==6 and wr16['failed_methods']==4 and wr16['failure_records']==10 and wr16['error_records']==0)
check('WR16_raw_final8methods_OK',raw_counts['WR16_final']['methods']==8 and raw_counts['WR16_final']['success'])
check('WR17_raw_transcript11methods4failed5errored9fail10error_records',wr17['methods']==11 and wr17['failed_methods']==4 and wr17['error_methods']==5 and wr17['failure_records']==9 and wr17['error_records']==10)
check('WR17_raw_repair11methods_OK',raw_counts['WR17_repair']['methods']==11 and raw_counts['WR17_repair']['success'])
def methods(path):return {n.name:ast.dump(n,include_attributes=False) for c in ast.parse(path.read_bytes()).body if isinstance(c,ast.ClassDef) for n in c.body if isinstance(n,ast.FunctionDef) and n.name.startswith('test_')}
beforemethods=methods(D/'original_wr16-before__test_input.py');aftermethods=methods(S/'tests/test_wr16_registry_admission.py')
wr16changes={'baseline_methods':len(beforemethods),'final_methods':len(aftermethods),'added':sorted(set(aftermethods)-set(beforemethods)),'removed':sorted(set(beforemethods)-set(aftermethods)),'modified_existing_methods':[p for p in beforemethods if beforemethods[p]!=aftermethods.get(p)]}
check('WR16_six_existing_test_method_ASTs_unchanged_two_added',len(beforemethods)==6 and len(aftermethods)==8 and not wr16changes['removed'] and not wr16changes['modified_existing_methods'],wr16changes)
check('source_all1843_raw_bytes_unchanged_after_supplement',before==hashes(S) and len(before)==1843)
report={'scope':'Pure identity mutations in memory, readiness, and saved transcript accounting; no test suite rerun',
 'checks':checks,'check_count':len(checks),'passed_checks':sum(c['passed'] for c in checks),'failed_checks':sum(not c['passed'] for c in checks),
 'unit_test_methods_executed':0,'QC_market_model_calls':0,'identity_source_deltas':deltas,'policy_probes':policy_probes,'source_influence_probes':source_probes,'developer_raw_transcript_counts':raw_counts,
 'inspection_path_lookup':{'exit_code':1,'cause':'Optional inspection used guessed original_wr16-before.stdout, which does not exist; directory listing succeeded. Correct raw filename original_wr16-before__new_tests.stderr was read and independently parsed here. No software command or candidate modification was involved.'},
 'boundary':'Developer baseline errors are missing recovery product behavior, not reviewer setup errors. These raw transcript counts are checked, but repair acceptance belongs to the separate independent software audit. No new runtime cloud comparison.'}
p=OUT/'supplemental_verification.json';p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');(OUT/'supplemental_verification.json.sha256').write_text(sha(p.read_bytes())+'  supplemental_verification.json\n',encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k not in ('source_influence_probes','checks')},ensure_ascii=False,indent=2))
for c in checks:
    if not c['passed']:print('FAILED',c)
raise SystemExit(0 if all(c['passed'] for c in checks) else 1)
