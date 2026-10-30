from pathlib import Path
import hashlib,json
O=Path(__file__).resolve().parent
R=O.parent
report_path=R/'formal_report.json'; text_path=R/'formal_report.txt'
before_json=report_path.read_bytes(); before_text=text_path.read_bytes()
sha=lambda raw:hashlib.sha256(raw).hexdigest()
report=json.loads(before_json); text=before_text.decode('utf-8')
own=json.loads((O/'report.json').read_bytes())
supp=json.loads((O/'supplement/report.json').read_bytes())
tests={item['name']:item for item in report['tests']}
checks=[]
def check(name,condition,detail=None):
    checks.append({'name':name,'passed':bool(condition),'detail':detail})
check('fixed_formal_report_hash',sha(before_json)=='aad0c66f970efe90f53e1877028ab4dbda07778651de66868f4774266b9e82ad')
check('fixed_source_identity',report['reviewed_source_commit']==own['source_commit']==supp['source_commit'])
check('fixed_materials_identity',report['evidence_commits']['materials']==own['materials_commit']==supp['materials_commit'])
check('prior_lock_report_preserved',sha((O/'report.json').read_bytes())=='db046704ec8a3ea242adbee32aa689e76b6b51d79b7f8d4cf315cfbc2c491c39')
check('supplement_report_preserved',sha((O/'supplement/report.json').read_bytes())=='a3d4670ba392b8858af4dff3d2ba46641a0df42e5a88697bf4ca940103856ca4')
lock=tests['independent_Windows_lock']; cycles=tests['independent_cycles_rounds_preflight']; native=report['Windows_lock']
for key,value in [('methods',18),('scenarios',37),('failures',0),('errors',0),('skips',0),('actually_executed',True),('result','passed_first_run')]:
    check('Windows_test_row_'+key,lock.get(key)==value)
for key,value in [('methods',7),('scenarios',28),('failures',0),('errors',0),('skips',0),('actually_executed',True),('result','passed_first_run')]:
    check('supplement_test_row_'+key,cycles.get(key)==value)
check('three_native_handle_methods',native['actual_native_Win32_handle_methods']==own['native_Win32']['methods']==3)
check('actual_native_WinError32',native['native_WinError32_observed'] is True)
check('body_not_reexecuted',native['body_not_reexecuted'] is True)
check('captured_owner_path',native['captured_owner_and_path_verified'] is True)
check('120_backoffs_not_120_total_attempts',native['max_backoffs']==120)
check('121_attempts_includes_initial',native['max_unlink_attempts_including_initial']==121)
check('six_second_exact_uses_controlled_clock',native['six_second_exact_bound_uses_controlled_clock'] is True)
check('real_OS_timeout_is_point12',native['actual_OS_timeout_test_seconds']==.12)
check('no_all_race_or_powerloss_certification',native['all_races_or_power_loss_certified'] is False)
check('stage0_finite_scope',report['software_acceptance']['stage0_offline_regression']=='已测范围通过')
check('stage2_local_scope_only',report['software_acceptance']['stage2_notification_lock_local_scope']=='通过' and report['software_acceptance']['stage2_overall']=='未通过')
check('formal_budget_new_events_debits_refunds_zero',all(report['budget_replay'][key]==0 for key in ['new_events','new_debits','refunds']))
check('no_budget_or_execution_authority_granted','不授予预算变更或执行授权' in report['budget_replay']['authority'])
check('human_authorization_not_independently_authenticated',report['budget_replay']['original_human_authorization_dialogue_independently_obtained'] is False)
check('no_QC_R_LEAN_compile_calls',all(report['tool_capabilities'][key]==0 for key in ['QC_cloud_calls','Research_executions','LEAN_submissions','compile_calls','market_or_model_calls','authoritative_budget_or_production_writes']))
check('all_production_gates_closed',all(report['software_acceptance'][key] is False for key in ['formal_research_enabled','GPT_runtime_enabled','orders_enabled','final_test_enabled']))
check('no_new_candidate_cloud_run_or_order_claim',report['platform_evidence_level']['new_candidate_cloud_run'] is None and report['platform_evidence_level']['new_candidate_orders'] is None)
check('financial_evidence_false',report['financial_evidence'] is False)
check('no_financial_metrics_invented',all(value is None for value in report['financial_metrics'].values()))
check('round008_closed_observation_not_reopened',report['budget_replay']['round008']=='closed')
check('no_positive_schema4_completion_inference','旧b1a归档工程回执重解析' in report['stage_results'][2]['evidence'] and '新候选真实调度/云端' in report['stage_results'][2]['missing'])
check('supplement_commands_referenced','windows_lock_agent/supplement/execution_records.json' in report['artifacts']['independent_commands'])
check('nonunique_counts_explicit','不合计独有测试总数' in report['counting'])
check('text_counts_separate','Windows18/37' in text and '周期轮次7/28' in text)
check('text_native_clock_distinction','Windows三项为真实Win32句柄，6秒精确边界为可控时钟' in text)
check('text_historical_runtime_not_inherited','不继承新源码' in text)
check('text_contains_complete_same_JSON',json.loads(text.split('完整机器报告：',1)[1].strip())==report)
check('original_formal_files_not_changed_by_QA',report_path.read_bytes()==before_json and text_path.read_bytes()==before_text)
issues=[item for item in checks if not item['passed']]
qa={'reviewed_formal_report_sha256':sha(before_json),'reviewed_formal_text_sha256':sha(before_text),
    'static_checks':len(checks),'passed':len(checks)-len(issues),'issues':issues,
    'scope':'Read-only QA of own18/37 native lock and7/28 revision/cycle/schema4/preflight evidence; no suites rerun.',
    'checks':checks,'original_files_written':False,'cloud_calls':0,'suite_reruns':0}
(O/'formal_QA.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'static_checks':len(checks),'passed':qa['passed'],'issues':issues,'report_sha256':qa['reviewed_formal_report_sha256']}))
raise SystemExit(1 if issues else 0)
