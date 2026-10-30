from pathlib import Path
import hashlib,json
R=Path(__file__).resolve().parent;T=R.parent
read=lambda p:json.loads((T/p).read_bytes())
d=read('formal_report.json');s=read('archive_agent/report.json');wr=read('archive_agent/wr27_report.json');ts=read('test_execution_summary.json');text=(T/'formal_report.txt').read_text(encoding='utf-8')
rootmre=read('root_wr27_confirmation/result.json');rootexec=read('root_wr27_confirmation_execution.json');rootcommands=read('root_wr27_confirmation/commands.json');build=read('build_execution.json')
a=d['actually_executed'];budget=d['budget_replay'];archive=d['archive_validation']
checks={
 'five_source_identity_hashes_equal_independent_report':all(d[x]==s[y] for x,y in [('source_manifest_hash','source_manifest_hash'),('execution_source_manifest_hash','execution_source_manifest_hash'),('deployment_hash','deployment_hash'),('implementation_hash','implementation_hash'),('economic_configuration_hash','active_economic_configuration_hash')]),
 'source5433_review145_deploy31_change6':d['source_counts']=={'raw_Git':5433,'review_manifest':145,'local_deployment':31,'source_changes':6},
 'version_bindings446_ccad7fc':d['reviewed_source_commit']==s['reviewed_source_commit'] and d['baseline_commit']==s['baseline_commit'] and d['platform']['actual_execution_source']==s['actual_cloud_execution_commit'] and d['platform']['candidate_deployed_or_executed'] is False,
 'static67_no_unit':a['static_source_archive']=={'checks':67,'passed':67,'unit_methods':0},
 'metadata9groups_7reject14child3root_no_unit':a['metadata']=={'check_groups':9,'passed':9,'negative_target_CLI_scenarios':7,'child_metadata_CLI':14,'root_confirmation_CLI':3,'unit_methods':0},
 'original_scope_failed_before_product_CLI':a['WR27_MRE']['original_candidate_scope_exit']==1 and a['WR27_MRE']['original_candidate_product_CLI']==0 and a['WR27_MRE']['only_version_constants_adapted'] is True,
 'WR27_positive_old_negative_root_repeat_states_correct':a['WR27_MRE']['ccad_exit']==1 and a['WR27_MRE']['adapted_candidate_exit']==0 and a['WR27_MRE']['root_repeat_exit']==rootexec['exit_code']==0 and (rootmre['default_legal_control_exit'],rootmre['foreign_hash_actual_exit'],rootmre['own_hash_actual_exit'])==(0,1,0) and len([x for x in rootcommands if 'review_metadata.py' in ' '.join(x['command'])])==3,
 'build_unchanged_full_copy_record':a['root_build']['all_copy_bytes_unchanged'] is True and build['all_copy_bytes_unchanged'] is True and build['changed_paths']==[] and build['exit_code']==0,
 'budget17_raw_hash_and_old13':budget['events']==17 and budget['raw_equal_ccad'] is True and budget['old13_prefix_unchanged'] is True and budget['journal_raw_sha256']==s['budget']['journal_raw_sha256'],
 'budget7_10_1_stop2_2_1_no_charge':[(budget[k]['used'],budget[k]['limit']) for k in ('configurations','Research','LEAN')]==[(7,12),(10,20),(1,16)] and budget['engineering_used']==[2,2,1] and budget['engineering_caps']==[2,2,2] and budget['stopped'] is True and budget['current_real_charges']==0 and budget['refund'] is False,
 'archive381_1581651_14739_ZIP_and_manifest':archive['prior_ZIP_bytes']==39319686 and archive['prior_ZIP_sha256']=='2ffc9089ad19a5675d18cafb5379262db7c99a431e518ae4f52cb2dd094b313c' and archive['prior_manifest_entries']==15119 and archive['selected_original_files']==381 and archive['selected_bytes']==1581651 and archive['omitted_original_files']==14739 and archive['old_Git_archive_files_unchanged']==4745 and archive['developer_manifest_entries_verified']==61,
 'binary_original_claim_exactly_matches_independent_read':archive['omitted_binary_original_independently_read'] is True and archive['omitted_binary_bytes']==740565 and archive['omitted_binary_raw_sha256']=='2ff2e0dab64f5a800a5ea8d56029f93e36f0de4be9b8970ac99686aa30e3843f',
 'no_new_findings_software_tested_pass_not_full_phase2':d['findings']==[] and d['software_acceptance']['overall_status']=='本轮已测离线软件范围通过' and d['software_acceptance']['full_phase2_accepted'] is False and d['software_acceptance']['blocking']==[] and d['data_certification']['accepted'] is False and d['data_certification']['observed_input_audit_software_passed'] is True,
 'cloud_comparison28_3_is_archived_not_inventory':d['platform']['archived_cloud_comparison']=={'same':28,'different':3,'not_current_inventory':True} and d['tool_capabilities']['current_QC_calls']==0,
 'stages3_unimplemented_stratified_return_retained':'分层收益未实现' in d['stage_results'][3]['implementation'] and '分层收益未实现' in d['stage_results'][3]['gaps'] and d['stage_results'][3]['status']=='未验收',
 'financial_false_unknown_metrics':d['financial_evidence'] is False and d['financial_metrics'] is None and all(d['closed_gates'][k] is True for k in ('formal_research','automatic_GPT','trading','final_test')),
 'formal_TXT_embedded_JSON_exact':json.loads(text.split('完整机器报告：',1)[1])==d,
 'test_summary_tests_and_execution_exact':ts['tests']==d['tests'] and ts['actually_executed']==d['actually_executed'],
 'all_reported_execution_paths_exist':all((T/p).is_file() for p in a['records']),
 'new_protocol_outer_binding_records_exist':(T/'protocol_agent/outer_execution_records.json').is_file() and (T/'protocol_agent/script_bindings.json').is_file(),
}
paths=['formal_report.json','formal_report.txt','test_execution_summary.json','archive_agent/report.json','archive_agent/wr27_report.json','archive_agent/execution_summary.json','root_wr27_confirmation_execution.json','root_wr27_confirmation/result.json','build_execution.json','protocol_agent/outer_execution_records.json','protocol_agent/script_bindings.json']
hashes={p:hashlib.sha256((T/p).read_bytes()).hexdigest() for p in paths}
notes='''最终正式报告只读QA：来源、计数、证据范围及结论一致；未发现错报。

绑定最终formal_report.json/.txt（含最后补充的旧literal SHA只是历史标签、当前source argv/外层绑定说明，以及protocol outer_execution_records.json/script_bindings.json两个路径）和test_execution_summary.json。

来源5433原字节、145review、31部署、6源码变化及5种hash与独立来源报告完全一致。真实17事件SHA0f9668…与ccad相同，旧13前缀，7/12、10/20、1/16及2/2/1停止正确，零新增扣费/退款。67项静态明确unit0。

WR27当前9/9检查组、7负向CLI、14子审元数据CLI与3root复核CLI准确，不累加为独有unit方法。14子审CLI包含原ccad负控，不冒称全部都在新版本执行。原字节脚本对新候选的固定旧baseline断言失败，产品CLI0，已明确作为范围适配记录而非产品失败；仅C/B常量适配，断言/预期不变。root原件实际默认0/错误S hash1/正确T hash0、MRE总exit0，与独立子审一致。

build完整副本不变记录exit0/changed_paths=[]；668仓库、16组248/2307及其他已执行回归不作独有总数。正式TXT内嵌JSON与formal JSON完全相同，test_execution_summary的tests和actually_executed也完全相同。新增两个protocol外层绑定记录路径真实存在；旧脚本literal不是当前版本身份。

归档完整旧ZIP39319686 bytes/2ffc9089…、15119清单项；选择381原件1581651 bytes、省略14739（合计15120完整文件），4745旧Git归档原件和61开发manifest项口径准确；未将选择性目录冒称完整包。开发binary省略原件实际独立读取的740565bytes/raw2ff2…与正式说明一致，首UnicodeDecodeError是开发打包问题，未被当生产或独立测试失败。

平台本轮QC0，28同3异仅旧归档31源码比较；7fc旧实际失败、无新版成功链、worker/底层原因未知、数字null均未被软件通过替代。软件结论仅本轮已测离线范围通过，原三问题按具体触发及注明边界关闭；phase2整体待真实运行/数据认证、正式研究/GPT自动调用/交易/最终测试仍关闭，financial_evidence=false。阶段3分层收益未实现明确保留，阶段3–7未扩大验收。

本QA只读，未修改root正式稿，未新运行产品测试/MRE。曾先后读取猜测的wr27_confirmation_execution.json与root_confirmation_records.json，路径不存在；随即以root目录实际文件名定位root_wr27_confirmation_execution.json，不计产品失败或测试。
'''
notes+='\n只读字段交叉核对（不是新增unit测试）：\n'+json.dumps(checks,ensure_ascii=False,indent=2)+'\n'
notes+='\n最终读取文件SHA256：\n'+json.dumps(hashes,ensure_ascii=False,indent=2)+'\n'
(R/'qa.txt').write_bytes(notes.encode())
(R/'qa_hashes.json').write_bytes((json.dumps({'checks':checks,'hashes':hashes},ensure_ascii=False,indent=2)+'\n').encode())
print(json.dumps({'qa_file':str(R/'qa.txt'),'all_checks_consistent':all(checks.values()),'failed':[k for k,v in checks.items() if not v],'formal_report_hash':hashes['formal_report.json'],'formal_text_hash':hashes['formal_report.txt']},ensure_ascii=False))
