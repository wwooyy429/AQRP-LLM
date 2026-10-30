from pathlib import Path
import copy,json
R=Path(__file__).parent;O=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-ccad61d-20261027')
def load(p):return json.loads((R/p).read_text(encoding='utf-8-sig'))
def save(p,d):(R/p).write_bytes((json.dumps(d,ensure_ascii=False,indent=2)+'\n').encode())
C='44676db609b3b7c2175fa7fa4f19c8ccf8165458';B='ccad61d03ccf17bf2bdc2d7ffc88dfd11b6d3ca6'
D=json.loads((O/'formal_report.json').read_bytes());A=load('archive_agent/report.json');T=load('root_test_execution_summary.json');P=load('protocol_agent/report.json');Q=load('cert_agent/qualification_first_results.json');M=load('archive_agent/wr27_report.json')
assert T['all_pass'] and Q['methods']==Q['passed_methods']==9 and Q['scenario_checks']==47 and Q['failed_methods']==Q['error_methods']==0
assert M['groups_passed']==M['metadata_check_groups']==9 and M['adapted_MRE_positive_exit']==0
assert P['publication_concurrency']['success'] and P['WR21']['outer_exit']==0 and P['original_WR23']['outer_exit']==0
assert all(t['success']for t in P['historical_regressions'])
assert load('build_execution.json')['all_copy_bytes_unchanged'] and load('root_repair_confirmation/execution.json')['exit_code']==0 and load('root_wr27_confirmation_execution.json')['exit_code']==0
D.update(review_id='AQRP-20261027-44676DB-WINDOWS-20',verdict='WR25/26/27修复后通过，本轮已测离线软件范围通过，未发现新增已复现软件问题；阶段2整体仍待真实运行与数据认证。',reviewed_source_commit=C,baseline_commit=B)
D['evidence_commits']['current_archive']=C
for k in ['source_manifest_hash','execution_source_manifest_hash','deployment_hash','implementation_hash']:D[k]=A[k]
D['economic_configuration_hash']=A['active_economic_configuration_hash'];D['source_counts']={'raw_Git':5433,'review_manifest':145,'local_deployment':31,'source_changes':6}
D['environment']=load('environment.json');D['PR'].update(head=C,CI_run=40525429449,CI_jobs=[122263592253,122263592465])
S=D['stage_results'];S[0].update(implementation='已有骨架和固定程序；配置、来源、预算及目标目录哈希一致',evidence='668仓库、独立回归、67静态校验及跨目录专项',gaps=[],status='已测离线范围通过')
S[2].update(implementation='主体实现；WR25/26/27修补及原回归通过',evidence='实际生产函数合成链、进程并发、原生回执离线解析；本候选未上云',blocking=[],status='已测离线软件范围通过；阶段整体待验收')
tests=[dict(suite='repository',**T['repository'])]+T['legacy_16_suites']+T['additional_root_suites']
for label,m,s in [('WR20 original',13,43),('WR22 previous boundaries',9,23),('WR25 WR26 previous boundaries',9,29),('new qualification boundaries',9,47)]:tests.append(dict(suite=label,methods=m,passed=m,failed=0,errors=0,skipped=0,scenario_checks=s,subcases=None,actually_executed=True))
for label,m,n in [('WR23 publication and concurrency',5,21),('native LEAN',6,62),('completion compatibility',3,28),('engineering recovery legal fixture',5,46),('native Research failure',6,91)]:tests.append(dict(suite=label,methods=m,passed=m,failed=0,errors=0,skipped=0,subcases=n,actually_executed=True))
assert all(t['failed']==t['errors']==t['skipped']==0 for t in tests)
D['tests']=tests
D['actually_executed']={
 'root_regression_processes':26,'root_build':{'command':'python -B tools/research.py build','exit':0,'all_copy_bytes_unchanged':True,'record':'build_execution.json'},
 'records':['runs/execution_records.json','regression_execution_records.json','control_replay/execution_records.json','cert_agent/original_replay_index.json','cert_agent/qualification_execution.json','protocol_agent/execution_records.json','protocol_agent/outer_execution_records.json','protocol_agent/script_bindings.json','archive_agent/execution_summary.json'],
 'entry_publication':{'methods':5,'scenarios':21,'custom_check_calls':281,'ordinary_CLI':180,'concurrent_CLI':16,'synthetic_finish':27,'worker':0,'plan_versions':[1,2],'processes_per_prepare_race':4,'processes_per_dispatch_race':4,'only_one_permission_each':True},
 'legacy_native_manual_chains':8,'native_recovery_actual_CLI':193,'native_recovery_direct_processes':12,'native_recovery_synthetic_finish':18,'native_Research_failure_CLI':25,
 'original_WR23_candidate':{'exit':0,'CLI':5,'synthetic_finish':1},'WR21_recognized_legacy_fixture':{'exit':0,'CLI':17,'assertions_unchanged':True},
 'static_source_archive':{'checks':67,'passed':67,'unit_methods':0},
 'metadata':{'check_groups':9,'passed':9,'negative_target_CLI_scenarios':7,'child_metadata_CLI':14,'root_confirmation_CLI':3,'unit_methods':0},
 'original_WR25_WR26_7case_MRE':{'ccad_exit':1,'candidate_exit':0,'root_repeat_exit':0,'original_bytes_unchanged':True,'script_sha256':'b31690726e1e34a763cc7f3de779d08bd85f70ff716f550bff6846b62b56c1cf'},
 'previous_9method_29scenario_negative':{'ccad_methods':9,'ccad_passed':7,'ccad_failed':2,'ccad_failure_records':5,'candidate_passed':9},
 'WR27_MRE':{'ccad_exit':1,'original_candidate_scope_exit':1,'original_candidate_product_CLI':0,'only_version_constants_adapted':True,'adapted_candidate_exit':0,'root_repeat_exit':0,'default_exit':0,'foreign_hash_exit':1,'correct_target_hash_exit':0},
 'counts_are_overlapping_not_unique':True,
 'first_results_preserved':[{'scope':'WR27 unchanged original version scope','reason':'原脚本固定ea/ccad常量，新候选先在旧baseline断言失败，产品CLI运行0；原始stderr保留。仅C/B两常量适配，原预期/断言不变后通过。','records':'archive_agent/wr27_scope_adapter.json'},
 {'scope':'old negative evidence','reason':'原7场景MRE与旧9/29套件在ccad负控仍失败；当前原字节及断言通过。旧失败未覆盖或删除。'},
 {'scope':'recognized prior fixture adapters','reason':'沿用已认可adapted56、e513旧pending、Collection13事件/9Research、native/recovery合法绑定和WR21明确历史四字段前置；实际17事件与停止门不变。旧脚本内literal SHA及静态目标标签只保留历史出处，当前执行身份由新source argv、外层记录及脚本hash绑定。'},
 {'scope':'developer publication first error','reason':'开发暂存Git index为非UTF8二进制，首次打包解码失败及省略纠正记录真实；原件仍在忽略工作目录，740565bytes/rawhash独立匹配。不是生产或独立测试失败。'}]}
D['findings']=[];save('findings.json',[])
D['budget_replay'].pop('raw_equal_ea',None);D['budget_replay']['raw_equal_ccad']=True
D['platform_evidence_level']='本轮独立离线源码/合成执行及既有平台原生证据重解析；无本轮QC访问。GitHub/CI为本轮独立只读。'
D['archive_validation']={'prior_ZIP_bytes':39319686,'prior_ZIP_sha256':'2ffc9089ad19a5675d18cafb5379262db7c99a431e518ae4f52cb2dd094b313c','prior_manifest_entries':15119,'selected_original_files':381,'selected_bytes':1581651,'omitted_original_files':14739,'old_Git_archive_files_unchanged':4745,'developer_manifest_entries_verified':61,'omitted_binary_original_independently_read':True,'omitted_binary_bytes':740565,'omitted_binary_raw_sha256':'2ff2e0dab64f5a800a5ea8d56029f93e36f0de4be9b8970ac99686aa30e3843f'}
D['historical_findings']={'WR01_WR24':'保持各固定SHA及有限范围结论；本轮相关既有回归通过，未扩大为阶段整体通过。','WR25':'旧未知分类+全缺路径在ccad复现；当前原7场景/9方法29场景及新增资格组合修复后通过。','WR26':'旧future/missing current路径在ccad复现；当前未知保留、明确排除及未来库存隔离范围修复后通过。','WR27':'原跨root问题ccad负控确认；仅测试版本常量适配后新版本默认/绝对/相对/同root拒绝范围修复后通过。','new_blocking':[],'new_nonblocking':[]}
D['unverified']=['新版真实Research→缓存→LEAN成功联合链','旧worker具体源码差异及源迭代底层原因','完整历史US200、财务版本、实际送达/摄入认证','阶段3–7完整实现、真实运行与金融效果','其他OS独立执行及OS kill/断电持久性','2026独立性；2024–2025已暴露']
D['software_acceptance']={'original_fix_scope':'WR25/26/27修复后通过','overall_status':'本轮已测离线软件范围通过','blocking':[],'nonblocking':[],'full_phase2_accepted':False,'runtime_and_data_acceptance':'待验收，证据不足'}
D['data_certification'].update(status='观测审计已测软件范围通过；真实数据认证证据不足',observed_input_audit_software_passed=True)
D['reproduction']={'WR25_WR26':'python -B minimal_wr25_wr26.py --source <fixed-source> --output <fresh.json>；原7场景，旧ccad退出1，新446退出0；正常API原创合成夹具。','WR27':'python -B archive_agent/adapted_minimal_wr27.py --source <fixed-source> --git-repository <local-Git> --output <fresh-dir>；新版本默认0/错误S哈希1/正确T哈希0，MRE退出0；原失败和仅版本常量适配保留。','offline':'在新完整可写副本运行 python -B tools/research.py build 和 python -B tools/stages.py verify，禁止向sealed包写输出。'}
save('formal_report.json',D);save('test_execution_summary.json',{'source_commit':C,'tests':tests,'actually_executed':D['actually_executed']})
text=[D['verdict'],'审核SHA：'+C,'失败基线：'+B,'证据：'+D['platform_evidence_level'],'\n全系统覆盖：']
for s in S:text.append(f"阶段{s['stage']}｜{s['modules']}｜{s['implementation']}｜{s['evidence']}｜{s['status']}；缺口：{'、'.join(s['gaps'])or'已测范围未见新增阻断'}")
text+=['\n当前发现：无新增已复现软件问题。原WR25/26/27限本次原触发及注明相邻边界修复后通过，不认证无缺陷或真实平台可用。','\n实际执行（不计独有总数）：']
for t in tests:text.append(f"{t['suite']}：{t['passed']}/{t['methods']}方法；失败{t['failed']}、错误{t['errors']}、跳过{t['skipped']}；子例{t.get('subcases')}；场景{t.get('scenario_checks')}")
text+=['\n首次结果/适配：']+[x['scope']+'：'+x['reason']for x in D['actually_executed']['first_results_preserved']]
text+=['\n来源/预算：5433Git原文件、145review、31部署、6源码变更一致；build完整副本字节不变。17事件与ccad原字节一致，7配置/10Research/1LEAN，工程2/2/1停止，本轮无新增真实调用或扣费，不退款。','本轮当前QC0，旧云端仅归档重解析。实际source仍7fc，Research归档CollectionError、旧LEAN归档初始化源码不符失败，底层原因及worker差异未知；无新版成功联合链或数据认证。history API次数、接收行数、订单、金融统计null。','正式研究/自动GPT/交易/最终测试关闭。2024–2025已暴露，2026独立性未知；financial_evidence=false。','\n后续缺失证据：'+ '；'.join(D['unverified']), '由有权执行者处理工程停止条件和真实联调/数据证据，本次复验不授权新增执行或扩大限额。','\n完整机器报告：',json.dumps(D,ensure_ascii=False,indent=2)]
(R/'formal_report.txt').write_bytes(('\n'.join(text)+'\n').encode())
print(json.dumps({'json_bytes':(R/'formal_report.json').stat().st_size,'tests_rows':len(tests),'new_findings':0,'software_scope':'passed','phase2':'pending'}))
