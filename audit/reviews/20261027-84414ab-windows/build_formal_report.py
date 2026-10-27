from pathlib import Path
import importlib.metadata,json,platform,sys
R=Path(__file__).parent
def read(n):return json.loads((R/n).read_text(encoding='utf-8-sig'))
def write(n,d):(R/n).write_bytes((json.dumps(d,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
SHA='84414ab49c39e25cb50ece1c1debeefa3993c874';BASE='81fbe5294055423e88ee5aeae48ca6223e7971da'
i=read('identity_agent/identity_checks.json');e=read('evidence_agent/metadata_verification.json');c=read('comparison_agent/results.json')
new=i['identities']['candidate844'];old=i['identities']['baseline81']
assert i['passed_checks']==148 and i['failed_checks']==0 and i['protected_unique_files']==115
assert e['passed_checks']==591 and e['failed_checks']==0 and c['passed_checks']==37 and c['failed_checks']==0
assert new['implementation_hash']==old['implementation_hash'] and new['deployment_hash']==old['deployment_hash']
env={'platform':platform.platform(),'python':platform.python_version(),'executable':sys.executable,
 'dependencies':{n:importlib.metadata.version(n)for n in ['numpy','pandas','python-dateutil','pytz','six','tzdata']},
 'execution_kind':'metadata/hash/JSON/identity functions only; no software suite or build'}
write('environment.json',env)
stage_rows=[
 [0,'规范、StudySpec/AuditEvidence、身份及预算','保留既有离线范围','115保护文件原字节保持，未重跑软件'],
 [1,'受限因子、执行标签、模型协议及数值','保留既有离线范围','计算及测试代码与81相同，原软件结论保持'],
 [2,'QC桥、缓存、快照、联合任务及恢复','保留81已测离线通过；整体验收待定','WR19元数据更正通过；缺真实运行/终态/认证'],
 [3,'固定模型、六轮滚动及Research报告','未验收','部分实现，无新增金融/平台证据'],
 [4,'LEAN交易、成本/成交/风险及一致性','未验收','部分实现，无新增真实交易验收'],
 [5,'GPT提案、持久调度及修复','未验收','模型与调用额度未配置，自动调用关闭'],
 [6,'受限搜索、相似度及消融','未验收','未开展正式市场搜索'],
 [7,'冻结、独立最终执行器及监控','未验收','最终测试关闭']]
D={'review_id':'AQRP-20261027-84414AB-METADATA-15','review_date':'2026-10-27','reviewer':'GPT Work / Codex 独立审核',
 'review_kind':'WR19 metadata correction only','reviewed_source_commit':SHA,'baseline_commit':BASE,
 'software_acceptance_bound_to_commit':BASE,'evidence_commits':[SHA,BASE,'ae2b8985f3799c246e90341370f86d80483f63ed'],
 'source_manifest_hash':new['source_manifest_hash'],'source_manifest_files':123,'Git_archive_files':2890,
 'execution_manifest_hash':new['execution_manifest_hash'],'deployment_hash':new['deployment_hash'],
 'implementation_hash':new['implementation_hash'],'active_configuration_hash':new['active_configuration_hash'],
 'environment':env,'tool_capabilities':{'GitHub':'已只读核对PR2与本提交CI job元数据，仍草稿未合并',
 'local':'固定Git导出、原字节/归档/JSON/引用哈希/身份函数/元数据MRE与负例',
 'QuantConnect':'本轮未访问QC，不读旧回测状态/结果/日志，不编译/更新/派发'},
 'stage_results':[dict(stage=n,modules=m,acceptance=s,evidence=p)for n,m,s,p in stage_rows],
 'tests':{'actually_executed':True,'software_unit_methods':0,'software_subcases':0,'software_suite_runs':0,'builds':0,
 'metadata_check_groups':[{'name':'identity_and_runtime_scope','checks':148,'passed':148,'failed':0},
 {'name':'comparison_and_negative_variants','checks':37,'passed':37,'failed':0},
 {'name':'archive_provenance_budget','checks':591,'passed':591,'failed':0}],
 'group_counting':'分组存在重复核对，不声称三组相加是独有检查。元数据检查/子进程不算软件测试方法。',
 'original_MRE':{'script_sha256':'4e65b60ae1621b8fd158b945d147118b733d27913600031663f824564ce48c6d',
 'original_bytes_unchanged':True,'baseline_exit':1,'baseline_declared':12,'baseline_computed':13,
 'candidate_exit':0,'candidate_declared':13,'candidate_computed':13},
 'developer_verifier':{'candidate_exit':0,'independent_negative_variants':7,'each_negative_exit':1,
 'rejects':['escaping_reference','candidate_commit_mismatch','reference_hash_mismatch','count12','raw_reference_tamper','path_list_mismatch','duplicate_reference_path'],
 'scope':'只核对所引用比较，不认证任意readiness字段或远程来源'},
 'reviewer_first_measurement':{'checks':590,'passed':589,'overstrict_reader_assertions':1,
 'reason':'误要求当前deployment_comparison_scope说明逐字节不变；该说明合理澄清ae13，原历史dc49及d0细表原字节未变。',
 'correction':'保留首脚本/原报告/raw，按历史范围及原档案保存核对；补充d0细表核验后591项通过。','product_failure':False},
 'previous_software_evidence':{'commit':BASE,'repository_methods':453,'independently_rerun_this_round':False,
 'WR18':'81fbe52修复后通过结论保持','developer_current453_output':'只作开发归档核对，不称本轮独立453运行'},
 'commands':[{'cwd':str(R),'command':'python -B run_metadata_probes.py','exit_code':0},
 {'cwd':str(R),'command':'python -B metadata_replay/original_minimal_wr19.py source','exit_code':0},
 {'cwd':str(R),'command':'python -B source/audit/review_packages/wr19/verify_archived_comparison.py source','exit_code':0}],
 'command_records':['metadata_replay/execution_records.json','identity_agent/command_log.json','comparison_agent/command_log.json',
 'comparison_agent/execution.json','evidence_agent/corrected_execution_record.json']},
 'actually_executed':True,'findings':[],
 'WR19_acceptance':{'status':'元数据更正通过','compared_candidate_commit':'ae2b8985f3799c246e90341370f86d80483f63ed',
 'candidate_paths':29,'known_reference_paths':25,'same_hash':16,'different_hash':9,'not_in_reference':4,'total_different_or_outside':13,
 'candidate_manifest_raw_sha256':'5b0a0a698b005d8ba1bdf378935cefa82809786b83650e340d6fb44f4fe22bdb',
 'archived_platform_comparison_raw_sha256':'1f946c026a3c24999be0a60ccea9f0cc748dbca62b231d09deaf41bbcedbad46',
 'original_claim12_preserved':True,'original81_readiness_raw_preserved':True,'historical_dc49_8_plus4_equal12_preserved':True,
 'scope':'归档29候选路径与25已知参考的比较；4不在参考不证明实际云端缺4，不认证当前平台或全集。'},
 'runtime_identity_check':{'protected_unique_files':115,'all_raw_equal_baseline':True,'runtime_semantic_changes_detected':0,
 'implementation_deployment_active_config_unchanged':True,'source_and_execution_manifest_changed':True,
 'changed_manifest_paths':i['source_manifest_changed_paths'],
 'reason':'文档及.gitattributes参与清单，因此新SHA的source/execution身份改变；身份算法未变。新派发仍须绑定当前身份，不从软件通过推导派发许可。'},
 'historical_findings':{'WR01_to_WR18':'既有固定版本实际范围通过结论保持；软件通过身份固定81fbe52',
 'WR19':'本轮更正通过，原错误12、完整81 Git状态及旧报告保留',
 'preserved_evidence':'2202旧证据、22开发原件、487原独立原件及27引用、4754项原最终封包/ZIP核验；引用数不是原生回执数'},
 'budget_replay':dict(e['budget'],new_real_charges={'configurations':0,'research':0,'lean':0,'model_API':0},
 engineering_stop_limits={'configurations':2,'research':2,'lean':2},engineering_used={'configurations':1,'research':1,'lean':1}),
 'platform_evidence_level':{'current_round':'无新增平台读取/部署/Research/LEAN/原生回执证据',
 'historical_only':'前轮25实现及1输入已知路径核对；当时列表18py漏8可读路径，全集未认证',
 'current_cloud_source_commit':None,'current_cloud_deployment_hash':None,'candidate_runtime_verified':False,
 'full_cloud_inventory_certified':False,'real_native_failure_receipt_verified':False},
 'backtest_terminal':{'project_id':38436695,'backtest_id':'39cafa1e9b11f91b27e396b66d033a6d','last_archived_status':'pending',
 'current_platform_status':None,'completed':None,'failed':None,'status_results_logs_read':False},
 'CI':{'run_id':40452157673,'commit':SHA,'status':'completed','conclusion':'success',
 'jobs':[{'id':122017145376,'python':'3.10','conclusion':'success','tests_count':None},
 {'id':122017145076,'python':'3.11','conclusion':'success','tests_count':None}],
 'scope':'只读job元数据，不是本轮独立双版本453测试'},
 'data_exposure':{'2024_2025_prior_research_exposure':True,'2026_independence_certified':None},
 'execution_switches':{'market_research':False,'automatic_GPT':False,'final_test':False,'live_trading':False,
 'GPT_model':None,'GPT_call_limit':None,'GPT_spend_limit_USD':None},
 'unverified':['旧LEAN原生终态及原attempt结算','新候选真实部署/输入读回/Research/LEAN及成功失败原生回执',
 '云端全集、完整历史US200/PIT分类/永久SID/20交易日排名','财务原报/修订版本及真实公开、供应商送达、历史摄入时点',
 '迁移后实际数据分支及未观察公司行动','真实金融一致性、成本/成交/风险、组合增量；阶段3–7及最终测试'],
 'next_actions':['保留软件结论与81fbe52绑定，后续新派发按当前执行身份冻结并遵守原预算/占用保护',
 '取得旧LEAN原生终态并按原attempt结算，之后再处理新云端运行',
 '真实有界运行/原生回执与完整数据认证分别验收；最终测试继续关闭'],
 'software_acceptance':'retained_81fbe52_scope; no_new_software_test_or_approval_at84414ab',
 'metadata_acceptance':'WR19_passed_at84414ab','data_certification':False,'financial_evidence':False,
 'artifact_directory':'review-84414ab-20261027'}
write('formal_report.json',D)
(R/'formal_report.txt').write_bytes(('''84414ab WR19元数据独立局部核对通过，无新增发现；软件通过结论仍固定81fbe52，不扩大阶段2或完整系统验收。
固定元数据SHA：'''+SHA+'''
原WR19 MRE原字节：旧81声明12/计算13退出1；新844声明13/计算13退出0。开发只读verifier当前0，7独立负例预期拒绝；归档ae候选29份中16同哈希，9不同+4参考外=13。来源候选ae、两引用原字节hash及全部路径一致。原错误12及整个81 readiness Git原字节保留，历史dc49=8+4=12及原档案/历史d0细表未改。4参考外不证明当前云端缺4或全集。
本轮0软件测试方法/0子例/0suite/0build/0QC，未重跑453或旧软件套件。148身份/作用范围、37比较/负例、591归档/预算分组元数据检查均通过，分组有重叠不称独有总数。首归档590中1条过严阅读断言及修正/raw均保留，非产品错误。
2890源raw等固定Git；115受保护文件原字节等81，运行逻辑变化0。实现07ba5c...、部署25d3c8...、配置272e24...不变；源码3d6a236f...及执行432d7f42...因attributes/wr18/wr19三路径改变，不能说所有哈希不变。新派发仍要绑定当前执行身份，软件通过不授派发许可。
22开发原件、487旧独立原件/27引用、2202旧证据和4754旧最终artifact/ZIP逐项核对。开发453及Git导出输出只是开发归档证据，CI3.10/3.11 job元数据成功不当作本轮独立双版本运行。
12事件独立重放仍配置6/12、Research9/20、LEAN1/16，工程各用1/2；新真实执行/模型/部署/扣费0。旧LEAN39cafa...完成/失败未知，归档pending不等当前仍运行；未查状态/结果/日志。
阶段0/1既有范围保留；阶段2已测软件范围保持81通过，完整仍缺终态/新真实运行/原生成功失败及US200/财务时点等认证；阶段3–7未验收。2024–25暴露、2026独立性未知保留，正式研究/自动GPT/最终测试/交易关闭，financial_evidence=false。
独立便携核对：python -B metadata_replay/original_minimal_wr19.py source（844退出0）；改source为baselines/81fbe52/source（退出1）。开发工具：python -B source/audit/review_packages/wr19/verify_archived_comparison.py source（0）。完整环境/命令/矩阵/预算/身份/缺口见formal_report.json。本轮只交付审核，不修改/批准/合并开发成果。
''').encode('utf-8'))
print(json.dumps({'review_id':D['review_id'],'WR19':'passed_metadata_correction','findings':0,'software_methods':0,'json_bytes':(R/'formal_report.json').stat().st_size},ensure_ascii=False))
