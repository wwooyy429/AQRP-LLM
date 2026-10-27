from pathlib import Path
import json
R=Path(__file__).parent
def load(p):return json.loads((R/p).read_text(encoding='utf-8-sig'))
def save(p,x):(R/p).write_bytes((json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode())
E=load('source_evidence_verification.json');T=load('test_execution_summary.json');N=load('native_agent/report.json')
assert E['checks_run']==E['checks_passed']==227
findings=[load('finding_WR21.json'),load('cert_agent/finding_WR20.json')]
save('findings.json',findings)
stages=[
 {'stage':0,'modules':'章程、配置生成、身份、Registry、预算及归档','implemented':'既有工程骨架；预算共享原子门保持','evidence':'612仓库、历史回归、227身份/证据检查','blockers':[],'status':'既有已测范围通过'},
 {'stage':1,'modules':'FactorSpec、数值、标签、PIT、通用模型','implemented':'通用计算内核；无活跃因子/模型','evidence':'历史数值/时间/缓存独立套件','blockers':[],'status':'既有离线范围通过'},
 {'stage':2,'modules':'采集/缓存、任务桥、原生回执、entry/dispatch、源码诊断和数据审计','implemented':'新增实现；部分独立范围通过','evidence':'WR20/21反例、原生失败恢复、只读源码/固定cell','blockers':['WR21/P1','WR20/P2','实际Research失败，缺真实成功链','旧worker差异及正式数据认证证据不足'],'status':'软件验收失败；整体未通过'},
 {'stage':3,'modules':'IC/RankIC、分层、样本匹配、六轮评价','implemented':'IC/匹配/六轮组件；分层收益未实现','evidence':'合成及数值组件回归','blockers':['分层收益、冻结研究设计及真实六轮结果'],'status':'未验收'},
 {'stage':4,'modules':'信号、组合、订单成交、现金、成本、风险','implemented':'工程接收宿主；完整交易适配未实现','evidence':'合成工程链；无成功真实策略链','blockers':['完整交易/成本/风险/对账及Research-LEAN一致性'],'status':'未实现／未验收'},
 {'stage':5,'modules':'GPT受限提案、调用额度、持久闭环','implemented':'注入adapter的状态机；GPT模型和额度未配、关闭','evidence':'状态机和拒绝门组件测试','blockers':['实际GPT客户端与有限闭环'],'status':'未实现／未验收'},
 {'stage':6,'modules':'去重、相关、受限搜索、消融、成本后增量','implemented':'辅助组件；无实际搜索产物','evidence':'离线组件测试','blockers':['搜索/消融/净增量和选择偏差实证'],'status':'未验收'},
 {'stage':7,'modules':'完整冻结、独立最终评估、前向监控','implemented':'冻结元数据和关闭闸门；独立执行器未配置','evidence':'开关、暴露及时间分区静态核对','blockers':['完整冻结/独立执行器/前向监控','2026独立性未知'],'status':'未实现／未验收'}]
tests=[dict(T['repository'],suite='repository verify'),{'suite':'16 historical suites with explicit recognized fixtures','methods':248,'passed':248,'failed':0,'errors':0,'skipped':0,'subcases':2307,'actually_executed':True}]+[{k:v for k,v in x.items()if k!='result_file'}for x in T['additional_suites']]
report={
 'review_id':'AQRP-20261027-DEB85D9-WINDOWS-17','reviewed_source_commit':E['reviewed_source_commit'],'baseline_commit':E['baseline'],
 'evidence_commits':{'current_archive':E['reviewed_source_commit'],'actual_cloud_source':E['actual_cloud_source_commit'],'previous_offline_acceptance':E['baseline']},
 'verdict':'不通过本轮软件验收：WR21/P1、WR20/P2。阶段2整体未通过；已测原生失败恢复和既有离线回归的局部通过不扩为整体验收。',
 'PR':{'number':2,'state':'open','draft':True,'merged':False,'head':E['reviewed_source_commit'],'base_sha':'6a1edbf07fa8fc6cf774084094f4beacc28ff60b','metadata_source':'GitHub official read-only REST after two connector transport failures'},
 'source_manifest_hash':E['source_manifest_hash'],'execution_source_manifest_hash':E['execution_source_manifest_hash'],'deployment_hash':E['deployment_hash'],'implementation_hash':E['implementation_hash'],'active_configuration_hash':E['active_configuration_hash'],
 'source_counts':{'raw_Git':4270,'review_manifest':138,'local_deployment':31,'developer_raw_outputs':163,'preserved_prior_review_files':2989},
 'environment':load('environment.json'),
 'tool_capabilities':{'offline_Python':True,'actual_QC_SDK_executed':False,'QC_read_only':True,'QC_calls':E['QC_read_calls'],'notebook_outputs_read':False,'Research_executions':0,'LEAN_submissions':0,'models':0,'cloud_writes':0,'authoritative_registry_writes':0,'production_changes':0,'PR_approval_merge':0},
 'stage_results':stages,'tests':tests,'test_counts_unique':False,
 'other_execution':{'static_checks':{'run':227,'passed':227,'failed':0,'unit_methods':0,'actually_executed':True},
 'native_agent':{'actual_CLI':134,'synthetic_finish':14,'worker_or_SDK':0,'old_manual_probes':8,'new_failure_unit_methods':6,'new_failure_subcases':91,'normal_event_replay':[15,17,17],'fault_event_replay':[15,16,18,18]},
 'entry_new_worker_tests':{'methods':6,'passed':6,'subcases':51},'entry_legacy_preflight':{'methods':12,'passed':12,'subcases':70,'actual_CLI':62},
 'entry_root_controls':{'manual_chains':3,'passed':3,'actual_CLI':21,'actual_Windows_parallel_processes':2,'one_dispatch_permission':True},
 'certification_suite':{'methods':13,'passed':12,'failed_methods':1,'failure_records':2,'scenario_checks':43,'errors':0,'skipped':0,'metadata_CLI':4},
 'MREs':T['MREs'],'counts_are_overlapping':True,
 'CI':{'run':40493506432,'py310_job':122153035163,'py311_job':122153034705,'both_success':True,'independently_counted_CI_tests':None}},
 'findings':findings,'first_results_preserved':T['first_nonproduct_failures']+[
 {'scope':'entry reviewer artifact formatting','detail':'Original first/commands JSON end with literal backslash-n; raw preserved. Root strict_result.json is separately normalized, not substituted as native evidence. First saved CLI count17 is authoritative; earlier message14 was a reviewer count error.'},
 {'scope':'entry subagent incomplete expansion','detail':'A tool safety filter ended that child turn. No unrun expansion is counted. Existing saved tests and defect were independently inspected; root separately reran the full MRE and added actual process/dispatch controls.'},
 {'scope':'cert static matrix preparation','detail':'Two reviewer matrix/README-anchor reading errors preserved separately by cert_agent; not errors in the13-method software suite.'}],
 'budget_replay':{'events':17,'old_13_raw_prefix_unchanged':True,'journal_raw_sha256':E['journal_raw_sha256'],
 'configurations':{'used':7,'limit':12,'normal':6,'reserve':1},'Research':{'used':10,'limit':20,'normal':6,'reserve':4},'LEAN':{'used':1,'limit':16,'normal':1,'reserve':0},
 'engineering_used':{'configurations':2,'Research':2,'LEAN':1},'engineering_limits':{'configurations':2,'Research':2,'LEAN':2},'stop_reached':True,'this_review_new_charges':0,'refund':False,'authoritative_writes':0,
 'current_attempt':'f5d05f5b964b4a1d924e4b70cd207386','current_status':'failed','old_LEAN_status':'failed','successful_result_created':False},
 'platform_evidence_level':{'new_Research_failure':'Developer archived native packet independently reparsed offline; no fresh live notebook output read by auditor.',
 'current_source_and_cell':'Auditor independently read listed32 Python files and cell1 source only; no notebook outputs/data.',
 'software_tests':'Actual Windows independent synthetic functions/CLI/processes; no true SDK/market execution.'},
 'platform':{'project_id':38436695,'actual_source_commit':E['actual_cloud_source_commit'],'current_delivered_controller_cloud_executed':False,'Research_attempt':'f5d05f5b964b4a1d924e4b70cd207386',
 'Research_status':'failed','developer_round_real_Research_calls':1,'error_class':'CollectionError','underlying_source_cause_known':False,'raw_error_packet_sha256':'14ae4a18636496737862a1ce314d90ae7fcf1abaf35f8a0f27145e0e839af8f3',
 'original_native_result_hash':'6a5371b3ff243998baded6dc2f9627b110af793a94907a4a73859ced3d5f4f0b','MCP_isError':False,'error_representations':2,'logical_failures':1,'traceback_entries':9,'traceback_physical_lines':43,
 'actual_deployment_hash':E['actual_cloud_deployment_hash'],'actual_input_hash':E['actual_input_hash'],'actual_cell_hash':E['actual_cell_source_hash'],'readback_old31_and_input_raw_match':True,'local_matches_deployed31':29,'local_differs_deployed31':2,
 'full_platform_inventory_certified':False,'failed_old_worker_source_verified':False,'actual_success_engineering_report':False,'new_LEAN_submitted':False,'history_calls':None,'received_records':None,'orders':None,'financial_statistics':None},
 'acceptance_gates':{'G1':'失败：真实Research在源迭代失败；无新版成功联合链或新LEAN。','G2':'证据不足：旧worker差异仍未知；受控诊断通过合成检查。','G3':'原生失败解析/恢复已测通过；新协议成功入口WR21失败，不能整体通过。','G4':'WR20数据审计软件失败；完整历史US200/财务版本/实际送达认证仍不足。'},
 'historical_findings':{'WR01_WR19':'保留各原SHA和有限范围结论；本轮既有回归通过。','new_open':['WR21/P1','WR20/P2']},
 'unverified':['修复后新SHA及两个反例的回归','旧worker具体源码差异和实际源迭代底层原因','后续解析修补的真实云端运行','完整历史US200、财务版本及真实历史供应商送达','阶段3–7完整实际系统及金融效果','非本机独立运行、OS kill/断电持久性','2026最终区间独立性；2024–2025暴露已知'],
 'software_acceptance':{'status':'失败','blocking':['WR21','WR20'],'passed_partial':['原生失败双载体/原attempt恢复','受控worker指纹诊断','单次派发许可的并发正控','既有数值/缓存/采集/准入/恢复回归'],'full_phase2_accepted':False},
 'data_certification':{'status':'证据不足且观测审计软件存在WR20','accepted':False,'vendor_authentication':False,'full_historical_US200':False,'financial_vintage':False,'actual_availability':False},
 'financial_evidence':False,'financial_metrics':None,
 'closed_gates':{'formal_research':True,'automatic_GPT':True,'trading':True,'final_test':True,'GPT_model':None,'GPT_calls_limit':None,'GPT_spend_limit':None,'active_factor':None,'active_model':None,'active_trading':None},
 'reproduction':{'WR20':'python -B cert_agent/minimal_wr20.py --output <fresh-result.json>; current exit1, three legal controls pass',
 'WR21':'Copy entry_agent minimal_new_success_without_dispatch.py and three independent helpers to fresh sibling directory of fixed source; run script, current exit1; root repeated17CLI, plus1 downstream synthetic admission.',
 'immutable_artifacts':'Run verify_artifacts.py in sealed package; source trees are fixed raw Git bytes.',
 'records':['test_execution_summary.json','source_evidence_verification.json','native_agent/report.json','cert_agent/report.json','entry_additional/results.json','wr20_confirmation/execution.json','wr21_confirmation/execution.json','wr21_confirmation/downstream_execution.json']}}
save('formal_report.json',report)
text=['总体：'+report['verdict'],'SHA：'+report['reviewed_source_commit'],'基线：'+report['baseline_commit'],'实际执行：'+E['actual_cloud_source_commit'],
 '612仓库检查与历史回归通过，不能代替独立反例。本次独立审核未修改生产、真实预算或配置，未新增Research/LEAN/模型调用、部署、交易、PR提交批准合并；开发联调的1次Research失败另列。',
 '\n全系统覆盖矩阵：']
for x in stages:text.append(f"阶段{x['stage']} {x['status']}：{x['modules']}；{x['implemented']}；证据{x['evidence']}；缺口{'、'.join(x['blockers'])or'已测范围无新增缺口'}。")
text+=['\n按优先级的问题：']
for f in findings:text.extend([f[ 'id']+'/'+f['priority']+' '+f['title'],'位置：'+','.join(p['file']+':'+str(p['line'])for p in f['locations']),'触发：'+f['trigger'],'预期：'+f['expected'],'实际：'+f['actual'],'原因：'+f['cause'],'范围：'+f['scope_and_severity'],'最小修复：'+f['minimal_fix'],'回归：'+'；'.join(f['regression_tasks']),'复现：'+f['reproduction']])
text+=['\n实际测试（方法/子例/场景严格分列，不加为独有总数）：']
for x in tests:text.append(f"{x['suite']}：{x['passed']}/{x['methods']}方法；失败{x['failed']}、错误{x['errors']}、跳过{x['skipped']}；子例{x['subcases']}"+(f"；场景{x['scenario_checks']}"if'scenario_checks'in x else''))
text+=['额外旧native8手工探针；根入口3链/21CLI（2Windows进程只发一许可）；WR20根MRE exit1；WR21原17CLI及根17CLI均exit1，另1次隔离同父LEAN准入实证；均不涉及实际provider。',
 '旧Collection首0方法/1setUp错误是已满工程限额正确拒绝，原测试计数-1不采信；历史13事件夹具后12/36通过。旧worker首8/9通过，失败因写死预算10遇10+1；只换历史budget夹具后9/81通过。首次均保留且不改断言。',
 '静态reader首次误把attempts list当dict，原脚本/trace保留，修正227/227；重复验证不加计。entry首元数据字面\\n和14/17计数错误另留原件及规范化副本。未完成的子审扩展未计入，根独立补验。',
 '\n身份和平台：4270Git原文件/138review/31部署；163开发原件及2989旧归档raw保留。当前32Python读回均匹配7fc31实现+原input，cell1只读源码hash匹配。deb只有29份部署与7fc相同，2不同，不宣称已上云。',
 '真实Research归档原生CollectionError；2载体=1失败，9traceback条目=43物理行；底层cause未知，成功报告/History次数/收到行数/订单/金融统计均无证据。审核者只独立读当前源码/cell源，不读取notebook数据输出；失败原件属开发归档的独立离线解析。',
 '正常15→17→17；写故障恢复15→16→18→18，多1审计pending事件而非重复扣费。真实17事件未写，原13raw前缀保留。配置7/12、Research10/20、LEAN1/16，工程2/2/1已达配置/Research停止门。',
 '\n下一步：先修WR21和WR20，保留旧结果并提供新固定SHA；重放合法/拒绝/旧兼容及下游依赖。保持当前停止门，不为复验自动重交云端；G1真实失败、G2旧worker、G4来源认证继续单列缺口。',
 '正式研究、自动GPT、交易、最终测试关闭。2024–2025已暴露、2026独立性未知。financial_evidence=false；软件结论不构成金融有效性结论。']
(R/'formal_report.txt').write_bytes(('\n'.join(text)+'\n').encode());print(json.dumps({'review_id':report['review_id'],'findings':[f['id']for f in findings],'test_rows':len(tests),'software_passed':False,'financial_evidence':False}))
