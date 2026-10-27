from pathlib import Path
import hashlib,json
R=Path(__file__).parent
def read(rel):return json.loads((R/rel).read_text(encoding='utf-8-sig'))
def save(rel,obj):(R/rel).write_bytes((json.dumps(obj,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
summary=read('test_execution_summary.json');evidence=read('evidence_agent/evidence_verification.json');native=read('native_agent/report.json');cloud=read('cloud_comparison.json')
assert native['findings']==[]and evidence['passed_checks']==327
tests=[{'suite':'repository','methods':530,'subcases':None,'passed':530,'failed':0,'errors':0,'skipped':0,'actually_executed':True},
 {'suite':'16历史套件（含认可adapted56及pending账本夹具适配）','methods':248,'subcases':2307,'passed':248,'failed':0,'errors':0,'skipped':0,'actually_executed':True}]
for x in summary['additional_accepted']:
    tests.append({'suite':x['suite'],'methods':x['methods'],'subcases':x['subcases'],'passed':x['passed_methods'],'failed':x['failed_methods'],'errors':x['errors'],'skipped':x['skipped'],'actually_executed':True})
for path,label,m,n in [('preflight_agent/pure_corrected_results.json','新增预检/诊断纯函数',7,42),
 ('preflight_agent/cli_first_results.json','新增stage2 CLI预检入口',4,24),('preflight_agent/preflight_cli_first_results.json','新增deployment_preflight CLI',1,4)]:
    d=read(path)
    f=d.get('failed_methods',d.get('failure_records',d.get('failures')))
    e=d.get('error_methods',d.get('error_records',d.get('errors')))
    assert d['methods']==m and d['subcases']==n and f==e==0
    tests.append({'suite':label,'methods':m,'subcases':n,'passed':m,'failed':0,'errors':0,'skipped':0,'actually_executed':True})
for key,label in [('new_first_run','新增原生失败/拒绝/恢复'),('compatibility_replay','旧完成合同边界')]:
    d=native[key]if key=='new_first_run'else native[key]['boundaries']
    assert d['failure_records']==d['error_records']==d['skipped']==0
    tests.append({'suite':label,'methods':d['methods'],'subcases':d['subcases'],'passed':d['passed_methods'],'failed':0,'errors':0,'skipped':0,'actually_executed':True})
stages=[
 {'stage':0,'modules':'章程、配置生成、身份、Registry、预算与归档','implementation':'既有工程骨架及本轮身份/账本变更','evidence':'530仓库回归、327证据检查、并发/恢复边界','blockers':[],'status':'修复后通过（已测软件范围）'},
 {'stage':1,'modules':'FactorSpec/白名单、标签、PIT、模型、数值内核','implementation':'通用计算核；无活跃生产因子/模型','evidence':'独立手算/数值/时间旧套件重放','blockers':[],'status':'修复后通过（既有离线范围）'},
 {'stage':2,'modules':'QC、采集缓存、任务桥、原生回执、冻结预检','implementation':'新增离线范围通过；新版未部署/运行','evidence':'独立合成链、旧LEAN原生失败及只读源码','blockers':['新版真实成功运行','失败worker具体源码差异','Research原生异常适配及实证','完整数据认证'],'status':'待验收／证据不足'},
 {'stage':3,'modules':'IC/RankIC、分层、样本匹配、六轮评价','implementation':'IC、样本匹配及六轮通用组件已覆盖；分层收益未实现，生产研究未注册','evidence':'数值与合成测试，无真实因子评价','blockers':['分层收益实现','阶段2数据认证','冻结因子/模型与实际六轮结果'],'status':'未验收'},
 {'stage':4,'modules':'信号、组合、订单成交、现金、成本、风险','implementation':'仅工程接收宿主；完整交易适配及对账未实现','evidence':'合成接收链；旧真实LEAN初始化失败','blockers':['交易全链、成交成本风险、真实Research/LEAN一致性'],'status':'未实现／未验收'},
 {'stage':5,'modules':'GPT受限提案、调用额度、持久工作流','implementation':'注入adapter的状态机；GPT模型/调用/费用未配置且关闭','evidence':'固定程序与合成工作流测试','blockers':['实际GPT客户端和有限生成修复闭环'],'status':'未实现／未验收'},
 {'stage':6,'modules':'结构去重、相关、受限搜索、消融与组合增量','implementation':'通用辅助组件；无实际受限搜索产物','evidence':'离线组件测试，无经济评价','blockers':['试验登记、消融、成本后净增量与选择偏差证据'],'status':'未验收'},
 {'stage':7,'modules':'完整冻结、独立最终测试、前向监控','implementation':'冻结元数据与关闭闸门；独立执行器未配置','evidence':'关闭开关和暴露记录静态核对','blockers':['完整冻结与独立执行器','2026独立性、前向监控/停止回滚'],'status':'未实现／未验收'}]
gates=[
 {'id':'G1','priority':'P1验收缺口','status':'待验收','requirement':'证明新版固定源码在真实Research、联合历史采集/缓存复用及LEAN成功运行；保留原生提交、终态与原attempt绑定。旧初始化失败不满足成功运行要求。'},
 {'id':'G2','priority':'P1验收缺口','status':'证据不足','requirement':'取得失败worker具体源码/哈希或受控诊断证据，解释冻结不一致。当前返回25份引用一致、官方自动导入说明及合成插入均不能证明本次根因或已修复。'},
 {'id':'G3','priority':'P1未实现范围','status':'未验收','requirement':'实现并独立验证Research原生异常回执解析及失败恢复，补真实失败cell原件；正常cell内固定检查失败不能替代。'},
 {'id':'G4','priority':'P1数据认证缺口','status':'证据不足','requirement':'补全历史当时US200、永久SID/映射/公司行动、原始价格、供应商DollarVolume、财务公开/版本/实际送达及摄入证据；两股工程样例和模型化end_time不足。'}]
report={
 'review_id':'AQRP-20261027-66FF72F-WINDOWS-16','review_date':'2026-10-27','reviewed_source_commit':summary['reviewed_source_commit'],
 'baseline_commit':'84414ab49c39e25cb50ece1c1debeefa3993c874',
 'evidence_commits':{'current_archive':summary['reviewed_source_commit'],'previous_software_acceptance':'81fbe5294055423e88ee5aeae48ca6223e7971da',
 'previous_metadata_acceptance':'84414ab49c39e25cb50ece1c1debeefa3993c874','actual_old_cloud_source':'75f24629d3b7f94ff3aa906c3ce8a2b8b9a8d3c4','original_execution_archive':'1f7c0c0ab4640a825fd317684f854158ad5d2193'},
 'verdict':'本轮新增及回归的离线软件范围通过；未发现新增软件缺陷。阶段2整体待验收，数据认证及金融验收未通过。',
 'pr':{'number':2,'state':'open','draft':True,'merged':False,'head':summary['reviewed_source_commit'],'base_branch':'feat/staged-research-workflow','base_sha':'6a1edbf07fa8fc6cf774084094f4beacc28ff60b'},
 'source_manifest_hash':evidence['source']['review_hash'],'execution_source_manifest_hash':evidence['source']['execution_hash'],
 'deployment_hash':evidence['source']['local_deployment_hash'],'implementation_hash':evidence['source']['implementation_hash'],
 'active_configuration_hash':evidence['source']['active_configuration_hash'],'raw_git_files':3178,'review_manifest_files':130,'local_deployment_files':29,
 'environment':read('environment.json'),
 'tool_capabilities':{'offline_Python':True,'actual_QuantConnect_SDK':False,'GitHub_read_only':True,'QC_read_only':True,
 'QC_calls':{'list_projects':1,'read_open_project':1,'read_file':26,'read_backtest_after_existing_terminal_delivery':1},
 'Research_executions':0,'LEAN_submissions':0,'model_API_calls':0,'cloud_writes':0,'production_changes':0,'PR_approval_or_merge':0,'notebook_content_read':False},
 'stage_results':stages,'tests':tests,'test_counts_are_unique':False,
 'other_checks':{'evidence_checks':{'checks':327,'passed':327,'failed':0,'actually_executed':True,'unit_methods':0},
 'manual_probes':{'legacy_failure':4,'new_injected_write_failure':4,'bounded_reproduction_chains':4,'bounded_script_executions':2,'all_passed':True,'unit_methods':0},
 'new_scope_counts':{'unit_methods':18,'subcases':132,'all_passed_after_reviewer_fixture_correction':True},
 'new_preflight_actual_CLI_processes':62,'native_agent_actual_CLI_processes_including_compatibility':109,
 'native_agent_synthetic_metadata_finish_calls':14,'native_agent_worker_executions':0,
 'joint_worker_invocations':{'Research_pure_Python':11,'receiver_initialize':6,'receiver_finish':5,'receiver_slices':15,'probe_helper_replays':3},
 'fraction_pure_Python_worker_runs':2,'old_native_parser_replay_calls_by_evidence_agent':3,'old81_isolated_Bridge_consume_calls':4,
 'CI':{'run_id':40471231434,'Python_3_10_job':122078558461,'Python_3_11_job':122078558029,'both_success':True,'CI_test_count_read_from_logs':None,'auditor_executed_CI':False}},
 'first_results_preserved':[
 {'scope':'新增pure7/42','passed_methods':6,'failed_methods':0,'errors':1,'cause':'审核器在进入产品前对surrogate路径计算外部hash失败；另稿用合法固定expected_hash到达原拒绝断言，7/42通过。'},
 {'scope':'历史e513 24/36','passed_methods':23,'failed_methods':1,'errors':0,'cause':'旧pending假设遇当前已failed的13事件账本；另稿仅选归档12事件夹具，断言AST不改，24/36通过。'},
 {'scope':'历史quick7','passed_methods':6,'failed_methods':1,'errors':0,'cause':'同一旧pending账本假设；原脚本字节不改，隔离workspace只换历史12事件夹具，7/0通过。'},
 {'scope':'工程恢复5/46','passed_methods':4,'failed_methods':1,'failure_subcases':12,'errors':0,'cause':'审核器漏将direct_freeze_entry.py放到OUT；原脚本/辅助文件字节不改，另OUT重放5/46通过。'},
 {'scope':'静态证据读取','cause':'先误读payload.identity路径触发KeyError，后将开发stdout JSON误当stderr导致325/326；原件保留，修正读取后327/327。非产品缺陷。'},
 {'scope':'报告汇总','cause':'前两稿没有覆盖三种实际计数字段而KeyError/AssertionError；均未生成正式报告，两稿和trace保留，读取实际字段后汇总。测试输出和通过标准不变。非测试/产品失败。'}],
 'findings':[],'remaining_acceptance_gates':gates,
 'budget_replay':{'authoritative_event_count':13,'original_event_prefix':12,'original_prefix_unchanged':True,
 'configurations':{'used':6,'limit':12,'normal_used':6,'reserve_used':0},'research':{'used':9,'limit':20,'normal_used':6,'reserve_used':3},'lean':{'used':1,'limit':16,'normal_used':1,'reserve_used':0},
 'engineering_stop_caps':{'configurations':2,'research':2,'lean':2},'engineering_used':{'configurations':1,'research':1,'lean':1},
 'old_attempt':'bfd00f2611fd4496b9498d4597618a8e','old_attempt_status':'failed','isolated_replay_events':[12,13,13],
 'actual_registry_writes':0,'new_budget_charges':0,'refund':False,'old_success_result_created':False,'protected_old_paths_unchanged':38},
 'platform_evidence_level':['静态源码检查','审核者实际运行独立合成测试','开发原生工具证据已离线重解析','审核者独立只读取得旧LEAN终态及当前源码'],
 'platform':{'project_id':38436695,'backtest_id':'39cafa1e9b11f91b27e396b66d033a6d','old_status':'runtime_error','old_terminal':True,
 'native_error_isError':True,'native_success':False,'diagnostic_strings':2,'failure_tasks':1,
 'native_wrapper_sha256':'867148e882d39a024d12d68a01803ba80c282f05b872f16616dfded53c7eea27',
 'normalized_observation_hash':'ff5002cdf15423e9a7f45a0b5b5744d89c675506ef7331df49bdec9b4f5c3233',
 'completed_field':None,'progress':None,'orders':None,'financial_statistics':None,'initialization_failure':'Cloud implementation differs from the frozen deployment',
 'current_returned_old_implementation_matches':25,'current_returned_input_matches':1,'returned_source_reference_hash':cloud['returned_implementation_manifest_hash'],
 'original_input_hash':cloud['input_raw_sha256'],'raw_candidate_matches_in_old25':16,'worker_source_verified':False,'full_cloud_inventory_certified':False,'candidate_deployed':False,'candidate_cloud_successful_run':False},
 'historical_findings':{'WR01_WR18':'保留原固定SHA与范围的修复后通过；本轮跨模块回归通过，不将软件结论扩为金融有效性。','WR19':'84414ab元数据更正通过；旧原声明和历史12计数保存，9+4=13比较范围明确。','new_WR':[]},
 'unverified':['新版真实SDK/云端成功和实际Research原生异常链','失败worker具体文件/源码差异与根因修复','完整历史US200、财务版本及供应商实际送达认证',
 'OS断电/kill持久性和未覆盖的任意封装语法','非本机平台的独立运行；CI只核对状态','真实因子/模型/组合、成本后增量、独立最终评估和前向运行','2026最终区间独立性；2024–2025既往暴露已知'],
 'software_acceptance':{'status':'通过（本轮明确覆盖的离线范围）','scope':['v1/v2本地物理源码预检和扣费前拒绝','单次读取/EOF保留/安全诊断','只读源码引用预检','原生运行失败及受限编译拒绝/原attempt绑定','接受/拒绝共享锁、幂等、写失败恢复及旧准入兼容'],
 'full_phase2':False,'root_cause_repaired':False,'v1_controller_source_recheck':False,'v1_scope':'冻结物理部署严格校验；不冒称具有v2稳定控制器/目录身份保证'},
 'data_certification':{'status':'证据不足','accepted':False,'full_historical_US200':False,'financial_vintage':False,'actual_vendor_availability':False},
 'financial_evidence':False,'financial_metrics':None,
 'research_gates':{'formal_research_enabled':False,'automatic_GPT_enabled':False,'final_test_enabled':False,'orders_enabled':False,'GPT_model':None,'GPT_call_limit':None,'GPT_spend_limit':None,'active_factor':None,'active_model':None,'active_trading':None},
 'evidence_files':{'test_execution_details':'test_execution_summary.json','actual_commands':['runs/execution_records.json','additional_regression_records.json','preflight_agent/cli_command_log.json','native_agent/report.json'],
 'static_matrix_with_lines_and_hashes':'evidence_agent/system_matrix.json','native_replay':'evidence_agent/old_bridge_replay.json','cloud_readback':'cloud_comparison.json','minimal_reproduction':'verify_phase2_scope.py'}}
save('formal_report.json',report);save('findings.json',[])
lines=['结论：'+report['verdict'],'审核SHA：'+report['reviewed_source_commit'],'基线：'+report['baseline_commit'],
 '固定原始源码3178份，审核清单130份，29份本地部署；均与Git/内容身份一致。新候选未部署。',
 '实际旧LEAN已终结：Runtime Error，初始化冻结部署不一致；不是成功回测。orders/progress/completed/statistics缺失，均null。',
 '审核者独立QC只读：先list_projects，再open_project、26份Python源码、已交付旧终态read_backtest各一次；未读notebook/日志，未轮询或重交。',
 '25份旧实现及原input原字节全匹配；不证明失败worker快照、完整平台文件全集或新故障已修。',
 '\n全系统覆盖矩阵：']
for x in stages:lines.append(f"阶段{x['stage']}：{x['status']}。{x['modules']}；{x['implementation']}；证据：{x['evidence']}；缺口：{'；'.join(x['blockers'])or'本轮已测范围无新增阻断问题'}。")
lines+=['\n实际测试（方法/子例，跨套件有重叠）：']
for x in tests:lines.append(f"{x['suite']}：{x['passed']}/{x['methods']}方法，子例{x['subcases']}；失败{x['failed']}、错误{x['errors']}、跳过{x['skipped']}。")
lines+=['另有原失败4、新写失败4手工探针、便携4链（执行两次但不计8独有链）及327静态/证据检查。',
 '原始首轮失败均保留：pure6/7+1审核器错误；历史pending夹具原e51323/24、quick6/7；工程辅助文件遗漏首4/5且12子例失败；静态读取两次纠正。适配只改隔离审核夹具/辅助位置，不改产品和断言。',
 'CI双版本成功只作GitHub平台状态证据，未从日志独立统计CI测试数。',
 '\n预算：权威13事件，原12事件raw前缀不改。全局配置6/12、Research9/20、LEAN1/16；工程各1/2。隔离原件结算12→13→13，无退款/成功产物；实际权威账本和源未写。',
 '\n按优先级列出的验收缺口（无新增WR软件缺陷）：']
for x in gates:lines.append(x['id']+' '+x['priority']+' '+x['status']+'：'+x['requirement'])
lines+=['\n复现：在固定依赖环境运行 python -B verify_phase2_scope.py source；4链通过，无提供商调用/Registry写入。',
 '完整生产回归入口 python -B tools/stages.py verify 必须在source临时副本中运行。其他原脚本写旁边结果，先复制scripts/support到新目录；原始本机路径、命令与首次输出已保存。',
 '金融证据=false；正式研究、自动GPT、最终测试、交易关闭。2024–2025已暴露，2026独立性未知。软件通过不证明因子、模型或组合有效。',
 '本轮未修改/提交/批准/合并开发成果。下一轮优先补G2，再在单独授权与准入下补G1/G3，并独立完成G4。']
(R/'formal_report.txt').write_bytes(('\n'.join(lines)+'\n').encode('utf-8'))
print(json.dumps({'review_id':report['review_id'],'test_rows':len(tests),'new_software_findings':0,'full_phase2_accepted':False,'financial_evidence':False},ensure_ascii=False))
