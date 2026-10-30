"""WR19 metadata/evidence local verification; no suite/build/identity/platform call."""
from pathlib import Path
import hashlib,io,json,subprocess,tarfile,zipfile
R=Path(__file__).resolve().parents[1];O=Path(__file__).resolve().parent;S=R/'source'
G=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\repo')
OLD=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-81fbe52-20261027')
B=Path(r'B:\BaiduSyncdisk\学习\投资\量化\量化交易比赛\LLM审核\review-81fbe52-20261027')
SHA='84414ab49c39e25cb50ece1c1debeefa3993c874';BASE='81fbe5294055423e88ee5aeae48ca6223e7971da';AE='ae2b8985f3799c246e90341370f86d80483f63ed'
checks=[]
def canon(v):return json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def check(n,ok,detail=None):checks.append({'check':n,'passed':bool(ok),'detail':detail})
def gitfiles(rev):
 raw=subprocess.check_output(['git','-C',str(G),'archive',rev])
 with tarfile.open(fileobj=io.BytesIO(raw)) as t:return {m.name:t.extractfile(m).read() for m in t.getmembers() if m.isfile()}
files=gitfiles(SHA);base=gitfiles(BASE);ae=gitfiles(AE);doc=lambda p:json.loads(files[p])
disk={p.relative_to(S).as_posix():p.read_bytes() for p in S.rglob('*') if p.is_file()}
bad=[p for p in set(files)|set(disk) if files.get(p)!=disk.get(p)]
check('2890_fixed_Git_file_set',len(files)==2890 and set(files)==set(disk))
check('all2890_raw_source_bytes_equal_fixed_Git',not bad,bad)
diff=[{'path':p,'change':'added' if p not in base else 'removed' if p not in files else 'modified','old_raw_sha256':sha(base[p]) if p in base else None,'new_raw_sha256':sha(files[p]) if p in files else None} for p in sorted(set(files)|set(base)) if files.get(p)!=base.get(p)]
runtime=[p for p in base if p.startswith(('cloud/','config/','tools/','templates/','tests/'))]
check('runtime_config_tools_templates_tests_all_unchanged',all(files.get(p)==base[p] for p in runtime) and not [p for p in set(files)-set(base) if p.startswith(('cloud/','config/','tools/','templates/','tests/'))],{'unchanged_files':len(runtime)})
existing_evidence=[p for p in base if p.startswith(('audit/reviews/','audit/review_packages/'))]
check('all_prior_review_and_failure_evidence_unchanged',all(files.get(p)==base[p] for p in existing_evidence),{'files':len(existing_evidence)})

D='audit/review_packages/wr19/';dev=doc(D+'developer_verification.json');dm=doc(D+'original_files_manifest.json');developer_originals=[]
for e in dm['files']:
 b=files[D+e['path']];ok=sha(b)==e['raw_sha256'] and len(b)==e['bytes'];check('developer_raw_'+e['path'],ok);developer_originals.append({'path':e['path'],'raw_sha256':sha(b),'bytes':len(b),'passed':ok})
check('22_developer_original_manifest_raw_declaration',len(developer_originals)==22==dm['file_count']==dev['saved_original_files'] and sha(files[D+'original_files_manifest.json'])==dev['original_files_manifest_raw_sha256'])
check('WR19_developer_raw_bytes_protection','audit/review_packages/wr19/** -text' in files['.gitattributes'].decode('utf-8-sig'))
check('original_wrong_Git_readiness_saved_raw',files[D+'original_readiness_Git_81fbe52.json']==base['audit/stage2_current_readiness.json'])
before=doc(D+'original_before.stdout');after=doc(D+'original_after.stdout');runs=doc(D+'original_reproduction_runs.json')
check('developer_before12_after13_output_evidence_not_software_acceptance',before['declared']==12 and after['declared']==13 and before['computed']==after['computed']==13 and before['candidate_paths']==after['candidate_paths']==29 and before['old_known_reference_paths']==after['old_known_reference_paths']==25 and runs['before_exit']==dev['before_original_MRE_exit']==1 and runs['after_exit']==dev['after_original_MRE_exit']==0)
for phase,expected in [('before',1),('after',0)]:
 ex=doc(D+'original_peer_'+phase+'_execution.json');audit=doc(D+'original_peer_'+('pre' if phase=='before' else 'post')+'_fix_comparison_audit.json')
 check('developer_peer_'+phase+'_raw_record_boundary',ex['exit_code']==expected and ex['expected_exit_code']==expected and audit['declared_total']==(12 if phase=='before' else 13) and audit['computed_total']==13 and audit['actual_cloud_or_market_or_model_calls']==0 and audit['current_cloud_missing_files_proven'] is False and audit['current_cloud_inventory_certified'] is False)
ge=doc(D+'git_export_verification.json')
check('developer_Git_export_two_records_and_raw_outputs',ge['both_commands_passed'] is True and len(ge['runs'])==2 and all(v['exit_code']==0 for v in ge['runs']) and all(p in files for p in ge['paths']) and json.loads(files[D+'original_Git_export_original_minimal_wr19.py.stdout'])==after and files[D+'original_Git_export_original_minimal_wr19.py.stderr']==files[D+'original_Git_export_verify_archived_comparison.py.stderr']==b'')
check('developer_scope_keeps81_software_identity_and_no_new_runtime',dev['purpose']=='WR19_nonblocking_metadata_correction_not_new_software_acceptance' and dev['independently_accepted_software_commit']==BASE and dev['documentation']=='docs/review/wr19.md' and dev['whole_system']=='not_accepted' and dev['cloud_deployed'] is False and dev['financial_evidence'] is False)

A='audit/reviews/20261027-81fbe52-windows/';am=doc(A+'archive_manifest.json');archive_rows=[]
for e in am['files']:
 b=files[A+e['archive_path']];origins=[str(p) for p in (B/e['origin_relative_path'],OLD/e['origin_relative_path']) if p.is_file() and p.read_bytes()==b]
 ok=sha(b)==e['raw_sha256'] and len(b)==e['bytes'] and bool(origins);check('81_independent_original_'+e['archive_path'],ok);archive_rows.append({'path':e['archive_path'],'raw_sha256':sha(b),'bytes':len(b),'matching_originals':origins,'passed':ok})
check('487_originals_declared_bytes_and_manifest',len(archive_rows)==487==am['file_count']==dev['original_archive_files'] and sum(v['bytes'] for v in archive_rows)==am['total_original_bytes'] and sha(files[A+'archive_manifest.json'])==dev['original_archive_manifest_raw_sha256']==doc('audit/81fbe52_review_archive_check.json')['archive_manifest_raw_sha256'])
reused=[]
for e in am['reused_existing_evidence']:
 b=files[e['existing_archive_path']];origin=B/e['origin_relative_path'];ok=origin.is_file() and origin.read_bytes()==b and sha(b)==e['raw_sha256'] and len(b)==e['bytes'];check('81_reused_original_'+e['origin_relative_path'],ok);reused.append({'path':e['existing_archive_path'],'origin':str(origin),'passed':ok})
check('27_deduplicated_original_refs',len(reused)==27)
artifact=doc(A+'artifact_manifest.json');artifactbad=[p for p,h in artifact.items() if not (B/p).is_file() or sha((B/p).read_bytes())!=h]
check('4754_final_artifact_entries_raw_equal_B_original',len(artifact)==4754==am['full_original_artifact_manifest_hash_checks'] and artifact==json.loads((B/'artifact_manifest.json').read_text(encoding='utf-8-sig')) and not artifactbad,artifactbad)
source_proofs=[]
for label,path,mapping in [('candidate',B/'source',base),('baseline_ae',B/'baselines/ae2b898/source',ae)]:
 actual={p.relative_to(path).as_posix():p.read_bytes() for p in path.rglob('*') if p.is_file()};mismatch=[p for p in set(actual)|set(mapping) if actual.get(p)!=mapping.get(p)]
 check('81_final_package_'+label+'_source_raw_equals_fixed_Git',not mismatch and len(mapping)==am['source_Git_blob_checks'][label]['files'],{'files':len(mapping),'mismatches':mismatch});source_proofs.append({'label':label,'files':len(mapping),'all_equal_Git':not mismatch})
zp=Path(am['review_zip']['path'])
with zipfile.ZipFile(zp) as z:
 check('81_final_ZIP_raw_SHA_CRC_unique_paths',sha(zp.read_bytes())==am['review_zip']['raw_sha256'] and z.testzip() is None and len(z.namelist())==len(set(z.namelist())))
 zipbad=[p for p,h in artifact.items() if sha(z.read(B.name+'/'+p))!=h];check('all4754_final_ZIP_entries_equal_original_manifest',not zipbad and am['review_zip']['verified_entries']==4754,zipbad)
for e in am['omitted']:
 p=B/e['path'];check('declared_omitted_original_hash_'+e['path'],p.is_file() and sha(p.read_bytes())==e['raw_sha256'])
for p in am['sidecar_sha256_checks']:check('independent_sidecar_'+p,sha(files[A+p.removesuffix('.sha256')])==files[A+p].decode('utf-8-sig').split()[0])
formal=doc(A+'formal_report.json');findings=doc(A+'findings.json')
check('original81_scoped_software_pass_and_WR19_open_not_rewritten',formal['software_acceptance']=='passed_retested_WR18_and_offline_regressions; nonblocking_WR19_open; full_stage2_pending' and [f['id'] for f in findings]==['WR-19'] and formal['reviewed_source_commit']==BASE and formal['data_certification'] is False and formal['financial_evidence'] is False)
first=doc(A+'evidence_agent/evidence_verification_first.json');corrected=doc(A+'evidence_agent/evidence_verification.json')
check('original634_measurement_errors_and_true_difference_retained',first['check_count']==634 and first['passed_checks']==627 and first['failed_checks']==7 and corrected['check_count']==634 and corrected['passed_checks']==633 and corrected['failed_checks']==1 and corrected['first_run_measurement_correction']['measurement_errors']==6)
check('original_fixture_error_and_correction_preserved',formal['tests']['admission_initial_auditor_error']['error_methods']==1 and formal['tests']['admission_initial_auditor_error']['assertions_changed'] is False and am['admission_first_fixture_correction']==formal['tests']['admission_initial_auditor_error'])
check('original_short_MRE_safe_refusal_explanation_retained',formal['tests']['original_short_MRE']['candidate_exit']==1 and '安全' in formal['tests']['original_short_MRE']['meaning'] and formal['tests']['original_full_MRE']['baseline_exit']==1 and formal['tests']['original_full_MRE']['candidate_exit']==0)
check('original_WR19_minimal_script_raw_unchanged',files[D+'original_minimal_wr19.py']==files[A+'minimal_wr19.py']==(B/'minimal_wr19.py').read_bytes() and runs['original_script_sha256']==sha(files[D+'original_minimal_wr19.py']))

ready=doc('audit/stage2_current_readiness.json');ref=ready['platform_comparison_from_independent_review'];cm=doc(ref['candidate_manifest_ref']['path'])['candidate'];comparison=doc(ref['archived_platform_comparison_ref']['path'])
candidate={p[6:]:h for p,h in cm['files'].items() if p.startswith('cloud/') and p.endswith('.py')};reference={v['path']:v['cloud_utf8_sha256'] for v in comparison['files'] if v['path']!='_engineering_task_input.py'}
different=sorted(p for p in set(candidate)&set(reference) if candidate[p]!=reference[p]);outside=sorted(set(candidate)-set(reference));same=sorted(p for p in set(candidate)&set(reference) if candidate[p]==reference[p])
check('WR19_current_summary29_25_16_9_4_13_recomputed',len(candidate)==29 and len(reference)==25 and len(same)==16 and len(different)==9 and len(outside)==4 and ref['candidate_different_or_missing_paths']==13 and ref['candidate_known_reference_different_paths']==9 and ref['candidate_paths_not_in_reference']==4 and ref['candidate_manifest_files']==29 and ref['known_reference_files']==25 and ref['differing_known_reference_paths']==different and ref['paths_not_in_known_reference']==outside)
check('WR19_reference_versions_raw_SHA_bindings',cm['commit']==comparison['reviewed_source_commit']==ref['candidate_commit']==AE and all(sha(files[ref[k]['path']])==ref[k]['raw_sha256'] for k in ('candidate_manifest_ref','archived_platform_comparison_ref')))
check('WR19_comparison_does_not_claim_new_cloud_or_inventory',ref['this_archival_turn_new_QC_read'] is False and ref['cloud_inventory_certified'] is False and 'not current platform inventory' in ref['comparison_scope'])
check('original_wrong_declaration_preserved_current_corrected',json.loads(files[D+'original_readiness_Git_81fbe52.json'])['platform_comparison_from_independent_review']['candidate_different_or_missing_paths']==12 and ref['candidate_different_or_missing_paths']==13)
dc=[p for p in base if p.startswith('audit/reviews/20261027-dc49f0f-windows/')]
check('all189_historical_dc49_archive_raw_files_unchanged',len(dc)==189 and all(files.get(p)==base[p] for p in dc))
old_ready=json.loads(base['audit/stage2_current_readiness.json'])
check('historical_dc4912_scope_preserved_in_clarified_current_description','Earlier dc49 count12 remains historical' in ready['deployment_comparison_scope'] and 'No current platform inventory certification' in ready['deployment_comparison_scope'] and ready['WR19_comparison_correction']['original_claim']==old_ready['platform_comparison_from_independent_review'],{'old_explanation':old_ready['deployment_comparison_scope'],'clarified_current_explanation':ready['deployment_comparison_scope']})
check('historical_d0_detail_table_unchanged',ready['deployment_differences']==old_ready['deployment_differences'])
protected=[p for p in base if p.startswith(('config/','templates/','audit/runtime/','audit/task_inputs/','audit/tool_observations/')) or p in ('audit/data_exposure.json','audit/engineering_current.json','audit/stage2_cloud_deployment.json','audit/stage2_live_preflight.json','audit/stage2_live_project_listing.json','audit/stage2_real_execution.json','docs/research_charter.md','AGENTS.md')]
protectedbad=[p for p in protected if files.get(p)!=base[p]];check('all_budget_pointer_pending_input_switch_exposure_protected_bytes_unchanged',not protectedbad,{'paths':len(protected),'changed':protectedbad})
check('no_new_authoritative_attempt_input_or_configuration',not [p for p in set(files)-set(base) if p.startswith(('audit/runtime/','audit/task_inputs/'))])
events=[];prev=None;raw=files['audit/runtime/registry/events.jsonl'];check('journal_tail_complete',raw.endswith(b'\n'))
for i,line in enumerate(raw.splitlines(),1):
 env=json.loads(line);body={k:v for k,v in env.items() if k!='hash'};check('event_'+str(i)+'_sequence_hash_chain',env['sequence']==i and env['previous_hash']==prev and sha(canon(body))==env['hash']);events.append(env['event']);prev=env['hash']
usage=json.loads(json.dumps(events[0]['initial_usage']));attempts={}
for ev in events[1:]:
 if ev['kind'] in ('config_registered','attempt_started'):
  st='configurations' if ev['kind']=='config_registered' else ev['stage'];usage[st]['total']+=1;usage[st][ev['allocation']]+=1
 if ev['kind']=='attempt_started':attempts[ev['attempt_id']]=dict(ev,status='started')
 if ev['kind'] in ('pending','ambiguous','failed','completed'):attempts[ev['attempt_id']].update(ev,status=ev['kind'])
totals={k:usage[k]['total'] for k in ('configurations','research','lean')};pending=attempts['bfd00f2611fd4496b9498d4597618a8e']
check('12_events_independent_usage_replay6_9_1',len(events)==12 and totals==dev['budget_used']=={'configurations':6,'research':9,'lean':1})
check('pending_archived_identity_retained_not_current_status',pending['status']=='pending' and pending['external_id']=='39cafa1e9b11f91b27e396b66d033a6d' and ready['current_platform_lean_status'] is None)
flags=doc('config/development.json')['execution'];check('four_runtime_switches_false',all(flags[k] is False for k in ('market_research_enabled','llm_runtime_enabled','final_test_enabled','live_trading_enabled')))
check('docs_and_readiness_do_not_extend_stage_or_financial_acceptance',ready['new_candidate_acceptance_scope']=='metadata_only; software_acceptance_bound_to81fbe52' and ready['stage2_status']=='pending_platform_runtime_receipts_terminal_and_data_certification' and ready['new_candidate_independently_accepted'] is False and ready['candidate_cloud_deployed'] is False and ready['financial_evidence'] is False)
afterdisk={p.relative_to(S).as_posix():p.read_bytes() for p in S.rglob('*') if p.is_file()};check('all2890_candidate_source_bytes_unchanged_after_static_checks',afterdisk==disk)
report={'fixed_candidate':SHA,'baseline':BASE,'scope':'Metadata-only raw Git/JSON/ZIP/ledger checks; no software suite, build, source/execution identity recomputation or platform call',
 'check_count':len(checks),'passed_checks':sum(v['passed'] for v in checks),'failed_checks':sum(not v['passed'] for v in checks),'software_unit_methods':0,'software_suite_runs':0,'builds':0,'new_QC_market_model_calls':0,'identity_recomputation_performed':False,
 'source':{'raw_files':len(files),'equal_fixed_Git':not bad,'unchanged_after_checks':afterdisk==disk,'runtime_config_tools_templates_tests_unchanged_files':len(runtime)},'complete_diff':diff,
 'old_evidence_files_unchanged':len(existing_evidence),'developer_originals':developer_originals,'developer_boundary':'Saved developer453 output and Git-export records are archived evidence only, not independent runs by this agent. Raw hashes do not independently authenticate historical execution provenance.',
 'prior_independent_archive':{'originals':archive_rows,'reused':reused,'full_artifact_entries_verified':len(artifact),'source_Git_proofs':source_proofs,'ZIP_sha256':sha(zp.read_bytes()),'original_mismatch_and_reviewer_corrections_preserved':True},
 'WR19':{'declared_now':ref['candidate_different_or_missing_paths'],'computed':len(different)+len(outside),'same':same,'different':different,'outside_known_reference':outside,'historical_dc49_files_unchanged':len(dc),'no_actual_current_cloud_inventory_assertion':True},
 'protected_metadata':{'paths':len(protected),'changed':protectedbad},'budget':{'events':len(events),'usage':usage,'limits':events[0]['limits'],'pending_attempt':{k:pending[k] for k in ('attempt_id','stage','status','external_id')}},
 'reviewer_first_measurement':{'checks':590,'passed':589,'nonconforming':1,'product_or_metadata_defects':0,'cause':'Reviewer initially required current comparison explanatory text to be byte-identical. It intentionally clarifies ae13 while explicitly preserving historical dc4912; original raw readiness and189 dc49 historical files are preserved. Corrected the overly strict reading assertion and added a separate unchanged historical d0 table check. First script/report/raw output retained.'},
 'checks':checks,'financial_evidence':False,'boundary':'Software approval remains bound to81fbe52 and prior scopes; full stage2/system and financial/data certification not inferred. Current old LEAN terminal unknown.'}
p=O/'metadata_verification.json';p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');(O/'metadata_verification.json.sha256').write_text(sha(p.read_bytes())+'  metadata_verification.json\n',encoding='utf-8')
print(json.dumps({k:report[k] for k in ('fixed_candidate','check_count','passed_checks','failed_checks','software_unit_methods','source','WR19','protected_metadata','budget')},ensure_ascii=False,indent=2))
for c in checks:
 if not c['passed']:print('FAILED',c)
raise SystemExit(0 if all(c['passed'] for c in checks) else 1)
