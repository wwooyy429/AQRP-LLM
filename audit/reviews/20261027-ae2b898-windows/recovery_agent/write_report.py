import hashlib,json
from pathlib import Path
OUT=Path(__file__).resolve().parent;ROOT=OUT.parent/'source'
def read(name):return json.loads((OUT/name).read_text(encoding='utf-8'))
first=read('first_run_summary.json');execution=read('first_execution.json')
failure=read('failure_settlement_result.json');failure_execution=read('failure_execution.json')
original=read('original_mre/result.json');original_execution=read('original_mre_execution.json')
commands=read('command_log.json');failure_commands=read('failure_command_log.json')
assert first['success'] and first['source_and_authority_unchanged'] and failure['passed']==4
assert original_execution['exit_code']==0 and original_execution['byte_identical_to_original']
assert original['joint_freeze_refused'] and original['legacy_freeze_returncode']!=0 and not original['pointer_changed']
assert original['ledger_unchanged'] and original['prepare_old_attempt_returncode']==0
after={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in first['source_hashes_before']}
assert after==first['source_hashes_before']==first['source_hashes_after']
missing=[]
for command in commands:
    if command['label'] in {'reject-v1-missing','reject-v2-missing'}:
        data=(OUT/command['stderr']).read_bytes()
        assert b'admitted-inputs' in data and b'not-read.json' not in data
        missing.append({'label':command['label'],'stderr':command['stderr'],'failure_is_missing_admission_before_tool_read':True})
assert len(missing)==2
matrix={}
for case in first['inputs']:matrix[case['method']]=matrix.get(case['method'],0)+1
report={'reviewer':'recovery_agent independent WR-17 repair review','commit':'ae2b8985f3799c246e90341370f86d80483f63ed',
    'date':'2026-10-27','verdict':'WR-17原冻结/按attempt恢复问题在本次独立离线范围修复后通过；本代理未新增确认缺陷。不覆盖其他代理确认的WR-18或完整系统验收。',
    'findings':[],
    'first_run':{'methods':5,'passed_methods':5,'subcases':46,'failure_records':0,'error_records':0,'skipped':0,'first_failure':None,
        'exit_code':0,'seconds':77.452,'actual_CLI_processes':72,'direct_freeze_processes':12,'synthetic_metadata_finish_calls':4,'actual_worker_executions':0},
    'additional_failure_settlement':{'programs':1,'subcases':4,'passed':4,'failure_records':0,'exit_code':0,
        'actual_CLI_processes':28,'synthetic_metadata_finish_calls':6,'actual_worker_executions':0,
        'scope':'v1/v2 synthetic fixed-check failed Research report and synthetic LEAN Runtime Error delivered envelope; never actual remote failure evidence'},
    'original_MRE':{'script':'original_minimal_pending_freeze.py','byte_identical':True,'raw_sha256':original_execution['script_raw_sha256'],
        'exit_code':0,'joint_freeze_refused':True,'legacy_freeze_refused':True,'pointer_changed':False,
        'original_pending_prepare_exit':0,'ledger_unchanged':True,'subprocesses':4,
        'scope':'Original pending ledger copied into isolated full source; 2 production freeze CLI calls refuse, direct old-context inspection and original pending prepare succeed.'},
    'counting':'Methods, parameterized probes, metadata writer calls and CLI processes are separate. The first suite contains 46 cases; four supplemental failure probes and the original MRE overlap and are not added as unique method counts.',
    'method_subcases':matrix,
    'freeze_coverage':{'original_plan_versions':[1,2],'states':['started','pending','ambiguous'],'target_plan_versions':[1,2],
        'entrypoints':['production stage2.py CLI in new subprocess','production stage2.freeze function in new subprocess'],
        'serial_refusal_subcases':24,'concurrent_refusal_subcases':2,'concurrent_processes_each':2,
        'no_write_check':'Before/after all persisted source-case file hashes equal, including journal, plans/listing proof, budget and engineering_current pointer. Explicit policy error text checked, not timeout failures.'},
    'recovery_coverage':['Fresh independent v1/v2 plans freeze/register/claim/prepare through actual copied production CLI and Filesystem Registry.',
        'After original admission: delete current pointer, current deployment manifest, current source catalog and local input; change a current cloud source file. Original prepare/status/Research result then restore and LEAN prepare/submission/result recover by original attempt, with no new charges.',
        'After Research terminal, a real zero-charge plan-B freeze changes current pointer; old finalized A admission is still readable without rebuilding its missing input file.',
        'Copied prepared LEAN input survives the same pointer/catalog/deployment deletion and code drift, then accepted submission and terminal completed result use original Research resolution.',
        'Canonical admission/input-hash/source-attempt/cloud-path/extra-field/noncanonical/local-byte tampering rejects with no additional file or usage mutation. Unknown canonical attempt IDs reject for prepare/status.',
        'Missing admission rejects at admitted-input read before missing tool file is considered; raw stderr was checked for that exact cause.',
        'After finalized LEAN, removing its original admission cannot create a fresh remote input. Existing original admission idempotent read is separately allowed and does not grant dispatch.',
        'Supplemental v1/v2 Research check-failed reports and LEAN Runtime Error shapes settle to failed under drift without refund/additional debit; synthetic error text is not copied into Registry.'],
    'missing_admission_failure_source_QA':missing,
    'source_locations':{'freeze_guard_and_writes':'tools/stage2.py:70-74','immutable_attempt_lookup':'tools/stage2.py:91-117',
        'admission_byte_manifest_hash_check':'tools/stage2.py:120-149','prepare_reuse_and_finalized_guard':'tools/stage2.py:152-157',
        'CLI_attempt_routing':'tools/stage2.py:224-247'},
    'actual_execution_limits':{'actual_worker_executions':0,'SDK_executions':0,
        'actual_metadata_finish_calls_total':10,'first_plus_supplement_CLI_processes':100,'direct_freeze_processes':12,
        'original_MRE_additional_processes':4,
        'receipt_construction':'Independent bounded JSON counts/checks/references are passed through actual _finish, then native-shaped parser/Bridge/Registry via actual CLI. These are self-built trusted test observations, not proof the market worker ran.',
        'case_copy':'Execution source/config tree copied unchanged; unrelated historical audit archives omitted in new synthetic fixtures. Original MRE separately copied the whole source/old ledger unchanged. Fresh synthetic Registry baseline preserves original aggregate usage, not a claim to recreate all historical engineering events.'},
    'raw_evidence':{'first_stdout':'first_run.stdout','first_stderr':'first_run.stderr','first_execution':'first_execution.json',
        'per_command_stdout_stderr':'commands/ and command_log.json','failure_stdout':'failure_settlement.stdout',
        'failure_stderr':'failure_settlement.stderr','failure_execution':'failure_execution.json','failure_commands':'failure_command_log.json',
        'original_MRE_stdout':'original_mre.stdout','original_MRE_stderr':'original_mre.stderr','original_execution':'original_mre_execution.json'},
    'regression_inputs':'first_run_summary.json:inputs','first_run_preserved':True,'reviewer_measurement_corrections':[],
    'source_and_authority_hashes_before_after_equal':True,'source_and_authority_hashes':after,
    'actions':{'network':0,'QC':0,'real_SDK':0,'Research':0,'LEAN':0,'market':0,'models':0,'deployment':0,
        'production_source_edits':0,'authoritative_budget_changes':0,'actual_final_market_data_opened':0},
    'remaining_unverified':['Real deployment/input readback, actual successful and full failed native executions, old LEAN delivered terminal and data certification.',
        'A check-failed report in a successful synthetic cell is not an actually failed Research execution; Runtime Error envelope is also fabricated.',
        'New identity preparation/Registry-completion admission is independently reviewed by other agents. This WR17 pass does not close their findings.']}
(OUT/'report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
(OUT/'report.md').write_text('''# WR-17独立修复复验

固定 `ae2b8985f3799c246e90341370f86d80483f63ed`：**WR-17原冻结/按attempt恢复问题在本次离线范围修复后通过，未新增确认缺陷。** 不覆盖其他代理确认的WR-18，也不代表阶段2或完整系统通过。

首跑5方法46子例全过，0失败/错误/跳过，无重跑覆盖。实际72个隔离CLI子进程、12个直接freeze函数子进程，4次受限metadata `_finish`，实际worker次数0。另4个失败结算探针全过（28 CLI、6次metadata `_finish`），不计为4个单元方法；它们仅使用自建受限回执。

v1/v2原计划×started/pending/ambiguous×v1/v2目标×CLI/函数子进程24例及2个双进程混合freeze例全部拒绝，明确核对策略错误，前后持久文件SHA完全相同，未写新计划/listing、current指针、journal或预算。

两版本均从实际CLI freeze→register→claim→prepare开始。原admission保存后，删除current/deployment/catalog/本地input、改动当前源码，旧Research和LEAN仍能按原attempt prepare/status/settle；不重建缺失input文件、不新增费用。Research终结后合法零费freeze到B，仍可读取A原准入。篡改/foreign/missing admission、输入hash/字节或目标路径、额外字段、未知attempt均拒绝；finalized无admission不能创建新input。原本已存在的admission幂等读取仍允许，未当作新执行许可。

补充v1/v2各测固定check失败的Research报告及LEAN Runtime Error形状，在同样漂移后都进入failed，usage不变，错误文本不入账。成功cell中的失败check不是实际Research执行失败；LEAN错误封装也完全合成，不能替代真实原生失败证据。

原 `minimal_pending_freeze.py` 原字节SHA `c2771ab9fdf7b90f971b988491ab95d1d1eb35da69da058c2cba9d45e1aead8c` 已单独重放exit0：v1/v2 freeze都拒绝、旧指针/journal不变、原pending attempt prepare成功。原件和原始stdout/stderr均保留。

源码主范围：stage2.py:70–74统一冻结锁/检查，91–117从不可变config恢复Bridge，120–149校验admission/hash/本地字节，152–157幂等读取/终结新输入拒绝，224–247按attempt路由。所用原源码及权威budget/journal前后SHA相同；只在隔离副本写合成账本和输入。

全部原始命令、stdout/stderr、首跑与补充输出及精确计数均归档。未导入作者测试fixture，未运行真实SDK/worker/Research/LEAN/QC/模型或市场任务。真实平台运行、旧任务终态、数据/金融证据及其他共享准入问题仍单独待验。
''',encoding='utf-8')
manifest={p.relative_to(OUT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.rglob('*')
    if p.is_file() and p.name!='manifest.json' and 'cases' not in p.relative_to(OUT).parts and 'original_mre/source' not in p.relative_to(OUT).as_posix()}
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps({'report':str(OUT/'report.json'),'WR17':'passed_in_reviewed_offline_scope','methods':5,'subcases':46,'failures':0,'errors':0,'skipped':0,
    'additional_failure_probes':4,'original_MRE_exit':0,'actual_workers':0,'authority_unchanged':True},ensure_ascii=False))
