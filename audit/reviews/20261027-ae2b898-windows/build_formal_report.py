from pathlib import Path
import importlib.metadata,json,platform,sys
import numpy as np
R=Path(__file__).parent
def read(n):return json.loads((R/n).read_text(encoding='utf-8-sig'))
def write(n,d):(R/n).write_bytes((json.dumps(d,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
SHA='ae2b8985f3799c246e90341370f86d80483f63ed';BASE='8f7236ecbafcb514f07a6af4150a5afdbc1fd474'
e=read('evidence_agent/evidence_verification.json');sup=read('evidence_agent/supplemental_verification.json')
g=read('regression_summary.json');c=read('cloud_comparison.json');a=read('admission_agent/review_report.json')
recovery=read('recovery_agent/first_run_summary.json');w=read('joint_worker_replay/results/first_run_summary.json')
frac=read('fraction_replay/results/first_run_summary.json');col=read('collection_recovery_replay/first_results.json')
mre=read('root_confirmation/minimal_checked_dependency_first.json')
assert g['repository_methods']==442 and g['archived_regression_methods']==248
assert recovery['success'] and recovery['methods']==5 and recovery['subcases']==46
assert w['success'] and w['methods']==9 and frac['success'] and col['passed_methods']==12
assert mre['positive_checked_research_permits_lean'] and mre['malformed_dependency_lean_permits']==3
assert e['passed_checks']==350 and sup['passed_checks']==14
environment={'platform':platform.platform(),'python':platform.python_version(),
 'executable':sys.executable,'dependencies':{n:importlib.metadata.version(n) for n in ['numpy','pandas','python-dateutil','pytz','six','tzdata']},
 'native_Windows':True,'numpy_longdouble_mantissa_bits':np.finfo(np.longdouble).nmant,'locked_dependencies_checked':True}
write('environment.json',environment)
finding={'id':'WR-18','priority':'P2','reviewed_source_commit':SHA,
 'title':'共享准入把与原提交不一致或缺提交证据的Research当作合格LEAN依赖',
 'locations':[{'file':'cloud/qresearch/registry.py','line':416,'end_line':425},
              {'file':'cloud/qresearch/engineering_tasks.py','line':625,'end_line':642}],
 'trigger':'在独立合成账本中用公开Registry.complete保存canonical/hash自洽的Research结果，再经共享Registry申请同父LEAN；完成回执input_hash与已记录提交不同，或raw_receipt为空，或没有提交记录。',
 'expected':'同一LOCK内、LEAN扣费前核对原提交存在及身份，完整deployment含input_hash相等，原生回执元数据非空；不合格依赖拒绝且账本与用量不变。',
 'actual':'三种路径均被Bridge.consume_completion拒绝（缺提交时在读取回执前拒绝）；共享Registry仍返回should_execute=true且LEAN用量0→1。合法匹配Bridge完成记录则正常允许LEAN。主审核代理原字节MRE及更短主案例均再次复现。',
 'cause':'新增_joint_research_complete只检查source_manifest_hash/deployment_hash及完成证据形状/哈希，漏掉原提交存在、完整deployment对应和raw_receipt非空，弱于既有Bridge完成合同。',
 'scope_and_severity':'属于任务依赖及预算准入可靠性P2，阻断本候选软件验收。只用公开API与合成内存账本，未修改原journal、未真实执行LEAN；全局预算及工程2/2/2上限仍有效。不是要求账本提供远程签名或抵御任意文件写入者。WR-16原三类准入MRE通过，不扩大其关闭范围覆盖本新增证据一致性问题。',
 'reproduction':'python -B minimal_wr18.py source（本候选exit1）；完整三负一正：python -B root_confirmation/minimal_checked_dependency.py source（exit1）。',
 'minimal_fix':'提取不重新获取锁的纯完成合同校验，在Registry同一事务内读取并校验原提交及引用，比较含input_hash的完整deployment并要求非空raw_receipt；复用Bridge相同规则，避免两个入口校验强度不同。',
 'regression_tests':'直接Registry与Bridge对同观测一致拒绝：input_hash冲突、缺/错提交、空回执、错外部ID/阶段/引用；拒绝无新扣费/attempt。保留合法Research→LEAN、幂等、max1重试、FS重启及最后槽并发。',
 'introduced_by_commit':None}
write('findings.json',[finding])
stage_rows=[
 [0,'StudySpec/AuditEvidence、身份、规范和预算','已实现离线组件','原范围修复后通过','442及相关历史回归',[]],
 [1,'受限因子、执行标签、固定模型协议和数值','已实现离线组件','原范围修复后通过','Pearson10/896、数值16/84、IC摘要11/716等',[]],
 [2,'QC桥、缓存、历史快照、联合准入和原attempt恢复','已有离线实现，真实运行及认证未完成','软件失败；整体验收待定','原WR16/17通过；新依赖完整性负例失败',['WR-18']],
 [3,'固定模型、六轮滚动、标签匹配及Research报告','部分实现','未验收','无候选真实研究及独立指标认证',[]],
 [4,'LEAN交易、成本/成交/风险、组合账本及一致性','部分实现','未验收','零订单合成接收器不构成交易验收',[]],
 [5,'GPT受限提案、持久调度、修复及记忆','部分实现','未验收','模型/调用额度未配置，自动调用关闭',[]],
 [6,'受限搜索、相似度、消融及选择偏差','部分实现','未验收','未开展正式市场搜索',[]],
 [7,'冻结、独立最终执行器、前向监控及回滚','部分实现','未验收','最终测试关闭',[]]]
stages=[dict(stage=i,modules=m,implementation=impl,acceptance=state,evidence=proof,blocking_findings=blocks)for i,m,impl,state,proof,blocks in stage_rows]
def suite(name,n,passed,failed,subcases):return dict(name=name,methods=n,passed=passed,failed=failed,errors=0,skipped=0,subcases=subcases)
suites=[suite('repository',442,442,0,None),suite('archived_16_suites',248,248,0,2307),
 suite('original_collection_recovery',12,12,0,36),suite('original_annotation_fraction',10,10,0,803),
 suite('original_joint_worker',9,9,0,81),suite('original_quick_all',7,7,0,0),
 suite('new_shared_admission',9,6,3,4),suite('new_Engineering_recovery',5,5,0,46)]
failure_raw=read('recovery_agent/failure_settlement_result.json')
failure_extra={'manual_scenarios':failure_raw['subcases'],'passed':failure_raw['passed'],'failed':failure_raw['failures'],
 'unit_methods':0,'process_counts':failure_raw['stats'],'evidence_file':'recovery_agent/failure_settlement_result.json',
 'scope':failure_raw['limits']}
tests={'actually_executed':True,'suites':suites,
 'archived_suite_rows':[[x['label'],x['methods'],x['subcases']]for x in g['suites'][1:]],
 'original_full_MRE':{'scripts':2,'unchanged_original_bytes':True,'old8f_exit_codes':[1,1],'candidate_exit_codes':[0,0]},
 'original_short_inline_MRE':{'registry_exit_code':1,'registry_meaning':'原短脚本未捕获新RegistryError：Preregistered joint engineering retry bound reached。是在扣费前安全拒绝，不是原非法准入断言失败。原输出保留。','freeze_exit_code':0},
 'additional_partial_original_replay':{'methods':6,'passed':6,'failed':0,'errors':0,'skipped':0,'overlaps_original_quick_all':True},
 'new_admission_positive_controls':a['positive_controls'],
 'new_recovery_process_counts':recovery['stats'],
 'new_recovery_failure_settlement_probes':failure_extra,
 'joint_worker_component_invocations':w['actual_component_invocations'],
 'fraction_worker_runs':frac['actual_worker_runs'],
 'root_WR18_MRE':{'full_scenarios':4,'full_exit_code':1,'short_scenarios':2,'short_exit_code':1,'unit_methods':0,'repeats_new_admission_cases':True},
 'metadata_checks':{'primary':350,'supplemental':14,'passed':364,'failed':0,'unit_methods':0},
 'build_preview':{'builds':2,'CLI_previews':2,'each_exit_code':0,'files_unchanged':1843,'valid_preflight':'accepted','stale_deployment':'rejected'},
 'counting':'方法、子例、脚本/进程、元数据检查分列；套件有重叠，不合计为独有测试数。追加原6、原MRE及重复新MRE不增加独有方法。',
 'evidence_limits':'准入原6/新9首次保留unittest输出及JSON，外层stderr未单独捕获；WR18原MRE及主代理复验均实际保存raw stdout/stderr。证据代理一次猜错文件名的只读命令失败已保留，不归为产品测试错误。',
 'commands':[{'cwd':str(R/'runs/repository_source'),'command':'python -B tools/stages.py verify','exit_code':0},
 {'cwd':str(R),'command':'python -B run_main_checks.py','exit_code':0},
 {'cwd':str(R),'command':'python -B run_original_regressions.py','exit_code':0},
 {'cwd':str(R),'command':'python -B replay_original_quick.py','exit_code':0},
 {'cwd':str(R),'command':'python -B admission_agent/independent_wr16_boundaries.py','exit_code':1},
 {'cwd':str(R),'command':'python -B root_confirmation/minimal_checked_dependency.py source','exit_code':1},
 {'cwd':str(R),'command':'python -B minimal_wr18.py source','exit_code':1}],
 'command_records':['runs/execution_records.json','original_regression_records.json','original_quick_full/execution_record.json',
 'admission_agent/review_report.json','recovery_agent/command_log.json','recovery_agent/first_execution.json',
 'root_confirmation/execution_record.json','inline_minimal/execution_record.json','evidence_agent/command_log.json']}
D={'review_id':'AQRP-20261027-AE2B898-WINDOWS-13','review_date':'2026-10-27','reviewer':'GPT Work / Codex 独立审核',
 'reviewed_source_commit':SHA,'baseline_commit':BASE,
 'evidence_commits':[SHA,BASE,'1f7c0c0ab4640a825fd317684f854158ad5d2193'],
 'source_manifest_hash':e['source']['review_hash'],'source_manifest_files':120,'Git_archive_files':1843,
 'execution_manifest_hash':e['source']['execution_hash'],'deployment_hash':e['deployment']['local_deployment_hash'],
 'implementation_hash':e['deployment']['implementation_hash'],'active_configuration_hash':e['deployment']['active_configuration_hash'],
 'environment':environment,
 'tool_capabilities':{'GitHub':'本提交PR/CI job只读元数据；PR2仍草稿且未合并',
  'QuantConnect':'先list_projects，再读取38436695文件列表和26份已知Python文件；未读notebook、回测状态/结果/日志，未编译/写入/派发',
  'backtest_constraint':'未交付终态不得主动轮询；本轮按用户所述终态未知和归档pending保留，不推断当前仍在运行'},
 'stage_results':stages,'tests':tests,'actually_executed':True,'findings':[finding],
 'historical_findings':{'WR-01_to_WR-15':'各固定版本实际范围结论保留；原失败、原raw56不兼容及两次审核器注解准备错误均归档',
  'WR-16':'原固定operation/前置Research/重试上限三类准入范围修复后通过；不覆盖新增WR-18完成证据一致性',
  'WR-17':'修复后通过：原MRE及5方法46子例验证统一冻结和按原attempt恢复',
  'previous_8f_review_archive':'208原件及11引用、1398旧证据、最终3328条清单和ZIP逐项核对；首次封包漏6历史源与修正保留'},
 'budget_replay':dict(e['budget'],new_real_charges={'configurations':0,'research':0,'lean':0,'model_API':0},
  engineering_stop_limits={'configurations':2,'research':2,'lean':2},engineering_used={'configurations':1,'research':1,'lean':1}),
 'platform_evidence_level':{'source_reads':'本轮独立平台只读核对25份实现raw等旧75，另1份任务输入raw等已准入归档；26份均匹配各自历史基线',
  'cloud_source_commit':'75f24629d3b7f94ff3aa906c3ce8a2b8b9a8d3c4','implementation_files':25,'task_input_files':1,
  'cloud_known_file_deployment_hash':c['deployment_hash_newline_normalized'],'cloud_input_hash':c['input_hash'],
  'input_baseline':'source/audit/task_inputs/bfd00f2611fd4496b9498d4597618a8e.py',
  'listing_python_files':18,'known_readable_files_missing_from_listing':c['known_but_not_listed'],'full_inventory_certified':False,
  'candidate_deployment_verified':False,'candidate_runtime_verified':False,'real_native_failure_receipt_verified':False},
 'backtest_terminal':{'project_id':38436695,'backtest_id':'39cafa1e9b11f91b27e396b66d033a6d','last_archived_status':'pending',
  'current_platform_status':None,'completed':None,'failed':None,'status_results_logs_read':False},
 'CI':{'run_id':40436072138,'status':'completed','conclusion':'success',
  'jobs':[{'id':121964921625,'python':'3.10','conclusion':'success','tests_count':None},
          {'id':121964921999,'python':'3.11','conclusion':'success','tests_count':None}],
  'scope':'仅CI job元数据；本地独立442方法实际运行于Python3.10.11'},
 'data_exposure':{'2024_2025_prior_research_exposure':True,'2026_independence_certified':None},
 'execution_switches':{'market_research':False,'automatic_GPT':False,'final_test':False,'live_trading':False,
  'GPT_model':None,'GPT_call_limit':None,'GPT_spend_limit_USD':None},
 'unverified':['WR-18修复及新固定版本复验','旧LEAN原生终态及原任务结算','候选真实Research/LEAN和实际原生失败回执',
 '云端完整文件全集：列表漏列8份已知可读文件','完整历史US200/PIT分类/永久SID/20交易日排名',
 '财务原报/重述vintage及真实公开、供应商送达、摄入时点','迁移后真实数据分支及未观察公司行动',
 '真实金融一致性、成本/成交/风险、组合增量；阶段3–7及最终测试'],
 'next_actions':['修复WR-18，使Registry和Bridge使用一致的提交/完成合同，非法依赖扣费前拒绝',
 '保留本轮原始失败，加入三负一正及FS/并发回归后提交固定SHA独立复验',
 '取得旧LEAN原生终态并按原attempt结算，再处理候选云端更新及预算准入',
 '澄清云端文件清单完整性；真实有界观察与完整数据认证分别验收'],
 'software_acceptance':'failed_WR18; WR16_and_WR17_passed_in_retested_scope; prior_stage0_1_scope_preserved',
 'data_certification':False,'financial_evidence':False,'artifact_directory':'review-ae2b898-20261027'}
write('formal_report.json',D)
text='''ae2b898独立复验：WR-16、WR-17在原及本轮已测范围修复后通过；新增WR-18/P2，当前阶段2候选软件失败，阶段2整体仍待验收。
固定SHA：'''+SHA+'''
WR18：共享Registry的已验证Research依赖校验弱于Bridge。提交input_hash=d而completion=e、空raw_receipt、无submission这3类同观测均被Bridge拒绝；经公开Registry.complete形成canonical/hash自洽结果后，LEAN却获should_execute=true且预算0→1。合法匹配完成仍能准入。无原journal篡改、远程签名攻击或真实LEAN执行，总预算及2/2/2 cap仍有效。
修复应在同一LOCK内核对原提交及引用、完整deployment含input_hash和非空原回执，复用不重入锁的纯完成合同校验；保留合法链/重试/幂等。
原2完整MRE原字节：old8f各exit1，ae各exit0。原7方法全过。旧短inline Registry仍exit1，原因是新增RegistryError安全早拒绝未被旧脚本捕获，不是原非法准入断言失败；原输出未改。
本地442通过；16组历史248方法/2307子例、旧Collection12/36、注解10/803、联合worker9/81全部通过。
新共享准入9方法6过3失败/4子例；WR17新5方法46子例全过，72实际隔离CLI+12函数子进程；追加原6方法与完整原7重叠，不合计独有测试。完整WR18 MRE由主代理重放3负1正并另写短主例/合法正控，两次exit1不算通过方法。
补充4个失败结算手工场景通过，28隔离CLI、6次合成metadata_finish、worker0，不是4个额外单元方法，也不是真实原生失败证据。
350+14=364元数据/哈希/ZIP/身份检查通过，0unit方法；两build/两preview通过，1843源码与权威账本未改。65份开发原始输出和旧8f完整归档/最终3328清单及ZIP核验。开发WR17基线错误不冒称审核器错误。
主代理本轮实际读取25份已知云端实现raw等Git75/cloud，另1任务输入raw等已准入归档；26份匹配各自历史基线。目录只列18py，其余8份虽能逐个读，不认证全集。未读notebook/任何回测状态、结果、日志，未编译、更新、部署或派发。
旧LEAN39cafa...仍只有pending归档，当前完成/失败未知，不能称现在仍在运行。新候选尚无真实运行验收证据。
12事件重放预算配置6/12、Research9/20、LEAN1/16，工程各用1/2；本轮真实执行/模型/预算变更0。2024–2025暴露保留、2026独立性未知，正式研究/GPT自动/最终测试/交易关闭。
完整矩阵、环境、命令、问题触发/实际/预期/范围/修复/回归及缺口见formal_report.json。阶段0/1原离线范围保持；阶段3–7未验收；数据认证false、financial_evidence=false。
可运行短主例：python -B minimal_wr18.py source（当前exit1）；完整自包含三负一正：python -B root_confirmation/minimal_checked_dependency.py source（当前exit1）。仅内存合成，未修改/批准/合并开发成果。
'''
(R/'formal_report.txt').write_bytes(text.encode('utf-8'))
print(json.dumps({'review_id':D['review_id'],'WR16':'passed_original_scope','WR17':'passed_retested_scope','findings':['WR-18'],'failure_probes_ready':failure_extra is not None,'json_bytes':(R/'formal_report.json').stat().st_size},ensure_ascii=False))
