from pathlib import Path
import json,hashlib,re,sys
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parent
def read(name):return json.loads((R/name).read_text(encoding='utf-8-sig'))
api=read('host_api_agent/report.json');stdio=read('stdio_agent/report.json');archive=read('archive_agent/report.json')
repo=read('repository_verification.json');identity=read('identity_verification.json');guard=read('root_guard.json');maps=read('source_git_manifest.json')
assert repo['local_tests_passed'] and re.search(r'Ran 1006 tests.*?OK',repo['test_output'],re.S)
assert not api['findings'] and len(stdio['findings'])==1 and not archive['findings']
assert not guard['source']['changed'] and not guard['materials']['changed']
assert guard['work_source']['changed']==['audit/stage_verification.json']
finding=stdio['findings'][0]
assert finding['id']=='WR-29' and finding['line']==469 and finding['priority']=='P1'
tests=[
 {'name':'repository','methods':1006,'passed':1006,'failures':0,'errors':0,'skips':0,'scenarios':None,'kind':'repository_synthetic_suite'},
 {'name':'developer_host_subset','methods':19,'passed':19,'failures':0,'errors':0,'skips':0,'scenarios':None,'kind':'subset_rerun_not_extra_unique_tests'},
 {'name':'developer_scope_metadata','methods':7,'passed':7,'failures':0,'errors':0,'skips':0,'scenarios':None,'kind':'metadata_boundary_suite'},
 {'name':'independent_Python_API','methods':18,'passed':18,'failures':0,'errors':0,'skips':0,'scenarios':89,'kind':'new_independent_synthetic_and_native_processes'},
 {'name':'independent_stdio_CLI','methods':19,'passed':17,'failures':2,'errors':0,'skips':0,'successfully_completed_scenarios':69,'kind':'new_independent_actual_subprocess_and_synthetic'},
 {'name':'prior_Windows_lock_replayed_on_current_source','methods':18,'passed':18,'failures':0,'errors':0,'skips':0,'scenarios':37,'kind':'original_independent_suite_replay'},
 {'name':'prior_notification_main_replayed','methods':12,'passed':12,'failures':0,'errors':0,'skips':0,'scenarios':79,'kind':'original_independent_suite_replay'},
 {'name':'prior_notification_supplement_replayed','methods':6,'passed':6,'failures':0,'errors':0,'skips':0,'scenarios':27,'kind':'original_independent_suite_replay'},
 {'name':'prior_cycles_rounds_replayed','methods':7,'passed':7,'failures':0,'errors':0,'skips':0,'scenarios':28,'kind':'original_independent_suite_replay'}
]
for t in tests:t['actually_executed']=True
stages=[
 {'stage':0,'modules':'规范、身份、Registry、预算、归档','implementation':'已有组件','evidence':'1006回归、216身份、205归档恢复及71事件重放','verdict':'原有组件已测回归范围通过','missing':'不授予新CLI或真实调度通过'},
 {'stage':1,'modules':'因子、PIT、标签、固定模型及滚动内核','implementation':'与975相同','evidence':'原213份身份文件未改；1006包含旧987回归','verdict':'已测回归范围通过','missing':'无经济因子/模型/金融有效性验收'},
 {'stage':2,'modules':'QC、任务桥、通知恢复与新宿主','implementation':'部分实现','evidence':'API18/89通过；stdio19中2失败；旧通知/锁/周期重放通过','verdict':'启用CLI/stdio失败；整体未通过','missing':'WR29；真实factory/transport/通知联调；完整数据认证及计费认证派发'},
 {'stage':3,'modules':'评价和滚动原语','implementation':'局部内核','evidence':'仓库合成回归','verdict':'未验收','missing':'完整分层收益/风险与固定真实六轮研究'},
 {'stage':4,'modules':'无订单工程接收器、标签成交/成本定义','implementation':'局部组件','evidence':'旧b1a工程证据保留，无新云端执行','verdict':'未验收','missing':'完整组合交易、账本对账、风险及压力验证'},
 {'stage':5,'modules':'受限提案、状态机、注入接口','implementation':'局部组件','evidence':'离线回归；新host不等于GPT研究闭环','verdict':'未验收','missing':'实际GPT客户端、模型/调用/费用设置及真实闭环'},
 {'stage':6,'modules':'结构相似、相关性与复杂度','implementation':'局部组件','evidence':'合成回归','verdict':'未验收','missing':'完整搜索、消融、扣费后增量与选择偏差实证'},
 {'stage':7,'modules':'冻结、暴露及关闭闸门','implementation':'元数据骨架','evidence':'既往暴露与关闭闸门保留','verdict':'未验收','missing':'独立最终执行器、前向监控回滚及2026独立性'}
]
report={
 'review_id':'AQRP-20261029-2D1D306-HOST010-26','review_date':'2026-10-29','timezone':'Asia/Shanghai',
 'reviewed_source_commit':'2d1d3060dbc7eb136c1dee61f0647977528b8aad','baseline_commit':'975f676d62b561689909744f9e7236290e3f5fcb',
 'evidence_commits':{'materials':'fe088461e84586d7feb73f20be54a22d09706942','post_materials_handoff':'027f29c6a6fe30fc2e1ef9e0b5af9b88d6875c25','historical_runtime':'b1a4041ce98867047294b8f0830292af5d7ec56e','historical_terminal':'ca5e4f3f68a58297cf02d97629346e10306ebcf0'},
 'conclusion':'新宿主启用CLI/stdio范围不通过：WR29/P1阻断合法factory。Python API及其他实际通过的本地范围单独保留；阶段2整体未通过。975f676原有限通过不变。',
 'source_manifest_hash':identity['source_hash'],'deployment_hash':identity['deployment_manifest_hash'],'implementation_hash':identity['implementation_hash'],'configuration_hash':identity['configuration_hash'],
 'environment':read('environment.json'),
 'tool_capabilities':{'readonly_Git_GitHub':True,'private_native_Windows_subprocess_and_synthetic_tests':True,'QC_calls':0,'Research_executions':0,'LEAN_submissions':0,'compile_calls':0,'market_or_model_calls':0,'production_automation':0,'authoritative_budget_or_production_writes':0,'PR_push_approval_merge':0},
 'version_consistency':{'source_raw_files':7080,'materials_raw_files':7445,'managed_identity_files':216,'prior_managed_files':213,'prior_managed_changes':[],'new_managed_files':identity['new_managed_files'],'deployment_files':44,'deployment_raw_unchanged_from975':True,'two_builds_config_changed':False,'source_materials_managed_equal':True,'materials_git_verifier_exit':0,'current_packet_files':57,'source_and_materials_guard_changes':[],'scratch_changes':['audit/stage_verification.json'],'post_materials_handoff_only':['audit/review_handoffs/host010.json']},
 'PR':{'number':2,'draft':True,'merged':False,'source_CI_run':40848715203,'Python3.10':'success','Python3.11':'success','independently_extracted_CI_test_count':None},
 'stage_results':stages,'tests':tests,'actually_executed':True,
 'minimum_reproduction':{'program':'python -B minimal_wr29.py source','assertion_program_exit':1,'canonical_import_control_exit':0,'documented_script_expected_exit':0,'documented_script_actual_exit':2,'module_expected_exit':0,'module_actual_exit':2,'classification':'实际产品失败；不计额外通过方法','uses':'空Memory Registry、空stdin、标准同源码factory，无attempt或真实工具调用'},
 'counting':'方法、成功完成子场景、子进程请求、原套件重放、专项子集与静态核验重叠，不累加独有总数；stdio失败后的未执行步骤不算通过。开发辅助10边界本轮未独立重跑，未计为通过。',
 'findings':[finding],
 'local_host_scope':{'Python_API':'18方法/89场景已测合成范围通过','stdio_protocol_other_tested_boundaries':'17方法通过','enabled_CLI_factory':'WR29失败，2方法失败','real_factory_transport_scheduler':'未部署/未验证','automatic_native_receipt_collection_and_settlement':'未完成；host仅awaiting_native_receipt，仍须原parser/日志/零订单/Bridge/Registry','authority_boundary':'可信Python factory/TransportAuthority与原派发上下文不是外部密码学来源证明；stdin不授读取权限'},
 'reviewer_corrections':{'API':'首跑1个审核夹具签名错误，改为既定backtest_observation五参数及Bridge completion_source；主12/63重跑通过，补6/26首次通过，原脚本/输出保留','stdio':'首跑15方法有2失败/1错误；400000中文约1.2MB未超2MiB，改700000；在失败CLI后先断言退出码避免后续JSON解析错误。保留原合法factory期望，修正后仍2产品失败','archive':'首跑审核helper遗漏UTF8，在Windows默认GBK解码失败；仅修正编码，原脚本和输出保留','product_source_or_assertions_changed_to_force_pass':False},
 'historical_findings':{'WR01_WR28':'原精确SHA和有限范围保留，不扩大','prior975_review_id':'AQRP-20261029-975F676-RECOVERY009-25','prior_formal_raw_sha256':'ef0fa58a5e87d0930ed7b6c6ddbd11a1b96ecc0ea56678dd7989dbee2a890057','prior_987':'原测试文件未变，包含于本次1006；新19专项重跑是重叠子集','new_prior_independent_replays':'Windows18/37、通知12/79+6/27、周期7/28在当前源码全部首跑通过；脚本内旧SHA仅历史标签','all_original_WR_suites_rerun_this_round':False},
 'archive_verification':{'static_file_blob_metadata_checks':59339,'static_checks_are_not_unit_methods':True,'old_complete_ZIP':archive['old_complete_ZIP'],'selected_archive':archive['selected_archive'],'developer_guard':archive['developer_guard'],'provisional14_synthetic_store_records':'原c5 Git blob保留，最终移除，未检出长路径provisional树','selected_archive_is_complete_original_bundle':False},
 'budget_replay':{'events':71,'journal_sha256':'cea800e0fe5a0facc5f2aed238d105a6f3d1c80db40c1dc4b674efd3026cd48a','prior69_prefix_sha256':'2d3131a32864434d22635f058ec3de8062e9b1b610a90185bf6ba6cf9c637934','prior69_prefix_raw_preserved':True,'configuration_cycle':{'used':3,'limit':13},'lifetime_configurations':16,'Research':{'used':17,'limit':20},'LEAN':{'used':3,'limit':16},'round008':'closed','new_events':0,'new_debits':0,'refunds':0,'original_human_authorization_dialogue_independently_obtained':False,'future_1_1_1':'仅准备，无授权/准入/attempt/project/backtest ID'},
 'platform_evidence_level':{'current_review':'本地原生Windows合成/子进程，Git/ZIP/归档离线核验；无独立QC访问','historical_b1a':'保留原975审核的归档平台元数据离线重解析范围；本轮不重复宣称新QC运行','historical_Research_checks':13,'historical_LEAN_checks':7,'historical_orders':0,'historical_PROJECT_raw_files':43,'historical_Research_EOF_normalized':0,'historical_LEAN_EOF_normalized':43,'historical_LEAN_original_source_identity_match':False,'historical_terminal':'一次历史对账；未观测自动push','new_source_cloud_run':None,'new_source_orders':None},
 'software_acceptance':{'prior975_scope':'原有限通过保留','stage0_1_existing_components_regression':'已测范围通过','new_host_Python_API':'已测合成范围通过','new_host_enabled_CLI_stdio':'失败_WR29','new_host_component_overall':'不通过','real_host_engineering_chain':'未验收','stage2_overall':'未通过','stages3_to7':'未验收','formal_research_enabled':False,'GPT_runtime_enabled':False,'orders_enabled':False,'final_test_enabled':False},
 'data_certification':{'full_historical_US200':False,'SID_economic_ambiguity_resolved':False,'financial_statement_numeric_catalog_count':0,'financial_vintage_publication_actual_delivery_ingestion':False,'complete_charged_certification_dispatch':'未完成'},
 'financial_evidence':False,'financial_metrics':{'IC':None,'returns':None,'costs':None,'risk':None,'NAV':None},
 'research_constraints':{'historical_top200_US_equities':True,'no_rank201_substitution':True,'timezone':'America/New_York','rolling':'六个固定八年训练/一年验证窗，2010-2017/2018至2015-2022/2023','final_window':'2024-01-01至2026-10-23','2024_2025_exposed':True,'2026_independence':'未认证','independent_final_executor_configured':False},
 'unverified':['WR29阻断实际启用子进程后的发现/恢复/响应/时钟链；canonical import控制不能替代官方CLI','生产factory、MCP transport、真实调度与自动通知传输；新候选真实云端工程链','完整US200/SID、价格/公司行动、财务数值与历史版本/公开/实际送达/摄入认证','完整自动原生回执收集/关轮与完整计费认证派发','任意文件系统竞争、OS硬终止/断电耐久性、远端真实性及原人类额度授权对话','阶段3–7、2026独立性和金融有效性'],
 'next_required_work':['在新固定SHA统一公开宿主类型的规范导入身份，保留薄CLI与严格默认off/权限门槛，修复WR29','实际subprocess验证脚本及-m启用serve空stdin退出0、合法pending任务流程/UTC、坏factory仍拒绝；保留现失败并重跑全部相关回归','按新SHA独立复验后才讨论另行授权的最小真实联调；不得自动执行1/1/1或重开008','补齐生产transport/回执收集与数据/计费认证证据，阶段2整体重新申请验收；最终测试等闸门继续关闭'],
 'artifacts':{'commands':'root_execution_records.json; host_api_agent/execution_records.json; stdio_agent/execution_records.json; archive_agent/replay_execution.json','raw_maps':'source_git_manifest.json; identity_verification.json; root_guard.json','minimum':'minimal_wr29.py; minimum_execution.json; minimum.stdout; minimum.stderr; mre_wr29/*','original_failures':'各agent首脚本/首结果/修正差异均保留','seal':'python -B verify_artifacts.py'}
}
(R/'formal_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
text='新宿主CLI/stdio不通过，发现WR-29/P1；阶段2整体未通过。固定源码2d1d306、资料fe08846。\n合法factory正常导入followup_host.FollowupHost；官方脚本/-m中类型为__main__.FollowupHost，第469行拒绝同源码合法类型。空stdin+空Memory Registry实际exit2，应0；canonical import控制exit0。不要通过改factory为__main__或删除权限/类型门槛规避。\n\n实际1006仓库、19专项、7元数据自测通过；新独立API18/89通过；stdio19中17过2失败，69成功完成场景，失败后未到达的步骤未算通过。旧Windows18/37、通知12/79+6/27、周期7/28原脚本在新source全部首跑通过。计数重叠不相加。\n\n完整205原件/原ZIP/旧Git映射已核对；346工作树守卫前后相等，其中5项CRLF表示单独核验，不能统称Git原字节相等。71事件及3/13累计16、R17/20L3/16不变；真实调用和预算写入0。\n\n阶段矩阵：\n'
for s in stages:text+=f"{s['stage']} {s['modules']}：{s['verdict']}；证据：{s['evidence']}；缺口：{s['missing']}\n"
text+='\n修复任务：\n'+'\n'.join(report['next_required_work'])+'\n\n完整机器报告：\n'+json.dumps(report,ensure_ascii=False,indent=2)+'\n\n实际最小复现（当前失败断言保留）：\n'+(R/'minimal_wr29.py').read_text()
(R/'formal_report.txt').write_text(text,encoding='utf-8')
print(json.dumps({'review_id':report['review_id'],'bytes':(R/'formal_report.json').stat().st_size,'sha256':hashlib.sha256((R/'formal_report.json').read_bytes()).hexdigest(),'findings':1,'blocking':'WR29/P1'}))
