from pathlib import Path
from hashlib import sha256
import json, sys
sys.dont_write_bytecode=True
A=Path(__file__).resolve().parent;R=A.parent
expected='224a7b8a0e7667b6759e685f71dae0fd54ba0eb6c914ced1c9c1332deb009e14'
reportfile=R/'formal_report.json';textfile=R/'formal_report.txt'
raw=reportfile.read_bytes();formal=json.loads(raw);text=textfile.read_text(encoding='utf-8')
child= json.loads((A/'report.json').read_text(encoding='utf-8'))
checks=[];issues=[]
def check(name,condition,detail=None):
    check={'name':name,'passed':bool(condition),'detail':detail};checks.append(check)
    if not condition:issues.append(check)
check('formal_fixed_hash',sha256(raw).hexdigest()==expected)
check('source_full_SHA',formal['reviewed_source_commit']=='2d1d3060dbc7eb136c1dee61f0647977528b8aad')
check('materials_full_SHA',formal['evidence_commits']['materials']=='fe088461e84586d7feb73f20be54a22d09706942')
check('candidate_identity_hash',formal['source_manifest_hash']=='74bbefc270a6bd0d1385db9624eaa2bd600e38503f5932a88267a02a11c76a07')
identity=formal['version_consistency'];archive=formal['archive_verification'];budget=formal['budget_replay'];platform=formal['platform_evidence_level']
check('raw_source_count',identity['source_raw_files']==7080==child['source_guard']['source']['files'])
check('raw_materials_count',identity['materials_raw_files']==7445==child['source_guard']['materials']['files'])
check('managed_identity216_prior213',identity['managed_identity_files']==216 and identity['prior_managed_files']==213)
check('only3_managed_additions',identity['new_managed_files']==['docs/followup_host.md','tests/test_followup_host.py','tools/followup_host.py'] and not identity['prior_managed_changes'])
check('deployment44_unchanged',identity['deployment_files']==44 and identity['deployment_raw_unchanged_from975'] is True)
check('source_materials_managed_equal',identity['source_materials_managed_equal'] is True)
check('export_guard_no_changes',identity['source_and_materials_guard_changes']==[] and all(not x['changed'] for x in child['source_guard'].values()))
check('only_expected_generated_report_scratch_change',identity['scratch_changes']==['audit/stage_verification.json'])
check('materials57',identity['current_packet_files']==57==child['current_packet_raw_files'])
check('static59339_not_unit',archive['static_file_blob_metadata_checks']==59339==child['static_logical_checks'] and archive['static_checks_are_not_unit_methods'] is True)
check('old_ZIP_dictionary_exact',archive['old_complete_ZIP']==child['old_complete_ZIP'])
check('old_ZIP14330map14331entries',archive['old_complete_ZIP']['manifest_entries']==14330 and archive['old_complete_ZIP']['ZIP_entries']==14331)
check('old_Git7045_7076',archive['old_complete_ZIP']['complete_old_Git_blob_counts']=={'source':7045,'materials':7076})
check('old_ZIP_CRC_passed',archive['old_complete_ZIP']['CRC'] is True)
check('old_ZIP_pinned_raw_hash',archive['old_complete_ZIP']['raw_sha256']=='c4437f468fdb57797832df564eb917f3798cc1fe6b6f87dbe39bef6bf7bcace4')
check('selected_archive_dictionary_exact',archive['selected_archive']==child['selected_archive'])
selection=archive['selected_archive']
check('205_originals_1756416bytes',selection['originals']==205 and selection['original_bytes']==1756416)
check('100raw_105base64mirror',selection['direct_raw']==100 and selection['mirrors_with_raw_base64']==105)
check('311representations_312files',selection['representation_files']==311 and selection['actual_files']==312)
check('selected_not_full',selection['scope_not_full_original_bundle'] is True and archive['selected_archive_is_complete_original_bundle'] is False)
check('actual_local_Codex_identity',selection['actual_reviewer']=='local Codex thread 01a175b6-fed2-77d0-a763-522b6fd695cf; former ChatGPT handoff only')
check('developer_guard_exact_to_child',archive['developer_guard']==child['developer_guard'])
guard=archive['developer_guard']
check('guard346_before_after',guard['records']==346 and guard['before_after_exact_equal'] is True)
check('guard5_CRLF_named',guard['recorded_worktree_CRLF_vs_Git']==['audit/data_exposure.json','cloud/main.py','config/data.json','config/research.json','docs/review/phase0-phase1/manifest.json'])
check('not_live_developer_worktree_observation',guard['original_developer_worktree_live_observation'] is False)
check('provisional14_scope_retained','原c5 Git blob保留' in archive['provisional14_synthetic_store_records'] and '未检出长路径' in archive['provisional14_synthetic_store_records'])
tests={row['name']:row for row in formal['tests']}
expected_replays={
 'prior_Windows_lock_replayed_on_current_source':(18,37),
 'prior_notification_main_replayed':(12,79),
 'prior_notification_supplement_replayed':(6,27),
 'prior_cycles_rounds_replayed':(7,28)}
for name,(methods,scenarios) in expected_replays.items():
    row=tests[name]
    check('replay_numbers:'+name,row['methods']==methods and row['scenarios']==scenarios and row['passed']==methods)
    check('replay_actual_success:'+name,row['actually_executed'] is True and row['failures']==row['errors']==row['skips']==0 and row['kind']=='original_independent_suite_replay')
check('43methods171scenarios_not_grand_total',sum(tests[k]['methods'] for k in expected_replays)==43 and sum(tests[k]['scenarios'] for k in expected_replays)==171 and '不相加' in text and bool(formal['counting']))
history=formal['historical_findings']
check('WR_original_scopes_only','原精确SHA和有限范围' in history['WR01_WR28'])
check('prior975_original_formal_hash',history['prior_formal_raw_sha256']=='ef0fa58a5e87d0930ed7b6c6ddbd11a1b96ecc0ea56678dd7989dbee2a890057')
check('not_all_WR_suites_rerun',history['all_original_WR_suites_rerun_this_round'] is False)
check('embedded_old_SHA_scope_explicit','脚本内旧SHA仅历史标签' in history['new_prior_independent_replays'])
check('budget71_hash',budget['events']==71 and budget['journal_sha256']==child['budget']['journal_sha256'])
check('prior69_raw_prefix',budget['prior69_prefix_sha256']=='2d3131a32864434d22635f058ec3de8062e9b1b610a90185bf6ba6cf9c637934' and budget['prior69_prefix_raw_preserved'] is True)
check('cycle3of13_lifetime16',budget['configuration_cycle']=={'used':3,'limit':13} and budget['lifetime_configurations']==16)
check('R17of20_L3of16',budget['Research']=={'used':17,'limit':20} and budget['LEAN']=={'used':3,'limit':16})
check('008closed_noevents_nodebits_norefund',budget['round008']=='closed' and budget['new_events']==budget['new_debits']==budget['refunds']==0)
check('human_authorization_not_independently_obtained',budget['original_human_authorization_dialogue_independently_obtained'] is False)
check('future111_not_authorized',budget['future_1_1_1']=='仅准备，无授权/准入/attempt/project/backtest ID')
check('no_live_QC_claim','无独立QC访问' in platform['current_review'] and '本轮不重复宣称新QC运行' in platform['historical_b1a'])
check('historicalR13L7only',platform['historical_Research_checks']==13 and platform['historical_LEAN_checks']==7 and platform['historical_orders']==0)
check('historical43_raw_0ResearchEOF_43LEANEOF',platform['historical_PROJECT_raw_files']==43 and platform['historical_Research_EOF_normalized']==0 and platform['historical_LEAN_EOF_normalized']==43 and platform['historical_LEAN_original_source_identity_match'] is False)
check('historical_terminal_not_push','一次历史对账' in platform['historical_terminal'] and '未观测自动push' in platform['historical_terminal'])
check('new_source_cloud_unknown',platform['new_source_cloud_run'] is None and platform['new_source_orders'] is None)
check('archive_first_encoding_error_disclosed','UTF8' in formal['reviewer_corrections']['archive'] and 'GBK' in formal['reviewer_corrections']['archive'])
software=formal['software_acceptance']
check('new_stdio_WR29_fails',software['new_host_enabled_CLI_stdio']=='失败_WR29' and software['new_host_component_overall']=='不通过')
check('stage2_not_accepted',software['stage2_overall']=='未通过' and software['real_host_engineering_chain']=='未验收')
check('prior_scope_retained',software['prior975_scope']=='原有限通过保留')
check('gates_closed',all(software[k] is False for k in ('formal_research_enabled','GPT_runtime_enabled','orders_enabled','final_test_enabled')))
check('financial_false',formal['financial_evidence'] is False and all(v is None for v in formal['financial_metrics'].values()))
check('WR29_not_archival_new_finding',len(formal['findings'])==1 and formal['findings'][0]['id']=='WR-29')
embedded_start=text.split('完整机器报告：',1)[1].lstrip()
obj,end=json.JSONDecoder().raw_decode(embedded_start)
check('text_JSON_object_exact',obj==formal)
check('text_reproduction_separate','实际最小复现' in embedded_start[end:])
check('formal_raw_unchanged_by_QA',reportfile.read_bytes()==raw)
check('archive_subreport_raw_unchanged',sha256((A/'report.json').read_bytes()).hexdigest()=='357e80f05c599a3914a6c4f67b863305fc7e23b076d55fcf7c5f0842e9967a0f')
result={'reviewed_formal_report_sha256':expected,'actual_formal_report_sha256':sha256(raw).hexdigest(),'formal_text_sha256':sha256(textfile.read_bytes()).hexdigest(),'kind':'read_only_static_QA_not_unit_tests','checks':checks,'check_count':len(checks),'passed':sum(x['passed'] for x in checks),'issues':issues,'source_or_formal_report_writes':0,'tests_rerun':0,'cloud_calls':0}
(A/'formal_QA.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k!='checks'},ensure_ascii=False),flush=True)
sys.exit(bool(issues))
