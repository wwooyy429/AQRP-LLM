from pathlib import Path
import hashlib,json,re
R=Path(__file__).resolve().parent
def read(p):return json.loads((R/p).read_bytes())
def sha(p):return hashlib.sha256((R/p).read_bytes()).hexdigest()
C='4520fd1a4421a9b764d2bfd61e5fb5cf4b59a9c8'
P='44676db609b3b7c2175fa7fa4f19c8ccf8165458'
A='662ccd876b67ca0949f921a53c4c33df37cfbbf1'
D='42b45c830aac691fe0763bfc6363997947625bc1'
static=read('static_verification.json');data=read('data_recheck/report.json');budget=read('budget_recheck/report.json');runtime=read('runtime_recheck/report.json');prior=read('prior_report_reference.json')
assert not(data['findings']or budget['findings']or runtime['findings'])
rootruns=read('root_execution_records.json');assert len(rootruns)==5 and all(x['exit_code']==0 for x in rootruns)
repo=read('repository_verification.json');assert repo['local_tests_passed']and'Ran 765 tests'in repo['test_output']and repo['test_output'].rstrip().endswith('OK')
tests=[
 {'name':'repository_verify','methods':765,'named_scenarios':None,'result':'passed','kind':'repository_suite_independently_rerun','actually_executed':True,'evidence':'repository_verification.json'},
 {'name':'normal_gate_auxiliary','methods':8,'named_scenarios':None,'result':'passed','kind':'developer_auxiliary_independently_rerun','actually_executed':True,'evidence':'test_independent_normal_gate.py.stderr'},
 {'name':'occurrence_auxiliary','methods':10,'named_scenarios':None,'result':'passed','kind':'developer_auxiliary_independently_rerun','actually_executed':True,'evidence':'test_independent_occurrences.py.stderr'}]
for x in data['actually_executed']:
 if 'methods'in x:tests.append(dict(name=x['suite'],methods=x['methods'],named_scenarios=x['named_scenario_checks'],result='passed_first_run',kind='new_independent_synthetic',actually_executed=True,evidence='data_recheck/'+x['result']))
tests.extend([
 {'name':'full_capacity_settlement','methods':7,'named_scenarios':32,'result':'passed_first_run','kind':'new_independent_synthetic','actually_executed':True,'evidence':'budget_recheck/first_results.json'},
 {'name':'native_parser_bridge','methods':10,'named_scenarios':57,'result':'passed_after_disclosed_reviewer_helper_and_scope_corrections','kind':'new_independent_synthetic','actually_executed':True,'evidence':'runtime_recheck/corrected/first_results.json'}])
assert len(tests)==7 and all((R/x['evidence']).is_file()for x in tests)
stages=[
 dict(stage=0,modules='StudySpec, source/config identity, event registry',implementation='offline_components',evidence='Fresh repository verification, full-capacity budget settlement and immutable identity checks.',verdict='prior_scoped_acceptance_retained_and_relevant_rechecks_passed',missing='No acceptance of downstream runtime or financial design.'),
 dict(stage=1,modules='restricted factors, execution labels, fixed models',implementation='offline_components',evidence='Fresh repository regressions; prior fixed-SHA numeric suites retained, not rerun here.',verdict='prior_scoped_acceptance_retained',missing='No active registered factor/model/trading specification; generic partial-fill/short/noncash accounting incomplete.'),
 dict(stage=2,modules='QC source/cache/collection/admission/native bridge',implementation='partial',evidence='New data13 methods/109 scenarios; budget7/32; runtime10/57; native archive35 static checks.',verdict='not_accepted',missing='New LEAN terminal; financial numeric catalog; charged certification dispatch bridge; complete historicalUS200/vintage/publication/actual-delivery evidence.'),
 dict(stage=3,modules='Research evaluation and rolling folds',implementation='partial_core',evidence='Fresh repository regressions and unchanged static matrix.',verdict='not_accepted',missing='Stratified returns implementation and real registered six-fold factor report.'),
 dict(stage=4,modules='LEAN portfolio/fills/cash/cost/risk',implementation='contracts_and_engineering_receiver',evidence='Synthetic receiver checks only; no new real terminal.',verdict='not_accepted',missing='Generic portfolio execution adapter, transaction ledger, Research/LEAN reconciliation and real stress evidence.'),
 dict(stage=5,modules='bounded GPT generation and workflow',implementation='persistent_controller_primitives',evidence='Current configured GPT provider; model/call/spend settings null.',verdict='not_accepted',missing='Configured and independently accepted real GPT/QC closed loop.'),
 dict(stage=6,modules='search, ablation, selection bias',implementation='similarity_correlation_primitives',evidence='Unchanged static matrix; no real financial trials.',verdict='not_accepted',missing='Preregistered comparison/ablation and net incremental performance evidence.'),
 dict(stage=7,modules='freeze, final executor, forward monitoring',implementation='metadata_skeleton',evidence='Final execution gates closed; exposure ledger retained.',verdict='not_accepted',missing='Independent final executor, full freeze, forward simulation/monitoring/rollback;2026 independence unverified.')]
arch=runtime['archived_evidence'];rep=arch['repaired_Research'];lean=arch['LEAN']
obj={
 'review_id':'AQRP-20261028-4520FD1-RECHECK-22','review_date':'2026-10-28','timezone':'Asia/Shanghai',
 'reviewed_source_commit':C,'baseline_commit':C,'prior_scoped_acceptance_commit':P,
 'evidence_commits':{'diagnostic_runtime':D,'repaired_runtime':A,'archive':C},
 'conclusion':'New bounded offline rechecks passed with disclosed reviewer corrections; no new product defect confirmed; overall phase2 NOT accepted.',
 'source_manifest_hash':static['source_manifest_hash'],'execution_source_manifest_hash':static['execution_source_manifest_hash'],'deployment_hash':static['deployment_hash'],'implementation_hash':static['implementation_hash'],'economic_configuration_hash':static['economic_configuration_hash'],
 'version_consistency':{'raw_Git_files':5976,'managed_review_files':169,'cloud_files':32,'all_raw_bytes_equal_prior_review':True,'runtime_to_review_cloud_tools_tests_changes':[],'runtime_to_review_managed_difference':'budget usage projection; archive documents/evidence also changed','review_source_manifest_includes_usage':True,'execution_identity_excludes_usage':True,'deployment_normalizes_LF_preserving_EOF':True,'evidence':'source_git_manifest.json; static_verification.json'},
 'PR':{'number':2,'head':C,'base':'6a1edbf07fa8fc6cf774084094f4beacc28ff60b','state':'open','draft':True,'merged':False,'PR1_head_equals_PR2_base':True,'CI_run':40573653730,'Python3.10':'success','Python3.11':'success','CI_independently_extracted_test_count':None},
 'environment':read('environment.json'),
 'tool_capabilities':{'Git_GitHub_readonly':True,'fresh_GitHub_reads':5,'offline_native_Windows_tests':True,'QC_calls_this_round':0,'Research_executions':0,'LEAN_submissions':0,'LEAN_terminal_or_log_reads':0,'compile_calls':0,'model_API_calls':0,'market_row_exports':0,'production_original_Git_source_or_authoritative_budget_writes':0,'PR_push_approval_merge':0,'reviewer_scratch_extra_bytecode_files_created_then_preserved_outside_source':8},
 'stage_results':stages,
 'phase2_acceptance_checklist':[
  {'requirement':'small_real_data_fixture','status':'bounded_archived_Research_engineering_scope_supported','limit':'2018 two-symbol cache plus40 calendar snapshot windows; no full coverage certification.'},
  {'requirement':'minimal_completed_backtest','status':'pending_not_accepted','limit':'Only newLEAN submission archived; terminal/logs and7 actual checks absent.'},
  {'requirement':'raw_and_adjustment_trace','status':'partial_not_full_certification','limit':'Raw-mode engineering metadata does not establish all vendor/corporate-action/history provenance.'},
  {'requirement':'failure_recovery','status':'tested_offline_scope_passed','limit':'Private synthetic terminal settlement and original Research replays; no OS kill or power-loss certification.'},
  {'requirement':'historical_universe_and_availability_audit','status':'incomplete','limit':'Audit computation kernel exists; financial numeric catalog0 and charged native certification dispatch missing; actual origin/availability evidence absent.'}
 ],
 'tests':tests,'actually_executed':True,
 'counting':'Methods, named scenarios, CLI/process/thread calls, parser calls and static checks overlap; never sum as unique tests. Historical results are separately identified, not new executions. Named scenarios are not measured unittest subTest counts.',
 'additional_executions':{'budget_native_Windows_processes':4,'budget_thread_tasks':12,'budget_clean_source_synthetic_chains':2,'budget_static_logical_checks':8,'data_capabilities_CLI':1,'native_archive_static_checks':35,'direct_Research_parser_calls':13,'Research_bridge_calls':6,'original_Research_replays':4,'original_terminal_replacement_rejections':2,'synthetic_LEAN_parser_calls':34,'synthetic_LEAN_private_Memory_completion':1,'synthetic_LEAN_usage_changed':False,'minimum_occurrence_reproduction':{'retained':5,'duplicates':3,'first_relative_conflicts':1,'batches':3,'cache_fetches':0,'ordinal_gap_rejected':True},'developer_evidence_checker_exit':0,'build_exit':0,'build_config_changed':False,'static_matrix_unique_source_references':105},
 'first_results_and_corrections':{
  'runtime_first':{'methods':10,'passed_methods':8,'failure_records':2,'error_records':0,'evidence':'runtime_recheck/first/first_results.json'},
  'runtime_helper':'Mutable native mirror references fixed by deepcopy; original outputs retained.',
  'runtime_scope':'Original nbformat-error rejection oracle demanded attempt/source authentication absent from native error fields. Corrected test discloses trusted-dispatcher boundary; original oracle is NOT claimed to pass. Original completed/failed terminal replacement rejections tested separately.',
  'scratch_source':'Reviewer inspection omitted-B, creating8 pyc files in exported scratch source. Original5976 Git files unchanged; caches preserved as raw.bin outside source; exact5976 source restored and guarded. Root initial raw-file-set assertion exit1 retained.',
  'static_reference_scope':'Root initially compared88 stage-row reference entries to105 full-matrix unique references. Corrected checker verifies full top-level105 including controls; intermediate exit1/script/output retained.',
  'prior_report_metadata':'Prior sealed report said newLEAN13 checks in unverified wording. Corrected: Research13, LEAN7. Prior sealed package unchanged. Earlier derived-summary SHA-label correction also remains preserved.',
  'product_edits':False
 },
 'findings':[],
 'historical_findings':{'WR01_WR27':'Prior fixed-SHA scoped conclusions retained; no phase-wide promotion. Same5976 source bytes verified. Prior248 methods/2307 subcases, earlier independent data/budget/runtime suites and35 live source-only QC calls are historical references, not rerun counts.','prior_review_seal_verified_again':True,'prior_review_zip_sha256':prior['prior_zip_sha256'],'prior_review_report_sha256':prior['prior_formal_report_sha256'],'new_WRs':[]},
 'budget_replay':{**budget['budget_replay'],'authority_boundary':budget['authority_boundary'],'real_terminal_settlement_this_round':False,'synthetic_retries_do_not_authorize_real_executions':True},
 'platform_evidence_level':{
  'archived_native':'Developer-archived packets independently decoded and source/input/cell/dispatch/evidence-bound offline; not reviewer live platform results or remote signatures.',
  'diagnostic':{'attempt_id':arch['diagnostic']['attempt_id'],'status':'failed/runtime_error','code':'native_sid_duplicate','partial_fetch_emitted_rows':5124,'whole_Research_completed':False},
  'Research':{'attempt_id':rep['attempt_id'],'source_commit':A,'status':'completed_in_archived_native_metadata','checks_required':13,'checks_true':13,'price_field_records':2510,'formation_count':250,'price_History_first':0,'price_History_second':0,'calendar_windows':40,'retained_projections':208223,'duplicates':27,'selected_field_conflicts':0,'empty_windows':13,'cache_only_source_fetches':0,'selected_fields':4,'raw_cloud_rows_recounted':False,'native_packet_sha256':rep['native_packet_sha256']},
  'LEAN':{'attempt_id':lean['attempt_id'],'backtest_id':lean['external_id'],'frozen_ledger_status':'pending','native_submission_verified':True,'terminal_status':None,'runtime_success':None,'orders':None,'required_checks':lean['required_checks']['lean'],'actual_runtime_check_results':None},
  'compile':'Developer success summary only; original native compile packet missing.',
  'source_readback':'Prior independent35 source-only QC calls retained and rehashed; no new cloud read in this recheck. Present project inventory and historical worker packaging remain uncertified.',
  'authenticity_boundary':'A native nbformat error contains no originating attempt/source identity. Trusted dispatcher actual I/O supplies context. Hashes detect inconsistency, not remote provenance or a self-consistent fabricated corpus.'
 },
 'software_acceptance':{'tested_data_and_budget_scope':'passed','tested_parser_bridge_scope':'passed_under_documented_contract_after_disclosed_reviewer_corrections','archived_Research_engineering':'supported_at_metadata_level','phase2_overall':'not_accepted','unattended_factor_research':False,'formal_research_enabled':False,'GPT_runtime_enabled':False,'orders_enabled':False,'final_test_enabled':False},
 'data_certification':{'full_historical_US200':False,'permanent_SID_ambiguity_economically_resolved':False,'financial_vintage':False,'actual_delivery_and_ingestion':False,'financial_numeric_catalog_count':0,'certification_computation_kernel':'implemented','charged_certification_native_dispatch_bridge':'not_implemented','canonical_commands':['capabilities','validate-plan'],'ready_to_dispatch':False,'budget_admission_performed':False,'occurrences':'Every selected projection retained with ordered source ordinal and first-relative duplicate/conflict counts; no economic winner/deduplication/averaging; unique-liquidity converter rejects v2 rows.','exact_gap_references':['tools/data_certification.py:16','tools/data_certification.py:30','cloud/qresearch/data_certification.py:411','cloud/qresearch/data_certification.py:689','cloud/qresearch/data_certification.py:724']},
 'financial_evidence':False,'financial_metrics':{'IC':None,'returns':None,'costs':None,'risk':None,'NAV':None},
 'research_constraints':{'universe':'Historical point-in-time top200 US equities; no201st substitution','timezone':'America/New_York','rolling':'Six8-year/1-year folds2010-2017/2018 through2015-2022/2023; only frozen trainable parameters refit annually','final_window':'2024-01-01/2026-10-23; actual exits within final boundary','2024_2025_exposed':True,'2026_independence':'unverified','independent_final_executor_configured':False},
 'unverified':['NewLEAN delivered terminal, native logs,7 actual engineering checks and0 actual orders; no polling or substitute new run.','Original native compile packet, complete project inventory and exact old failed worker source.','Full historicalUS200, source ambiguity, real exchange sessions, corporate actions, financial values/periods/units/vintages, publication and actual supplier delivery/ingestion.','External original human grant2/4/2 message; latest direct human statement supports already executed2/2/1 only. Audit grants no further execution.','Native packet provenance beyond trusted dispatcher; self-consistent fabricated corpus cannot be certified by hashes alone.','OS kill/power-loss durability, stages3-7, financial effectiveness and an untouched final holdout.'],
 'next_required_work':['Obtain platform-delivered newLEAN terminal and logs; reconcile original frozen attempt and7 checks/actual0 orders once without implicit resubmission.','Complete financial numeric catalog and charged native certification dispatch bridge; preserve observation ambiguity until resolved by source evidence.','Obtain full historical universe/vintage/publication/actual-delivery certification under explicit authorization and exhausted configuration constraints.','Keep formal research, autonomous GPT, orders and final test closed until corresponding independent acceptance.'],
 'artifacts':{'commands_and_exits':'root_execution_records.json; root_evidence_execution.json; data_recheck/*execution.json; budget_recheck/execution.json; runtime_recheck/*execution.json','new_independent_tests':'data_recheck/adversarial_occurrence.py; data_recheck/additional_closed_checks.py; budget_recheck/settlement_frontier_tests.py; runtime_recheck/independent_runtime_recheck_corrected.py','minimum':'python -B minimal_occurrence_known_answer.py --source source','prior_reference':'prior_report_reference.json','full_matrix':'reused_stage_matrix.json','verification':'python -B verify_artifacts.py'}
}
assert all(x['actually_executed']for x in tests)
(R/'formal_report.json').write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
intro='''Phase2独立重审完成：已测试局部软件范围通过，阶段2整体验收未通过，无新确认产品缺陷。
固定审核提交4520fd1a4421a9b764d2bfd61e5fb5cf4b59a9c8；本次PR仍是该SHA、草稿未合并，5976份文件与上轮逐字节一致。
本轮实际执行765项仓库测试、两套开发辅助8+10项；新增独立数据10/105+3/4、预算7/32、运行回执10/57（方法/命名场景）。运行套件原10方法8通过、2失败记录，经明确披露的审查器helper和来源验证预期修正后通过，原失败不被覆盖。计数重叠不加总。
预算46事件、配置12/12、Research15/20、LEAN2/16，normal004实际2/2/1，记录额度2/4/2。无退款、无预算增加，配置余额0；合成私有账本的结算和重试不授权真实执行。
真实Research归档原生元数据13项工程检查通过；40日历窗口208223投影/27重复/选定4字段冲突0/空13，并非原始云端逐行重计数或完整数据认证。价格History0/0来自已有缓存。
新LEAN37dc/3e688只确认提交与冻结pending，终态/日志/订单未知。冻结LEAN要求7项检查，与Research13不同；上轮报告这一措辞已在本轮明确更正，原包保留。编译原生回执仍缺。
完整历史US200、财务版本/公开/实际送达/摄入认证仍缺。财务数值字段目录0；认证计算内核已有实现，计费native认证派发桥缺失，不能将两者混称未实现。来源序号不解决经济SID歧义，含糊v2记录拒绝唯一流动性转换。
本轮QC、Research/LEAN、模型调用、终态日志读取、权威账本/生产源码写入0。上轮35次独立源码只读回读作为历史证据保留，不冒充本轮云端状态。
审查器早期导入产生8份scratch源码pyc，原5976Git文件未变；缓存另存后恢复纯Git树。静态矩阵初次把88条阶段引用误与105条完整引用比较，原失败保留，已改为核验完整105唯一引用。以上不是产品修复。
原生nbformat错误没有内生attempt/source身份，只能在可信dispatcher上下文内校验；哈希不是远端签名。已结算原成功/失败结果替换拒绝另测通过。OS kill/断电未认证。
正式研究、自动GPT、交易、最终测试继续关闭；2024-2025既往暴露保留，2026独立性未认证。无金融有效性结论，无IC/收益/成本/风险/NAV数值。
'''
lines=[intro,'全系统矩阵：']
for s in stages:lines.append(f"阶段{s['stage']} {s['modules']}: {s['verdict']}\n{s['evidence']}\n缺口: {s['missing']}")
lines.extend(['','完整机器报告：',json.dumps(obj,ensure_ascii=False,indent=2)])
(R/'formal_report.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(json.dumps({'report_bytes':(R/'formal_report.json').stat().st_size,'report_sha256':sha('formal_report.json'),'test_rows':len(tests)}))
