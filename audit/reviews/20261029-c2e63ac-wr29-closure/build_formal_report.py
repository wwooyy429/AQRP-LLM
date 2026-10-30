from pathlib import Path
import json,hashlib,re,sys
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parent
def read(name):return json.loads((R/name).read_text(encoding='utf-8-sig'))
entry=read('entry_agent/report.json');api=read('api_agent/report.json');archive=read('archive_agent/report.json')
repo=read('repository_verification.json');identity=read('identity_verification.json');guard=read('root_guard.json');mre=read('original_MRE_replay.json')
assert all(not x['findings'] for x in (entry,api,archive))
assert repo['local_tests_passed'] and re.search(r'Ran 1012 tests.*?OK',repo['test_output'],re.S)
assert not guard['source']['changed'] and not guard['materials']['changed']
assert guard['work_source']['changed']==['audit/stage_verification.json']
assert [x['assertion_program_exit'] for x in mre['records']]==[1,0]
tests=[]
def test(name,methods,scenarios,kind,first):
    tests.append({'name':name,'methods':methods,'scenarios':scenarios,'passed':methods,'failures':0,'errors':0,'skips':0,'kind':kind,'first_run':first,'actually_executed':True})
test('repository',1012,None,'repository_synthetic_suite','passed')
test('original_host_subset',19,None,'overlapping_repository_subset','passed')
test('new_entrypoint_subset',6,None,'overlapping_repository_subset','passed')
test('metadata_scope_self_test',7,None,'developer_scope_suite','passed')
test('original_independent_stdio',15,61,'original_script_replayed_on_fixed_source','passed')
test('original_independent_stdio_supplement',4,12,'original_script_replayed_on_fixed_source','passed')
test('new_independent_entrypoints',8,51,'new_actual_subprocess_and_synthetic','passed')
test('original_independent_API',12,63,'original_script_replayed_on_fixed_source','passed')
test('original_independent_API_supplement',6,26,'original_script_replayed_on_fixed_source','passed')
test('new_independent_append_recovery',3,28,'actual_Win32_fault_and_synthetic','one_reviewer_OS_field_expectation_corrected_then_passed')
test('prior_Windows_lock',18,37,'original_script_replayed_on_fixed_source','passed')
test('prior_notification_main',12,79,'original_script_replayed_on_fixed_source','passed')
test('prior_notification_supplement',6,27,'original_script_replayed_on_fixed_source','passed')
test('prior_cycles_rounds',7,28,'original_script_replayed_on_fixed_source','passed')
resolution={'id':'WR-29','original_priority':'P1','status':'fixed_verified_closed','original_review_id':'AQRP-20261029-2D1D306-HOST010-26','original_source_commit':'2d1d3060dbc7eb136c1dee61f0647977528b8aad','original_file':'tools/followup_host.py','original_line':469,'fixed_source_commit':'c2e63ac5f19901bd95e127069b5998452f7f9864','scope':'标准脚本及-m入口拒绝普通canonical-import合法factory的原缺陷范围','original_expected_exits':[0,0,0],'original_actual_exits':[0,2,2],'fixed_actual_exits':[0,0,0],'original_MRE_assertion_exit':1,'fixed_MRE_assertion_exit':0,'original_script_and_success_expectations_unchanged':True,'repair':'在定义类型和加载factory前委派canonical followup_host.main；10个顶层函数/类AST原样保留','normal_path_and_strict_negative_paths_verified':True,'not_granted':['倒改2d1d306原失败','生产factory/MCP调度/平台通知成功','完整回执收集或计费认证派发','完整阶段2、数据认证或金融有效性']}
stages=[
 {'stage':0,'modules':'规范、身份、Registry、预算、归档','implementation':'已有组件','evidence':'1012回归、218身份、161原件恢复、71事件重放','verdict':'已测离线回归范围通过','missing':'不涵盖生产调度或远端真实性'},
 {'stage':1,'modules':'因子、PIT、标签、模型、滚动内核','implementation':'共享内核未改','evidence':'仓库及既往相关回归重放','verdict':'已测回归范围通过','missing':'无金融有效性验收'},
 {'stage':2,'modules':'QC、任务桥、通知与本地宿主','implementation':'部分实现','evidence':'WR29原范围关闭；本地CLI/stdio/API及故障恢复有限测试通过','verdict':'局部软件通过；整体未通过','missing':'真实factory/transport/通知/新云端工程、完整回执、数据认证及计费认证派发'},
 {'stage':3,'modules':'评价、共同样本与滚动','implementation':'局部内核','evidence':'合成回归','verdict':'未验收','missing':'完整分层收益/风险及真实固定六轮研究'},
 {'stage':4,'modules':'工程接收器、标签成交/成本','implementation':'局部组件','evidence':'无新真实执行，旧b1a有限证据保留','verdict':'未验收','missing':'完整组合交易/账本/风险/压力与对账'},
 {'stage':5,'modules':'受限提案与持久化状态机','implementation':'局部组件','evidence':'默认关闭及权限边界测试','verdict':'未验收','missing':'实际GPT客户端、模型/调用/费用及真实研究闭环'},
 {'stage':6,'modules':'相似性、相关性及复杂度','implementation':'局部组件','evidence':'合成回归','verdict':'未验收','missing':'完整搜索/消融/净增量/选择偏差实证'},
 {'stage':7,'modules':'冻结、暴露与关闭闸门','implementation':'元数据骨架','evidence':'既往暴露保留，最终测试关闭','verdict':'未验收','missing':'独立最终执行器/前向监控回滚及2026独立性'}
]
report={
 'review_id':'AQRP-20261029-C2E63AC-WR29-27','review_date':'2026-10-29','timezone':'Asia/Shanghai',
 'reviewed_source_commit':'c2e63ac5f19901bd95e127069b5998452f7f9864','baseline_commit':'2d1d3060dbc7eb136c1dee61f0647977528b8aad',
 'evidence_commits':{'materials':'f698a38a99c3ed8388c9403f2eda723b579c5eaf','original_failed_materials':'fe088461e84586d7feb73f20be54a22d09706942','prior_finite_pass':'975f676d62b561689909744f9e7236290e3f5fcb','historical_runtime':'b1a4041ce98867047294b8f0830292af5d7ec56e','historical_terminal':'ca5e4f3f68a58297cf02d97629346e10306ebcf0'},
 'conclusion':'WR29/P1在固定c2e63ac原CLI/stdio合法factory缺陷范围修复后通过、独立关闭；未确认新产品缺陷。阶段2整体仍未通过。',
 'source_manifest_hash':identity['source_hash'],'deployment_hash':identity['deployment_manifest_hash'],'implementation_hash':identity['implementation_hash'],'configuration_hash':identity['configuration_hash'],
 'environment':read('environment.json'),
 'tool_capabilities':{'readonly_Git_GitHub':True,'native_Windows_private_subprocess_and_synthetic_tests':True,'QC_calls':0,'Research_executions':0,'LEAN_submissions':0,'compile_calls':0,'market_or_model_calls':0,'production_automation':0,'authoritative_budget_or_production_writes':0,'PR_push_approval_merge':0},
 'version_consistency':{'source_raw_files':7448,'materials_raw_files':7766,'managed_identity_files':218,'baseline_managed_files':216,'changed_managed':identity['changed_managed'],'added_managed':identity['added_managed'],'source_materials_managed_equal':True,'top_level_function_class_ASTs_unchanged':10,'canonical_delegation_precedes_types':True,'deployment_files':44,'deployment_raw_unchanged_from2d':True,'two_builds_config_changed':False,'materials_git_verifier_exit':0,'packet_raw_files':77,'immutable_source_materials_changed':False,'scratch_changes':['audit/stage_verification.json']},
 'PR':{'number':2,'draft':True,'merged':False,'source_CI_run':40870978944,'Python3.10':'success','Python3.11':'success','independently_extracted_CI_test_count':None},
 'WR29_resolution':resolution,'stage_results':stages,'tests':tests,'actually_executed':True,
 'counting':'方法、命名场景、进程请求、原脚本重放、专项子集、旧负对照和静态检查重叠，不合计独有总数；旧1006与本轮1012不相加。',
 'native_append_recovery':{'new_methods':3,'named_scenarios':28,'actual_CLI_processes':4,'actual_Win32_share_denial_error':32,'Python_CRT_errno':13,'Python_CRT_winerror':None,'observed':'拒写时安全attention/unknown，无重派；解除后同原response跨canonical/script/-m恢复，一次发现+一次历史许可，Registry账本不变','synthetic_cases':['写前拒绝','完整落盘后ack丢失','controller已观察而host确认失败'],'does_not_authenticate_original_developer_incident_cause':True},
 'findings':[],
 'historical_findings':{'WR01_WR28':'原精确SHA及有限范围保留','WR29_original':'2d1d306原报告confirmed_open/P1与原0/2/2失败保留，未重写','WR29_new_resolution':resolution,'prior975_and2d_API_scopes':'各自原范围保留，不继承全部新版本通过','all_original_independent_WR_suites_rerun':False},
 'archive_verification':{'static_file_blob_metadata_checks':45370,'additional_representation_checks':4,'static_checks_are_not_unit_methods':True,'old_complete_ZIP':archive['old_complete_ZIP'],'selected_archive':archive['selected_archive'],'developer_guard':archive['developer_guard'],'original_formal_sha256':'224a7b8a0e7667b6759e685f71dae0fd54ba0eb6c914ced1c9c1332deb009e14','old_failure_and_first_scripts_outputs_preserved':True,'selected_archive_is_complete_original_bundle':False},
 'developer_auxiliary_history':{'initial':'79/84：3项夹具预期错误，2项晚响应失败无trace','corrected':'89/90：1次有确切私有store append EACCES trace，安全停止','recorded_recovery':'原store8/8，原输入克隆10/10，原记录分别保留','original_store_recovery_and_clone_independently_replayed':False,'reason':'历史原私有store未归档；本轮只读核对所存原件/trace/摘要，不伪造初始状态','two_untraced_failures_same_cause_proven':False,'all_auxiliary_runs_retroactively_passed':False,'new_equivalent_fault_tests_are_separate':True},
 'reviewer_corrections':{'new_append_probe':'首跑误预期Python Path.open(ab)的winerror=32；实际CRT为errno13/winerrorNone，独立Win32写打开确认错误32。仅修正OS字段预期，首脚本/trace保留，3/28通过','archive_helper':'首跑误将focused JSON object.records当顶层list，修正审核读取形状后通过；原脚本/失败输出及探索读取记录保留','entry_and_original_API_replays':'本轮首次通过，原脚本和成功预期未改','product_changed_by_reviewer':False},
 'budget_replay':{'events':71,'journal_sha256':'cea800e0fe5a0facc5f2aed238d105a6f3d1c80db40c1dc4b674efd3026cd48a','prior69_prefix_sha256':'2d3131a32864434d22635f058ec3de8062e9b1b610a90185bf6ba6cf9c637934','prior69_prefix_raw_preserved':True,'configuration_cycle':{'used':3,'limit':13},'lifetime_configurations':16,'Research':{'used':17,'limit':20},'LEAN':{'used':3,'limit':16},'round008':'closed','new_events':0,'new_debits':0,'refunds':0,'original_human_authorization_dialogue_independently_obtained':False,'future_1_1_1':'仍未授权/未准入/无真实任务ID'},
 'platform_evidence_level':{'current_review':'本地原生Windows合成/子进程及Git/ZIP/原件离线核验，无QC访问','historical_b1a':'只保留原975审查的2018有限归档工程证据；不继承为新候选运行','historical_Research_checks':13,'historical_LEAN_checks':7,'historical_orders':0,'historical_PROJECT_files':43,'historical_Research_EOF_normalized':0,'historical_LEAN_EOF_normalized':43,'historical_LEAN_original_source_identity_match':False,'historical_automatic_push_observed':False,'new_source_cloud_run':None,'new_source_orders':None},
 'software_acceptance':{'WR29_original_CLI_stdio_defect':'修复后通过并关闭于c2e63ac','local_CLI_stdio_API':'已测有限合成范围通过','stage0_1_regression':'已测范围通过','real_factory_transport_scheduler':'未验收','complete_native_receipt_collection_and_charged_certification':'未完成','stage2_overall':'未通过','stages3_to7':'未验收','formal_research_enabled':False,'GPT_runtime_enabled':False,'orders_enabled':False,'final_test_enabled':False},
 'data_certification':{'full_historical_US200':False,'SID_economic_ambiguity_resolved':False,'financial_statement_numeric_catalog_count':0,'financial_vintage_publication_actual_delivery_ingestion':False,'complete_charged_native_dispatch':'未完成'},
 'financial_evidence':False,'financial_metrics':{'IC':None,'returns':None,'costs':None,'risk':None,'NAV':None},
 'research_constraints':{'historical_top200_US_equities':True,'no_rank201_substitution':True,'timezone':'America/New_York','rolling':'六个固定八年训练/一年验证窗，2010-2017/2018至2015-2022/2023','final_window':'2024-01-01至2026-10-23','2024_2025_exposed':True,'2026_independence':'未认证','independent_final_executor_configured':False},
 'unverified':['真实生产factory/MCP transport、调度、平台通知与新候选云端工程链','完整原生回执/日志/订单收集、自动结算关轮及完整计费认证派发','完整US200/SID、价格/公司行动、财务数值和历史版本/公开/实际送达/摄入认证','开发初两次无trace晚响应失败根因；未归档历史私有store的8/8及10/10未独立重放','任意文件系统竞争、硬终止/断电耐久性、原人类额度授权对话及远端真实性','阶段3–7、2026样本独立性和金融有效性'],
 'next_required_work':['以新SHA追加归档WR29关闭，保留原2d失败报告及所有辅助失败，不倒改历史','维持真实派发关闭，按原S2清单准备受限宿主/transport及完整回执收集，另行授权后才能真实联调','补齐历史数据与完整计费认证证据，分项独立验收后再申请完整阶段2','正式研究、自动GPT、交易及最终测试继续关闭'],
 'artifacts':{'root_commands':'root_execution_records.json','independent_commands':'entry_agent/execution_records.json; api_agent/execution_records.json; archive_agent/replay_execution.json','identity':'source_git_manifest.json; identity_verification.json; root_guard.json','original_MRE':'original_minimal_wr29.py; original_MRE_replay.json; old_failed_minimum.*; new_fixed_minimum.*','minimum_command':'python -B original_minimal_wr29.py source','seal':'python -B verify_artifacts.py'}
}
report['reviewer_corrections']['formal_QA_wording']='10个顶层定义包含3个私有helper，不称10个公开接口；旧草稿formal_report_pre_QA.json及首QA问题保留。首次shell措辞编辑因引号失败未改报告，另存记录后用独立脚本更正。'
(R/'formal_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
text='WR-29/P1独立复验：固定c2e63ac原CLI/stdio合法factory缺陷范围修复后通过、关闭。新产品确认缺陷0；阶段2整体仍未通过。\n\n原最小脚本不改：旧2d canonical/script/module=0/2/2，assertion exit1；新c2=0/0/0，exit0。默认off、严格factory/controller/authority门槛、真实UTC、跨入口迟到/重启不重派均实际验证。原2d失败不倒改。\n\n实际1012仓库、原host19、新entry6、scope7通过；原独立stdio15/61+4/12、API12/63+6/26、原锁18/37、通知12/79+6/27、周期7/28当前重放首跑通过；新增entry8/51首跑通过，append3/28更正审核者OS字段期望后通过。计数重叠不相加。\n\n开发辅助79/84、89/90和trace分别保留；原store未归档，8/8与10/10仅核对归档记录、未独立重跑。新Win32拒写只是独立等效案例，不归因首两次无trace错误，不将历史失败追认通过。\n\n348工作树守卫前后相等，5份CRLF表示不冒称Git原字节。161原件及完整旧ZIP/Git映射核验。71账本不变，3/13累计16、R17/20、L3/16；实际云端调用和权威预算写入0。\n\n阶段矩阵：\n'
for s in stages:text+=f"{s['stage']} {s['modules']}：{s['verdict']}；证据：{s['evidence']}；缺口：{s['missing']}\n"
text+='\n后续工作：\n'+'\n'.join(report['next_required_work'])+'\n\n完整机器报告：\n'+json.dumps(report,ensure_ascii=False,indent=2)+'\n\n原可运行最小检查（以source参数选择旧/新树，成功预期始终0）：\n'+(R/'original_minimal_wr29.py').read_text()
(R/'formal_report.txt').write_text(text,encoding='utf-8')
print(json.dumps({'review_id':report['review_id'],'bytes':(R/'formal_report.json').stat().st_size,'sha256':hashlib.sha256((R/'formal_report.json').read_bytes()).hexdigest(),'WR29':'fixed_verified_closed','phase2_accepted':False}))
