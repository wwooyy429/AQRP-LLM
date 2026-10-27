from pathlib import Path
import importlib.metadata, json, platform, sys
import numpy as np
R=Path(__file__).parent
def read(n):return json.loads((R/n).read_text(encoding='utf-8-sig'))
def write(n,x): (R/n).write_bytes((json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
SHA='8f7236ecbafcb514f07a6af4150a5afdbc1fd474'
E=read('evidence_agent/evidence_verification.json');B=read('evidence_agent/build_preview_verification.json')
G=read('regression_summary.json');W=read('joint_worker_agent/first_run_summary.json')
A=read('admission_agent/quick_first_results.json')
C=read('cloud_comparison.json');F=read('fraction_replay/complete_fixture_results/first_run_summary.json')
Q=read('recovery_replay/first_results.json')
environment={'platform':platform.platform(),'python':platform.python_version(),'executable':sys.executable,
 'dependencies':{n:importlib.metadata.version(n) for n in ['numpy','pandas','python-dateutil','pytz','six','tzdata']},
 'numpy_longdouble_mantissa_bits':np.finfo(np.longdouble).nmant,'native_Windows':True,
 'dependency_file':'source/requirements-test.txt','fixed_dependencies_checked':True}
write('environment.json',environment)
findings=[
 {'id':'WR-16','priority':'P2','reviewed_source_commit':SHA,'title':'联合计划的执行约束未在共享Registry准入事务内执行',
  'locations':[{'file':'cloud/qresearch/registry.py','line':502,'end_line':508},
               {'file':'cloud/qresearch/registry.py','line':487,'end_line':488},
               {'file':'cloud/qresearch/engineering_tasks.py','line':394,'end_line':409}],
  'trigger':'对已注册合法v2计划直接调用Registry.begin_attempt；operation任意、Research尚未完成先LEAN，或max_retries=0的失败Research显式重试。',
  'expected':'在预扣和写入attempt前拒绝不符合父计划固定operation、Research依赖及重试上限的请求，账本字节和用量不变。',
  'actual':'三个负例均获得should_execute=true并扣1槽。Bridge会拒绝前置LEAN与超零重试；但直接Registry生成的超零重试仍能由Bridge.payload生成可用Research输入。错误operation与前置LEAN则在后续payload阶段才拒绝，已消耗额度。',
  'scope_and_severity':'有实际预算及任务可靠性影响，阻断本候选软件验收。全局12/20/16和工程2/2/2上限仍有效；当前真实工程已用1/2时额外重试会受总上限约束，不声称现账本可以超支。合成空工程域独立证明每计划max_retries=0失效。无实际远端执行。',
  'reproduction':'python -B minimal_boundaries.py source registry；本提交exit1，should_execute=True，Research用量1→2，payload stage=research。完整三分支见admission_agent/minimal_joint_registry.py。',
  'minimal_fix':'将v2固定operation、同父Research完成依赖和每阶段重试次数校验放入Registry.begin_attempt的同一LOCK事务，在_charge之前执行；保留合法幂等复用与失败不退款。',
  'regression_tests':'直接Registry/Bridge/CLI三入口；max0/1、任意operation、LEAN前置、失败显式重试和并发最后槽；非法请求无账本/用量变更，合法成功链保持。'},
 {'id':'WR-17','priority':'P2','reviewed_source_commit':SHA,'title':'v1冻结入口可覆盖未结算旧任务的当前计划指针',
  'locations':[{'file':'tools/stage2.py','line':75,'end_line':78},
               {'file':'tools/stage2.py','line':82,'end_line':92},
               {'file':'tools/stage2.py','line':173,'end_line':187}],
  'trigger':'含原LEAN pending记录的完整临时副本中，先运行v2 freeze被拒绝，再通过v1 config/engineering.json运行同项目freeze。',
  'expected':'所有会改变项目结算上下文的冻结入口，在同一Registry锁下检查pending/started/ambiguous；拒绝时保留旧指针和账本。',
  'actual':'v2拒绝且指针不变；v1 freeze exit0并改变audit/engineering_current.json，journal未变。随后真实CLI prepare --attempt bfd00f2611fd4496b9498d4597618a8e exit1：Attempt does not belong to this exact registered task plan。',
  'scope_and_severity':'继承的v1入口使本轮新增v2在途保护不完整；原任务身份仍在不可变账本中，未丢数据，可恢复指针，但正常CLI恢复被阻断。未执行任何旧结果读取或远端更新。历史WR-12仅Collection任务恢复通过范围不被改写。',
  'reproduction':'python -B minimal_boundaries.py source freeze；只创建新临时副本，本提交exit1，内部freeze exit0且pointer changed=True。完整前后对照及prepare错误见admission_agent/minimal_pending_freeze.py。',
  'minimal_fix':'统一v1/v2 freeze的同项目在途检查、锁和指针写入；结果/prepare最好按原attempt冻结配置解析，避免可变current指针阻断已准入任务。',
  'regression_tests':'原pending账本下v1/v2/混合并发freeze都应拒绝且无指针/账本变更；换current目录或计划后仍能按原attempt结算；终态后合法新冻结可用。'}]
write('findings.json',findings)
stages=[]
for i,modules,status,proof,block in [
 (0,'StudySpec/AuditEvidence、规范、身份及预算','修复后通过（既有离线范围）','423仓库及相关历史回归；原验收范围保持',[]),
 (1,'受限因子、执行标签、固定模型协议及数值','修复后通过（既有离线范围）','Pearson10/896、数值16/84、IC摘要11/716等实际重放',[]),
 (2,'QC桥、历史快照、缓存、v2联合父计划及恢复','软件失败；整体验收待定','423仓库；联合worker9/81通过；独立准入负例复现2项P2',['WR-16','WR-17']),
 (3,'固定模型、六轮滚动、匹配标签及Research报告','未验收','有协议/离线组件；无本候选真实研究结果',[]),
 (4,'LEAN交易、成本/成交/风险、组合账本及一致性','未验收','零订单接收器仅合成工程证据；无实际净绩效核对',[]),
 (5,'GPT受限提案、持久调度、修复与开发记忆','未验收','部分框架存在；模型/调用额度未配置，自动调用关闭',[]),
 (6,'受限搜索、相似度、消融及选择偏差','未验收','未开展正式受限市场搜索',[]),
 (7,'冻结、独立最终执行器、前向监控与回滚','未验收','最终测试关闭；未取得独立最终金融结论',[])]:
    stages.append({'stage':i,'modules':modules,'implementation':'部分实现' if i>=3 else '已实现离线组件；完整范围见证据',
                   'acceptance':status,'evidence':proof,'blocking_findings':block})
old_rows=[[x['label'],x['methods'],x['subcases']] for x in G['suites'][1:]]
tests={
 'actually_executed':True,'repository':{'methods':423,'passed':423,'failed':0,'errors':0,'skipped':0,'subcases':None,'exit_code':0},
 'archived_regressions':{'suites':16,'methods':248,'passed':248,'failed':0,'errors':0,'skipped':0,'subcases':2307,
                         'row_order':['suite','methods','subcases'],'rows':old_rows},
 'original_collection_recovery':{'methods':12,'passed':12,'failed':0,'errors':0,'skipped':0,'subcases':36,'exit_code':0},
 'fraction_final':{'methods':10,'passed':10,'failed':0,'errors':0,'skipped':0,'subcases':803,'exit_code':0},
 'fraction_auditor_setup_errors':[{'run':'first','methods':10,'passed':9,'failed':0,'errors':1,'skipped':0,'subcases':799,'cause':'重放目录漏放固定MCP schema原件'},
                                 {'run':'second','methods':10,'passed':9,'failed':0,'errors':1,'skipped':0,'subcases':799,'cause':'重放目录漏放固定helper身份原件'}],
 'fraction_setup_error_resolution':'仅补齐原证据文件，测试断言和生产代码未改；三次各2个合成worker执行，重复次数不加独有用例。原输出均保留。',
 'new_joint_worker':{'methods':9,'passed':9,'failed':0,'errors':0,'skipped':0,'subcases':81,'executions':2,
                     'repeat_reason':'第二次捕获原字节stdout/stderr；不累计独有方法/子例',
                     'per_execution_component_invocations':W['actual_component_invocations'],'real_SDK':False},
 'new_admission_first':{'methods':7,'passed':3,'failed':4,'errors':0,'skipped':0,'subcases':A.get('subcases'),
                        'failure_meaning':'四个产品负例归为WR-16和WR-17，不能计为测试通过'},
 'root_minimal_confirmations':{'original_standalone_scripts':2,'inline_modes':2,'each_exit_code':1,'unit_methods':0,
                              'meaning':'四次有意失败的复现；重复验证两个问题，不是四个独立缺陷或通过用例'},
 'metadata_checks':{'checks':63,'passed':63,'failed':0,'unit_methods':0},
 'additional_manual_preflight_probe':{'evidence_file':'admission_agent/api_preflight_boundary.json','unit_methods':0,
   'scope':'tools.stage2.joint_preflight函数拒绝陈旧source/deploy；公开Bridge假adapter探针属可信调用者I/O边界，未成功执行错误部署worker，不作为第三个缺陷。'},
 'build_preview':{'build_executions':2,'preview_executions':2,'each_exit_code':0,'files_unchanged':1563,
                  'preflight_legal':'accepted','preflight_stale_deployment':'rejected','unit_methods':0},
 'counting':'方法/子例/脚本运行/元数据检查分别列出；套件之间重叠，不合并成独有测试总数；historical commit literal in unchanged old scripts is overridden by actual current source/command binding。',
 'command_records':['runs/execution_records.json','additional_regression_records.json','root_confirmation_complete/execution_records.json',
                    'inline_minimal/execution_records.json','admission_agent/quick_command_log.json','joint_worker_agent/captured_execution.json','evidence_agent/command_log.json'],
 'primary_commands':[
 {'cwd':str(R/'runs/repository_source'),'command':'python -B tools/stages.py verify','exit_code':0},
 {'cwd':str(R),'command':'python -B run_main_checks.py','exit_code':0},
 {'cwd':str(R),'command':'python -B recovery_replay/independent_recovery.py','exit_code':0},
 {'cwd':str(R),'command':'python -B fraction_replay/independent_fraction_boundaries.py --source source --out fraction_replay/complete_fixture_results','exit_code':0},
 {'cwd':str(R),'command':'python -B minimal_boundaries.py source registry','exit_code':1},
 {'cwd':str(R),'command':'python -B minimal_boundaries.py source freeze','exit_code':1}]}
D={'review_id':'AQRP-20261027-8F7236E-WINDOWS-12','review_date':'2026-10-27','reviewer':'GPT Work / Codex 独立审核',
 'reviewed_source_commit':SHA,'baseline_commit':'dd094f345f45b9d9cb78dd9295a6aefd587f4c68',
 'last_accepted_software_baseline':'4a94430144cd3d9e4b5469bd2b6e4a48d80d5fc7',
 'evidence_commits':[SHA,'dd094f345f45b9d9cb78dd9295a6aefd587f4c68','1f7c0c0ab4640a825fd317684f854158ad5d2193'],
 'source_manifest_hash':E['source']['review_hash'],'source_manifest_files':117,'Git_archive_files':1563,
 'execution_manifest_hash':E['source']['execution_hash'],'implementation_hash':E['deployment']['implementation_hash'],
 'deployment_hash':E['deployment']['local_deployment_hash'],'active_configuration_hash':E['deployment']['active_configuration_hash'],
 'environment':environment,
 'tool_capabilities':{'GitHub':'已只读读取PR1/2和本提交CI job元数据；PR2已附到当前审核聊天',
    'QuantConnect':'已list_projects并读取38436695文件名及26份.py源码；未读取notebook、回测状态/结果/日志，未编译/写云端/执行任务',
    'terminal_gate':'read_backtest仅供已完成结果；本会话尚未交付结果的任务不得用它主动查询。原用户审核约束亦禁止轮询未交付终态。',
    'checked_delivery_sources':'仓库归档、相关开发聊天最近一轮、相关旧独立审核记录；未找到原生终态，不等同断言平台仍运行。'},
 'stage_results':stages,'tests':tests,'actually_executed':True,'findings':findings,
 'budget_replay':dict(E['budget'],new_real_charges={'configurations':0,'research':0,'lean':0,'model_API':0},
                     engineering_stop_limits={'configurations':2,'research':2,'lean':2},engineering_used={'configurations':1,'research':1,'lean':1}),
 'backtest_terminal':{'project_id':38436695,'backtest_id':'39cafa1e9b11f91b27e396b66d033a6d',
    'last_archived_status':'pending','current_platform_status':None,'completed':None,'failed':None,
    'native_terminal_found_in_checked_evidence':False,'status_results_logs_read':False,
    'acceptance':'证据不足，无法确认完成或失败；不得把归档pending视为当前仍运行。'},
 'platform_evidence_level':{'source_reads':'本轮独立平台只读核对','runtime':'仅保留旧开发归档Research证据；本候选无真实运行',
    'cloud_source_commit':'75f24629d3b7f94ff3aa906c3ce8a2b8b9a8d3c4','Python_files_read':26,
    'implementation_files':25,'task_input_files':1,'raw_bytes_equal_old':26,
    'cloud_deployment_hash':C['deployment_hash_newline_normalized'],'cloud_input_hash':C['input_hash'],
    'candidate_implementation_manifest_files':29,'candidate_deployed':False,
    'new_runtime_terminal':None,'real_native_failure_receipt_verified':False,'notebook_read':False},
 'CI':{'run_id':40385525081,'commit':SHA,'status':'completed','conclusion':'success',
        'jobs':[{'id':121792642631,'python':'3.10','conclusion':'success','tests_count':None},
                {'id':121792642319,'python':'3.11','conclusion':'success','tests_count':None}],
        'scope':'只读job元数据；本地423为独立执行，不把CI元数据等同独立本地双版本执行'},
 'historical_findings':{'WR-01_to_WR-14':'保留各自固定版本/实际范围修复后通过结论，历史失败及raw56不兼容结果仍保留',
    'WR-15':'dd094f3非阻断元数据更正通过；本轮1387旧证据原字节未变',
    'WR-12_scope':'Collection任务按原attempt恢复通过；WR-17是Engineering/v1 current指针路径的新发现',
    'WR-08_precision':'常数0.7标准差0、真实小方差保留；普通float绝对误差范围，不扩大为无限精度认证'},
 'data_exposure':{'2024_2025_prior_research_exposure':True,'2026_independence_certified':None,'final_test_enabled':False},
 'execution_switches':{'market_research':False,'automatic_GPT':False,'final_test':False,'live_trading':False,
                       'GPT_model':None,'GPT_call_limit':None,'GPT_spend_limit_USD':None},
 'unverified':['旧LEAN原生完成或失败终态及按原输入结算','本候选真实Research/LEAN及原生失败回执完整链',
   '2010–2023完整历史US200、永久SID及PIT证券分类/20日完整交易日排名','历史财务原报/重述版本、实际公开/供应商送达/摄入时点',
   '迁移后实际引擎/供应商数据分支及未观察公司行动','真实Research/LEAN金融一致性、成本/成交/风险及组合增量',
   '阶段3–7及独立最终测试；非Windows/未执行依赖环境边界'],
 'next_actions':['修复WR-16并加入共享事务入口负例/合法路径回归','修复WR-17并验证旧attempt恢复与所有freeze入口一致',
   '提交新固定SHA及保留本轮失败/MRE后独立复验','取得原生旧LEAN终态并按原任务结算后，才可讨论候选云端更新和预算准入',
   '真实有界观察单独验收；完整US200/财务可用性证据不足时继续关闭正式研究及最终测试'],
 'software_acceptance':'failed_stage2_joint_candidate_WR16_WR17; prior_stage0_1_scope_preserved',
 'data_certification':False,'financial_evidence':False,
 'artifact_directory':'review-8f7236e-20261027','artifact_notes':'正式JSON与最小复现同时直接交付；附件保留完整脚本、原始输出、固定Git源码及哈希。'}
assert G['repository_methods']==423 and G['archived_regression_methods']==248
assert W['success'] and W['methods']==9 and W['subcases']==81
assert F['success'] and F['subcases']==803 and Q['passed_methods']==12
assert E['passed_checks']==63 and E['source']['all_raw_bytes_match_Git']
write('formal_report.json',D)
text='''8f7236e独立审核：阶段2联合候选软件失败（WR-16、WR-17均P2）；阶段2整体待验收。
旧LEAN39cafa1e9b11f91b27e396b66d033a6d的当前终态无法确认。已查证据只有pending归档；未主动读取/轮询状态、结果或日志，不能据此声称仍在运行。
固定SHA：'''+SHA+'''
独立本地423通过；16组旧回归248方法/2307子例通过；Collection恢复12/36通过；注解最终10/803通过。
注解前两次各10方法/799子例，9通过/1审核器证据文件缺失错误，原始输出保留；仅补齐schema和helper原件，没有改断言或生产代码。
联合worker9方法/81子例通过，另一次为原字节输出捕获的同例重放，不增加独有用例。每次实际纯PythonResearch worker11、receiver初始化6、finish5、slice15、probe重放3；均非SDK/真实市场。
准入首7方法3通过/4产品负例失败；两项MRE由主代理原脚本及简短内嵌版各复验一次，均预期exit1。细分记录见JSON。
证据63/63检查、两build/两preview、合法/陈旧preflight边界均通过；1563源文件原字节及1387旧证据保持，未登记真实配置或扣费。
云端25份实现及1份输入与旧75原字节完全相同；新候选29份部署身份77a676...尚未部署。GitHub本SHA双版本job元数据成功，未取得各job测试数。
权威12事件重放配置6/12、Research9/20、LEAN1/16；各工程停止已用1/2。新真实执行/模型/部署为0。2024–25旧暴露保留，2026独立性未知。
P2 WR-16：Registry.begin_attempt仅对Collection校验固定operation/重试，对joint v2漏检；Bridge拒绝的前置LEAN、max0重试经直接Registry仍被预扣，max0重试还能产可用payload。总预算/工程总cap仍有效，不夸大为真实超支。
P2 WR-17：同项目pending时v2 freeze拒绝，v1 freeze仍能改current指针；原attempt随后的实际CLI prepare拒绝。journal未变，可恢复但普通结算路径受阻。
修复任务：在共享LOCK/扣费前统一joint固定operation、Research依赖、max_retry及所有v1/v2 freeze在途保护；旧attempt按冻结身份解析，保留幂等、失败不退款与合法完整链。
完整全系统矩阵、环境/依赖、命令、范围、两个问题细节、预算及缺口在同目录formal_report.json；原生终态/真实候选运行/原生失败/完整历史US200/财务vintage及实际可用性认证仍缺。阶段3–7未验收。
运行最小：python -B minimal_boundaries.py source registry 或 freeze，当前均应exit1；仅内存或新临时复制写入，不进行任何QC或模型调用。
完整脚本：admission_agent/minimal_joint_registry.py 与 admission_agent/minimal_pending_freeze.py；joint_worker_agent/independent_joint_worker.py --source source --out <新目录> 为独立成功全链。
金融证据financial_evidence=false，data_certification=false；正式研究、GPT自动调用、最终测试、交易全部关闭。未修改/批准/合并开发成果。
'''
(R/'formal_report.txt').write_bytes(text.encode('utf-8'))
print(json.dumps({'review_id':D['review_id'],'findings':[x['id'] for x in findings],'json_bytes':(R/'formal_report.json').stat().st_size},ensure_ascii=False))
