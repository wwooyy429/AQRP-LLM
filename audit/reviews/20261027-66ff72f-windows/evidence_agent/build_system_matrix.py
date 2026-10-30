"""Static 0-7 system matrix. Reads source/JSON/AST only; executes no product code."""
from pathlib import Path
import ast,hashlib,json
R=Path(__file__).resolve().parents[1];O=Path(__file__).resolve().parent;S=R/'source'
SHA='66ff72ffaaff8c91c008898e6527c91131176c2a'
def sha(b):return hashlib.sha256(b).hexdigest()
def read(p):return json.loads((S/p).read_text(encoding='utf-8-sig'))
refs={}
def ref(path,needle=None,declaration=None):
 raw=(S/path).read_bytes();text=raw.decode('utf-8-sig');lines=text.splitlines()
 if declaration:
  tree=ast.parse(text);names=declaration.split('.');nodes=tree.body
  for name in names:
   found=[n for n in nodes if isinstance(n,(ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==name]
   assert len(found)==1,(path,declaration);node=found[0];nodes=node.body
  start,end=node.lineno,node.end_lineno
 else:
  matches=[i for i,line in enumerate(lines,1) if needle in line];assert matches,(path,needle);start=end=matches[0]
 key=path+':'+str(start);refs[key]={'path':path,'absolute_path':str(S/path),'line':start,'end_line':end,'raw_sha256':sha(raw),'excerpt':lines[start-1][:350]}
 return key
def code(p,n):return ref('cloud/qresearch/'+p+'.py',declaration=n)
def cfg(p,n):return ref('config/'+p+'.json',n)
plan=read('config/development.json');research=read('config/research.json');data=read('config/data.json');catalog=read('config/source_catalog.json');workflow=read('config/workflow.json');qc=read('config/quantconnect.json');budget=read('config/budget.json');exposure=read('audit/data_exposure.json')
ident=json.loads((O/'evidence_verification.json').read_text(encoding='utf-8'))['source']
g={n.targets[0].id:ast.literal_eval(n.value) for n in ast.parse((S/'cloud/research_config.py').read_bytes()).body if isinstance(n,ast.Assign)}
assert all(plan['execution'][k] is False for k in ('market_research_enabled','llm_runtime_enabled','final_test_enabled','live_trading_enabled'))
assert all(research[k] is None for k in ('active_factor_spec','active_model_spec','active_trading_spec'))
assert all(g['CONFIGURATION'][k] is None for k in ('active_factor','active_model','active_trading_rules'))
assert all(workflow[k] is None for k in ('active_factor','active_model','active_trading_rules'))
assert research['final_evaluation']['execution_enabled'] is False and research['final_evaluation']['independent_executor_configured'] is False
stages=[
 {'stage':0,'name':'规范、审计及预算骨架','static_implementation':'implemented_offline_components','acceptance_boundary':'既有固定版本阶段0离线范围保留；本矩阵不作新软件验收。',
  'implemented':['StudySpec和交易/模型/标签/数据组成身份；AuditEvidence及原始引用验证。','唯一配置入口、生成配置/源码与执行身份；不可变配置、事件链预算登记。'],
  'missing_or_unverified':['合同形状与hash不认证真实数据覆盖、经济机制、远程来源或真实执行。','运行软件最终66提交的独立边界结论由主审报告给出。'],
  'references':[cfg('development','"id": 0'),code('study','StudySpec'),code('study','AuditEvidence'),code('audits','verify_evidence'),code('registry','Registry'),ref('tools/stages.py',declaration='verify')]},
 {'stage':1,'name':'受限因子、标签与固定模型','static_implementation':'implemented_offline_components','acceptance_boundary':'既有阶段1离线范围保留；无已登记经济因子或已选生产模型。',
  'implemented':['受限JSON表达式及有限窗口、因果数据窗口、逐日历史成员约束。','实际进出场/费用/现金分配的多头完整往返标签及成熟时点。','identity/ridge固定模型、训练统计和版本化模型工件。'],
  'missing_or_unverified':['当前字段白名单为空，FactorSpec/ModelSpec/TradingSpec均未激活。','标签不支持部分成交、空头、非现金公司行动或通用组合账本。','既有精度验收不等于所有近零值都有统一相对精度保证。'],
  'references':[cfg('development','"id": 1'),code('factors','FactorSpec'),ref('cloud/qresearch/factors.py','OPERATORS ='),code('point_in_time','causal_window'),code('labels','build_execution_labels'),code('models','ModelSpec'),code('models','FrozenModel')]},
 {'stage':2,'name':'QuantConnect数据、任务与恢复','static_implementation':'implemented_bridges_and_new_candidate_not_full_stage_accepted','acceptance_boundary':'旧81f软件通过范围保留；新66候选正在主审。旧LEAN已取得原生RuntimeError并失败结算，不能记运行成功。',
  'implemented':['共享缓存、交易日历、批量History、历史快照/采集/永久SID及覆盖合同。','同父Research→LEAN、原生提交/终态/拒绝适配和原attempt恢复。','本轮新增部署身份预检与安全逐文件诊断；已有真实原件在旧81镜像12→13→13失败重放。'],
  'missing_or_unverified':['新66候选未真实部署/运行成功；实际原生编译拒绝、Research原生运行异常专用解析及真实失败回执仍缺。','完整历史US200、分类、财务原报/修订vintage、公开/供应商送达/历史摄入和未观察公司行动认证缺失。','read_project返回源码投影不等于worker文件，import插入演示为合成机制；具体运行差异文件及原故障消除均未证明。'],
  'references':[cfg('development','"id": 2'),code('cache','SharedDataCache'),code('quantconnect','QuantConnectHistoryProvider'),code('historical_source','QuantConnectSnapshotSource'),code('collection','HistoricalSnapshotCollector'),code('engineering_tasks','EngineeringTaskBridge'),ref('audit/stage2_terminal_reconciliation.json','"registry_status"'),ref('audit/stage2_deployment_root_cause.json','"runtime_transform_root_cause_proven"'),ref('docs/stage2-next.md','Research原生执行异常')]},
 {'stage':3,'name':'Research六轮评价','static_implementation':'partial_generic_evaluation_core','acceptance_boundary':'阶段3未验收，当前不能开展正式市场因子研究。',
  'implemented':['固定8年训练+1年验证的六轮滚动、成熟标签/边界剔除、训练期拟合。','注册Study匹配因子/模型/标签/交易/数据计划，IC摘要和候选/基线共同样本及相关计算。'],
  'missing_or_unverified':['未注册生产因子、模型、交易规范或合格真实数据审计批准。','没有候选真实Research报告、完整市场指标独立复算或净组合增量证据。'],
  'references':[cfg('development','"id": 3'),code('evaluation','six_rolling_folds'),code('evaluation','walk_forward_evaluate'),code('pipeline','evaluate_registered_study'),code('runtime','ResearchEngine._authorize'),cfg('research','"active_factor_spec"')]},
 {'stage':4,'name':'组合、成交、成本与风险','static_implementation':'contracts_and_engineering_receiver_only','acceptance_boundary':'阶段4未验收；零订单工程接收器和单笔标签不是完整交易系统。',
  'implemented':['显式成本/成交/风险合同校验和实际往返标签。','工程接收器禁止订单事件，主机无任务时退出并提示交易adapter未登记。'],
  'missing_or_unverified':['通用LEAN组合交易adapter、组合账本、完整成交/成本/风险规则和Study生产绑定缺失。','Research/LEAN真实因子→信号→订单→持仓对账、净值/成本复核、压力测试及组合增量未验收。','本次旧LEAN在初始化失败，原生返回没有订单统计，不能推断真实订单数为0。'],
  'references':[cfg('development','"id": 4'),code('study','validate_trading_spec'),ref('templates/trading_spec.json','"capital"'),ref('templates/trading_spec.json','"orders_enabled"'),ref('cloud/main.py','Trading adapter is not registered'),ref('cloud/main.py','Orders are forbidden'),ref('audit/stage2_terminal_reconciliation.json','"orders_count"')]},
 {'stage':5,'name':'有界GPT闭环与持久调度','static_implementation':'persistent_program_controller_only','acceptance_boundary':'阶段5未验收，自动GPT关闭；provider=GPT不代表模型或API已配置。',
  'implemented':['WorkflowController可登记、审计、预算、提交/等待、判定、修复上限、归档和冻结；外部adapter注入。','受限规范/字段/算子和固定审计合同可以校验提案，但LLM不能提供审批布尔位。'],
  'missing_or_unverified':['当前GPT模型/调用数/花费额度均null，未见启用的GPT客户端及端到端自动提案研究闭环。','开发记忆、持续真实平台调度、受限自动修复全过程尚无独立验收。'],
  'references':[cfg('development','"id": 5'),cfg('development','"llm_runtime_enabled"'),cfg('development','"llm_provider"'),cfg('development','"llm_model"'),code('workflow','WorkflowController'),ref('cloud/qresearch/study.py','never from an LLM proposal')]},
 {'stage':6,'name':'受限搜索、消融与选择偏差','static_implementation':'partial_similarity_and_correlation_primitives','acceptance_boundary':'阶段6未验收；未开展本轮正式经济因子搜索。',
  'implemented':['因子结构相似度与逐对Pearson/Spearman相关工具。','研究章程要求先固定模型研究因子，再固定因子研究模型，并记录全部试验。'],
  'missing_or_unverified':['没有已登记的实际比较矩阵、模型/因子搜索、消融结果、验证复用计量或选择偏差结论。','净组合增量和成本压力依赖阶段4，尚无真实金融证据。'],
  'references':[cfg('development','"id": 6'),code('factors','structure_similarity'),code('evaluation','pairwise_factor_correlations'),ref('docs/research_charter.md','先固定模型研究因子'),cfg('workflow','"execution_prerequisites"')]},
 {'stage':7,'name':'冻结、独立最终执行与前向监控','static_implementation':'freeze_metadata_skeleton_only','acceptance_boundary':'阶段7未验收；最终测试、前向交易和自动监控回滚未开放。',
  'implemented':['冻结开发归档的元数据包，但明确final_execution_enabled=false且要求独立执行器。','最终年度重估/截止退出/不反馈研究的计划字段与测试区间访问保护。'],
  'missing_or_unverified':['独立最终执行器未配置、完整发布/前向模拟/监控及回滚未验收。','2024–2025已有研究暴露；2026独立性待审核，整个最终区间不能称untouched holdout。'],
  'references':[cfg('development','"id": 7'),code('workflow','WorkflowController.freeze'),cfg('research','"independent_executor_configured"'),cfg('research','"execution_enabled"'),code('contracts','PITWindow'),ref('audit/data_exposure.json','"whole_window_uncontaminated"')]},
]
control_refs=[cfg('development','"market_research_enabled"'),cfg('development','"llm_runtime_enabled"'),cfg('development','"final_test_enabled"'),cfg('development','"live_trading_enabled"'),cfg('research','"active_factor_spec"'),cfg('research','"active_model_spec"'),cfg('research','"active_trading_spec"'),cfg('workflow','"orders_enabled"'),cfg('quantconnect','"backtest_submission_enabled"'),cfg('budget','"final_evaluation_execution_enabled"'),cfg('data','"end_exclusive"'),cfg('data','"factor_field_whitelist"'),cfg('source_catalog','"factor_fields_enabled"'),cfg('source_catalog','"vendor_revision_certified"'),cfg('source_catalog','"actual_availability_certified"'),ref('audit/data_exposure.json','"independent_test_eligible"'),ref('audit/data_exposure.json','"year2026_independence"'),ref('docs/research_charter.md','完整区间含先前研究暴露'),ref('README.md','下文旧版本和旧预算段落按历史记录理解')]
configured=plan['execution'];final=research['final_evaluation']
report={'fixed_commit':SHA,'kind':'static_system_stage0_7_matrix_not_new_software_acceptance','software_methods_executed':0,'software_suites_or_builds':0,'new_platform_calls':0,'production_code_executed':False,
 'identity':ident,'active_configuration':{'id':research['configuration_id'],'status':research['status'],'generated_configuration_hash':g['SOURCE_SHA256'],'active_factor_spec':research['active_factor_spec'],'active_model_spec':research['active_model_spec'],'active_trading_spec':research['active_trading_spec'],'complete_strategy_configurations_frozen':budget['usage']['complete_strategy_configurations_frozen']},
 'stages':stages,'controls':{'declared_execution':configured,'workflow_orders_enabled':workflow['orders_enabled'],'quantconnect_backtest_submission_enabled':qc['backtest_submission_enabled'],'quantconnect_live_deployment_enabled':qc['live_deployment_enabled'],'final_evaluation_execution_enabled':final['execution_enabled'],'independent_final_executor_configured':final['independent_executor_configured'],'budget_final_evaluation_execution_enabled':budget['final_evaluation_execution_enabled'],'scope':'Current declared configuration and actual active study bindings; not certification that arbitrary manual external calls are technically impossible.','references':control_refs},
 'fields_operators_models_trading':{'factor_field_whitelist':data['factor_field_whitelist'],'operator_catalog':data['operator_catalog'],'expression_core':['field','add','subtract','multiply','safe_divide','positive_log','lag','rolling_mean','rolling_std','rolling_corr','rank','zscore'],'operator_scope':'asof_available_join belongs to PIT data preparation; expression core hasfield plus fixed aliases. Catalog does not authorize unrestricted parameter mining.','engineering_source_catalog_fields':len(catalog['fields']),'factor_fields_enabled':catalog['factor_fields_enabled'],'financial_vendor_revision_certified':catalog['vendor_revision_certified'],'actual_availability_certified':catalog['actual_availability_certified'],'model_families_implemented':['identity','ridge'],'active_model':None,'trading_template_status':read('templates/trading_spec.json')['status']},
 'partitions':{'timezone':research['timezone'],'development_end_exclusive':data['development_access']['end_exclusive'],'first_training_start':data['development_access']['first_training_start'],'rolling_type':research['rolling_validation']['type'],'folds':[{k:f[k] for k in ('round','training_start','training_end','validation_start','validation_end')} for f in research['rolling_validation']['folds']],'final_window':{'start':final['start'],'end':final['end'],'execution_enabled':final['execution_enabled']},'annual_final_refit_segments':final['annual_refit_segments'],'final_tail_rule':final['tail_rule'],'no_test_feedback':final['feedback_to_research_for_changes'] is False,'embargo_sessions':research['boundaries']['embargo_sessions'],'embargo_rule':research['boundaries']['embargo_policy'],'warmup_start':data['development_access']['warmup_start'],'warmup_rule':data['development_access']['warmup_policy']},
 'exposure':{'ledger':exposure,'whole_window_untouched_independent_holdout':False,'year2026_independently_certified':False,'qualification':'2026 is unknown/pending independent review, not proven contaminated or proven independent. Deletion does not erase2024–2025 exposure.'},
 'budget':{'authoritative_events':13,'used':{'configurations':6,'research':9,'lean':1},'limits':budget['limits'],'no_refund_on_failure':True,'source_of_fact':'independent13-event replay in evidence_verification.json; config/budget.json is a projection'},
 'global_missing':['current candidate deployment/runtime success and real native rejection/Research-failure evidence','full historical US200/PIT/financial-vintage and actual-availability certification','registered market factor/model/trading design and actual research approvals','generic portfolio execution and accounting/cost/risk parity','enabled GPT adapter/call budget and unattended closed loop','independent final executor and forward monitoring/rollback'],
 'references':refs,'conclusion':'Stage0/1 prior scoped offline acceptance retained; current66 software review remains the parent audit task. Full stage2 and stages3–7, autonomous real factor research, final testing and financial validity are unaccepted.','financial_evidence':False}
report['fields_operators_models_trading']['engineering_source_catalog']=catalog
report['fields_operators_models_trading']['expression_bounds']={'max_window':2520,'max_constant':1e12,'max_nodes':256,'max_depth':32}
report['fields_operators_models_trading']['trading_template']=read('templates/trading_spec.json')
path=O/'system_matrix.json';path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');(O/'system_matrix.json.sha256').write_text(sha(path.read_bytes())+'  system_matrix.json\n',encoding='utf-8')
lines=['固定66ff72ffaaff8c91c008898e6527c91131176c2a 全系统0–7静态矩阵。0软件方法/0套件/0构建/0平台调用；只读源、JSON和AST，无新验收。',
 '当前通用配置GENERIC-WF-001，配置hash '+g['SOURCE_SHA256']+'；active factor/model/trading均null，完整策略冻结数0。',
 '正式研究/自动GPT/最终测试/交易均false；GPT provider已声明，model/call_limit/spend_limit均null；字段白名单空，source_catalog15字段只作工程观察，财务版本和实际可用时点未认证。','']
for row in stages:
 lines.append(str(row['stage'])+' '+row['name']+'：'+row['acceptance_boundary']);lines.append('已实现：'+'；'.join(row['implemented']));lines.append('缺口：'+'；'.join(row['missing_or_unverified']));lines.append('证据：'+'，'.join(row['references']));lines.append('')
lines.extend(['时间：纽约时区；2010–2017→2018、2011–2018→2019、2012–2019→2020、2013–2020→2021、2014–2021→2022、2015–2022→2023；每轮固定8年，不是扩展窗。开发事件/可用性严格早于2024。',
 '最终计划2024-01-01至2026-10-23，年度拟合2016–23→2024、2017–24→2025、2018–25→2026截止；最终标签必须实际退出于截止日前。执行关闭，独立执行器未配置，warmup/embargo须按冻结因子/标签派生，不能偷用旧固定20期。',
 '2024–25曾作研究筛选/方向决策，整最终窗口非未触碰独立样本；2026独立性待核验。删除旧文件不消除暴露；2016、2020公司行动、2018双股还有技术夹具暴露记录。',
 '13事件预算仍配置6/12、Research9/20、LEAN1/16；旧LEAN真实初始化RuntimeError失败不退款，不证明订单0、数据成功或具体worker源码原因。',
 'source '+ident['review_hash']+'；execution '+ident['execution_hash']+'；impl '+ident['implementation_hash']+'；deployment '+ident['local_deployment_hash']+'。',
 '以下每项为固定源码精确行与整文件raw SHA256，JSON还给出函数结束行/首行摘录：'])
for key,v in refs.items():lines.append(key+'  '+v['raw_sha256'])
lines.extend(['','结论：既有阶段0/1限定离线范围保留；阶段2新候选由主审继续独立审核，整个阶段2和阶段3–7未验收，系统不能无人值守开展真实因子研究。financial_evidence=false。'])
(O/'system_matrix.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(json.dumps({'matrix_written':True,'stage_count':len(stages),'reference_count':len(refs),'JSON_raw_sha256':sha(path.read_bytes()),'software_methods_executed':0},ensure_ascii=False,indent=2))
