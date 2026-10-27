import hashlib,json
from pathlib import Path

OUT=Path(__file__).resolve().parent;SOURCE=OUT.parent/'source'
def read(path):return json.loads((OUT/path).read_text(encoding='utf-8-sig'))
first=read('first_run_summary.json');failed=read('failure_settlement_result.json');new=read('boundaries/result.json')
copies=read('byte_identical_replay_inputs.json')
assert all(item['old_sha256']==item['new_sha256'] for item in copies)
assert first['success'] and failed['passed']==4 and new['success']
assert first['source_hashes_before']==first['source_hashes_after']==new['source_hashes_before']==new['source_hashes_after']
final={name:hashlib.sha256((SOURCE/name).read_bytes()).hexdigest() for name in first['source_hashes_before']}
assert final==first['source_hashes_before']
for log_path in ('command_log.json','failure_command_log.json','boundaries/command_log.json'):
    for command in read(log_path):
        root=OUT/'boundaries' if log_path.startswith('boundaries/') else OUT
        assert (root/command['stdout']).is_file() and (root/command['stderr']).is_file()

report={
 'reviewer':'recovery_agent independent live completion / historical recovery review',
 'commit':'81fbe5294055423e88ee5aeae48ca6223e7971da',
 'verdict':'本代理负责的旧v1/v2恢复、成功/失败结算及新共享原提交loader/完成合同边界通过；未确认新增缺陷。Registry新准入关闭结论由主审及另一代理负责，完整系统/阶段2及真实平台运行仍未验收。',
 'findings':[],
 'byte_identical_replay':{'files':copies,'modified_original_files':False,
     'metadata_caveat':'Original scripts intentionally retain hardcoded commit=ae2b898 in their summaries. Actual --source argv resolves to this new 81fbe52/source; the candidate engineering_tasks.py SHA-256 is c957b7ccc415e86a88f90b29bea63ee01f5ca657d1437340a890dad21b482a9e. Do not interpret the old literal as the tested source.'},
 'original_recovery_suite':{'methods':first['methods'],'subcases':first['subcases'],'passed_methods':5,
     'failure_records':first['failure_records'],'error_records':first['error_records'],'skipped':first['skipped'],
     'first_failure':first['first_failure'],'exit_code':read('first_execution.json')['exit_code'],'seconds':91.088,
     'stats':first['stats'],'method_subcases':{
       'test_freeze_all_versions_states_entrypoints_no_write':24,
       'test_missing_tampered_foreign_admission_and_input_rejected_no_write':14,
       'test_original_attempt_research_and_lean_settlement_after_drift':2,
       'test_two_process_mixed_freeze_cannot_change_pointer':2,
       'test_unknown_attempt_rejected_without_pointer_dependency_or_write':4}},
 'original_failure_probe':{'programs':1,'subcases':4,'passed':4,'failure_records':0,'exit_code':read('failure_execution.json')['exit_code'],
     'stats':failed['stats'],'records':failed['records'],
     'limits':'Research check-failed report is fabricated inside a successful synthetic cell; the delivered LEAN Runtime Error envelope is also synthetic. Neither proves real platform failed execution.'},
 'new_loader_completion_boundaries':{'methods':new['methods'],'subcases':new['subcases'],'passed_methods':3,
     'failure_records':new['failure_records'],'error_records':new['error_records'],'skipped':new['skipped'],
     'first_failure':new['first_failure'],'exit_code':read('boundaries/execution.json')['exit_code'],'seconds':21.669,
     'stats':new['stats'],'method_subcases':{
       'test_01_loader_rejects_before_completion_read_and_no_write':12,
       'test_02_contract_rejects_input_raw_and_rows_without_persistence':12,
       'test_03_legacy_submission_status_success_and_completed_idempotence':4},
     'inputs':'boundaries/result.json:inputs',
     'coverage':[
       'All four v1/v2 x Research/LEAN pending submissions use actual Filesystem Registry; initial freeze/register/claim/prepare and parent Research/LEAN admission run via production CLI.',
       'Missing original receipt, hash-self-consistent empty raw_receipt and accepted=false are rejected before invoking completion_source; whole filesystem and usage remain unchanged.',
       'Mismatched terminal input_hash, empty terminal raw_receipt and unknown completion rows are rejected after one completion callback; whole filesystem and usage remain unchanged.',
       'Missing Research submission status and synchronous completed LEAN submission status remain compatible. Successful completion consumes the exact recorded checked submission.',
       'With malformed current pointer/catalog, removed deployment manifest/local input and drifted current source, the original frozen Bridge still completes Research/LEAN.',
       'After completed settlement, remove original submission/evidence/admission: direct Bridge.consume_completion returns completed with should_execute=false, never calls source or writes. This is an idempotent read, not a new dispatch permission.'
     ]},
 'historical_recovery_scope':[
   'v1/v2 originals, started/pending/ambiguous states, both freeze target schemas, CLI and direct freeze process entrypoints; same-project refusal preserves all case file hashes.',
   'Two concurrent v1/v2 CLI freezes each refused without pointer or journal changes.',
   'Actual CLI success Research then LEAN recovers original admitted input and resolution after pointer/deployment/catalog deletion, source drift and local input deletion, without new charge.',
   'After Research terminal, a legal zero-charge different-plan freeze changes current pointer; old finalized admission remains readable.',
   'Missing/tampered/foreign/noncanonical admissions, cloud destination changes, unknown row fields, bad local bytes and unknown attempts reject without new writes/charges. A finalized missing admission cannot generate new input.',
   'Both original synthetic failure kinds settle failed after pointer/catalog/deployment deletion, source drift and input loss, without new debit or error-text persistence.'
 ],
 'counting':{'unit_methods':8,'unit_subcases':74,'supplemental_probe_programs':1,'supplemental_probe_subcases':4,
     'MRE_programs_executed_by_this_agent_this_round':0,'actual_CLI_processes':116,'direct_freeze_processes':12,
     'synthetic_metadata_finish_calls':14,'actual_worker_executions':0,
     'limits':'Unit methods/subcases, parameterized probes, CLI processes and metadata writer calls are separate counters. Overlapping checks are not independent economic observations.'},
 'source_locations':{
   'shared_recorded_submission_loader':'cloud/qresearch/engineering_tasks.py:436-479',
   'completion_metadata_residency_check':'cloud/qresearch/engineering_tasks.py:531-549',
   'shared_completion_contract':'cloud/qresearch/engineering_tasks.py:662-690',
   'live_consume_and_completed_idempotence':'cloud/qresearch/engineering_tasks.py:692-720',
   'immutable_attempt_and_admitted_input_CLI':'tools/stage2.py:91-157',
   'CLI_native_result_routing':'tools/stage2.py:224-261'},
 'commands':[
   read('first_execution.json'),read('failure_execution.json'),read('boundaries/execution.json')],
 'evidence':{'first_stdout':'first_run.stdout','first_stderr':'first_run.stderr','first_unittest':'first_run_unittest.txt',
     'first_inputs_and_hashes':'first_run_summary.json','first_commands':'command_log.json',
     'failure_stdout':'failure_settlement.stdout','failure_stderr':'failure_settlement.stderr','failure_commands':'failure_command_log.json',
     'new_stdout':'boundaries/first.stdout','new_stderr':'boundaries/first.stderr','new_unittest':'boundaries/unittest.txt',
     'new_commands':'boundaries/command_log.json','per_command_streams':'commands/ and boundaries/commands/'},
 'first_runs_preserved':True,'reviewer_measurement_corrections':[],
 'source_and_authority_hashes_before_after_equal':True,'source_and_authority_hashes':final,
 'actions':{'network':0,'QC':0,'SDK':0,'Research':0,'LEAN':0,'models':0,'market':0,'deployment':0,
     'production_source_edits':0,'authoritative_budget_changes':0},
 'remaining_unverified':['Actual deployed source/input readback, real successful and full failed platform executions, current pending cloud terminal, row-level market data and complete historical universe/availability/vintage certification.']}
(OUT/'report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
text='''固定提交 `81fbe5294055423e88ee5aeae48ca6223e7971da`：本代理负责的旧恢复链及新共享 loader／完成合同边界通过，未确认新增缺陷。Registry 准入由主审和另一代理独立复验；完整系统、阶段2及真实平台执行仍未验收。

- 原 ae 独立脚本、support、direct 入口和两份 capture 共6文件原字节 SHA 一致，旧结果未覆盖。首跑 **5方法／46子例全过**，0 failure/error/skip，exit 0，91.088秒。涵盖 v1/v2、三个 open 状态、两种 freeze schema、CLI/函数进程及并发拒绝，以及原 attempt Research/LEAN 成功结算、current 计划切换、输入缺失／漂移／篡改拒绝。
- 原失败探针 **1程序／4子例全过**：v1/v2 Research 固定检查失败报告和 LEAN Runtime Error 合成信封在漂移后结算 failed，无新扣款，错误正文不持久化。成功合成 cell 内的 failed 报告不是真实失败 Research 执行；LEAN 信封也为合成。
- 新增首跑 **3方法／28子例全过**，0 failure/error/skip，exit 0，21.669秒。四种 v1/v2×Research/LEAN 路径分别验证：12例原提交缺失／哈希自洽空raw／accepted=false在完成回调前拒绝；12例 input_hash 冲突／空终态raw／未知rows在写入前拒绝；4例合法缺席或同步completed提交status、成功结算和completed幂等。坏current/catalog、缺deployment/local input、current source漂移均不阻断原冻结Bridge结算。幂等只读不赋予重新dispatch权限。

计数分别为8个unittest方法／74个子例，另1个程序／4个参数化失败探针；存在语义重叠，不作金融独立样本相加。实际生产CLI子进程116、direct freeze进程12、合成 metadata `_finish` 调用14，**实际worker／SDK／Research／LEAN执行均0**。本代理本轮无新增失败MRE，未重跑旧pending-freeze MRE；该问题由原5/46回归覆盖。

原脚本摘要保留硬编码 `commit=ae2b898…`，没有为新版本改写原件。实际 `--source` 命令及新 `engineering_tasks.py` SHA `c957b7ccc415e86a88f90b29bea63ee01f5ca657d1437340a890dad21b482a9e` 证明本轮目标为81f。见 `byte_identical_replay_inputs.json` 和三份 execution JSON。

源码核对：`engineering_tasks.py:436-479`共享原提交loader、`:662-690`完成合同、`:692-720`幂等和先验证后保存；`stage2.py:91-157`原attempt/准入恢复。首跑 stdout/stderr、每CLI原始输出、argv、输入和源码哈希完整保留，路径见 `report.json`；源文件、权威预算和原journal SHA前后相等。所有输入是独立合成受限元数据，不导入作者测试夹具、不访问网络/QC/市场/模型、不部署。
'''
(OUT/'report.md').write_text(text,encoding='utf-8')
manifest=[]
for path in OUT.rglob('*'):
    if path.is_file() and 'cases' not in path.relative_to(OUT).parts and path.name!='manifest.json':
        manifest.append({'path':path.relative_to(OUT).as_posix(),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
(OUT/'manifest.json').write_text(json.dumps({'commit':report['commit'],'excludes':'copied synthetic cases/ trees; all scripts, raw command streams and summaries included',
    'files':manifest},indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps({'verdict':report['verdict'],'counting':report['counting'],'files':len(manifest),'source_authority_unchanged':True},ensure_ascii=False))
