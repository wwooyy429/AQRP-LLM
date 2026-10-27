from pathlib import Path
import hashlib,json
R=Path(__file__).resolve().parent;S=R.parent/'source'
def sha(b):return hashlib.sha256(b).hexdigest()
def write(p,v):p.write_bytes((json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode())
main=json.loads((R/'report.json').read_bytes());meta=json.loads((R/'wr24_report.json').read_bytes());mre=json.loads((R/'wr27_first/result.json').read_bytes());execution=json.loads((R/'wr27_first_execution.json').read_bytes())
lines=(S/'tools/review_metadata.py').read_text(encoding='utf-8-sig').splitlines()
finding={'id':'WR-27','priority':'P3','blocking':False,'status':'open','reviewed_source_commit':main['reviewed_source_commit'],'baseline_commit':main['baseline_commit'],
 'title':'显式--root跨目录元数据检查使用工具所在源码树的哈希',
 'locations':[{'file':'tools/review_metadata.py','line':82,'end_line':84}],
 'source_lines':{str(i):lines[i-1] for i in (82,83,84)},
 'trigger':'从固定ccad源码运行tools/review_metadata.py --root <另一合法本地源码树>，目标树的源码内容与工具所在树不同，且目标metadata的current源文件差异列表已按实际Git差异正确更新。',
 'expected':'预算、账本、历史描述、Git差异和candidate_source_manifest_hash均应针对同一个--root目录；外来工具树hash应拒绝，目标树正确hash应通过。默认目录仍应通过。',
 'actual':'check_repository(root)先在root读取metadata/Git/预算/账本，但82–84行导入stages.source_manifest()时未传入root；该函数使用stages模块的全局ROOT，指向工具所在ccad源码。目标树如实声明10份变化但使用错误的工具树hash046770…时exit0/metadata_consistent；换为正确目标hash19dc830…反而exit1。默认正常目录exit0，当前固定源码的独立144文件哈希正确。',
 'reproduction':{'script':'archive_agent/minimal_wr27_root_manifest.py','command':execution['command'],'exit_code':execution['exit_code'],'expected_defect_exit':1,'execution_record':'archive_agent/wr27_first_execution.json','result':'archive_agent/wr27_first/result.json','command_log':'archive_agent/wr27_first/commands.json','stdout':'archive_agent/wr27_first.stdout','stderr':'archive_agent/wr27_first.stderr','script_raw_sha256':execution['script_raw_sha256']},
 'observed_controls':{'default_root_exit':mre['default_legal_control_exit'],'default_source_hash':mre['default_source_hash'],'alternate_actual_source_hash':mre['alternate_actual_source_hash'],'foreign_hash_false_accept_exit':mre['foreign_hash_actual_exit'],'correct_hash_false_reject_exit':mre['own_hash_actual_exit'],'actual_source_raw_unchanged':mre['source_original_raw_unchanged'],'actual_Git_index_unchanged':mre['actual_repository_index_unchanged']},
 'impact':'显式跨目录校验的源码身份归属错误，既可误报外来hash一致，也可拒绝正确目标hash。仅作用于该只读CLI的--root选项；默认同目录路径和本轮固定来源独立重算不受影响。工具返回independent_acceptance=false与external_activity_authenticated=false，没有真实执行许可、金融认证、预算或平台状态变化。',
 'severity_rationale':'P3窄范围只读元数据CLI可靠性/可维护性问题，不阻断默认路径的WR24原修复范围，也不能据此声称当前固定源码身份不实。',
 'minimal_fix':'将source_manifest显式绑定到传入root（如给stages.source_manifest增加可选root参数并保留默认ROOT），或在review_metadata中对同一root按相同规范计算。不要靠切换cwd解释模块全局ROOT，也不要关闭合法--root功能。',
 'regression_tasks':['默认工具所在树仍metadata_consistent。','另一个正确声明差异和正确hash的源码树应通过。','目标树填工具树hash必须拒绝，即使该值在工具树中真实正确。','changed_paths、budget/journal、historical/sourcehash均绑定同一root；原WR24旧ea负控和当前9差异保持。'],
 'evidence_level':'审查者实际执行只读元数据CLI、独立哈希及隔离源码树MRE；12变异校验属于静态元数据检查，不计产品unit方法。',
 'current_QC_Research_LEAN_model_deployment_authoritative_registry_calls':0,'financial_evidence':False}
write(R/'finding_WR27.json',finding)
summary=f'''固定源码：{main['reviewed_source_commit']}；基线：{main['baseline_commit']}；实际旧云端执行仍为{main['actual_cloud_execution_commit']}。

源码／预算／归档65/65静态字节检查首跑通过，不计产品unit方法。4977份原始文件逐一等于固定Git archive；review清单144份，source={main['source_manifest_hash']}，stable execution={main['execution_source_manifest_hash']}。31部署={main['deployment_hash']}，implementation={main['implementation_hash']}；均标准化UTF8/BOM/LF且保留EOF；预算usage只在稳定execution排除。经济配置272e…及全部config原字节不变。开发tested_source_file_count140不含manifest另加的4份根文件，故与144不矛盾。

真实17事件原字节与ea相同，SHA={main['budget']['journal_raw_sha256']}，旧13前缀及链完整。独立事件预算重放与内存Registry快照吻合：配置7/12(normal6 reserve1)、Research10/20(normal6 reserve4)、LEAN1/16；工程2/2/1、2次停止门保持。4315份既有review/review_packages原件字节不变。独立保护范围39份包含runtime/input/tool-observation、budget与data_exposure；它比上一轮38保护范围多data_exposure，不与开发38份不同定义混用。

原f5d14ae…packet、6a537…response、项目38436695/index1/attempt/config/plan/input/deployment/dispatch binding及完成内容地址全部吻合；仍是1个真实失败的2个相同载体，9个traceback条目/43物理行，底层source cause未知，无成功产物。旧7fc31实现及原输入身份匹配；前轮独立只读32份源码仅离线重解析，当前31份候选28同3异，不认证当前平台或故障worker。

旧ea完整ZIP：{main['old_review_archive']['ZIP_bytes']}字节，SHA={main['old_review_archive']['ZIP_raw_sha256']}；14165清单登记项+清单自身=14166文件，目录和ZIP逐文件原字节重核通过。选择性归档325份原件1833366字节，省略13841份；规则、两份外部清单、两份非UTF8原输出引用及来源Git快照4541/4270/4204全部吻合；未把选择性目录当完整包。94份开发新输出manifest项真，旧652与最终654测试来源/哈希分开，开发重放不授予独立验收。

WR24原修复范围通过：保留的旧minimal反例原字节在ea负控退出1（固定deb..ea旧范围）；新current/historical字段逐一按ea..ccad9源码差异核验通过，旧描述原文连同ea/7fc身份保留，当前新增/平台计数0；默认实际tools/review_metadata.py CLI退出0；12种静态变异拒绝正确。这些属于元数据检查，不计产品unit方法。原固定ea脚本没有改标签冒充当前范围。

新增WR-27/P3非阻断：显式--root跨目录时，tools/review_metadata.py:82–84调用source_manifest()忽略root，使用工具树全局ROOT。最小独立MRE中默认目录exit0；目标正确声明10份差异但错误填工具树hash时exit0，填目标正确hash时exit1。当前真实固定树的144源码身份独立正确；不得扩大成默认路径错误。脚本、实际CLI原输出及hash见finding_WR27.json和wr27_first_*。

主65静态检查通过；WR24元数据汇总11项中9通过、2失败为同一WR27的误接纳/误拒绝两种表现，另含12个静态变异场景；不累加为产品unit测试。verify_wr24共原反例1次+元数据CLI3次，独立最小WR27再运行元数据CLI3次，均隔离只读、计数重叠不宣传独有总数。原真实Git index及源码未改；为raw export构造的Git index仅存在本archive_agent内。

本子审查本轮QC、真实Research、LEAN、模型、部署、交易、真实账本写入均0。financial_evidence=false。WR22/23产品动态行为由其他子审及root承担；真实成功联合链、旧worker差异和完整数据/金融认证继续缺证据。
'''
(R/'report.txt').write_bytes(summary.encode())
write(R/'execution_summary.json',{'static_source_budget_archive':{'checks':65,'passed':65,'unit_methods':0},'WR24_metadata':{'checks':11,'passed':9,'defect_checks':2,'negative_static_scenarios':12,'unit_methods':0,'original_ea_MRE_invocations':1,'metadata_CLI_invocations':3},'WR27_minimal_MRE':{'exit_code':1,'metadata_CLI_invocations':3,'default_control_exit':0,'foreign_hash_false_accept_exit':0,'own_hash_false_reject_exit':1,'unit_methods':0},'counts_overlap':True,'all_provider_or_real_budget_writes':0,'financial_evidence':False})
write(R/'exploration_notes.json',{'reviewer_exploration_only':[{'command':'Get-Content .../wr22_wr24/wr24/summary.json; Get-Content .../wr22_wr24/wr24/run_check.py','result':'Paths do not exist; actual saved WR24 files were discovered via rg --files afterwards. No product command/test was executed by those failed reads.','tool_command_exit_code':1}],'first_execution_preserved':True})
names=['report.json','report.txt','wr24_report.json','finding_WR27.json','execution_summary.json','first_execution.json','wr24_first_execution.json','wr27_first_execution.json','minimal_wr27_root_manifest.py']
write(R/'deliverable_hashes.json',{p:sha((R/p).read_bytes()) for p in names})
print(json.dumps({'source_checks':65,'WR24':'passed_original_scope','new_finding':'WR-27/P3/nonblocking','output':str(R)},ensure_ascii=False))
