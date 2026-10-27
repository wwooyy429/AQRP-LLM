from pathlib import Path
import importlib.metadata,json,platform,sys
import numpy as np
R=Path(__file__).parent
def read(n):return json.loads((R/n).read_text(encoding='utf-8-sig'))
def write(n,d):(R/n).write_bytes((json.dumps(d,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
SHA='81fbe5294055423e88ee5aeae48ca6223e7971da';BASE='ae2b8985f3799c246e90341370f86d80483f63ed'
e=read('evidence_agent/evidence_verification.json');g=read('regression_summary.json')
a=read('admission_agent/review_report.json');rec=read('recovery_agent/report.json')
w=read('joint_worker_replay/results/first_run_summary.json');f=read('fraction_replay/results/first_run_summary.json')
col=read('collection_recovery_replay/first_results.json');original=read('original_probes/minimal_checked_dependency_first.json')
assert g['repository_methods']==453 and g['archived_regression_methods']==248
assert original['malformed_dependency_lean_permits']==0 and original['positive_checked_research_permits_lean']
assert a['unique_test_counts']['passed_methods']==18 and w['success'] and f['success'] and col['passed_methods']==12
assert rec['new_loader_completion_boundaries']['passed_methods']==3 and e['passed_checks']==633 and e['failed_checks']==1
env={'platform':platform.platform(),'python':platform.python_version(),'executable':sys.executable,
 'dependencies':{n:importlib.metadata.version(n)for n in ['numpy','pandas','python-dateutil','pytz','six','tzdata']},
 'native_Windows':True,'numpy_longdouble_mantissa_bits':np.finfo(np.longdouble).nmant,'locked_dependencies_checked':True}
write('environment.json',env)
finding={'id':'WR-19','priority':'P3','blocking':False,'reviewed_source_commit':SHA,
 'title':'历史平台比较摘要将ae候选与旧计数12错误绑定',
 'location':{'file':'audit/stage2_current_readiness.json','line':124},
 'trigger':'按platform_comparison_from_independent_review.candidate_commit=ae2b898读取其归档25份旧已知实现参考和29份候选部署清单重算差异。',
 'expected':'该被引用比较应为9条不同路径+4条不在旧参考中的路径=13；或者明确该12属于更早dc49比较，不将其标为ae候选。',
 'actual':'nested候选标为ae，但candidate_different_or_missing_paths仍为12。独立raw/LF计算均13；主代理自包含归档MRE再次得到13并exit1。',
 'scope_and_severity':'非阻断元数据准确性P3，不影响生产逻辑、账本或WR18修复。这里只比较所引用的已知25文件参考与ae29清单，不证明当前云端缺4文件，也不认证云端全集。顶层明确标注dc49的历史12本身不作为错误。',
 'reproduction':'python -B minimal_wr19.py source（当前exit1，declared12/computed13）；不调用QC或读取市场数据。',
 'minimal_fix':'保留原声明和历史表，校正nested计数及其候选/运行参考绑定，并写明已知文件比较范围；不将原有历史12覆盖为当前平台结论。',
 'regression_tests':'用归档候选/参考清单自动重算并核对候选SHA、路径集合及差异计数；明确区分未出现在参考清单与实际云端缺失。'}
write('findings.json',[finding])
stage_rows=[
 [0,'StudySpec/AuditEvidence、身份、规范及预算','已实现离线组件','保留原范围修复后通过','453及相关历史回归',[]],
 [1,'受限因子、执行标签、固定模型协议及数值','已实现离线组件','保留原范围修复后通过','Pearson/数值/IC等原独立回归',[]],
 [2,'QC桥、缓存、历史快照、联合准入及恢复','已有离线实现，真实运行及认证未完成','已测离线软件通过；整体验收待定','WR18修复通过；WR19/P3非阻断；平台证据缺失',[]],
 [3,'固定模型、六轮滚动、标签匹配及Research报告','部分实现','未验收','无候选真实研究及独立指标认证',[]],
 [4,'LEAN交易、成本/成交/风险及一致性','部分实现','未验收','零订单合成接收器不构成交易验收',[]],
 [5,'GPT受限提案、持久调度、修复及记忆','部分实现','未验收','模型/调用额度未配置，自动调用关闭',[]],
 [6,'受限搜索、相似度、消融及选择偏差','部分实现','未验收','未开展正式市场搜索',[]],
 [7,'冻结、独立最终执行器、前向监控及回滚','部分实现','未验收','最终测试关闭',[]]]
stages=[dict(stage=i,modules=m,implementation=impl,acceptance=state,evidence=proof,blocking_findings=b)for i,m,impl,state,proof,b in stage_rows]
def suite(name,n,sub):return dict(name=name,methods=n,passed=n,failed=0,errors=0,skipped=0,subcases=sub)
tests={'actually_executed':True,'suites':[suite('repository',453,None),suite('archived_16_suites',248,2307),
 suite('original_collection_recovery',12,36),suite('original_annotation_fraction',10,803),suite('original_joint_worker',9,81),
 suite('original_quick_all',7,0),suite('WR18_original_admission',9,4),suite('WR18_new_contract_corrected',9,39),
 suite('original_Engineering_recovery',5,46),suite('new_live_loader_contract',3,28)],
 'archived_suite_rows':[[x['label'],x['methods'],x['subcases']]for x in g['suites'][1:]],
 'original_full_MRE':{'unchanged_original_bytes':True,'baseline_exit':1,'candidate_exit':0,'negative_scenarios':3,'positive_scenarios':1,'unit_methods':0},
 'original_short_MRE':{'candidate_exit':1,'meaning':'新增安全RegistryError在LEAN准入/扣费前拒绝，旧短脚本未捕获该异常；原输出保留，不能归为原缺陷仍在。'},
 'repair_assertion_probe':{'file':'verify_wr18_repair.py','baseline_exit':1,'candidate_exit':0,'matching_control':'allowed',
  'conflicting_input':'rejected','artifacts_and_usage_unchanged_on_refusal':True,'unit_methods':0,'adapter_diff':'verify_wr18_repair.diff'},
 'admission_initial_auditor_error':a['first_new_run_retained'],
 'recovery_failure_probes':{'programs':1,'manual_scenarios':4,'passed':4,'failed':0,'unit_methods':0,
  'scope':'合成检查失败Research报告及合成LEAN Runtime Error结算；不是真实原生失败证据。'},
 'recovery_runtime_counts':rec['counting'],'joint_worker_component_invocations':w['actual_component_invocations'],
 'annotation_worker_runs':f['actual_worker_runs'],
 'metadata_checks':{'checks':634,'passed':633,'failed':1,'failure':'WR-19/P3','unit_methods':0,
  'initial_measurement':'首634检查627通过7不符，其中6项是审核器CRLF末行OK解析错误；仅修正解析后633通过1真实声明不符，首稿/raw保留。'},
 'build_preview':{'builds':2,'CLI_previews':2,'each_exit_code':0,'files_unchanged':2374,'valid_preflight':'accepted','stale_deployment':'rejected'},
 'WR19_MRE':{'candidate_exit':1,'software_unit_methods':0,'declared':12,'archived_computed':13},
 'counting':'方法、子例、脚本/进程、手工探针及元数据检查分列；跨套件有重叠，不合计为独有测试数，重复MRE及修正版重放不增加独有方法。',
 'commands':[{'cwd':str(R/'runs/repository_source'),'command':'python -B tools/stages.py verify','exit_code':0},
 {'cwd':str(R),'command':'python -B run_main_checks.py','exit_code':0},
 {'cwd':str(R),'command':'python -B run_original_regressions.py','exit_code':0},
 {'cwd':str(R),'command':'python -B admission_agent/independent_wr18_contract_corrected.py','exit_code':0},
 {'cwd':str(R),'command':'python -B verify_wr18_repair.py source','exit_code':0},
 {'cwd':str(R),'command':'python -B minimal_wr19.py source','exit_code':1}],
 'command_records':['runs/execution_records.json','original_regression_records.json','repair_probe/execution_records.json',
 'admission_agent/original_replay_execution_records.json','admission_agent/new_contract_corrected_execution.json',
 'recovery_agent/report.json','evidence_agent/command_log.json','wr19_confirmation/execution_record.json']}
D={'review_id':'AQRP-20261027-81FBE52-WINDOWS-14','review_date':'2026-10-27','reviewer':'GPT Work / Codex 独立审核',
 'reviewed_source_commit':SHA,'baseline_commit':BASE,'evidence_commits':[SHA,BASE,'1f7c0c0ab4640a825fd317684f854158ad5d2193'],
 'source_manifest_hash':e['source']['review_hash'],'source_manifest_files':122,'Git_archive_files':2374,
 'execution_manifest_hash':e['source']['execution_hash'],'deployment_hash':e['deployment']['local_deployment_hash'],
 'implementation_hash':e['deployment']['implementation_hash'],'active_configuration_hash':e['deployment']['active_configuration_hash'],
 'environment':env,'tool_capabilities':{'GitHub':'本提交PR/CI job只读元数据，PR2草稿未合并',
 'QuantConnect':'本轮未访问QC；仅复核此前归档的平台源码比较，不刷新平台状态、结果或日志',
 'backtest_constraint':'未交付终态不轮询，当前完成/失败仍未知；归档pending不能证明当前仍运行。'},
 'stage_results':stages,'tests':tests,'actually_executed':True,'findings':[finding],
 'WR18_acceptance':{'status':'修复后通过','original_three_negative_paths':'扣费前拒绝，合法同父Research完成仍允许LEAN',
 'implementation':'Bridge和Registry共享_recorded_submission及_completion_contract；核对原提交及引用、完整deployment/input_hash、非空回执和完成通过标志',
 'compatibility':'v1/v2 Research/LEAN成功失败、已完成幂等、status缺席/completed、FS重开/不重入、重试及原最后槽并发在已测范围通过',
 'limitations':'本地合成及已知接口合同，不证明真实云端回执来源、运行完成、数据覆盖或金融有效性。'},
 'historical_findings':{'WR-01_to_WR-17':'各原固定版本及实际范围结论保留；原失败、raw56不兼容、审核运行/测量错误原件不覆盖',
 'WR-18':'本轮修复后通过，旧ae原MRE负对照及失败记录保留',
 'archive_integrity':'62开发原件、463旧审核原件及21引用、1674旧证据、3902项旧最终artifact/ZIP逐项核对；引用数不是原生回执数'},
 'budget_replay':dict(e['budget'],new_real_charges={'configurations':0,'research':0,'lean':0,'model_API':0},
 engineering_stop_limits={'configurations':2,'research':2,'lean':2},engineering_used={'configurations':1,'research':1,'lean':1}),
 'platform_evidence_level':{'current_round':'离线源码/归档复核；无新增独立平台读取或执行',
 'previous_ae_round':'25实现raw等Git75/cloud，1任务输入raw等已准入归档；列表18py漏8可读路径，未认证全集',
 'last_known_implementation_commit':'75f24629d3b7f94ff3aa906c3ce8a2b8b9a8d3c4',
 'current_cloud_source_commit':None,'current_cloud_deployment_hash':None,'candidate_runtime_verified':False,
 'full_cloud_inventory_certified':False,'real_native_failure_receipt_verified':False},
 'backtest_terminal':{'project_id':38436695,'backtest_id':'39cafa1e9b11f91b27e396b66d033a6d',
 'last_archived_status':'pending','current_platform_status':None,'completed':None,'failed':None,'status_results_logs_read':False},
 'CI':{'run_id':40443818298,'status':'completed','conclusion':'success',
 'jobs':[{'id':121990181879,'python':'3.10','conclusion':'success','tests_count':None},
 {'id':121990182184,'python':'3.11','conclusion':'success','tests_count':None}],
 'scope':'只读CI job元数据；本地独立453方法运行于Python3.10.11'},
 'data_exposure':{'2024_2025_prior_research_exposure':True,'2026_independence_certified':None},
 'execution_switches':{'market_research':False,'automatic_GPT':False,'final_test':False,'live_trading':False,
 'GPT_model':None,'GPT_call_limit':None,'GPT_spend_limit_USD':None},
 'unverified':['WR19非阻断摘要更正','旧LEAN原生终态及按原attempt结算','新候选真实部署/Research/LEAN与真实原生失败回执',
 '云端文件全集、完整历史US200/PIT分类/永久SID/20交易日排名','财务原报/修订vintage及真实公开、供应商送达、摄入时点',
 '迁移后真实数据分支及未观察公司行动','真实金融一致性、成本/成交/风险、组合增量；阶段3–7及最终测试'],
 'next_actions':['保留原声明并更正WR19所引用候选与差异计数，不重写历史dc49表',
 '取得旧LEAN原生终态并按原attempt结算后，才能处理候选云端更新及预算准入',
 '真实有界运行、原生成功失败回执和完整数据认证分别验收；最终测试保持关闭'],
 'software_acceptance':'passed_retested_WR18_and_offline_regressions; nonblocking_WR19_open; full_stage2_pending',
 'data_certification':False,'financial_evidence':False,'artifact_directory':'review-81fbe52-20261027'}
write('formal_report.json',D)
text='''81fbe529独立复验：WR-18在本轮范围修复后通过，未发现新增阻断性软件缺陷；WR-19/P3是非阻断历史比较元数据错配。阶段2整体仍待验收。
固定SHA：'''+SHA+'''
WR18原完整MRE原字节旧ae退出1，新81退出0：input_hash冲突/空raw/无提交3路径扣费前拒绝，合法匹配完成准入。原短脚本仍退出1是新RegistryError安全早拒绝，非原bug残留。新增明确拒绝/无写入断言探针旧1新0，原脚本及adapter diff均保留。
本地规定入口453通过；16旧套件248方法/2307子例、Collection12/36、注解10/803、联合worker9/81、原7准入都过。WR18原9/4与新修正版9/39=18方法43子例过。恢复原5/46、新3/28以及4合成失败手工探针均过，方法/子例/重复次数分列。
新共享合同首9方法8通过1审核输入错误：collection_nonempty=false与40个非空窗口矛盾，产品正确拒绝。仅将该失败检查输入改为raw_data_received=false，断言和生产不变；首脚本/raw及修正diff保留。
元数据634检查最终633过1真实声明不符（WR19）。首627过7不符中6条是审核器CRLF末行OK解析测量错误，修正后仍保留1条真实错配；不把测量错误计产品失败。
WR19：audit/stage2_current_readiness.json:124标candidate=ae却保留12。按所引ae29文件与旧25已知参考重算9不同+4不在参考=13，raw/LF一致；root自包含MRE也13/12退出1。P3不阻断软件通过，不证明实际云端缺4或全集；明确属于dc49的历史12不作为错误，不覆盖旧表。
2374源raw等固定Git；62开发原件、463旧审核原件/21引用、1674旧证据及3902旧最终artifact/ZIP核验。两build两preview/纯预检通过，源与权威账本不变。
本轮没有访问QuantConnect；此前25实现及1输入核对只是历史平台证据，不冒充本轮源码/部署/终态核验。旧LEAN39cafa...当前完成/失败未知，未读状态/结果/日志或轮询。
12事件重放预算6/12、Research9/20、LEAN1/16，工程各用1/2。真实Research/LEAN/模型/部署/预算变更0；2024–25暴露保留，2026独立性未知。正式研究/自动GPT/最终测试/交易关闭。
阶段0/1原离线范围保持；阶段2已测软件通过但真实运行/原生失败与US200/财务时点认证仍缺；阶段3–7未验收，data_certification=false、financial_evidence=false。
可运行修复探针：python -B verify_wr18_repair.py source（本候选0，旧ae1）；非阻断最小：python -B minimal_wr19.py source（当前声明12/计算13退出1）。完整原MRE保留original_probes/minimal_checked_dependency.py。所有脚本/原命令/raw/环境/覆盖矩阵/问题修复及回归建议见同目录JSON与附件。未修改/批准/合并开发成果。
'''
(R/'formal_report.txt').write_bytes(text.encode('utf-8'))
print(json.dumps({'review_id':D['review_id'],'WR18':'passed','blocking_findings':0,'nonblocking_findings':['WR-19'],'json_bytes':(R/'formal_report.json').stat().st_size},ensure_ascii=False))
