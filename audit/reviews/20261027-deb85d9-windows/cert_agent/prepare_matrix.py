from pathlib import Path
O=Path(__file__).resolve().parent
old=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-66ff72f-20261027\evidence_agent\build_system_matrix.py').read_text(encoding='utf-8-sig')
code=old.replace('66ff72ffaaff8c91c008898e6527c91131176c2a','deb85d9f27441b275ab8b108f0232ecd2707a1e8')
code=code.replace("ident=json.loads((O/'evidence_verification.json').read_text(encoding='utf-8'))['source']", "parent_identity=json.loads((R/'source_evidence_verification.json').read_text(encoding='utf-8-sig')); ident={'raw_files':parent_identity['raw_git_files'],'review_files':parent_identity['review_source_count'],'review_hash':parent_identity['source_manifest_hash'],'execution_hash':parent_identity['execution_source_manifest_hash'],'local_deployment_hash':parent_identity['deployment_hash'],'implementation_hash':parent_identity['implementation_hash'],'active_configuration_hash':parent_identity['active_configuration_hash']}")
code=code.replace("ref('docs/stage2-next.md','Research原生执行异常')", "ref('audit/review_packages/stage2_completion_runtime/REVIEW_INSTRUCTIONS.md','data_certification')")
override="""
stages[2]['static_implementation']='new_stage2_components_with_WR20_data_observation_failure'
stages[2]['acceptance_boundary']='新deb本地交付未独立通过，数据观测组件存在WR20/P2；真实执行身份为7fc5ef而不是本地deb。新Research实际CollectionError失败，未准入新LEAN。'
stages[2]['implemented'] += ['worker身份诊断/单次读取、Research固定cell入口许可、原生失败绑定与有界数据观测/私有分区重核组件。']
stages[2]['missing_or_unverified'] = ['WR20：上市前liquidity可误填IPO20期，错误observations_passed；这不是vendor/research认证批准，也不是此次真实CollectionError的根因。','实际7fc执行的Research在源取数迭代CollectionError失败，底层cause未提供；没有成功工程报告、没有新LEAN、新版成功云端运行。','旧LEAN具体worker源码差异仍未知；新worker诊断提取能力不等于已取得完整worker或证明旧根因。','有真实原生Research失败及17事件恢复事实，本地失败后2处部署文件变化须按新固定版本独立验收；不能沿用7fc或旧66批准。','完整历史US200、财务原报/修订vintage、实际公开/供应商送达/历史摄入及公司行动认证仍缺。']
stages[2]['references'] += [code('data_certification','audit_data_certification'),code('data_certification','summarize_certification_scope'),ref('tools/data_certification.py',declaration='main'),ref('audit/stage2_completion_round_report.json','"actual_cloud_source_commit"'),ref('audit/stage2_completion_round_report.json','"current_event_count"')]
stages[3]['missing_or_unverified'] += ['分层收益评价尚未实现；数据观测合规报告不能替代真实生产研究批准。']
"""
code=code.replace("configured=plan['execution'];final=research['final_evaluation']",override+"\nconfigured=plan['execution'];final=research['final_evaluation']")
post="""
report['budget']={'authoritative_events':17,'used':{'configurations':7,'research':10,'lean':1},'round_engineering_used':{'configurations':2,'research':2,'lean':1},'limits':budget['limits'],'no_refund_on_failure':True,'configuration_and_research_round_caps_reached':True,'no_automatic_retry':True,'source_of_fact':'parent source_evidence_verification.json and immutable completion_round_report; native_agent independently replays15→17→17; this static matrix did not rewrite or replay authority'}
report['implementation_versions']={'current_local_commit':'deb85d9f27441b275ab8b108f0232ecd2707a1e8','actual_executed_commit':parent_identity['actual_cloud_source_commit'],'current_local_deployment_hash':parent_identity['deployment_hash'],'actual_cloud_deployment_hash':parent_identity['actual_cloud_deployment_hash'],'local_deployment_paths':31,'actual_known_implementation_reference_paths':31,'local_equal_to_executed_reference_paths':29,'local_different_from_executed_reference_paths':[v['path'] for v in parent_identity['cloud_rows'] if v['matches_delivered_controller'] is False],'current_source_inventory_certification':False,'actual_cloud_success':False}
report['data_certification_observed_scope']={'implemented':True,'independently_executed_methods':13,'passed_methods':12,'failed_methods':1,'scenario_checks':43,'failed_scenario_records':2,'finding':'WR20/P2','all_vendor_full_history_research_approval_flags_still_false':True,'actual_historical_source_authentication_supported':False}
report['global_missing']=['WR20 data-observation IPO eligibility fix and independent retest','current local parser/entry fixes acceptance, matching real successful bounded Research/LEAN reports','oldworker actual-byte evidence and root-cause repair','authoritative full historical US200/PIT/financial-vintage and actual-availability evidence','registered production factor/model/trading design and general portfolio engine','enabled bounded GPT closed loop','independent final executor and forward monitoring/rollback']
report['conclusion']='Prior scoped0/1 and old fixed-version conclusions retained. Newdeb data observed-scope component fails WR20/P2; full stage2/system, actual successful runtime, full data/vendor certification and financial validity are unaccepted.'
"""
code=code.replace("report['fields_operators_models_trading']['engineering_source_catalog']=catalog",post+"\nreport['fields_operators_models_trading']['engineering_source_catalog']=catalog")
code=code.replace('13事件预算仍配置6/12、Research9/20、LEAN1/16；旧LEAN真实初始化RuntimeError失败不退款，不证明订单0、数据成功或具体worker源码原因。','17事件预算配置7/12、Research10/20、LEAN1/16；工程本轮2/2/1，配置和Research达停止条件、不自动重试；原旧LEAN失败与本轮7fc Research CollectionError均不退款。未知统计保持null，不证明数据成功或具体worker旧根因。')
code=code.replace('阶段2新候选由主审继续独立审核，整个阶段2和阶段3–7未验收','新deb数据观测组件因WR20失败，其余新范围由主审独立核定，整个阶段2和阶段3–7未验收')
code=code.replace('阶段2新候选由主审继续独立审核','新deb数据观测组件因WR20失败')
code=code.replace('source_catalog15字段只作工程观察','source_catalog字段只作工程观察')
code=code.replace('运行软件最终66提交的独立边界结论由主审报告给出。','本轮deb最终软件验收由主审报告核定；本矩阵不扩大旧66批准。')
code=code.replace('本轮新增部署身份预检与安全逐文件诊断；已有真实原件在旧81镜像12→13→13失败重放。','既有部署身份预检与安全逐文件诊断；前轮旧LEAN原件曾以旧81镜像12→13→13验证失败，不计本轮额外重放。')
code=code.replace("ref('README.md','下文旧版本和旧预算段落按历史记录理解')", "ref('README.md','# AQRP-LLM')")
(O/'build_system_matrix.py').write_text(code,encoding='utf-8')
print('Prepared static current-round matrix generator')
