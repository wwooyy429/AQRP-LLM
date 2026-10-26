from pathlib import Path
import importlib.metadata as metadata,json,platform,sys
import numpy as np
R=Path(__file__).parent
def read(name):return json.loads((R/name).read_text(encoding='utf-8'))
def write(name,data):(R/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
D=read('source/audit/reviews/20261026-be94426-windows/formal_report.json')
ev=read('evidence_agent/delivery_evidence_report.json');rc=read('recovery_agent/current_execution.json');pr=read('recovery_agent/parser_first_results.json')
ann=read('receipt_agent/role_corrected_summary.json');clock=read('root_receipt_probes/candidate_fractional_clock.json');base=read('receipt_agent/baseline_be94426_fractional_clock.json')
sha='dc49f0f3037918f3ce4413665c59b164a8d6e2b7'
assert ev['passed_checks']==432 and ev['failed_checks']==0
assert rc['methods']==rc['passed_methods']==12 and rc['subcases']==36
assert pr['methods']==pr['passed_methods']==2 and pr['subcases']==6
assert ann['methods']==12 and ann['subcases']==160 and ann['failure_records']==0 and ann['error_records']==2
assert clock['variants']==14 and clock['actually_completed']==6 and clock['incorrect_rejections']==8
assert base['variants']==base['actually_completed']==14
D.update(review_id='AQRP-20261027-DC49F0F-WINDOWS-09',reviewed_source_commit=sha,baseline_commit='be9442603a31481a9a71e51ca794df77650c7411',source_manifest_hash=ev['source_manifest']['hash'],source_manifest_files=110,git_files_verified=1088,execution_source_manifest_hash=ev['execution_source_manifest']['hash'],deployment_hash=ev['deployment']['local_candidate_hash'])
D['evidence_commits']['current_delivery']=sha
D['tool_capabilities']['QuantConnect']='先list_projects再只读38436695项目；仅保存核对.py，未解析notebook内容或待终态任务'
D['environment']={'os':platform.platform(),'python':platform.python_version(),'python_executable':sys.executable,'dependencies':{x:metadata.version(x) for x in ['numpy','pandas','python-dateutil','pytz','six','tzdata']},'longdouble_nmant':int(np.finfo(np.longdouble).nmant),'blas_threads_for_main_replays':1,'real_AlgorithmImports_executed':False}
write('environment.json',D['environment'])
D['stage_results'][0]['evidence']='401仓库、原共享准入24/36及432项审计检查'
D['stage_results'][2].update(evidence='WR13原MRE新版0/旧版1，原五例适配2完成3拒绝；新旧完整链14例新版6完成8误拒绝/旧版14完成',blockers=['WR-14','新版真实运行与失败回执证据缺失','旧LEAN无已交付终态','历史US200及财务时点未认证'],status='失败',scope='WR13原未知注解旁路修复后通过；普通小数秒回执兼容失败，整阶段仍未验收')
rows=D['tests']['suites'];rows[0].update(methods=401,passed=401)
rows[-2]['id']='be_carriers_corrected';rows[-1]['id']='be_recovery_replay'
rows += [dict(id='new_annotations_role_corrected',methods=12,passed=11,failed=0,errors=1,skipped=0,subcases=160,actually_executed=True),dict(id='new_parser_recovery',methods=2,passed=2,failed=0,errors=0,skipped=0,subcases=6,actually_executed=True)]
D['tests']={'actually_executed':True,'suites':rows,'counts_are_overlapping_not_unique':True,
 'annotation_error_records':2,'annotation_error_methods':1,
 'original_public_reproductions':{'unchanged_scripts':True,'WR13_candidate_exit':0,'WR13_baseline_be_exit':1,'WR11_and_WR12_candidate_exit_codes':[0,0,0],'unit_methods':None},
 'additional_probes':{'WR13_adapted_original_five':{'positive_completed':2,'negative_rejected':3,'root_replay_same_result':True,'unit_methods':None},'WR14_full_worker_chain':{'variants':14,'candidate_completed':6,'candidate_incorrect_rejections':8,'baseline_be_completed':14,'root_replay_same_result':True,'unit_methods':None},'WR14_boundary':{'actually_executed':True,'exit_code':1,'same_instant_3_and_6_digit_controls_passed':True,'unit_methods':None}},
 'audit_checks':{'checks':432,'passed':432,'failed':0,'unit_methods':0},'isolated_builds':{'executed':2,'exit_codes':[0,0],'all_1088_raw_files_unchanged':True},
 'command_logs':['runs/execution_records.json','original_probes/execution_records.json','receipt_agent/command_log.json','recovery_agent/current_execution.json','recovery_agent/command_log.json','recovery_agent/parser_command_log.json','root_receipt_probes/command_log.json'],
 'reviewer_measurement_corrections':{'annotations_first':{'methods':12,'passed':10,'failed':1,'errors':1,'subcases':160,'failure_records':1,'error_records':2,'skipped':0,'measurement_failure':'Role enum compared as ordered list; corrected separately to set equality','retained_product_error_records':2},'role_only_correction':'Only Role ordering measurement and output filenames changed; valid-clock errors remain; no source/input suppression','read_only_path_discovery':'Prior-review comparison initially used unresolved relative parent; corrected to Path.cwd; zero methods/mutations'},
 'historical_harness_limits':'原样56历史50/3/3及认可适配差异保留；原脚本历史SHA不作为本轮执行身份，current_execution与外层源码hash绑定dc49。',
 'portable_runner':{'help_and_syntax_checked':True,'full_aggregate_executed':False,'individual_acceptance_runs_actually_executed':True}}
D['findings']=[{'id':'WR-14','priority':'P2','source_commit':sha,'file':'cloud/qresearch/engineering_receipts.py','lines':[69,70,76,78],
 'title':'固定Python3.10环境误拒绝已声明支持的普通小数秒注解，合法完成回执无法结算',
 'trigger':'合法lastModified含1、2、4或5位小数秒，如2018-01-03T00:00:00.5Z，出现在受支持嵌套文本注解中',
 'expected':'普通小数秒通过已登记语法与日历校验；.5Z和同一时刻的.500Z同样允许，合法worker回执可完成',
 'actual':'正则接受任意位fraction，但Python3.10.11的datetime.fromisoformat拒绝这些位数。新旧两类实际合成worker的14例中8个普通fraction被误拒绝；3/6位与全秒6例完成。旧be同14例全部完成',
 'impact':'已完成worker的合法回执不能进入Registry completed，attempt保持started。属于新校验器兼容回归；预算和账本在拒绝时不变，无真实QC事件或金融结果证据',
 'minimal_reproduction':'python -B minimal_fractional_clock.py source（当前exit1；等价3/6位控制通过）；完整链fractional_clock_probe.py --source source --out <新目录>',
 'fix':'按已登记小数秒语法稳定校验日历；可只规范化用于校验的fraction或逐分量校验，保留原hint字符串及现有非法时区/日期拒绝；不能把合法fraction改为预期拒绝来消绿',
 'regression':'0到6位小数秒、点/逗号、Z/合法偏移、外层/嵌套文本、新采集及旧Research完整链；非法日期/偏移继续拒绝，恢复不新增扣费',
 'evidence_level':['E1','E2'],'introduced_by_this_commit':True,'scope':'主结论仅依赖普通微秒精度内的1/2/4/5位，不以9位fraction或全部ISO异体支持为前提'}]
D['budget_replay']=dict(ev['budget_replay'],new_real_configurations=0,new_real_Research=0,new_real_LEAN=0,new_model_calls=0,authoritative_files_unchanged=True)
D['platform_state'].update(candidate_differing_paths=12,cloud_python_files_total=26,cloud_separate_task_input_files=1,unchanged_from_previous_readback=True,CI_success_run_ids=[40358624443])
D['historical_findings']['WR-13']={'status':'修复后通过','scope':'原未知annotations行/错误旁路、非字符串text、非法偏移；原最小和原五变体适配通过；普通fraction合法兼容由WR14另行阻断'}
D['software_acceptance']={'overall':'failed','WR13_original_scope':'passed_after_fix','receipt_compatibility':'failed','blocking_findings':['WR-14'],'WR11_WR12_prior_scope':'retained','shared_budget_tested_scope':'passed','stage0_1_prior_scope':'retained','whole_system':'not_accepted'}
D['official_annotation_contract']={'source_commit':'c4c367f9f58296a7053f5c78a52fd02bfbb56a49','path':'schema/2025-11-25/schema.json','raw_sha256':'268a5f82ba70fd7e4b6dc4aa1e64f116f74b4d0edcb69dc046829c79dd4e97e7','scope':'三注解字段语义；适配器明确子集；不要求任意MCP扩展或全部ISO异体；hint不作实际送达时间'}
write('formal_report.json',D)
text=f'''AQRP-LLM 独立修复复审正式报告
审核编号：{D['review_id']}
固定源码：{sha}
比较基线：{D['baseline_commit']}
审核日期：2026-10-27，Asia/Shanghai。

总体结论：WR-13原未知注解旁路在实际离线范围修复后通过；新确认WR-14/P2，普通小数秒合法注解在固定Python3.10环境误拒绝，回执兼容范围失败。阶段2及完整系统仍未验收，financial_evidence=false。阶段0/1和WR01–12各自原范围保留。
证据E1静态/哈希/AST/固定官方合同，E2审核者实际Windows合成执行，E3开发归档平台JSON离线重解析，E4本轮只读QC源码与GitHub PR/CI；E5无。没有修改开发者源码/真实预算/配置或既有报告，没有提交/推送/批准/合并PR；无真实Research、LEAN、模型、部署、购买或交易，没有轮询或读待终态LEAN日志，没有打开最终数据。

全系统覆盖矩阵
'''
for s in D['stage_results']:text+=f"阶段{s['stage']} | {s['modules']} | {s['implementation']} | {s['evidence']} | 阻断{s['blockers']} | {s['status']}；范围{s['scope']}\n"
text+='''
WR13修复验收范围
engineering_receipts.py:43–78验证注解，81–87统一验证文本节点；外层及递归Research入口均使用同一校验。未知行/错误/outputs/_meta、非法字段类型、非有限priority、非字符串text及非法时区偏移均拒绝，标准注解控制保留。原最小脚本不改字节，新dc退出0、旧be退出1。原完整五变体只另存修复后拒绝处理的适配脚本，2正例完成、3负例ReceiptParseError、Registry仍started且字节和usage不变；root亲自逐字节重跑相同结论。没有把负例的未捕获错误冒称通过。原脚本及diff保留。小数秒的合法正路另有新WR14，不能扩大为全部注解时钟兼容通过。

新增问题 WR14 / P2
'''
f=D['findings'][0]
for key in ['title','trigger','expected','actual','impact','minimal_reproduction','fix','regression','scope']:text+=key+'：'+f[key]+'。\n'
text+='''
准确根因为engineering_receipts.py:76，前面的69–70正则接受[.,][0-9]+，随后把有效的小数秒交给固定3.10解释器的fromisoformat，合法1/2/4/5位被当作invalid calendar。root用独立dateutil解析确认.5Z与.500Z完全相同，后者及.500000Z通过、前者ReceiptParseError退出1。完整同脚本/同helper、同普通fraction集合、同空外层注解在旧be14/14完成；当前新采集与实际旧Research worker（假QuantBook）各7例共14，8例误拒绝，worker报告已completed而attempt仍started，无额外扣费或行哨兵入Registry。root重跑当前14得到相同6完成/8拒绝。不是以9位或任意ISO形式支持要求判断，也不声称实际QC已发送这种回执。注解时钟是提示，不替代市场、公开或供应商送达时点。

实际执行（重叠回归不累计为独有测试；方法与子例分列）
'''
for t in rows:text+=f"{t['id']}: 方法{t['methods']}，通过{t['passed']}，失败{t['failed']}，错误{t['errors']}，跳过{t['skipped']}，子例{t['subcases']}。\n"
text+='''
新增annotations首跑12方法160子例：10通过、1失败方法（Role集合测量顺序错）、1错误方法（2条合法clock错误）。只纠正Role排序和输出文件名后仍12/160：11通过、0失败、1错误方法（2条错误记录）。该生产兼容问题未被吞掉。首原件、修正版、diff均保留。完整14例clock probe是参数化探针而非14个单元方法，root重放不算28个独有例。
原401仓库、全部旧12/10/16/19/56、d0的11/8、fbe的8/3/19、WR09的9/27、WR10的12/75、原24/36准入、原14/54回执、原15/80载体、原12/36恢复均实际通过；新增parser恢复2/6也通过。所有skip0。432哈希/AST/JSON检查首跑全过，0单元方法；两次隔离build exit0且1088文件无变。原样56历史50/3/3及认可适配差异、旧精度边界都保持。
恢复套件原字节及其be944历史字面量保留，本轮current_execution.json明确绑定dc49/source/hash。新增恢复探针证明未知注解先拒绝，纠正后同一已扣attempt完成，不新增扣费或清除占用。所有比较和复现均合成，无金融结果。

实际命令与环境
python -B tools/stages.py verify（独立runs/repository_source）
python -B run_main_checks.py（所有原类/原main回归，全16条exit0）
python -B run_original_probes.py（原WR13当前0/旧be1，原WR11和WR12当前均0）
python -B receipt_agent/independent_annotations.py --source source --out receipt_agent
python -B receipt_agent/independent_annotations_role_corrected.py --source source --out receipt_agent
python -B recovery_agent/independent_recovery.py
python -B recovery_agent/new_parser_recovery.py
python -B receipt_agent/fractional_clock_probe.py --source source --out <新目录>
python -B run_root_receipt_probes.py
原始命令参数、cwd、退出码在JSON列出的command_logs，不拿开发侧重放代替审核者执行。
'''
text+='实际查询环境：'+json.dumps(D['environment'],ensure_ascii=False)+'\n'
text+=f'''
版本、平台、预算与数据核对
1088份固定Git原件逐字节一致；110审核hash {D['source_manifest_hash']}。
执行hash {D['execution_source_manifest_hash']}，只排budget.usage；109份源码变更、3种usage稳定性、45项政策变更和新增键探针通过。
本地29py部署hash {D['deployment_hash']}；配置hash {ev['deployment']['configuration_hash']}；实现hash {ev['deployment']['implementation_hash']}。本地build不作云端编译/运行。
旧be169原件+5引用、174artifact/14receipt/4侧hash绑定一致；旧740证据及20SDK原件保留。37保护文件、12事件、配置、开关不变。MCP2025-11-25官方schema固定c4c367f9f58296a7053f5c78a52fd02bfbb56a49，raw SHA268a5f82ba70fd7e4b6dc4aa1e64f116f74b4d0edcb69dc046829c79dd4e97e7，只用三注解字段合同，不泛化整个SDK认证。
'''
text+='''
本轮先list_projects再只读38436695，保存.py而排除notebook内容。实际26个Python条目=25部署源+1独立_engineering_task_input.py，与be轮无新增、删除或改变。25源仍匹配旧75，云部署hash dad57a0513899dc5ed89cef637d648229dd1c5c1b31bb70583ff95962c1c5bc6，距候选12路径。输入SHA95092b4de264c961895655f0853de639981143ad8cdb41e2c0d22b0adc7136b0仍绑定bfd00f2611fd4496b9498d4597618a8e，不是新版输入读回。
旧LEAN39cafa1e9b11f91b27e396b66d033a6d只归档pending，当前终态null；未轮询/读日志/重交。PR1/2仍open/draft/unmerged；PR2 base6a1edbf、head精确dc49，本轮独立确认PR CI40358624443 success，不假设其他CI运行。
预算配置6/12（正常6预留0）、Research9/20（正常6预留3）、LEAN1/16（正常1预留0）。真实新增配置/Research/LEAN/模型调用0；合成副本计数不写真实账本，早期aggregate起点不冒称逐项独立重建。2024–2025暴露仍在，2026独立性null。模型/次数/费用限额null，正式研究/最终测试/交易关闭。

未验证与后续修复
修复WR14合法小数秒拒绝，在固定Python3.10及支持环境重做宽度/格式边界、新旧worker完整链和不新增扣费检查；保留无效日期/偏移、未知注解和非字符串text拒绝。交付新SHA并保留本轮失败。之后仍需新版真实部署/输入/成功与完整失败回执、旧LEAN已交付终态、完整历史US200、SID/分类/公司行动、财务版本/公开/实际送达/摄入认证。阶段3–7缺失交付不能被软件测试替代。
包内聚合重现入口本轮仅检查语法与help；上述每个底层验收命令均实际执行，未声称聚合脚本整段重跑。重复生成的完整case源码副本不归档，可用固定source和保留的测试/命令/输出重建。原临时目录与全部旧失败未删除。

可直接运行的最小复现
python -B minimal_fractional_clock.py source（当前exit1）
'''
text+=(R/'minimal_fractional_clock.py').read_text(encoding='utf-8')
text+='\n完整机器可读JSON\n'+json.dumps(D,ensure_ascii=False,indent=2)+'\n'
(R/'formal_report.txt').write_text(text,encoding='utf-8')
print(json.dumps({'review_id':D['review_id'],'WR13':'passed_after_fix_in_original_scope','blocking':['WR-14'],'suites':len(rows)},ensure_ascii=False))
