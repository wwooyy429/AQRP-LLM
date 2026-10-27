from pathlib import Path
import json
R=Path(__file__).parent
def load(p):return json.loads((R/p).read_text(encoding='utf-8-sig'))
def save(p,d):(R/p).write_bytes((json.dumps(d,ensure_ascii=False,indent=2)+'\n').encode())
C='ccad61d03ccf17bf2bdc2d7ffc88dfd11b6d3ca6';B='ea6053e3e9ef4be17db246daf18a4cf9b2e5be58';E='7fc5ef2e9d2379d29f48d05a1f3cc760000884d6'
A=load('archive_agent/report.json');T=load('root_test_execution_summary.json');P=load('protocol_agent/report.json')
rawfindings=[load(p)for p in ['cert_agent/finding_WR25.json','cert_agent/finding_WR26.json','archive_agent/finding_WR27.json']]
save('findings.json',rawfindings)
findings=[]
for f in rawfindings:
 findings.append({k:f[k]for k in ['id','priority','blocking','title','locations','trigger','expected','actual','minimal_fix','regression_tasks']})
findings[0]['scope']='观测审计P2；旧ea亦复现，属于本轮未覆盖路径；所有正式认证false。'
findings[1]['scope']='观测审计P2；当前资格不可知被遗漏，不是已证明真实使用未来数据；所有正式认证false。'
findings[2]['scope']='仅显式跨目录--root；默认路径和本轮独立源码哈希正确，非阻断P3。'
for f,path in zip(findings,['minimal_wr25_wr26.py','minimal_wr25_wr26.py','archive_agent/minimal_wr27_root_manifest.py']):
 f['reproduction']=path;f['source_commit']=C
stages=[
 {'stage':0,'modules':'章程、配置、哈希、Registry、接口、CI与失败档案','implementation':'已有骨架和固定程序；当前默认来源/预算一致','evidence':'654仓库、既有独立回归、65静态校验及WR24专项','blocking':[],'gaps':['WR27跨目录元数据非阻断问题'],'status':'原范围通过，WR24修复后通过'},
 {'stage':1,'modules':'受限因子、算子、历史成员、时序标签、模型拟合恢复、数值','implementation':'离线内核已实现；无登记真实因子/模型','evidence':'手算/数值/Pearson/Spearman/常数微方差/Decimal/并发等原套件重放','blocking':[],'gaps':[],'status':'已测离线范围通过'},
 {'stage':2,'modules':'QC适配、PIT、采集缓存、任务桥、准入/恢复、观测审计','implementation':'主体实现；原WR22/23/24修补通过','evidence':'真实生产函数合成链、进程并发、原生回执离线解析；真实执行仍7fc失败','blocking':['WR25','WR26'],'gaps':['新版真实成功Research→缓存→LEAN联合链','旧worker具体差异/源迭代底层原因','完整US200/财务版本/实际送达认证'],'status':'软件观测审计失败，阶段整体未通过'},
 {'stage':3,'modules':'IC/RankIC、分层/风险、六滚动窗、训练隔离和样本对齐','implementation':'部分计算与协议已实现；分层收益未实现，完整真实评价未完成','evidence':'离线数值/标签/拟合/匹配回归','blocking':[],'gaps':['分层收益未实现','登记固定模型与真实滚动报告','训练/验证及成熟标签完整运行证据'],'status':'未验收'},
 {'stage':4,'modules':'LEAN信号→订单→成交→持仓→现金→净值及成本/风险','implementation':'仅工程receiver与部分标签/成本定义','evidence':'纯Python无订单工程链；旧LEAN初始化失败归档','blocking':[],'gaps':['完整交易规范和适用费用/成交/容量/风险','组合账本、压力、扣费后增量'],'status':'未实现完整交易链/未验收'},
 {'stage':5,'modules':'GPT提案、受限FactorSpec、编排、预算、记忆与恢复','implementation':'有受限入口/固定控制；provider=GPT；模型/额度未配置','evidence':'离线拒绝/去重/准入/恢复测试；真实模型调用0','blocking':[],'gaps':['具体模型/调用次数/费用上限及凭证隔离完整证据','真实受限闭环与提示注入全链'],'status':'未验收，自动调用关闭'},
 {'stage':6,'modules':'结构/相关去重、复杂度、消融、组合增量、选择偏差','implementation':'部分固定检查；完整受限搜索未完成','evidence':'离线受限规范和去重测试','blocking':[],'gaps':['真实全部试验登记、消融、扣费后增量及多重选择诊断'],'status':'未实现完整搜索/未验收'},
 {'stage':7,'modules':'冻结、独立最终执行器、年度重估、前向监控/停止/回滚','implementation':'冻结与隔离规则存在；最终执行器未配置','evidence':'配置/边界/暴露记录静态与离线回归；最终数据未打开','blocking':[],'gaps':['独立最终执行、完整冻结、前向模拟与监控回滚','2026独立性未知；2024–2025已暴露'],'status':'未验收，最终测试关闭'}]
tests=[dict(suite='repository',**T['repository'])]+T['legacy_16_suites']+T['additional_root_suites']
for label,m,s,path in [('WR20 original',13,43,'cert_agent/candidate_original/first_results.json'),('previous WR22 boundaries',9,23,'cert_agent/candidate_repair/first_results.json')]:
 tests.append(dict(suite=label,methods=m,passed=m,failed=0,errors=0,skipped=0,scenario_checks=s,subcases=None,actually_executed=True))
tests.append(dict(suite='new historical boundaries',methods=9,passed=7,failed=2,errors=0,skipped=0,scenario_checks=29,subcases=None,failure_records=5,actually_executed=True))
for label,m,n in [('new WR23 publication and concurrency',5,21),('native LEAN',6,62),('completion compatibility',3,28),('engineering recovery legal fixture',5,46),('native Research failure',6,91)]:
 tests.append(dict(suite=label,methods=m,passed=m,failed=0,errors=0,skipped=0,subcases=n,actually_executed=True))
first=[{'scope':'WR21 unchanged original fixture','exit_code':1,'reason':'旧夹具只删除sidecar，仍保留新inline协议，正确被拒。首次及带12CLI日志的原样重放保留；仅两行恢复明确历史四字段准入后，断言AST相同，17CLI全链通过。','records':'protocol_agent/wr21'},
 {'scope':'negative baselines and new failures','reason':'原WR22/23在ea负控exit1保留；新WR25/26/27首失败、独立MRE及root再次确认全保留；未改断言迎合实现。'},
 {'scope':'recognized historical fixtures','reason':'adapted56、e513旧pending、Collection旧13事件与9Research预算、native/recovery合法绑定前置按已认可范围显式使用；真实17事件权威不变。旧脚本内literal SHA/静态目标标签不是当前执行身份。'}]
report={
 'review_id':'AQRP-20261027-CCAD61D-WINDOWS-19','verdict':'原WR22/23/24修复后通过；新增WR25/P2、WR26/P2阻断观测审计，WR27/P3非阻断；阶段2整体未通过。',
 'reviewed_source_commit':C,'baseline_commit':B,'evidence_commits':{'actual_cloud_execution':E,'prior_original_failed_source':'deb85d9f27441b275ab8b108f0232ecd2707a1e8','current_archive':C},
 'source_manifest_hash':A['source_manifest_hash'],'execution_source_manifest_hash':A['execution_source_manifest_hash'],'deployment_hash':A['deployment_hash'],'implementation_hash':A['implementation_hash'],'economic_configuration_hash':A['active_economic_configuration_hash'],
 'source_counts':{'raw_Git':4977,'review_manifest':144,'local_deployment':31,'source_changes':9},
 'environment':load('environment.json'),
 'PR':{'number':2,'head':C,'base':'6a1edbf07fa8fc6cf774084094f4beacc28ff60b','open':True,'draft':True,'merged':False,'metadata_source':'官方GitHub REST；CI由GitHub连接器取得；完整本地Git差异已存','CI_run':40514396033,'CI_jobs':[122224408681,122224409090],'CI_success':True,'CI_test_count_independently_read':None},
 'tool_capabilities':{'offline_Python':True,'read_GitHub':True,'current_QC_calls':0,'current_Research_executions':0,'current_LEAN_submissions':0,'current_model_calls':0,'current_cloud_writes':0,'authoritative_registry_writes':0,'production_edits':0,'PR_approve_merge_push':0,'final_data_opened':False},
 'stage_results':stages,'tests':tests,'actually_executed':{
 'root_processes':26,'records':['runs/execution_records.json','regression_execution_records.json','control_replay/execution_records.json','cert_agent/original_replay_index.json','cert_agent/history_execution.json','protocol_agent/execution_records.json','archive_agent/execution_summary.json'],
 'entry_publication':{'methods':5,'scenarios':21,'custom_check_calls':281,'ordinary_CLI':180,'concurrent_CLI':16,'synthetic_finish':27,'worker':0,'plan_versions':[1,2],'processes_per_prepare_race':4,'processes_per_dispatch_race':4,'only_one_permission_each':True},
 'legacy_native_manual_chains':8,'native_recovery_actual_CLI':193,'native_recovery_direct_processes':12,'native_recovery_synthetic_finish':18,'native_Research_failure_CLI':25,
 'static_source_archive':{'checks':65,'passed':65,'unit_methods':0},'metadata':{'checks':11,'passed':9,'failed':2,'failures_both_WR27':True,'negative_scenarios':12,'unit_methods':0},
 'original_WR22_MRE':{'ea_exit':1,'candidate_exit':0,'original_bytes_unchanged':True},'original_WR23_MRE':{'ea_exit':1,'candidate_exit':0,'original_bytes_unchanged':True},
 'root_confirmed_new_MREs':{'WR25':'wr25_confirmation/execution.json','WR26':'wr26_confirmation/execution.json','WR27':'wr27_confirmation_execution.json','combined_WR25_WR26':'wr26_confirmation/inline_combined_execution.json'},
 'counts_are_overlapping_not_unique':True,'first_results_preserved':first},
 'findings':findings,
 'budget_replay':{'events':17,'raw_equal_ea':True,'old13_prefix_unchanged':True,'journal_raw_sha256':A['budget']['journal_raw_sha256'],'configurations':{'used':7,'limit':12,'normal':6,'reserve':1},'Research':{'used':10,'limit':20,'normal':6,'reserve':4},'LEAN':{'used':1,'limit':16,'normal':1,'reserve':0},'engineering_used':[2,2,1],'engineering_caps':[2,2,2],'stopped':True,'current_real_charges':0,'refund':False},
 'platform_evidence_level':'本轮仅离线源码/合成执行与归档平台证据重解析；未独立访问QC。GitHub/CI为本轮独立只读。',
 'platform':{'actual_execution_source':E,'candidate_deployed_or_executed':False,'archived_cloud_comparison':{'same':28,'different':3,'not_current_inventory':True},'Research_attempt':'f5d05f5b964b4a1d924e4b70cd207386','Research_status':'failed_in_archived_native_evidence','failure':'CollectionError，源迭代底层原因未知','native_packet_sha256':A['native_failure']['packet_raw_sha256'],'native_result_hash':A['native_failure']['response_hash'],'logical_failures':1,'representations':2,'traceback_entries':9,'traceback_physical_lines':43,'normal_failure_replay':[15,17,17],'write_failure_replay':[15,16,18,18],'extra_pending_not_new_charge':True,'old_LEAN_backtest':'39cafa1e9b11f91b27e396b66d033a6d','old_LEAN_status':'archived_initialization_failure_frozen_source_mismatch','successful_joint_chain':False,'history_API_calls':None,'received_records':None,'orders':None,'financial_statistics':None},
 'archive_validation':{'prior_ZIP_bytes':60923854,'prior_ZIP_sha256':'3eb0d548f2667c83c24e62f88495ae02fa2c8942440ce0c4aa665bb06b054753','prior_manifest_entries':14165,'selected_original_files':325,'selected_bytes':1833366,'omitted_original_files':13841,'old_Git_archive_files_unchanged':4315,'developer_manifest_entries_verified':94,'provisional652_and_final654_separated':True},
 'historical_findings':{'WR01_WR19':'保持各原SHA及有限范围结论；本轮相关既有回归通过','WR20_WR21':'保持原局部通过；WR21旧夹具前置已显式适配而不改断言','WR22':'原触发及上一轮边界修复后通过；不能扩为观测模块整体通过','WR23':'原触发及本轮同步发布/进程并发范围修复后通过','WR24':'历史/当前描述及默认一致性检查修复后通过；WR27另列','new_blocking':['WR25','WR26'],'new_nonblocking':['WR27']},
 'unverified':['WR25/26/27修复后的新固定SHA','新版真实Research→缓存→LEAN成功联合链','旧worker具体差异及源迭代底层原因','完整历史US200、财务版本、实际送达/摄入认证','阶段3–7完整运行及金融效果','其他OS独立执行与OS kill/断电持久性','2026独立性；2024–2025已暴露'],
 'software_acceptance':{'original_fix_scope':'WR22/23/24修复后通过','overall_status':'失败','blocking':['WR25','WR26'],'nonblocking':['WR27'],'full_phase2_accepted':False},
 'data_certification':{'status':'证据不足且观测审计边界失败','accepted':False,'vendor_provenance':False,'full_historical_US200':False,'actual_availability':False,'financial_vintage':False,'research_certified':False},
 'financial_evidence':False,'financial_metrics':None,
 'closed_gates':{'formal_research':True,'automatic_GPT':True,'trading':True,'final_test':True,'GPT_model':None,'GPT_call_limit':None,'GPT_spend_limit':None,'active_factor':None,'active_model':None,'active_trading':None},
 'reproduction':{'WR25_WR26':'python -B minimal_wr25_wr26.py --source <fixed-source> --output <fresh.json>；7场景，当前3失败场景对应2问题。依赖固定Git中已归档原创fixture，不导入开发测试。','WR27':'python -B archive_agent/minimal_wr27_root_manifest.py --source <fixed-source> --git-repository <local-Git> --output <fresh-dir>；默认0、错hash0、正确目标hash1，当前MRE退出1。','offline':'在新完整副本执行 python -B tools/stages.py verify；不可在sealed包内写输出。'}}
save('formal_report.json',report)
save('test_execution_summary.json',{'source_commit':C,'tests':tests,'actually_executed':report['actually_executed']})
text=[report['verdict'],'审核SHA：'+C,'基线：'+B,'证据：'+report['platform_evidence_level'],'\n全系统覆盖矩阵：']
for s in stages:text.append(f"阶段{s['stage']}｜{s['modules']}｜{s['implementation']}｜{s['evidence']}｜{s['status']}；缺口：{'、'.join(s['gaps']) or '已测范围未见新增阻断'}")
text+=['\n问题清单：']
for f in findings:text.extend([f['id']+'/'+f['priority']+' '+f['title'],'位置：'+','.join(x['file']+':'+str(x['line'])for x in f['locations']),'触发：'+f['trigger'],'预期：'+f['expected'],'实际：'+f['actual'],'修复：'+f['minimal_fix']])
text+=['\n实际执行（方法/子例/场景/CLI/静态有重叠，不作独有总数）：']
for t in tests:text.append(f"{t['suite']}：{t['passed']}/{t['methods']}方法；失败{t['failed']}，错误{t['errors']}，跳过{t['skipped']}；子例{t.get('subcases')}；场景{t.get('scenario_checks')}")
text+=['\n首次结果：']+[x['scope']+'：'+x['reason']for x in first]
text+=['\n版本/预算/平台：固定4977原文件、144源码清单、31部署与Git一致；真实云端仍7fc失败，当前没有上云。17事件/7配置/10Research/1LEAN原字节不变，工程2/2/1停止，不退款。','旧LEAN终态在已有归档中为初始化源码不符失败，本轮没有平台新读取。history调用数/接收行数/真实订单/金融统计均null，不能用0冒充。','当前PR草稿、未合并，CI双版本成功仅软件证据。2024–2025暴露及2026未知独立性保留；正式研究/GPT自动调用/交易/最终测试继续关闭。','\n下一步：只离线修WR25未知枚举、WR26当前资格缺失、WR27跨目录哈希，提交新固定SHA供独立复验；不自动扩大工程额度或重交云端。', '\n完整机器报告：',json.dumps(report,ensure_ascii=False,indent=2)]
(R/'formal_report.txt').write_bytes(('\n'.join(text)+'\n').encode())
print(json.dumps({'json_bytes':(R/'formal_report.json').stat().st_size,'tests_rows':len(tests),'blocking':['WR25','WR26'],'original_repairs':'passed'},ensure_ascii=False))
