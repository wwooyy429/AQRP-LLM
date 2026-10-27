from pathlib import Path
import hashlib,json
R=Path(__file__).resolve().parent;T=R.parent
def read(p):return json.loads((T/p).read_bytes())
d=read('formal_report.json');s=read('archive_agent/report.json');findings=read('findings.json');own=read('archive_agent/finding_WR27.json');text=(T/'formal_report.txt').read_text(encoding='utf-8')
checks={
 'all_five_identity_hashes_match':all(d[x]==s[y] for x,y in [('source_manifest_hash','source_manifest_hash'),('execution_source_manifest_hash','execution_source_manifest_hash'),('deployment_hash','deployment_hash'),('implementation_hash','implementation_hash'),('economic_configuration_hash','active_economic_configuration_hash')]),
 'fixed_source_baseline_cloud_separated':d['reviewed_source_commit']==s['reviewed_source_commit'] and d['baseline_commit']==s['baseline_commit'] and d['evidence_commits']['actual_cloud_execution']==s['actual_cloud_execution_commit'],
 'source_counts4977_144_31_9':d['source_counts']=={'raw_Git':4977,'review_manifest':144,'local_deployment':31,'source_changes':9},
 'static65_pass_not_unit':d['actually_executed']['static_source_archive']=={'checks':65,'passed':65,'unit_methods':0},
 'metadata11_9_2_WR27_and12notunit':d['actually_executed']['metadata']=={'checks':11,'passed':9,'failed':2,'failures_both_WR27':True,'negative_scenarios':12,'unit_methods':0},
 'finding_ids_priorities_blocking':[(x['id'],x['priority'],x['blocking']) for x in findings]==[('WR-25','P2',True),('WR-26','P2',True),('WR-27','P3',False)],
 'WR27_full_finding_equals_original_child':findings[2]==own,
 'embedded_machine_JSON_exactly_equals_formal_JSON':json.loads(text.split('完整机器报告：',1)[1])==d,
 'overall_failure_original_fixes_passed_scoped':d['software_acceptance']=={'original_fix_scope':'WR22/23/24修复后通过','overall_status':'失败','blocking':['WR25','WR26'],'nonblocking':['WR27'],'full_phase2_accepted':False},
 'budget_original_journal_hash':d['budget_replay']['events']==17 and d['budget_replay']['journal_raw_sha256']==s['budget']['journal_raw_sha256'] and d['budget_replay']['raw_equal_ea'] is True and d['budget_replay']['old13_prefix_unchanged'] is True,
 'budget7_10_1_engineering2_2_1_stopped':[(d['budget_replay'][k]['used'],d['budget_replay'][k]['limit']) for k in ('configurations','Research','LEAN')]==[(7,12),(10,20),(1,16)] and d['budget_replay']['engineering_used']==[2,2,1] and d['budget_replay']['stopped'] is True and d['budget_replay']['current_real_charges']==0,
 'archive_selection_and_complete_ZIP':d['archive_validation']=={'prior_ZIP_bytes':60923854,'prior_ZIP_sha256':'3eb0d548f2667c83c24e62f88495ae02fa2c8942440ce0c4aa665bb06b054753','prior_manifest_entries':14165,'selected_original_files':325,'selected_bytes':1833366,'omitted_original_files':13841,'old_Git_archive_files_unchanged':4315,'developer_manifest_entries_verified':94,'provisional652_and_final654_separated':True},
 'financial_false_metrics_unknown':d['financial_evidence'] is False and d['financial_metrics'] is None,
}
paths=['formal_report.json','formal_report.txt','findings.json','archive_agent/report.json','archive_agent/wr24_report.json','archive_agent/finding_WR27.json','archive_agent/execution_summary.json']
hashes={p:hashlib.sha256((T/p).read_bytes()).hexdigest() for p in paths}
notes='''只读正式报告交叉QA：无错报或需要阻止封包的报告问题。

已核对本轮正式JSON、可读文本和完整findings，与子审查的源码/预算/归档及WR24/27原始记录交叉一致；没有运行新产品测试或MRE，没有修改root文件。

来源：ccad固定SHA、ea失败基线、7fc旧实际云端分离正确；4977原字节、144review、31deployment、9变化及全部5种hash一致。654开发最终与旧652分开，主来源验证65/65只是静态检查。

计数：actually_executed.static_source_archive=65/65、unit0；metadata=11项9pass2fail、12negative_scenarios、unit0，两失败明确同属WR27。未称该专项全绿，未叠成独有unit数量。

WR27：三项findings编号25/26/27和P2/P2/P3、blocking true/true/false准确；WR27完整项与子审查逐字段相同，限于显式--root跨目录引用工具树hash，默认同目录源码hash独立正确。原WR24当前/历史及默认入口修复通过，与新增WR27非阻断、观测模块WR25/26阻断和阶段2整体未通过一致。

预算与平台：真实17事件原字节/旧13前缀、7/12、10/20、1/16及normal/reserve、工程2/2/1停止/无新增扣费退款正确。本轮QC0，GitHub/CI独立只读另列；旧28同3异明确不是本轮inventory。native原14ae packet/6a537response、1失败2载体/9traceback条目43物理行及底层未知均吻合；金融指标null和financial_evidence=false准确。

归档：旧ZIP60923854 bytes/3eb0d548…、14165登记项；选择325份1833366 bytes、省略13841份，合计14166完整文件=登记项+清单自身。4315是ea基线Git原有历史归档保存量，94为新开发输出manifest项；三个计数未混用，未冒称选取目录为完整原包。当前可读文本完整内嵌JSON与formal_report.json完全相同。

阶段0/1仅已有已测范围；阶段2失败，3–7仍未验收/未实现完整运行，真实成功链/旧worker/数据认证缺口未被软件测试覆盖。

封包尚未在本次QA中检查；待root输出封包脚本/结果后，可另核对选择边界和可移植最小脚本。WR27最小脚本接受source/git-repository/output参数并自建fresh目标树；纯已生成alternate_root可不选入，保留脚本/原结果/命令/stdout/stderr。
'''
notes+='\n静态逐字段QA结果（不计新产品测试）：\n'+json.dumps(checks,ensure_ascii=False,indent=2)+'\n'
notes+='\n本次读取文件SHA256：\n'+json.dumps(hashes,ensure_ascii=False,indent=2)+'\n'
(R/'qa.txt').write_bytes(notes.encode())
print(json.dumps({'qa_file':str(R/'qa.txt'),'all_crosschecks_match':all(checks.values())},ensure_ascii=False))
