"""Static matrix: fresh source lines/raw hashes, no software or platform execution."""
from pathlib import Path
from copy import deepcopy
import ast,hashlib,json,re
O=Path(__file__).parent;R=O.parent;S=R/'source';OLD=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-ccad61d-20261027');SHA='44676db609b3b7c2175fa7fa4f19c8ccf8165458'
def sha(b):return hashlib.sha256(b).hexdigest()
def read(p):return json.loads((S/p).read_text(encoding='utf-8-sig'))
previous=json.loads((OLD/'cert_agent/system_matrix.json').read_text(encoding='utf-8'));refs={};remap={}
for key,v in previous['references'].items():
 raw=(S/v['path']).read_bytes();lines=raw.decode('utf-8-sig').splitlines();needle=v['excerpt'];matches=[i for i,line in enumerate(lines,1) if needle in line]
 if not matches and v['path']=='cloud/qresearch/data_certification.py' and 'expected_candidates = {' in needle:
  matches=[i for i,line in enumerate(lines,1) if 'expected_candidates, unknown_history = _historical_candidate_evidence(' in line]
 if not matches and v['path']=='cloud/qresearch/data_certification.py' and 'for sid, versions in current.items()' in needle:
  matches=[i for i,line in enumerate(lines,1) if 'for sid in sorted(set(histories) | set(listing_clocks))' in line]
 if not matches and v['path'].endswith('.json'):
  prop=re.search(r'"([^"\n]+)"\s*:',needle)
  if prop:matches=[i for i,line in enumerate(lines,1) if '"'+prop[1]+'":' in line]
 assert len(matches)==1,(v['path'],needle,matches)
 start=matches[0];end=start+(v['end_line']-v['line'])
 if v['excerpt'].lstrip().startswith(('def ','class ','async def ')):
  nodes=[n for n in ast.walk(ast.parse(raw.decode('utf-8-sig'))) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)) and n.lineno==start];assert len(nodes)==1;end=nodes[0].end_lineno
 newkey=v['path']+':'+str(start);remap[key]=newkey;refs[newkey]={'path':v['path'],'absolute_path':str(S/v['path']),'line':start,'end_line':end,'raw_sha256':sha(raw),'excerpt':lines[start-1][:350]}
def add(path,needle):
 raw=(S/path).read_bytes();lines=raw.decode('utf-8-sig').splitlines();matches=[i for i,line in enumerate(lines,1) if needle in line];assert matches,(path,needle)
 i=matches[0];key=path+':'+str(i);refs[key]={'path':path,'absolute_path':str(S/path),'line':i,'end_line':i,'raw_sha256':sha(raw),'excerpt':lines[i-1][:350]};return key
def rewrite(v):
 if isinstance(v,dict):return {k:rewrite(x) for k,x in v.items()}
 if isinstance(v,list):return [rewrite(x) for x in v]
 return remap.get(v,v) if isinstance(v,str) else v
report=rewrite(deepcopy(previous));dev=read('config/development.json');research=read('config/research.json');budget=read('config/budget.json');workflow=read('config/workflow.json');qc=read('config/quantconnect.json');data=read('config/data.json');catalog=read('config/source_catalog.json');exposure=read('audit/data_exposure.json')
g={n.targets[0].id:ast.literal_eval(n.value) for n in ast.parse((S/'cloud/research_config.py').read_bytes()).body if isinstance(n,ast.Assign)}
protected={p:(S/p).read_bytes()==(OLD/'source'/p).read_bytes() for p in ('config/development.json','config/research.json','config/data.json','config/source_catalog.json','config/workflow.json','config/quantconnect.json','config/budget.json','audit/data_exposure.json','docs/research_charter.md')}
assert all(protected.values())
assert all(dev['execution'][k] is False for k in ('market_research_enabled','llm_runtime_enabled','final_test_enabled','live_trading_enabled'))
assert all(dev['execution'][k] is None for k in ('llm_model','llm_call_limit','llm_spend_limit_usd'))
assert all(research[k] is None for k in ('active_factor_spec','active_model_spec','active_trading_spec'))
assert all(g['CONFIGURATION'][k] is None for k in ('active_factor','active_model','active_trading_rules'))
assert all(workflow[k] is None for k in ('active_factor','active_model','active_trading_rules'))
assert workflow['orders_enabled'] is False and qc['backtest_submission_enabled'] is False and qc['live_deployment_enabled'] is False
assert research['final_evaluation']['execution_enabled'] is False and research['final_evaluation']['independent_executor_configured'] is False and budget['final_evaluation_execution_enabled'] is False
assert data['factor_field_whitelist']==[] and catalog['factor_fields_enabled'] is False
assert exposure['whole_window_uncontaminated'] is False and exposure['year2026_independence']=='requires independent review'
report.update(fixed_commit=SHA,kind='static_system_stage0_7_matrix_not_new_system_acceptance',software_methods_executed=0,software_suites_or_builds=0,new_platform_calls=0,production_code_executed=False)
report['identity']={'current_local_commit':SHA,'implementation_hash_from_generated_configuration':g['IMPLEMENTATION_SHA256'],'active_configuration_hash':g['SOURCE_SHA256'],'full_identity_verification':'Root/archive agent separate full identity checks; this matrix verifies only its own exact raw source references.'}
report['protected_static_bytes_equal_baseline']=protected
report['stages'][0]['missing_or_unverified']=['合同形状和hash不认证真实覆盖、来源或执行。','本轮446新增实现/元数据的最后验收由主审固定范围核定，不扩大旧批准。']
stage=report['stages'][2];stage['static_implementation']='WR25_WR26_fixed_and_independent_qualification_scope_passes';stage['acceptance_boundary']='WR25/26原七场景反例、新资格组合及原有13/43、9/23、9/29范围复验通过；这只是已测观测软件范围。WR27另由主审核定；真实成功链及来源认证未满足，阶段2整体仍未通过。'
stage['implemented']=['共享缓存、PIT交易日历、History、永久SID、历史快照采集、任务桥和原生回执。','IPO上市前行不进入20期排名视图，原raw/count/ref留存。','完整主表半开区间独立证明老SID连续上市；封闭分类纳入/排除/unknown，已知SID当前覆盖缺失或晚知不能消失。','明确及时排除合法，有限排除到期不永久延续；future-only历史不能创造过去库存。','汇总重新核对私有输入，观测状态不授予正式vendor/full-history/actual-availability/research认证。']
stage['missing_or_unverified']=['实际执行仍7fc；此前Research源取数迭代CollectionError失败，底层cause未知；无本轮新候选云端成功联合链。','旧LEAN具体worker差异及根因消除、完整US200/财务版本/实际公开/供应商送达/历史摄入认证不足。','本轮有界观测软件通过不能代替完整历史库存、供应商来源、真实送达或生产批准。','本代理不运行WR27或整个广回归；主审各组件结论按独立证据与范围核定。']
stage['references'] += [add('cloud/qresearch/data_certification.py','def _classification_kind'),add('cloud/qresearch/data_certification.py','def _master_qualification'),add('cloud/qresearch/data_certification.py','for sid in sorted(set(histories) | set(listing_clocks))'),add('audit/review_packages/wr25_wr27/README.md','有限区间到期'),add('docs/review/wr25-wr27.md','2024–2025已暴露')]
report['controls']['declared_execution']=dev['execution'];report['active_configuration'].update(generated_configuration_hash=g['SOURCE_SHA256'],active_factor_spec=None,active_model_spec=None,active_trading_spec=None)
report['budget']={'authoritative_events':17,'used':{'configurations':7,'research':10,'lean':1},'round_engineering_used':{'configurations':2,'research':2,'lean':1},'limits':budget['limits'],'configuration_and_research_stop_caps_reached':True,'no_refund_on_failure':True,'new_authority_writes_by_this_agent':0,'source_of_fact':'Root separate ledger verification; config/budget and immutable runtime protected bytes/readiness; this static matrix did not replay/write real authority.'}
report['implementation_versions']={'current_local_commit':SHA,'actual_executed_commit':'7fc5ef2e9d2379d29f48d05a1f3cc760000884d6','current_candidate_cloud_deployed':False,'current_review_QC_reads_by_this_agent':0,'platform_inventory_certified':False,'current_candidate_runtime_success':False,'comparison_boundary':'No fresh platform source, cell or output read. No old local-equality count reused for this changed source.'}
h=json.loads((O/'qualification_first_results.json').read_text(encoding='utf-8'));assert h['failed_methods']==0 and h['error_methods']==0
report['data_certification_observed_scope']={'original_WR25_WR26_MRE':{'baseline_ccad_exit':1,'candidate_exit':0,'scenarios':7,'byte_identical':True},'original_WR20_suite':{'methods':13,'passed':13,'failed':0,'errors':0,'scenario_checks':43},'previous_combinations_suite':{'methods':9,'passed':9,'failed':0,'errors':0,'scenario_checks':23},'previous_history_suite':{'methods':9,'passed':9,'failed':0,'errors':0,'scenario_checks':29},'new_qualification_suite':{k:h[k] for k in ('methods','passed_methods','failed_methods','error_methods','scenario_checks','failure_records')},'counts_overlap_and_not_unique':True,'named_scenarios_are_not_unittest_subcases':True,'all7_certification_flags_false':True,'vendor_truth_authentication_supported':False}
report['global_missing']=['Actual successful bounded Research/LEAN chain for current software','oldworker actual source evidence and root-cause repair','full historical US200/PIT/financial-vintage/actual-availability provenance','registered factor/model/trading and generic portfolio accounting/cost/risk','enabled GPT model/call/spend and unattended loop','independent final executor, forward monitoring/rollback']
report['conclusion']='WR25/26原触发及新增资格已测软件范围通过；原WR20/22与已测历史边界保留。既有阶段0/1限定范围及其余修复由主审核定。整个阶段2和阶段3–7、无人值守真实研究、最终测试、完整数据/供应商认证和金融有效性仍未验收。'
report['references']=refs;report['reference_count']=len(refs);report['financial_evidence']=False
raw=(json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode();(O/'system_matrix.json').write_bytes(raw);digest=sha((O/'system_matrix.json').read_bytes());(O/'system_matrix.raw.sha256').write_bytes((digest+'  system_matrix.json\n').encode())
lines=['固定 '+SHA+' 全系统0–7只读静态矩阵。0新增软件方法/0构建/0平台调用。',report['conclusion'],'当前配置hash '+g['SOURCE_SHA256']+'；active factor/model/trading null；GPT模型/调用数/花费额度null。','正式研究、自动GPT、交易、最终测试关闭；工程停止门保持。','']
for s in report['stages']:lines += [str(s['stage'])+' '+s['name']+'：'+s['acceptance_boundary'],'实现：'+'；'.join(s['implemented']),'缺口：'+'；'.join(s['missing_or_unverified']),'证据：'+'，'.join(s['references']),'']
lines += ['17事件：配置7/12、Research10/20、LEAN1/16；工程2/2/1；本代理0真实调用和账本写入。','2010–17→2018至2015–22→2023固定8+1六轮；最终计划2024-01-01至2026-10-23关闭且独立执行器未配。','2024–25已暴露，2026独立性未知。不得将最终整窗称为untouched；删除不抹除暴露。','实际云端仍7fc，不把新本地实现、旧源码读回或旧失败当作本轮成功执行。','原13/43、9/23、9/29均通过；新增'+str(h['methods'])+'方法/'+str(h['scenario_checks'])+'场景均通过。方法/场景/重复不相加为独有总数。','financial_evidence=false；软件检查不代表金融有效性。','','精确源码引用/rawSHA：']
for key,v in refs.items():lines.append(key+' '+v['raw_sha256'])
(O/'system_matrix.txt').write_bytes(('\n'.join(lines)+'\n').encode());print(json.dumps({'stages':8,'references':len(refs),'software_methods':0,'JSON_raw_sha256':digest},ensure_ascii=False,indent=2))
