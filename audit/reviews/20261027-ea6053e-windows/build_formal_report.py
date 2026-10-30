from pathlib import Path
import json
R=Path(__file__).parent
def load(p):return json.loads((R/p).read_text(encoding='utf-8-sig'))
def save(p,x):(R/p).write_bytes((json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode())
A=load('archive_agent/report.json');S=load('archive_agent/supplement_report.json');T=load('test_execution_summary.json');C=load('cert_agent/report.json');D=load('dispatch_agent/root_verified_summary.json')
assert A['checks_passed']==A['static_byte_metadata_checks']==55
f24=load('archive_agent/finding_WR24.json')
f24view={k:f24[k]for k in ['id','priority','blocking','title','reviewed_source_commit','file','line','additional_locations','trigger','expected','actual','impact','severity_rationale','minimal_fix','regression_test','minimal_reproduction']}
findings=[load('finding_WR23.json'),load('cert_agent/finding_WR22.json'),f24view];save('findings.json',findings)
stages=[
 {'stage':0,'implementation':'配置、身份、Registry、预算及归档骨架','evidence':'630仓库、历史回归、55+44字节/元数据检查','gaps':['WR24/P3当前元数据范围歧义'],'status':'既有已测工程范围通过；元数据待更正'},
 {'stage':1,'implementation':'数值、因子表达、PIT、标签和通用模型核','evidence':'独立数值、时间、缓存、合同回归','gaps':[],'status':'既有离线范围通过'},
 {'stage':2,'implementation':'新增IPO和派发修复；源码诊断、采集缓存及任务桥','evidence':'原WR20/21反例通过；WR22/23独立新反例','gaps':['WR23/P1','WR22/P2','真实成功联合链','旧worker差异及完整数据认证'],'status':'本轮模块整体软件验收失败；阶段2整体未通过'},
 {'stage':3,'implementation':'IC、匹配及六轮通用组件；分层收益未实现','evidence':'合成及数值回归','gaps':['分层收益、冻结实际研究设计及真实六轮结果'],'status':'未验收'},
 {'stage':4,'implementation':'工程接收宿主；完整组合/交易/成本/风险适配未实现','evidence':'合成工程链；无真实成功交易链','gaps':['订单成交现金对账、成本风险及Research-LEAN一致性'],'status':'未实现／未验收'},
 {'stage':5,'implementation':'注入adapter的状态机；GPT模型和额度未配且关闭','evidence':'离线工作流组件','gaps':['实际GPT客户端及有限闭环'],'status':'未实现／未验收'},
 {'stage':6,'implementation':'去重、相关辅助组件；无实际搜索/消融产物','evidence':'离线组件测试','gaps':['实际搜索、成本后增量和选择偏差证据'],'status':'未验收'},
 {'stage':7,'implementation':'冻结元数据和关闭闸门；独立最终执行器未配置','evidence':'配置/暴露静态核对','gaps':['完整冻结及独立执行器、前向监控','2026独立性未知'],'status':'未实现／未验收'}]
tests=[dict(T['repository'],suite='repository verify'),{'suite':'16 historical suites with explicit recognized fixtures','methods':248,'passed':248,'failed':0,'errors':0,'skipped':0,'subcases':2307,'actually_executed':True}]+[{k:v for k,v in x.items()if k!='result_file'}for x in T['additional_suites']]
report={
 'review_id':'AQRP-20261027-EA6053E-WINDOWS-18','reviewed_source_commit':A['reviewed_source_commit'],'baseline_commit':A['baseline_commit'],
 'evidence_commits':{'actual_cloud_execution':A['actual_cloud_source_commit'],'failed_original_review':'deb85d9f27441b275ab8b108f0232ecd2707a1e8','last_passed_old_offline_scope':'66ff72ffaaff8c91c008898e6527c91131176c2a','current_archive':A['reviewed_source_commit']},
 'verdict':'原WR20、WR21触发场景修复后通过；新增WR23/P1、WR22/P2阻断本轮模块整体软件验收。WR24/P3非阻断。阶段2整体未通过。',
 'repair_acceptance':{'WR20_original_counterexample':'修复后通过；IPO已测边界通过','WR21_explicit_entry_without_dispatch_counterexample':'修复后通过；合法绑定及旧任务正控保留','data_audit_module':'失败WR22','new_entry_protocol_overall':'失败WR23','old_failure_records_preserved':True},
 'PR':{'number':2,'state':'open','draft':True,'merged':False,'head':A['reviewed_source_commit'],'base_sha':'6a1edbf07fa8fc6cf774084094f4beacc28ff60b','metadata_source':'official GitHub read-only REST after connector transport failure'},
 'source_manifest_hash':A['source_manifest_hash'],'execution_source_manifest_hash':A['execution_source_manifest_hash'],'deployment_hash':A['deployment_hash'],'implementation_hash':A['implementation_hash'],'active_configuration_hash':A['active_configuration_hash'],
 'source_counts':{'raw_git':4541,'review_manifest':140,'local_deployment':31,'developer_raw_manifest_entries':43,'prior_archived_files_unchanged':4047,'protected_runtime_input_observation_files':38},
 'archive_boundary':{'previous_complete_review_ZIP':{'bytes':33811222,'sha256':'19d2614008caf209c18b79e16220826de0394ee9a86f585f32ccce5a9bfd6b49','registered_manifest_files':12474,'including_manifest_itself':12475},'selected_into_current_Git':{'files':216,'bytes':3361243,'omitted_from_complete_package':12259},'prior_Git_archive_files_unchanged_4047':'All historical review/package files already inbaseline Git, a different population from the216 selected files and the complete12475-file reviewZIP.'},
 'environment':load('environment.json'),
 'tool_capabilities':{'offline_Python':True,'GitHub_metadata_read':True,'current_QC_calls':0,'current_Research_executions':0,'current_LEAN_submissions':0,'current_model_calls':0,'cloud_writes':0,'authoritative_registry_writes':0,'production_changes':0,'PR_approval_or_merge':0,'final_data_opened':False},
 'stage_results':stages,'tests':tests,'test_counts_unique':False,
 'other_execution':{'static_main':{'checks':55,'passed':55,'unit_methods':0},'static_supplement':{'checks':44,'passed':44,'unit_methods':0},
 'WR21_original_unchanged_MRE':{'baseline_exit':1,'candidate_exit':0,'CLI_per_version':17,'original_script_sha256':'22e8b105fb413bd231b35284e9cb88f3f5a7aa016049429e74940203d2a7e4f4'},
 'WR20_original_unchanged_MRE':{'baseline_exit':1,'candidate_exit':0,'baseline_suite':[13,12,1],'candidate_suite':[13,13,0],'scenarios_per_suite':43},
 'entry_concurrent_controls':{'manual_chains':3,'passed':3,'CLI':21,'actual_parallel_Windows_processes':2,'single_permission':True},
 'native_and_recovery_adapters':{'native_methods':9,'native_subcases':90,'native_CLI':117,'native_synthetic_finish':14,'manual_probes':8,'recovery_methods':5,'recovery_subcases':46,'recovery_CLI':76,'recovery_direct_processes':12,'recovery_synthetic_finish':4,'assertion_class_AST_unchanged':True},
 'native_Research_failure_original_bytes':{'methods':6,'subcases':91,'passed':6,'CLI':25,'worker_or_SDK':0},
 'root_new_finding_confirmations':T['root_new_finding_MREs'],'WR23_CLI_per_MRE':6,'WR23_synthetic_finish_per_MRE':1,
 'WR24_readonly_MRE_exit':1,'CI':{'run':40504444358,'Python310_job':122190039456,'Python311_job':122190038731,'both_success':True,'independently_counted_CI_tests':None},
 'counts_are_overlapping':True,'archived_script_literals':'Old fixed_commit literals and SID200_ranked_first target label remain raw-identical; actual version/status/ranking is determined by outer execution bindings and computed result hashes.'},
 'findings':findings,'first_results_preserved':T['first_results_preserved']+[{'scope':'reviewer matrix checksum','reason':'A derived .sha256 sidecar originally used pre-write LF text while saved reviewer JSON used CRLF. Original sidecar retained; separate raw checksum and QA correction provided. Product/source hashes and root report values were not affected.'}],
 'budget_replay':{'events':17,'raw_equal_baseline_deb':True,'old_13_prefix_unchanged':True,'journal_raw_sha256':A['budget_replay']['journal_raw_sha256'],
 'configurations':{'used':7,'limit':12,'normal':6,'reserve':1},'Research':{'used':10,'limit':20,'normal':6,'reserve':4},'LEAN':{'used':1,'limit':16,'normal':1,'reserve':0},
 'engineering_used':{'configurations':2,'Research':2,'LEAN':1},'engineering_caps':{'configurations':2,'Research':2,'LEAN':2},'stopped':True,'current_real_charges':0,'refund':False,'authoritative_writes':0,'original_Research_status':'failed','old_LEAN_status':'failed'},
 'platform_evidence_level':{'current_review':'offline source/evidence/test review only; no current QC access','archived_source_readback':'Prior auditor read32 Python files andcell1 source at7fc; this round reparses saved bytes only','archived_failure':'Developer saved native Research failure independently replayed offline, not a fresh live failure read'},
 'platform':{'actual_cloud_source':'7fc5ef2e9d2379d29f48d05a1f3cc760000884d6','current_candidate_cloud_executed':False,'candidate31_vs_archived_executed31':{'same':28,'different':3,'scope':'archived reference comparison, not current platform inventory'},
 'original_Research_attempt':'f5d05f5b964b4a1d924e4b70cd207386','status':'failed','error_class':'CollectionError','underlying_cause_known':False,'native_packet_sha256':'14ae4a18636496737862a1ce314d90ae7fcf1abaf35f8a0f27145e0e839af8f3',
 'native_result_hash':'6a5371b3ff243998baded6dc2f9627b110af793a94907a4a73859ced3d5f4f0b','representations':2,'logical_failures':1,'traceback_entries':9,'traceback_physical_lines':43,
 'normal_failure_replay':[15,17,17],'write_failure_replay':[15,16,18,18],'extra_pending_is_new_charge':False,'success_engineering_report':False,'new_LEAN_submitted':False,
 'history_calls':None,'received_records':None,'orders':None,'financial_statistics':None,'old_worker_source_verified':False,'full_inventory_certified':False},
 'historical_findings':{'WR01_WR19':'保持原SHA及有限范围结论；本轮既有回归通过。','WR20_WR21':'原反例在本SHA修复后通过；不推导新模块整体通过。','new_blocking':['WR23/P1','WR22/P2'],'new_nonblocking':['WR24/P3']},
 'unverified':['修复WR22/23/24后的新固定SHA','真实新版Research-采集缓存-LEAN成功联合链','旧worker具体源码差异和源迭代底层原因','全历史US200、财务版本、实际送达及摄入认证','阶段3–7完整运行和金融效果','其他OS独立运行及OS kill/断电持久性','2026独立性；2024–2025既往暴露已知'],
 'software_acceptance':{'original_fix_scope':'修复后通过','overall_status':'失败','blocking':['WR23','WR22'],'nonblocking':['WR24'],'full_phase2_accepted':False},
 'data_certification':{'status':'证据不足且观测审计存在WR22','accepted':False,'vendor_authentication':False,'full_historical_US200':False,'financial_vintage':False,'actual_availability':False},
 'financial_evidence':False,'financial_metrics':None,
 'closed_gates':{'formal_research':True,'automatic_GPT':True,'trading':True,'final_test':True,'GPT_model':None,'GPT_call_limit':None,'GPT_spend_limit':None,'active_factor':None,'active_model':None,'active_trading':None},
 'reproduction':{'WR23':'python -B dispatch_agent/minimal_prepare_entry_crash.py --source source --out <fresh-output>; helper in same directory; current exit1',
 'WR22':'python -B cert_agent/minimal_wr22.py --output <fresh-result.json>; current exit1',
 'WR24':'python -B archive_agent/minimal_wr24_metadata.py; current exit1',
 'records':['test_execution_summary.json','archive_agent/report.json','archive_agent/supplement_report.json','cert_agent/report.json','dispatch_agent/root_verified_summary.json','root_confirmation_records.json','entry_controls_execution.json']}}
save('formal_report.json',report)
text=['结论：'+report['verdict'],'固定SHA：'+report['reviewed_source_commit'],'失败基线：'+report['baseline_commit'],'实际云端执行仍为7fc5ef2，当前ea仅离线修补。',
 '630仓库通过，独立原WR20/21反例均由baseline exit1变candidate exit0；不能代替新增组合/故障边界。当前P1/P2均根独立再次复现。', '\n全系统覆盖：']
for x in stages:text.append(f"阶段{x['stage']}：{x['status']}；{x['implementation']}；证据{x['evidence']}；缺口{'、'.join(x['gaps'])or'已测范围无新增缺口'}。")
text+=['\n按优先级的问题：']
for f in findings:
    locations=f.get('locations',[{'file':f.get('file'),'line':f.get('line')}]);text.extend([f['id']+'/'+f['priority']+' '+f['title'],'位置：'+','.join(str(p['file'])+':'+str(p['line'])for p in locations),'触发：'+f['trigger'],'预期：'+f['expected'],'实际：'+f['actual'],'最小修复：'+f['minimal_fix']])
text+=['\n实际执行（方法/子例/场景不加成独有总数）：']
for x in tests:text.append(f"{x['suite']}：{x['passed']}/{x['methods']}；失败{x['failed']}、错误{x['errors']}、跳过{x['skipped']}；子例{x['subcases']}"+(f"；场景{x['scenario_checks']}"if'scenario_checks'in x else''))
text+=['旧6/62+3/28+8manual在合法index4派发前置适配后过；原6/91原字节过；恢复5/46原首1方法/2子例因新guard拒绝，保留原件，适配只在setup pin绑定且类/断言AST不变。依赖原setup失败的manual未运行/缺template不计通过。',
 'worker6/51、预检12/70、实际Windows双进程只1许可等3链21CLI通过；原WR21两版本各17CLI，WR23每次6CLI+1合成_finish、0worker/provider。静态55/55+44/44不计软件方法。',
 '原测试旧literalSHA与SID200_ranked_first静态标签原字节保留；新版本结论只用外层实际SOURCE、状态/哈希。首次审查器schema错误54/55、root inline else0语法错误及中断子审均保留；未执行扩展未计通过。',
 '\n身份/预算/平台：4541Git原字节，140review，31本地部署；43开发原件、4047旧归档raw不改。经济配置272e…不变。真实17事件原字节与deb相同，旧13前缀，7/12、10/20、1/16；工程2/2/1保持停止，无退款或本轮真实扣费。',
 '旧完整deb审核ZIP33811222 bytes/19d261…含12474清单项+清单自身=12475文件；本次Git仅选择216原件/3361243bytes，遗漏12259项。4047不变旧Git归档是另一历史总体，不冒称完整旧包。本包保留此边界。',
 '本轮QC0，未读notebook数据/最终测试，未执行Research/LEAN/模型/部署/交易，未修改生产或批准合并PR。28同3异是本地候选与前轮归档7fc31源码比较，不是本轮平台读回或完整inventory认证。',
 '原f5d是1个真实失败/2载体、9traceback条目/43物理行；底层cause未知。正常15→17→17，写故障15→16→18→18的重复pending不是重复扣费。成功报告/History次数/收到记录/订单/金融统计无证据，null保留。',
 '\n下一步：仅离线修复WR23协议发布/身份和WR22连续历史资格后，以新固定SHA重审；WR24将旧描述显式归档并更新current字段。继续保持已触发工程停止门，不自动重交云端、不改预算/暴露/最终日期。实际成功链、旧worker和完整数据认证继续单列。',
 '正式研究、自动GPT、交易、最终测试关闭；2024–2025已暴露、2026独立性未知。financial_evidence=false，未给出因子/模型/组合金融有效性结论。']
(R/'formal_report.txt').write_bytes(('\n'.join(text)+'\n').encode());print(json.dumps({'review_id':report['review_id'],'original_repair_passed':True,'overall_software_passed':False,'findings':[x['id']for x in findings],'tests':len(tests)},ensure_ascii=False))
