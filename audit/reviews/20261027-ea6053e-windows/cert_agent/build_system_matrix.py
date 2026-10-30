"""Read-only stage/control matrix; refresh every cited source line and raw hash."""
from pathlib import Path
from copy import deepcopy
import ast,hashlib,json
O=Path(__file__).parent;R=O.parent;S=R/'source';OLD=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-deb85d9-20261027\cert_agent\system_matrix.json')
SHA='ea6053e3e9ef4be17db246daf18a4cf9b2e5be58'
def sha(b):return hashlib.sha256(b).hexdigest()
def read(p):return json.loads((S/p).read_text(encoding='utf-8-sig'))
previous=json.loads(OLD.read_text(encoding='utf-8'));refs={};remap={}
for oldkey,v in previous['references'].items():
 raw=(S/v['path']).read_bytes();lines=raw.decode('utf-8-sig').splitlines();matches=[i for i,line in enumerate(lines,1) if v['excerpt'] in line]
 assert len(matches)==1,(v['path'],v['excerpt'],matches)
 start=matches[0];end=start+(v['end_line']-v['line'])
 # For unchanged function/class declarations, use current AST end rather than old length.
 if v['excerpt'].lstrip().startswith(('def ','class ','async def ')):
  nodes=[n for n in ast.walk(ast.parse(raw.decode('utf-8-sig'))) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)) and n.lineno==start]
  assert len(nodes)==1;end=nodes[0].end_lineno
 key=v['path']+':'+str(start);remap[oldkey]=key;refs[key]={'path':v['path'],'absolute_path':str(S/v['path']),'line':start,'end_line':end,'raw_sha256':sha(raw),'excerpt':lines[start-1][:350]}
def add(path,needle):
 raw=(S/path).read_bytes();lines=raw.decode('utf-8-sig').splitlines();matches=[i for i,line in enumerate(lines,1) if needle in line];assert matches,(path,needle)
 start=matches[0];key=path+':'+str(start);refs[key]={'path':path,'absolute_path':str(S/path),'line':start,'end_line':start,'raw_sha256':sha(raw),'excerpt':lines[start-1][:350]};return key
def replace_refs(v):
 if isinstance(v,dict):return {k:replace_refs(x) for k,x in v.items()}
 if isinstance(v,list):return [replace_refs(x) for x in v]
 if isinstance(v,str):return remap.get(v,v)
 return v
report=replace_refs(deepcopy(previous));plan=read('config/development.json');research=read('config/research.json');data=read('config/data.json');catalog=read('config/source_catalog.json');workflow=read('config/workflow.json');qc=read('config/quantconnect.json');budget=read('config/budget.json');exposure=read('audit/data_exposure.json')
g={n.targets[0].id:ast.literal_eval(n.value) for n in ast.parse((S/'cloud/research_config.py').read_bytes()).body if isinstance(n,ast.Assign)}
assert all(plan['execution'][k] is False for k in ('market_research_enabled','llm_runtime_enabled','final_test_enabled','live_trading_enabled'))
assert all(plan['execution'][k] is None for k in ('llm_model','llm_call_limit','llm_spend_limit_usd'))
assert all(research[k] is None for k in ('active_factor_spec','active_model_spec','active_trading_spec'))
assert all(g['CONFIGURATION'][k] is None for k in ('active_factor','active_model','active_trading_rules'))
assert all(workflow[k] is None for k in ('active_factor','active_model','active_trading_rules'))
assert research['final_evaluation']['execution_enabled'] is False and research['final_evaluation']['independent_executor_configured'] is False
assert workflow['orders_enabled'] is False and qc['backtest_submission_enabled'] is False and qc['live_deployment_enabled'] is False
assert budget['final_evaluation_execution_enabled'] is False
assert data['factor_field_whitelist']==[] and catalog['factor_fields_enabled'] is False
assert exposure['whole_window_uncontaminated'] is False and exposure['year2026_independence']=='requires independent review'
report.update(fixed_commit=SHA,kind='static_system_stage0_7_matrix_not_new_software_acceptance',software_methods_executed=0,software_suites_or_builds=0,new_platform_calls=0,production_code_executed=False)
report['identity']={'current_local_commit':SHA,'implementation_hash_from_generated_configuration':g['IMPLEMENTATION_SHA256'],'active_configuration_hash':g['SOURCE_SHA256'],'full_identity_verification':'separate root/archive agent evidence; this matrix does not duplicate source/execution/deployment manifest verification'}
report['active_configuration']={'id':research['configuration_id'],'status':research['status'],'generated_configuration_hash':g['SOURCE_SHA256'],'active_factor_spec':research['active_factor_spec'],'active_model_spec':research['active_model_spec'],'active_trading_spec':research['active_trading_spec'],'complete_strategy_configurations_frozen':budget['usage']['complete_strategy_configurations_frozen']}
report['stages'][0]['missing_or_unverified']=['合同形状与hash不认证真实数据覆盖、经济机制、远程来源或真实执行。','本轮ea最终软件验收由主审报告核定；本矩阵不扩大旧固定版本批准。']
stage=report['stages'][2];stage['static_implementation']='WR20_IPO_fix_passes_original_scope_new_WR22_observed_history_failure'
stage['acceptance_boundary']='原WR20 IPO20期过滤范围独立复验通过；新增WR22/P2使数据观测组件不能整体通过。WR21结算绑定修复另由主审/entry代理验收；整个阶段2仍未通过。'
stage['implemented']=['共享缓存、交易日历、批量History、永久SID、历史快照采集与覆盖合同。','任务桥、同父Research→LEAN、原生失败与原attempt恢复、worker身份诊断、固定cell入口组件。','本轮IPO过滤只改变已核对的排名视图：上市前行不贡献20期，原批次refs/count/raw保持。','数据观测合规及汇总私有重算组件存在；不提供供应商/全历史/实际送达认证。']
stage['missing_or_unverified']=['WR22：连续老listed SID最近更新mapping/classification区间后，缺全liquidity可失去候选完整性检查资格并由rank201补位。','实际云端执行仍7fc5ef，Research源迭代CollectionError失败，底层cause未知，没有成功工程报告、新LEAN或本轮候选成功云端运行。','旧失败LEAN具体worker差异和根因消除未证明；源码/指纹只读不等于worker全认证。','完整历史US200、财务原报/修订vintage、实际公开/供应商送达/历史摄入及公司行动认证仍缺。','本轮原WR20局部通过不能授予新WR22模块、全阶段2或金融验收。']
stage['references'] += [add('cloud/qresearch/data_certification.py','post_listing = ['),add('cloud/qresearch/data_certification.py','active = [row for row in masters'),add('cloud/qresearch/data_certification.py','expected_candidates = {row'),add('docs/review/wr20-wr21.md','上市前记录不能计入'),add('audit/stage2_current_readiness.json','"stage2_status"')]
report['budget']={'authoritative_events':17,'used':{'configurations':7,'research':10,'lean':1},'round_engineering_used':{'configurations':2,'research':2,'lean':1},'limits':budget['limits'],'no_refund_on_failure':True,'configuration_and_research_round_caps_reached':True,'no_automatic_retry':True,'source_of_fact':'Unchanged authoritative journal/root independent ledger verification and current readiness projection; this static matrix does not rewrite or replay authority.'}
report['implementation_versions']={'current_local_commit':SHA,'actual_executed_commit':'7fc5ef2e9d2379d29f48d05a1f3cc760000884d6','current_candidate_cloud_deployed':False,'current_review_QC_reads':0,'current_platform_inventory_certified':False,'cloud_success':False,'comparison_boundary':'No new platform comparison run by this agent; historical deb29-equal/2-different count is not reused for this changed candidate.'}
report['data_certification_observed_scope']={'WR20_original_candidate_replay':{'methods':13,'passed':13,'failed':0,'errors':0,'scenario_checks':43,'original_assertions_and_bytes_unchanged':True},'new_boundaries':{'methods':9,'passed':8,'failed':1,'errors':0,'scenario_checks':23,'failure_records':2,'finding':'WR22/P2'},'counts_overlap_and_are_not_unique':True,'scenario_checks_are_not_unittest_subcase_counts':True,'all_vendor_full_history_actual_timing_research_financial_flags_false':True,'actual_historical_source_authentication_supported':False}
report['controls']['declared_execution']=plan['execution'];report['controls']['references']+= [add('docs/review/wr20-wr21.md','正式因子研究、自动GPT调用、交易和最终测试继续关闭')]
report['exposure']['ledger']=exposure
report['global_missing']=['WR22 observed completeness/history fix and independent retest','current repair software acceptance and matching actual successful bounded Research/LEAN evidence','oldworker actual-byte evidence and root-cause repair','authoritative full historical US200/PIT/financial-vintage and actual-availability evidence','registered production factor/model/trading design and generic portfolio engine','enabled bounded GPT closed loop','independent final executor and forward monitoring/rollback']
report['conclusion']='Prior scoped stage0/1 conclusions retained. WR20 original IPO-fix scope passes; current observed-data module fails new WR22/P2. WR21 decision belongs to separate independent root audit. Whole stage2/system, stages3–7, unattended actual factor research, final test and financial validity remain unaccepted.'
report['references']=refs;report['reference_count']=len(refs);report['financial_evidence']=False
raw=json.dumps(report,ensure_ascii=False,indent=2)+'\n';(O/'system_matrix.json').write_text(raw,encoding='utf-8');(O/'system_matrix.json.sha256').write_text(sha(raw.encode())+'  system_matrix.json\n',encoding='utf-8')
lines=['固定 '+SHA+' 全系统0–7只读静态矩阵；0新增软件方法/0构建/0平台调用。',report['conclusion'],'当前通用配置 '+research['configuration_id']+'；hash '+g['SOURCE_SHA256']+'；active factor/model/trading均null。','正式研究/自动GPT/交易/最终测试关闭；GPT model/call/spend限额null；字段白名单空；所有正式数据及金融认证false。','']
for s in report['stages']:lines += [str(s['stage'])+' '+s['name']+'：'+s['acceptance_boundary'],'已实现：'+'；'.join(s['implemented']),'缺口：'+'；'.join(s['missing_or_unverified']),'证据：'+'，'.join(s['references']),'']
lines += ['17事件：配置7/12、Research10/20、LEAN1/16；工程2/2/1，配置/Research停止门保持，失败不退款。','时间：2010–17→2018至2015–22→2023，固定8年+1年共六轮；最终计划2024-01-01至2026-10-23仍关闭，独立执行器未配。','2024–25已有筛选/方向暴露；2026独立性未知，不能称最终整窗untouched或已证明独立。删除文件不抹除暴露。','原WR20：旧deb原MRE exit1/13方法12过1失败43场景；新ea原MRE exit0/13方法全过43场景。新增独立边界9方法8过1失败23场景（2记录属WR22）。各复验有重叠，不加为独有总数。','实际执行仍7fc；此代理本轮未读取QC、数据、notebook输出，未执行市场或模型，未改真实17账本。','当前612或630开发/仓库计数不能代替真实数据/阶段/金融验收；本矩阵不自行重跑或宣称主审未完成的套件。','','精确固定源码raw hash引用：']
for key,v in refs.items():lines.append(key+' '+v['raw_sha256'])
(O/'system_matrix.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(json.dumps({'written':True,'stages':len(report['stages']),'references':len(refs),'JSON_raw_sha256':sha(raw.encode()),'software_methods':0},ensure_ascii=False,indent=2))
