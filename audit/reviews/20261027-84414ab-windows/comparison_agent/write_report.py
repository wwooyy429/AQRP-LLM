import hashlib,json
from pathlib import Path
OUT=Path(__file__).resolve().parent
result=json.loads((OUT/'results.json').read_text(encoding='utf-8'))
execution=json.loads((OUT/'execution.json').read_text(encoding='utf-8'))
assert result['failed_checks']==0 and execution['exit_code']==0
checks={item['name']:item for item in result['checks']}
report={
 'reviewed_commit':result['commit'],'reviewer':'comparison_agent','verdict':'WR-19元数据更正独立核对通过；未确认新增缺陷。软件通过身份仍为81fbe52，本轮不新增软件运行或阶段2验收。',
 'findings':[],'first_run':{'unit_methods':0,'metadata_checks':37,'passed':37,'failed':0,'first_failure':None,'exit_code':0,
     'reviewer_measurement_corrections':[],'first_outputs_preserved':True},
 'programs_and_commands':{'original_MRE_programs':1,'original_MRE_invocations':2,'developer_verifier_programs':1,
     'developer_verifier_invocations':8,'independent_negative_variants':7,'metadata_subprocess_invocations':10,
     'actual_worker_executions':0,'unit_methods':0,
     'limits':'37 named metadata assertions, standalone programs and subprocess invocations are distinct counts; negative variants deliberately exit1 and are successful refusal checks.'},
 'original_preservation':{
     'MRE_raw_sha256':checks['original_MRE_raw_bytes_preserved']['details']['raw_sha256'],
     'MRE_matches':'root original 81/minimal_wr19.py and candidate review_packages/wr19/original_minimal_wr19.py, exact raw bytes',
     'entire_81_readiness':checks['original_entire_81f_Git_readiness_raw_preserved']['details'],
     'entire_81_readiness_matches':'original_readiness_Git_81fbe52.json equals prior fixed 81f source export and its independent Git-source manifest digest',
     'original_claim_exact_equal':checks['original_erroneous_claim_preserved_exactly']['passed'],
     'historical_dc49_archive':checks['historical_dc49_archive_raw_files_preserved']['details'],
     'historical_dc49_archive_matches':'all189 archived files equal prior81 source archive; original12 and its prior conclusion remain intact'},
 'independent_recomputation':{
     'ae_candidate_commit':'ae2b8985f3799c246e90341370f86d80483f63ed',
     'old_known_runtime_reference_commit':'75f24629d3b7f94ff3aa906c3ce8a2b8b9a8d3c4',
     'candidate_files':29,'known_reference_files':25,'same_hash':16,'different_hash':9,'outside_reference':4,'difference_sum':13,
     'different_paths':result['computed_ae']['different'],'outside_reference_paths':result['computed_ae']['not_in_reference'],
     'per_path_sha256':'results.json:computed_ae.per_path',
     'raw_references':checks['raw_reference_paths_and_hashes_bound']['details'],
     'dc49_preserved_comparison':{'candidate_commit':'dc49f0f3037918f3ce4413665c59b164a8d6e2b7','different':8,'outside_reference':4,'sum':12,
       'per_path_sha256':'results.json:computed_dc49.per_path'}},
 'executed_controls':{'original_MRE_candidate_exit':0,'original_MRE_old81_exit':1,'old81_failure_reason':'declared12 but archived comparison computes13',
     'developer_verifier_candidate_exit':0,'negative_variants':[
       {'name':'scope_escape','mutation':'manifest reference points to same valid raw bytes outside exported fixture root','expected_actual':'ValueError: Comparison reference escapes; exit1'},
       {'name':'candidate_commit','mutation':'summary candidate_commit differs from manifest/comparison','expected_actual':'source identities differ; exit1'},
       {'name':'reference_hash','mutation':'summary raw SHA differs from referenced original bytes','expected_actual':'raw bytes differ; exit1'},
       {'name':'count_12','mutation':'reintroduce original difference total12','expected_actual':'declared comparison differs; exit1'},
       {'name':'tampered_raw','mutation':'append newline to original manifest bytes without refreshing reference digest','expected_actual':'raw bytes differ; exit1'},
       {'name':'wrong_path_list','mutation':'replace known differing path while retaining count','expected_actual':'declared comparison differs; exit1'},
       {'name':'duplicate_known_reference','mutation':'duplicate one known reference and update raw ref digest to remain byte-consistent','expected_actual':'known-reference paths duplicated; exit1'}],
     'negative_no_write_scope':'all three input metadata files for each variant keep their hashes; candidate readiness/verifier/budget/original journal hashes also unchanged'},
 'source_locations':{
     'corrected_current_comparison':'audit/stage2_current_readiness.json:117-155',
     'comparison_scope':'audit/stage2_current_readiness.json:147',
     'preserved_original_claim':'audit/stage2_current_readiness.json:168-192',
     'verifier_reference_scope_hash_identity':'audit/review_packages/wr19/verify_archived_comparison.py:8-24',
     'verifier_duplicate_count_path_checks':'audit/review_packages/wr19/verify_archived_comparison.py:25-42'},
 'tool_scope':'The helper recomputes an archived comparison and explicitly returns archive-only scope. It is not a general readiness-schema validator or current cloud certification tool. No requirement to authenticate arbitrarily rewritten entire audit trees is inferred.',
 'evidence':{'first_stdout':'first.stdout','first_stderr':'first.stderr','first_execution':'execution.json',
     'all_checks_and_recomputation':'results.json','all_child_commands':'command_log.json','per_command_raw_streams':'commands/',
     'independent_mutation_inputs':'cases/','original_MRE':'original_minimal_wr19.py','independent_check_program':'comparison_checks.py'},
 'limits':{
     'no_current_cloud_absence_claim':True,'no_current_inventory_certification':True,'no_current_platform_status_refresh':True,
     'source_software_acceptance_commit':'81fbe5294055423e88ee5aeae48ca6223e7971da','metadata_only':True,'stage2_and_whole_system':'still_unaccepted',
     'actual_provider_or_model_calls':0,'actual_worker_executions':0,'repository_453_or_worker_suites_rerun':False,
     'scope_of_outside_reference':'Four files absent from the archived known25 reference do not prove current cloud absence.'},
 'actions':result['actions']}
(OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'report.md').write_text('''固定提交 `84414ab49c39e25cb50ece1c1debeefa3993c874` 的 WR19 元数据更正通过，未确认新增缺陷。首跑 **37/37 元数据检查通过，0 unittest 方法**；没有测量纠正或未捕获错误。

独立重算 ae 候选29份 Python 文件与旧已知25份参考：16份同哈希、9份不同哈希、4份未记录在参考中，差异合计13。当前摘要的具体路径及逐文件哈希一致；两份引用原始 SHA 均一致。dc49仍为8+4=12，原结论及整套189份历史归档文件逐字节保留。原81f readiness的5933字节文件SHA `c5546b0ca12b7556b727f43e9cc36b348b352cffa92da9d08dcc5cbcd6972095` 与旧固定导出和独立Git清单一致，原错误声明完整保留。

原 `minimal_wr19.py` 原字节SHA `4e65b60ae1621b8fd158b945d147118b733d27913600031663f824564ce48c6d` 重放：新候选退出0、旧81f负对照退出1，原失败确为12与13不符。开发 `verify_archived_comparison.py` 当前退出0；另7个独立变体（边界外引用、commit错配、引用SHA错配、计数12、原始字节篡改、具体路径列表错配、自洽哈希下重复参考）均以对应错误退出1且输入元数据无写入。

以上为1个原MRE程序的2次调用、1个校验工具的8次调用，共10个元数据子进程；各项与37个断言分列。所有原命令、stdout/stderr、变体输入及逐路径SHA见 `results.json`、`command_log.json`、`commands/`。被审核readiness/校验脚本及权威预算/原journal SHA前后不变。

本轮只做元数据审核，不重跑453/worker/CLI大套件，不访问QC、SDK、Research、LEAN、市场或模型，不部署、不改生产或权威预算。辅助工具的职责是重算所引用的归档比较，不是通用readiness认证。4条“不在参考中”不表示当前云端缺文件，软件通过身份仍为81fbe52；真实运行、旧LEAN终态、阶段2及完整系统仍待验收。
''',encoding='utf-8')
manifest=[]
for path in OUT.rglob('*'):
    if path.is_file() and path.name!='manifest.json':
        manifest.append({'path':path.relative_to(OUT).as_posix(),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
(OUT/'manifest.json').write_text(json.dumps({'commit':result['commit'],'files':manifest},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'unit_methods':0,'metadata_checks':37,'passed':37,'failed':0,'manifest_files':len(manifest)},ensure_ascii=False))
