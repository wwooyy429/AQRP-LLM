from pathlib import Path
import hashlib,json,subprocess,sys
R=Path(__file__).resolve().parent;S=R.parent/'source'
G=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\repo')
B='deb85d9f27441b275ab8b108f0232ecd2707a1e8';C='ea6053e3e9ef4be17db246daf18a4cf9b2e5be58'
sha=lambda b:hashlib.sha256(b).hexdigest()
def write(p,v):p.write_bytes((json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode())
main=json.loads((R/'report.json').read_bytes());supp=json.loads((R/'supplement_report.json').read_bytes())
metadata_path='audit/stage2_current_readiness.json'
baseline_raw=subprocess.check_output(['git','-C',str(G),'show',B+':'+metadata_path]);baseline=json.loads(baseline_raw)
current=json.loads((S/metadata_path).read_bytes());mre=json.loads((R/'wr24_first.stdout').read_bytes())
finding={
 'id':'WR-24','priority':'P3','blocking':False,'status':'open','title':'当前readiness残留旧轮新增配置与源码变更范围',
 'reviewed_source_commit':C,'baseline_commit':B,'evidence_level':'静态源码/归档元数据检查及审查者实际执行的只读一致性MRE，不是产品动态单元测试',
 'file':metadata_path,'line':242,'additional_locations':[{'file':metadata_path,'line':124,'end_line':134},{'file':metadata_path,'line':264}],
 'trigger':'将audit/stage2_current_readiness.json作为本轮ea6053e WR-20/WR-21离线修复的当前状态读取。',
 'expected':'当前轮次的新增配置/Research消耗、源码变更列表和平台读取说明应与固定deb85d9..ea6053e差异、17事件原账本及当前零新增字段一致；旧轮事实须显式绑定旧SHA并放入historical范围。',
 'actual':'第242行仍宣称One new engineering configuration and one Research precharge；第124–134行当前源码列表误列4个本轮未改文件并漏2个本轮测试文件；第264行read_or_polled_this_turn_scope仍沿用上一轮read_project/旧终态列表读取说明。',
 'confirmed_current_fields':{'source_configuration_budget_changed_line84':False,'authoritative_budget_changed_line92':False,'current_candidate_change_scope_line237':current['current_candidate_change_scope'],'new_configuration_count_line261':0,'new_Research_execution_count_line262':0},
 'unchanged_baseline_claims':{k:{'baseline_value':baseline[k],'current_value':current[k],'identical':baseline[k]==current[k]} for k in ('source_configuration_budget_changed_scope','source_changed_this_round','read_or_polled_this_turn_scope')},
 'actual_pinned_diff_mismatches':{'declared_unchanged_files':mre['declared_unchanged_files'],'missing_changed_files':mre['missing_changed_files']},
 'budget_evidence':{'journal_equal_baseline':True,'events':17,'journal_raw_sha256':main['budget_replay']['journal_raw_sha256'],'configurations':7,'research':10,'lean':1,'engineering_usage':main['budget_replay']['engineering_usage'],'engineering_stopped':True},
 'minimal_reproduction':{'script':'archive_agent/minimal_wr24_metadata.py','command':[sys.executable,'-B',str(R/'minimal_wr24_metadata.py')],'exit_code':1,'execution_record':'archive_agent/wr24_first_execution.json','stdout':'archive_agent/wr24_first.stdout','stderr':'archive_agent/wr24_first.stderr','expected_metadata_assertions':mre['checks']},
 'impact':'当前机器可读元数据将历史动作标为当前轮次，造成变更范围与证据来源歧义。实际原账本、预算、当前哈希、未上云/未验收标志均正确；未发现因此新增真实执行或预算消耗。',
 'severity_rationale':'P3说明与可维护性问题；不影响WR-20/WR-21修复代码的动态行为判定，不构成新的预算或平台失控，不单独阻断软件验收。',
 'minimal_fix':'保留旧描述原文并移入带baseline/actual-cloud SHA的historical对象；将当前source_configuration_budget_changed_scope和read_or_polled_this_turn_scope改为本轮零新增/零平台读取说明，按实际固定差异更新source_changed_this_round。不要修改原17事件或退还历史预算。',
 'regression_test':'加入只读元数据一致性检查：当前0新增字段不能同时配未标historical的新增配置/Research描述，current source列表应等于明确基线到交付SHA的实现/测试/工具变更集合；历史记录保持原文与SHA。',
 'financial_evidence':False}
write(R/'finding_WR24.json',finding)
supp['metadata_observation']['assigned_finding']='WR-24';supp['metadata_observation']['severity']='P3';write(R/'supplement_report.json',supp)
summary='''本子审查固定源码 ea6053e3e9ef4be17db246daf18a4cf9b2e5be58，基线 deb85d9f27441b275ab8b108f0232ecd2707a1e8。源码/预算/归档字节一致性范围通过；另有WR-24/P3非阻断当前元数据归属不一致。

主检查修正后55/55通过，补充离线重解析44/44通过。两组均为静态字节/元数据检查，含内存中的只读Registry重放，不是产品单元测试；本子审查独立产品测试方法数0。初次主检查54/55，唯一失败是审查者误读工程配置schema，原脚本、报告及输出已保留；修正后按真实engineering_task_schema_version+plan.scope计数。

4541份候选原始文件与Git archive完全相同。完整审核源码清单140文件，source e82ee1cce13b020738e37d66b597616f3067e77bdefea99af653d76becf1ee13，稳定execution faf825ceb25092a14a5864839624a257b297b19f3ab4cd3030c758da21dcaf44。31文件部署hash 91294236d49d5aad5755ca75a2e96dced70a347c1a7c870a829cd9ab18dd31c4，implementation 712ffda1823796f08ac4db281fc97e1a7e6798f938c22701ab4b0f524e1324bb。均采用UTF8/BOM兼容/LF标准化且保留EOF；execution仅排除budget.usage，完整审核source不排除。

经济配置272e2461117c36aec1c4470d13d2e47ee47fccdaab86b92f31fd11f922701f94保持，全部config原字节未变。17事件账本原字节等于deb85d9，旧13前缀保留，链及内存Registry快照核对通过。预算配置7/12（normal6 reserve1），Research10/20（normal6 reserve4），LEAN1/16（normal1）；工程域2/2/1，配置与Research停止门仍触发。原f5d失败包14ae4a18636496737862a1ce314d90ae7fcf1abaf35f8a0f27145e0e839af8f3及旧38项runtime/input/observation/budget原件全部保留。4047份既有审核归档原字节全部保留。

开发修复包43份登记文件原字节、大小与manifest吻合，630方法日志/source身份一致；首个WR20不可变夹具错误与WR21旧接口错误仍保留。开发重放不能被当作本轮独立产品测试，重叠套件不能累计成独有测试。

旧完整ZIP 33811222字节，SHA256 19d2614008caf209c18b79e16220826de0394ee9a86f585f32ccce5a9bfd6b49，逐文件重算通过。12474清单项加清单自身为12475文件；开发选取216份原件共3361243字节，省略12259份，选择规则和外部两份清单引用精确吻合；未把选择性目录冒充完整包。旧Git快照4270/3178/4204文件均与原manifest吻合。

实际云端执行仍为7fc5ef2e9d2379d29f48d05a1f3cc760000884d6，其31源码部署hash3227c82d09fde3aaddeea61e82aa7e7845ca67b4ff817e932edd145b82b64118及原输入03dd4dcc9cf99c44496236b70370cb8785105d05523cd098798408bfa17c917b吻合。上一轮独立只读取得的32份源码和单元格源码仅在本轮离线重解析；当前候选31实现只有28份与该旧读回相同，不能称新候选已上云。本子审查本轮QC访问、真实Research、LEAN、模型、部署及真实账本写入均0。

WR-24/P3：audit/stage2_current_readiness.json:242当前字段残留上一轮“One new engineering configuration and one Research precharge”，与237、261/262的本轮离线/零新增声明冲突；124–134的source_changed_this_round误列4未改文件并漏2已改测试；264读取scope未标为上一轮。只读MRE退出1，账本原字节未变。建议旧描述保持原文并明确历史SHA，更新current字段；不改真实预算。

未验证：本轮修复代码动态行为由主审与其他子审承担；未独立访问当前QC；真实成功Research→LEAN链、旧故障worker源码、全量历史US200/财务版本/真实可用时点及金融有效性均未认证。financial_evidence=false。
'''
(R/'report.txt').write_bytes(summary.encode())
paths=[R/'report.json',R/'supplement_report.json',R/'finding_WR24.json',R/'report.txt',R/'execution_records.json',R/'wr24_first_execution.json',R/'verify_archive_evidence.py',R/'supplement_verification.py',R/'minimal_wr24_metadata.py']
write(R/'deliverable_hashes.json',{p.name:sha(p.read_bytes()) for p in paths})
print(json.dumps({'main_checks':main['checks_passed'],'supplement_checks':supp['checks_passed'],'finding':'WR-24/P3','report':str(R/'report.txt')},ensure_ascii=False))
