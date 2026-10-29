from pathlib import Path
import json, hashlib, re, sys, subprocess
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parent
def read(p): return json.loads((R/p).read_text(encoding='utf-8-sig'))
identity=read('independent_identity.json'); environment=read('environment.json')
notification=read('notification_agent/report.json'); windows=read('windows_lock_agent/report.json'); supplement=read('windows_lock_agent/supplement/report.json')
history=read('history_agent/report.json'); static=read('history_agent/history_static_results.json')
wr=read('history_agent/WR_current_matrix.json'); guard=read('root_guard.json')
repo=read('repository_verification.json'); maps=read('source_git_manifest.json')
assert repo['local_tests_passed'] and re.search(r'Ran 987 tests.*?OK',repo['test_output'],re.S)
assert all(not report.get('findings') for report in (notification,windows,supplement,history))
assert not guard['source']['changed'] and not guard['materials']['changed']
assert guard['work_source']['changed']==['audit/stage_verification.json']
assert len(wr)==28 and len({x['id'] for x in wr})==28
tests=[
 {'name':'repository','methods':987,'scenarios':None,'kind':'repository_suite','result':'passed','failures':0,'errors':0,'skips':0,'actually_executed':True},
 {'name':'independent_notification','methods':18,'scenarios':106,'kind':'new_independent_synthetic_and_Windows_processes','result':'passed_after_reviewer_fixture_correction','failures':0,'errors':0,'skips':0,'actually_executed':True},
 {'name':'independent_Windows_lock','methods':18,'scenarios':37,'kind':'new_independent_native_Win32_and_synthetic','result':'passed_first_run','failures':0,'errors':0,'skips':0,'actually_executed':True},
 {'name':'independent_cycles_rounds_preflight','methods':7,'scenarios':28,'kind':'new_independent_synthetic_and_processes','result':'passed_first_run','failures':0,'errors':0,'skips':0,'actually_executed':True},
 {'name':'independent_storage_identity','methods':5,'scenarios':26,'kind':'new_independent_known_answers','result':'passed_first_run','failures':0,'errors':0,'skips':0,'actually_executed':True},
 {'name':'historical_numeric_time','methods':16,'scenarios':84,'kind':'original_independent_suite_replayed_on_current_source','result':'passed_first_run','actually_executed':True},
 {'name':'historical_Pearson','methods':10,'scenarios':896,'kind':'original_independent_suite_replayed_on_current_source','result':'passed_first_run','actually_executed':True},
 {'name':'historical_IC_summary','methods':11,'scenarios':716,'kind':'original_independent_suite_replayed_on_current_source','result':'passed_first_run','actually_executed':True},
 {'name':'historical_certification','methods':13,'scenarios':43,'kind':'original_independent_suite_replayed_on_current_source','result':'passed_first_run','actually_executed':True},
 {'name':'historical_carriers','methods':15,'scenarios':80,'kind':'original_then_fixture_adapted_independent_suite','result':'passed_after_two_preserved_fixture_adaptations','actually_executed':True},
 {'name':'WR25_WR26_MRE','methods':None,'scenarios':7,'kind':'original_MRE_expected_outcomes','result':'matched','actually_executed':True},
 {'name':'historical_WR28_audit','methods':11,'scenarios':None,'kind':'developer_audit_suite_replayed_for_original_frozen_scope','result':'passed','actually_executed':True}
]
for test in tests:
 if test['result'] in ('passed_first_run','passed','matched','passed_after_two_preserved_fixture_adaptations'):
  test.setdefault('failures',0);test.setdefault('errors',0);test.setdefault('skips',0)
stages=[
 {'stage':0,'modules':'规范、身份、Registry、预算、持久化和交付','implementation':'已有离线组件','evidence':'987回归；213份身份；通知、原生锁、周期/轮次和资料检查','verdict':'已测离线范围回归通过','missing':'不包含真实宿主调度与远端真实性认证'},
 {'stage':1,'modules':'因子、PIT、标签、模型和滚动内核','implementation':'已有离线内核','evidence':'987回归及原数值16、Pearson10、IC汇总11方法重放','verdict':'已测离线范围回归通过','missing':'无已认证经济因子、生产模型或金融检验'},
 {'stage':2,'modules':'QC、缓存、摄入、任务桥、通知恢复','implementation':'部分实现','evidence':'本地通知恢复及Windows修复通过；旧b1a归档工程回执重解析','verdict':'局部软件范围通过；整体未通过','missing':'新候选真实调度/云端；完整US200/SID及财务时点认证；完整计费认证派发'},
 {'stage':3,'modules':'评价、共同样本、成熟标签、滚动','implementation':'局部内核','evidence':'仓库与数值合成回归','verdict':'未验收','missing':'完整分层收益/风险报告和真实固定六轮研究'},
 {'stage':4,'modules':'无订单接收器、标签成交与成本','implementation':'局部工程组件','evidence':'旧有限2018工程零订单回执','verdict':'未验收','missing':'完整组合、订单成交、持仓现金净值、风险、对账及压力验证'},
 {'stage':5,'modules':'提案、持久化控制器、adapter接口','implementation':'局部原语','evidence':'离线回归；闸门关闭','verdict':'未验收','missing':'实际GPT客户端、模型/调用/费用设置和真实无人值守闭环'},
 {'stage':6,'modules':'结构相似、相关性、复杂度','implementation':'局部原语','evidence':'合成回归','verdict':'未验收','missing':'完整搜索、消融、净组合增量和选择偏差实证'},
 {'stage':7,'modules':'冻结元数据、暴露记录及闸门','implementation':'骨架','evidence':'原暴露与关闭闸门保留','verdict':'未验收','missing':'独立最终执行器、前向模拟、监控回滚；2026独立性未认证'}
]
budget=static['budget']; old=static['old_platform']
report={
 'review_id':'AQRP-20261029-975F676-RECOVERY009-25','review_date':'2026-10-29','timezone':'Asia/Shanghai',
 'reviewed_source_commit':maps['source']['commit'],'baseline_commit':'ca5e4f3f68a58297cf02d97629346e10306ebcf0',
 'evidence_commits':{'materials':maps['materials']['commit'],'historical_runtime':'b1a4041ce98867047294b8f0830292af5d7ec56e','historical_terminal':'ca5e4f3f68a58297cf02d97629346e10306ebcf0','WR28_closure':'2f5591e28c0748ac42caeae7bbf3977141d031cb'},
 'conclusion':'975f676本轮通知恢复、Windows锁释放及已测试离线回归范围通过；未确认新产品缺陷。阶段2整体未通过验收。',
 'source_manifest_hash':identity['source_manifest_hash'],'deployment_hash':identity['deployment_hash'],'implementation_hash':identity['implementation_hash'],'configuration_hash':identity['configuration_hash'],
 'version_consistency':{'source_files':7045,'materials_files':7076,'managed_identity_files':213,'current_deployment_files':44,'historical_cloud_files':43,'source_materials_managed_raw_equal':True,'immutable_source_or_materials_changed':False,'scratch_changes':['audit/stage_verification.json'],'builds':2,'both_config_changed':False,'materials_git_verifier_exit':0,'packet_raw_files':38,'protected_records':10,'post_materials_PR_head':'338bd6ea211d287396836752509d828c156ec442','post_materials_difference':['audit/review_handoffs/recovery009.json']},
 'PR':{'number':2,'draft':True,'merged':False,'source_CI_run':40829100715,'Python3.10':'success','Python3.11':'success','independently_extracted_CI_test_count':None},
 'environment':environment,'tool_capabilities':{'readonly_Git_GitHub':True,'native_Windows_and_private_synthetic_execution':True,'QC_cloud_calls':0,'Research_executions':0,'LEAN_submissions':0,'compile_calls':0,'market_or_model_calls':0,'authoritative_budget_or_production_writes':0,'PR_mutations':0},
 'stage_results':stages,'tests':tests,'actually_executed':True,
 'counting':'方法、子场景、进程请求、静态核验及重跑存在重叠，不合计独有测试总数；旧909/924/940和本轮987不相加。',
 'notification_recovery':{'verdict':'已测本地软件范围通过','methods':18,'scenarios':106,'original_pending_1800_seconds_boundary':True,'max_pages':3,'durable_reservations_before_requests':True,'unknown_outcome_no_redispatch':True,'terminal_summary_does_not_settle':True,'parser_Bridge_Registry_full_synthetic_chain':True,'six_process_18_requests_permissions':1,'thread_history_permissions':1,'thread_completed_read_permissions':1,'real_host_and_push_verified':False},
 'Windows_lock':{'verdict':'原生Windows已测范围通过','methods':18,'scenarios':37,'actual_native_Win32_handle_methods':3,'native_WinError32_observed':True,'body_not_reexecuted':True,'captured_owner_and_path_verified':True,'max_backoffs':120,'max_unlink_attempts_including_initial':121,'six_second_exact_bound_uses_controlled_clock':True,'actual_OS_timeout_test_seconds':0.12,'all_races_or_power_loss_certified':False},
 'historical_findings':{'WR01_WR28_original_exact_scopes_retained':True,'current_related_repository_regressions_passed':True,'all_original_independent_suites_rerun':False,'per_WR_original_SHA_scope_current_tests_and_limits':'history_agent/WR_current_matrix.json','WR_count':28,'original_reports_checked':static['history_report_count'],'selected_archive_is_complete_original_bundle':False,'WR15_WR19_WR27_additional_static_or_MRE_checks_passed':True,'WR28_replay_scope':'Original three frozen Git snapshots/122 records/48-event historical chain; does not assert current changed files equal old protected list.'},
 'reviewer_corrections':{'notification_first_run':{'methods':12,'failures':0,'errors':1,'cause':'审核者分块夹具误用400字节/1基；按既定500字节/0基更正，产品未改','corrected':'12方法/79场景通过；另6方法/27场景首次通过'},'carrier_first_run':{'errors':44,'cause':'旧fresh baseline误用累计16配置投影；新周期限额13','second_errors':14,'second_cause':'旧合成完成payload缺当前deployment_manifest','adaptation':'仅改一处合成baseline引用及两处payload manifest夹具；15方法/80场景通过，断言未改'},'all_first_scripts_logs_and_diffs_preserved':True},
 'findings':[],
 'budget_replay':{'events':71,'journal_sha256':budget['journal_sha256'],'prior69_prefix_sha256':budget['prior69_prefix_sha256'],'prior_prefix_raw_preserved':True,'configuration_cycle':{'used':3,'limit':13},'lifetime_configurations':16,'Research':{'used':17,'limit':20},'LEAN':{'used':3,'limit':16},'round008':'closed','new_events':0,'new_debits':0,'refunds':0,'authority':'既有Registry原字节和私有Memory重放；本轮不授予预算变更或执行授权'},
 'platform_evidence_level':{'grade':'开发者归档原生工程元数据，经审核者离线重新解析；本轮未独立访问QC','historical_runtime_commit':'b1a4041ce98867047294b8f0830292af5d7ec56e','Research_checks_passed':13,'LEAN_checks_passed':7,'historical_orders':0,'PROJECT_raw_source_files':43,'Research_worker_EOF_normalized_files':0,'LEAN_worker_EOF_normalized_files':43,'LEAN_original_source_identity_match':False,'terminal_acquisition':'一次历史目录对账','automatic_push_observed':False,'new_candidate_cloud_run':None,'new_candidate_orders':None,'native_complete_compiler_worker_packet':'未归档'},
 'software_acceptance':{'stage0_offline_regression':'已测范围通过','stage1_offline_regression':'已测范围通过','stage2_notification_lock_local_scope':'通过','stage2_overall':'未通过','stages3_to7':'未验收','formal_research_enabled':False,'GPT_runtime_enabled':False,'orders_enabled':False,'final_test_enabled':False},
 'data_certification':{'full_historical_US200':False,'SID_economic_ambiguity_resolved':False,'financial_statement_numeric_catalog_count':0,'financial_vintage_publication_actual_delivery_ingestion':False,'computation_kernel':'已有实现及合成回归','complete_charged_native_dispatch':'未完成验收'},
 'financial_evidence':False,'financial_metrics':{'IC':None,'returns':None,'costs':None,'risk':None,'NAV':None},
 'research_constraints':{'universe':'历史当时流动性前200美股；财务缺失不换入201名','timezone':'America/New_York','rolling':'2010-2017/2018至2015-2022/2023的六个固定八年训练/一年验证窗','final_window':'2024-01-01至2026-10-23','2024_2025_exposed':True,'2026_independence':'未认证','independent_final_executor_configured':False},
 'unverified':['新候选真实MCP宿主调度、自动通知传输及云端超时对账联调','完整历史US200/SID/交易日、公司行动和财务版本/公开/实际送达/摄入认证','完整计费认证派发及阶段3–7缺失模块','任意文件系统竞争、硬终止、断电耐久性及远端工具真实性','2026样本独立性和实际金融有效性','本轮只核对选取归档原件，未全量重验全部外部原ZIP；未独立取得新增额度的原人类授权对话'],
 'next_required_work':['归档本次固定975f676的软件有限通过结论，保留全部旧SHA失败和原范围结论','在另行授权的受限联调中验证真实宿主调度及终态回执；本报告不授权执行','补齐数据认证和完整计费派发，随后重新提交阶段2整体验收','保持正式研究、自动GPT、交易和最终测试关闭'],
 'artifacts':{'root_commands':'root_execution_records.json','independent_commands':'notification_agent/execution_records.json; windows_lock_agent/execution_records.json; windows_lock_agent/supplement/execution_records.json; history_agent/historical_execution.json','source_raw_maps':'source_git_manifest.json','WR_matrix':'history_agent/WR_current_matrix.json','minimum':'python -B minimal_windows.py source','seal':'python -B verify_artifacts.py'}
}
report['reviewer_corrections']['history_summary_helper']='已完成测试后的汇总器因重复全树哈希被中止，并修正IC结果文件名；仅改审核汇总程序，原程序/退出记录/更正全部保留。'
report['reviewer_corrections']['formal_QA_wording']='QA将适配措辞精确为一处baseline引用加两处payload manifest；旧报告草稿formal_report_pre_QA.json及QA问题保留。'
report['historical_findings']['static_metadata_checks']=1582
report['budget_replay']['original_human_authorization_dialogue_independently_obtained']=False
(R/'formal_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
rows=['阶段 | 已有模块 | 实际证据 | 缺口 | 结论','--- | --- | --- | --- | ---']
for s in stages:rows.append(f"{s['stage']} | {s['modules']} | {s['evidence']} | {s['missing']} | {s['verdict']}")
text='本轮独立复审：975f676通知恢复、Windows锁释放及已测试离线回归通过；阶段2整体仍未通过。无新确认产品缺陷。\n\n'+ '\n'.join(rows)+'\n\n本轮实际重跑987项；Windows18/37、通知18/106、周期轮次7/28、身份缓存5/26；历史数值16/84、Pearson10/896、IC汇总11/716、认证13/43、载体15/80、WR25/26七个MRE及WR28审计11项通过。计数重叠不相加。\n\n首次通知夹具错误和载体两轮协议适配失败完整保留，产品未改。Windows三项为真实Win32句柄，6秒精确边界为可控时钟。旧b1a云端13/7只经归档回执重解析，不继承新源码。\n\nWR逐项当前覆盖与限制：\n'
for item in wr:text+=item['id']+'：'+item['current_execution_and_limits']+'\n'
text+='\n完整机器报告：\n'+json.dumps(report,ensure_ascii=False,indent=2)+'\n\n实际最小检查：\n'+(R/'minimal_windows.py').read_text()
(R/'formal_report.txt').write_text(text,encoding='utf-8')
print(json.dumps({'review_id':report['review_id'],'json_bytes':(R/'formal_report.json').stat().st_size,'sha256':hashlib.sha256((R/'formal_report.json').read_bytes()).hexdigest(),'tests_rows':len(tests)}),flush=True)
