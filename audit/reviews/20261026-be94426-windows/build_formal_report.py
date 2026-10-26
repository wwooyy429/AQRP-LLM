from pathlib import Path
import importlib.metadata as metadata,json,platform,sys
import numpy as np
R=Path(__file__).parent
def read(name):return json.loads((R/name).read_text(encoding='utf-8'))
def write(name,data):(R/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
D=read('source/audit/reviews/20261026-e513c66-windows/formal_report.json')
ev=read('evidence_agent/delivery_evidence_report.json');rec=read('recovery_agent/first_results.json');car=read('receipt_agent/corrected_run_summary.json')
sha='be9442603a31481a9a71e51ca794df77650c7411'
assert ev['passed_checks']==519 and ev['failed_checks']==0
assert rec['methods']==rec['passed_methods']==12 and rec['subcases']==36 and rec['failed_methods']==rec['error_methods']==0
assert car['methods']==15 and car['subcases']==80 and car['success']
assert read('root_nested_annotations.json')['negative_false_acceptances']==3
D.update(review_id='AQRP-20261026-BE94426-WINDOWS-08',reviewed_source_commit=sha,baseline_commit='e513c66e5965133fbe83fb0ab987eae853f96260',source_manifest_hash=ev['source_manifest']['hash'],source_manifest_files=108,git_files_verified=891,execution_source_manifest_hash=ev['execution_source_manifest']['hash'],deployment_hash=ev['deployment']['local_candidate_hash'])
D['evidence_commits']['current_delivery']=sha
D['environment']={'os':platform.platform(),'python':platform.python_version(),'python_executable':sys.executable,'dependencies':{x:metadata.version(x) for x in ['numpy','pandas','python-dateutil','pytz','six','tzdata']},'longdouble_nmant':int(np.finfo(np.longdouble).nmant),'blas_threads_for_main_replays':1,'real_AlgorithmImports_executed':False}
write('environment.json',D['environment'])
D['stage_results'][0]['evidence']='391仓库、既有回归、原24/36准入及519项审计检查'
s=D['stage_results'][2];s.update(evidence='原24/36与14/54、新15/80载体及12/36恢复通过；WR-13完整链5例中3误接受',blockers=['WR-13','新版真实运行与失败回执证据缺失','旧LEAN无已交付终态','历史US200及财务时点未认证'],status='失败',scope='WR-11和WR-12原范围修复后通过；受支持嵌套文本回执边界失败，整阶段仍未验收')
rows=D['tests']['suites'];rows[0].update(methods=391,passed=391)
rows[-2]['id']='e513_admission';rows[-1].update(id='e513_receipts',passed=14,failed=0)
for name,methods,subs in [('new_carriers_corrected',15,80),('new_recovery',12,36)]:rows.append(dict(id=name,methods=methods,passed=methods,failed=0,errors=0,skipped=0,subcases=subs,actually_executed=True))
D['tests']={'actually_executed':True,'suites':rows,'counts_are_overlapping_not_unique':True,
 'original_public_reproductions':{'unchanged_scripts':True,'candidate_passed':3,'candidate_exit_codes':[0,0,0],'baseline_e513_failed':3,'baseline_exit_codes':[1,1,1],'unit_methods':None},
 'additional_probes':{'WR13_full_chain':{'variants':5,'positive_passed':2,'false_acceptances':3,'root_replay_same_result':True,'unit_methods':None},'WR13_extractor_boundary':{'actually_executed':True,'exit_code':1,'unit_methods':None}},
 'audit_checks':{'checks':519,'passed':519,'failed':0,'unit_methods':0},'isolated_builds':{'executed':2,'exit_codes':[0,0],'all_891_raw_files_unchanged':True},
 'command_logs':['runs/execution_records.json','runs/e513_receipts_resolved.command.json','original_probes/execution_records.json','receipt_agent/command_log.json','recovery_agent/command_log.json','root_nested_commands.json'],
 'reviewer_measurement_corrections':{'carrier_first':{'methods':15,'passed':14,'failed':1,'errors':0,'skipped':0,'subcases':80,'failure_records':1,'product_failure':False,'reason':'None表示载体缺席；另存修正版改为两个实际存在载体的嵌套null与空字符串'},'evidence_first':{'checks':519,'passed':518,'failed':1,'product_failure':False,'reason':'历史SHA说明是字符串，审核器误要求布尔True，另存修正且不改输入'},'archived_receipt_path':{'initial_exit_code':2,'methods_executed':0,'product_failure':False,'resolution':'按归档14份去重引用定位原字节脚本，随后14/54通过'},'preparation_print':{'product_failure':False,'reason':'UTF-8文件打印漏指定编码；仅信息输出失败'}},
 'historical_harness_limits':'原样56历史50/3/3及认可适配差异保留；旧SHA字面量不作为本轮执行身份。新旧运行均由外层固定源码与哈希绑定。',
 'portable_runner':{'help_and_syntax_checked':True,'full_aggregate_executed':False,'individual_acceptance_runs_actually_executed':True}}
D['findings']=[{'id':'WR-13','priority':'P2','source_commit':sha,'file':'cloud/qresearch/engineering_receipts.py','lines':[271,272,273],
 'related_location':'cloud/qresearch/collection_execution.py:140',
 'title':'受支持的嵌套text节点忽略未知annotations，额外行侧载荷仍被认证stdout-only并完成',
 'trigger':'合法固定marker位于content/outputs包装text节点或原生text根；annotations含未知rows；structuredContent与content为完整语义相同的镜像',
 'expected':'载体一致后仍递归核验内容；未登记的行或错误侧载荷应在完成认证前拒绝',
 'actual':'完整worker→parser→Bridge/Registry的3种负例都completed，stdout_only=true、marker_count=1、market_values_exported=false；无注解及标准注解2正例完成',
 'impact':'输出边界及完成证据认证遗漏受支持路径。全部行合成，sentinel未写入Registry；不声称真实QC已发送此形状或发生市场行泄漏',
 'minimal_reproduction':'python -B minimal_nested_annotations.py source；完整链：python -B receipt_agent/nested_annotations_probe.py --source source --out result.json；均exit1',
 'fix':'对所有受支持text节点递归校验annotations，明确合法字段和类型，拒绝未知rows/error等侧载荷；保留合法标准注解和等价双载体',
 'regression':'content包装、outputs包装、text根的未知行/错误注解拒绝；无注解及合法标准注解正例；新采集和旧Research完整链；拒绝不写完成、不新增扣费',
 'evidence_level':['E1','E2'],'introduced_by_this_commit':False,'history':'同分支在7bf和e513已存在；本轮新增独立发现'}]
D['budget_replay']=dict(ev['budget_replay'],new_real_configurations=0,new_real_Research=0,new_real_LEAN=0,new_model_calls=0,authoritative_files_unchanged=True)
D['platform_state'].update(candidate_differing_paths=12,CI_success_run_ids=[40345201497])
D['historical_findings'].update({'WR-11':{'status':'修复后通过','scope':'原不同载体/隐藏输出问题；原复现和14/54、新15/80通过；不扩大为所有递归元数据安全认证'},'WR-12':{'status':'修复后通过','scope':'按原attempt结算、原输入绑定、切换/重启/缺失输入及拒绝篡改；原2复现及新12/36通过，预算不增加'}})
D['software_acceptance']={'overall':'failed','WR11_WR12_original_scope':'passed_after_fix','collection_receipt_boundary':'failed','blocking_findings':['WR-13'],'shared_budget_tested_scope':'passed','stage0_1_prior_scope':'retained','whole_system':'not_accepted'}
write('formal_report.json',D)
text=f'''AQRP-LLM 独立修复复审正式报告
审核编号：{D['review_id']}
固定源码：{sha}
比较基线：{D['baseline_commit']}

总体结论：WR-11、WR-12在本轮原问题和实际离线覆盖范围修复后通过；新增确认WR-13/P2，受支持嵌套text节点忽略未知annotations，采集回执边界仍失败。阶段2及完整系统未验收，financial_evidence=false。阶段0/1既有范围和共享预算准入保持。
E1为静态/哈希/AST/固定SDK合同，E2为审核者本轮Windows实际合成执行，E3为既有开发归档原生JSON离线重解析，E4为本轮只读QC源码及GitHub PR/CI，E5无。没有修改开发者生产代码、真实配置或账本，没有提交/推送/批准/合并PR，没有新增Research、LEAN、模型、部署、购买或交易，没有轮询/读取待终态LEAN日志或打开最终数据。

全系统覆盖矩阵
'''
for s in D['stage_results']:text+=f"阶段{s['stage']} | {s['modules']} | {s['implementation']} | {s['evidence']} | 阻断{s['blockers']} | {s['status']}；范围{s['scope']}\n"
text+='''
修复验收
WR-11：engineering_receipts.py:92–135遍历全部实际存在载体，按完整规范JSON比较，拒绝冲突、隐藏text/display/error及未知外层metadata，保留等价镜像。原最小载体脚本当前exit0、旧e513 exit1；原14/54当前通过，新15/80修正版通过，旧Research/LEAN及新采集合法链均保留。None表示缺席，不能据此要求与空字符串产生两载体冲突。WR-13是另一递归内容入口遗漏，不把原不同载体修复失败事实与新问题混淆。
WR-12：collection_task_cli.py:68–94按已预扣attempt的Registry不可变config重建原catalog/plan，97–126验证原admission/manifest/input哈希及现存本地字节；prepare和result按attempt恢复，新的登记/claim仍校验当前源码。原pointer/catalog两个原字节脚本当前均exit0、旧e513均exit1，当前新12/36实际CLI+完整副本+Filesystem Registry边界通过。A→B、目录/源码变化、指针损坏/缺失和进程重启后旧回执可结算；输入缺失从已准入绑定恢复，不创建文件或重取，不退款也不新扣费。未prepare的旧attempt遇源码/部署/目录变化不能生成新输入，完成任务不能再次prepare。任意能直接重写可信store的Python进程不在此CLI授权证明范围，未据任意文件篡改另造失控结论。

新增问题 WR-13 / P2
'''
f=D['findings'][0]
for key in ['title','trigger','expected','actual','impact','minimal_reproduction','fix','regression','history']:text+=key+'：'+f[key]+'。\n'
text+='''
源码位置为engineering_receipts.py:271–273。_native已确认两载体一致，但_research_stdout遇到type=text节点时直接visit(text)，没有检查annotations；collection_execution.py:140随后认证stdout_only=True。外层文本块对annotations有严格限制，嵌套受支持路径却忽略它。三种负例是content包装、outputs包装和text根；两正例为无注解和标准audience/priority/lastModified注解。root亲自逐字节重跑完整5例，仍3个误完成。行只存在合成原生形状输入，Registry不含sentinel，只存摘要。本问题不证明真实SDK发送了该形状或真实市场值外传，也不是声称本提交首次引入。

实际执行（方法与子例分开，重叠不累计为独有测试）
'''
for t in rows:text+=f"{t['id']}: 方法{t['methods']}，通过{t['passed']}，失败{t['failed']}，错误{t['errors']}，跳过{t['skipped']}，子例{t['subcases']}。\n"
text+='''
原公开3探针当前全exit0，旧e513全exit1，脚本字节不变，非单元方法。WR13完整5变体为2正例完成、3负例误完成；root再重放不算10个独有变体。519哈希/AST/JSON检查通过，0单元方法；两次隔离build exit0且891文件字节稳定。所有未执行、skip或历史归档均未冒称本轮通过。
审核器首跑记录均保留：载体15方法80子例首跑1失败记录属于把None误当实际存在载体，另存修正版及diff；证据首跑518/519的1失败属于说明字符串误要求布尔；原回执路径首次exit2执行0方法，后按归档去重引用解析到相同原字节脚本14/54通过；prep一次UTF-8打印漏编码只影响信息输出。均不作为产品缺陷，也不覆盖原件。
原样56历史50通过/3失败/3错误、认可适配及旧精度限制保持。归档脚本历史SHA字面量仍是原内容，当前身份由外层固定Git/文件hash及实际参数绑定。

命令及环境
python -B tools/stages.py verify（runs/repository_source独立副本）
python -B run_main_checks.py（原类及原main回放，原路径失败单列）
python -B run_resolved_receipts.py（解析归档去重引用后运行原14/54）
python -B run_original_probes.py（当前与旧e513各3次）
python -B receipt_agent/independent_carrier_boundaries.py --source source --out receipt_agent
python -B receipt_agent/independent_carrier_boundaries_corrected.py --source source --out receipt_agent
python -B recovery_agent/independent_recovery.py
python -B run_root_nested_probes.py
所有展开的完整实际命令、cwd、参数与退出码见JSON command_logs。没有把开发侧重放当审核者执行。
'''
text+='实际查询环境：'+json.dumps(D['environment'],ensure_ascii=False)+'\n'
text+=f'''
版本/平台/预算/数据一致性
891份固定Git原文件逐字节核验，108源码hash {D['source_manifest_hash']}。
执行hash {D['execution_source_manifest_hash']}；仅budget.usage排除；107份其他源码、3种usage变化、45项政策变更与新增政策键探针通过。
29份本地部署hash {D['deployment_hash']}；配置hash {ev['deployment']['configuration_hash']}；实现hash {ev['deployment']['implementation_hash']}。本地构建不当作云端部署/运行。
旧e513归档254原件+14去重引用逐字节核验，268个总清单和12个回执清单绑定通过；更早460证据及20固定SDK原件不变。37保护文件、12事件和开关不变。
'''
text+='''
本轮先list_projects，再只读38436695的源码，仅保存.py。25份云端源码仍对应75f24629，云端部署hash dad57a0513899dc5ed89cef637d648229dd1c5c1b31bb70583ff95962c1c5bc6，与候选12路径不同。旧input SHA95092b4de264c961895655f0853de639981143ad8cdb41e2c0d22b0adc7136b0仍绑定bfd00f2611fd4496b9498d4597618a8e，不是新版真实输入读回。
旧LEAN39cafa1e9b11f91b27e396b66d033a6d仅归档pending，当前终态null；未轮询/读日志/重交。PR1/2仍open/draft/unmerged，PR2 base6a1edbf、head精确be944；当前独立取得同提交PR CI40345201497 success。未假设其他未读取CI运行。
预算配置6/12（正常6预留0）、Research9/20（正常6预留3）、LEAN1/16（正常1预留0）。本轮真实新增三类和模型调用0，合成账本7/10/1不写真实账本。早期aggregate起点不冒称逐项独立重建。2024–2025暴露保持，2026独立性null；模型/次数/费用限额null，正式研究/最终测试/交易关闭。

未验证及后续
修复WR13递归注解边界，交付新固定SHA并保留本轮失败；复验未知row/error拒绝及标准注解、等价镜像、旧Research/新采集合法链。新版真实部署/输入读回/成功和完整失败回执、旧LEAN已交付终态、完整历史US200、财务版本/公开/实际送达/摄入及公司行动仍缺证据。阶段3–7各自仍需完整交付，软件验收不等于金融有效性。
包内run_offline_review.py提供新目录离线重现；本轮仅检查聚合入口语法和help，各验收命令已实际分别执行，不声称聚合入口完整重跑。生成副本的重复源码不归档，保留测试、命令、结果及合成状态差异，可从固定source重建；原临时目录不删除。

可直接运行最小复现（提取器边界，完整有效报告/worker链另已实际执行并归档）
python -B minimal_nested_annotations.py source（当前exit1）
'''
text+=(R/'minimal_nested_annotations.py').read_text(encoding='utf-8')
text+='\n完整机器可读JSON\n'+json.dumps(D,ensure_ascii=False,indent=2)+'\n'
(R/'formal_report.txt').write_text(text,encoding='utf-8')
print(json.dumps({'review_id':D['review_id'],'fixes_passed':['WR-11','WR-12'],'blocking':['WR-13'],'suites':len(rows)},ensure_ascii=False))
