import collections,hashlib,json
from pathlib import Path
OUT=Path(__file__).resolve().parent;SOURCE=OUT.parent/'source'
def read(path):return json.loads((OUT/path).read_text(encoding='utf-8-sig'))
main=read('main/results.json');compat=read('compat_boundaries/result.json');fail=read('compat_failure/failure_settlement_result.json')
assert main['success'] and compat['success'] and fail['passed']==4
copies=read('compat_script_hashes.json');assert all(item['old_sha256']==item['new_sha256'] for item in copies)
allstats=[main['stats'],compat['stats'],fail['stats']]
counting={name:sum(value[name] for value in allstats) for name in main['stats']}
assert counting['actual_CLI_processes']==102 and counting['synthetic_metadata_finish_calls']==14 and counting['actual_worker_executions']==0
source_hashes=main['source_hashes_before'];assert source_hashes==main['source_hashes_after']==compat['source_hashes_before']==compat['source_hashes_after']
assert source_hashes=={name:hashlib.sha256((SOURCE/name).read_bytes()).hexdigest() for name in source_hashes}
logs={'main':'main/command_log.json','compat_boundaries':'compat_boundaries/command_log.json','compat_failure':'compat_failure/failure_command_log.json'}
commands=[];breakdowns={}
for name,path in logs.items():
    records=read(path);breakdowns[name]=dict(collections.Counter(record['argv'][3] for record in records))
    for record in records:
        for stream in ('stdout','stderr'):assert (OUT/name/record[stream]).is_file()
    commands+=records
assert len(commands)==102
report={
 'reviewer':'native_agent independent synthetic native failure/rejection review',
 'commit':'66ff72ffaaff8c91c008898e6527c91131176c2a',
 'verdict':'本代理覆盖的新运行失败封装、受限编译拒绝/协议/CLI、旧合同及成功失败恢复兼容在本次独立合成范围通过；未确认新增缺陷。不得解释为真实SDK或完整阶段2验收。',
 'findings':[],
 'new_first_run':{'methods':6,'subcases':62,'passed_methods':6,'failure_records':0,'error_records':0,'skipped':0,
     'first_failure':None,'exit_code':read('main/execution.json')['exit_code'],'seconds':118.294,'stats':main['stats'],
     'method_subcases':{
       'test_01_runtime_parser_exact_context_and_all_carriers':20,
       'test_02_compile_parser_bound_diagnostics_and_ineligible_errors':20,
       'test_03_compile_cli_started_ambiguous_and_exact_idempotence':4,
       'test_04_compile_cli_protocol_and_acceptance_guards_no_write':14,
       'test_05_runtime_cli_old_input_failure_no_refund_and_no_raw_text':2,
       'test_06_successful_lean_and_parent_resolution_remain_compatible':2}},
 'new_coverage':[
   'v1/v2 plans are independently constructed via reviewer helper; production freeze/register/claim/prepare/parent Research result/LEAN admission run in actual copied CLI subprocesses and Filesystem Registry. No developer test fixture import.',
   'Runtime adapter: matching read_backtest project/backtest parameters, exact isError=true/success=false/terminal phrase plus diagnostics; equivalent dual carrier and content-only forms accepted. No invented completed/progress/order fields. Transport, absent error flag, absent/bad diagnostics, wrong IDs/project, contradictory carriers and hidden row payloads reject.',
   'Compile parser: frozen manifest file and separately hashed task input diagnostics eligible; generic string errors, unknown source path and invalid line are parsed as ineligible. Present backtestId, transport/isError, success=true, carrier conflict and unknown row output reject. Parser eligibility is distinct from settled failure.',
   'Actual backtest-rejection CLI: v1/v2 started and ambiguous tasks settle failed exactly once without new usage or fabricated external ID. Identical refusal repeats idempotently with unchanged files; a changed diagnostic is rejected with unchanged files; acceptance after failed rejection is refused.',
   'Actual CLI guards: pending/external identity without summary and accepted summary without original/journal cannot be overwritten; missing or foreign attempt/input-bound protocol, missing original admission and tampered local input refuse without file/usage changes.',
   'Existing admission prepare does not backfill a removed protocol marker. New protocol raw bytes equal the independently constructed canonical schema/identity/deployment known answer.',
   'Actual backtest-result CLI on already accepted old-style no-protocol input: transport and wrong native ID refuse without writes; valid synthetic runtime error settles failed once, keeps external ID and usage, and repeats idempotently after current pointer/catalog/deployment deletion, source drift and local input loss.',
   'Successful synthetic LEAN still completes under old no-protocol input and drift, retains exact parent Research resolution and financial_evidence=false. This requires matching accepted submission and original completion contract.',
   'Synthetic sensitive diagnostic and warning strings are inspected transiently and do not occur anywhere in fixture Registry storage. Only bounded hashes/counts remain. This is not an arbitrary encoded-string non-leakage proof.'
 ],
 'compatibility_replay':{
     'original_files':copies,'byte_identical':True,'prior_outputs_untouched':True,
     'boundaries':{'methods':3,'subcases':28,'passed_methods':3,'failure_records':0,'error_records':0,'skipped':0,
         'first_failure':None,'exit_code':read('compat_boundaries/execution.json')['exit_code'],'stats':compat['stats']},
     'failure_probes':{'programs':1,'subcases':4,'passed':4,'failed':0,'exit_code':read('compat_failure/execution.json')['exit_code'],
         'stats':fail['stats'],'records':fail['records']},
     'metadata_caveat':'Original byte-identical scripts retain hardcoded prior commit literals (81f / ae). Actual recorded --source is the fixed66ff source and source hashes bind this run. Those old literal fields are not runtime identity claims.',
     'contract_scope':'WR18 live loader/conflicting input/empty raw/hidden rows, original status absent/completed, completed idempotence, v1/v2 success and failure compatibility only.',
     'failure_scope':'The Research fixed-check-failed report is inside a synthetic successful cell; old LEAN Runtime Error backtest-object envelope is also fabricated. No real failed Research execution is claimed.'},
 'counting':{'new_unit_methods':6,'new_unit_subcases':62,'compat_unit_methods':3,'compat_unit_subcases':28,
     'unit_methods':9,'unit_subcases':90,'manual_probe_programs':1,'manual_probe_subcases':4,
     'MRE_programs':0,**counting,
     'limits':'Unit methods/subcases, parameterized manual probes, CLI processes and metadata writer calls are separate. Checks overlap and are not independent economic observations.'},
 'CLI_command_breakdown':breakdowns,
 'source_locations':{
     'runtime_native_adapter':'cloud/qresearch/engineering_receipts.py:476-500',
     'runtime_routing':'cloud/qresearch/engineering_receipts.py:503-507',
     'compile_rejection_parser':'cloud/qresearch/engineering_receipts.py:371-437',
     'fixed_protocol':'cloud/qresearch/engineering_tasks.py:24-28',
     'accepted_publication_order':'cloud/qresearch/engineering_tasks.py:556-603',
     'rejection_validation_and_transition':'cloud/qresearch/engineering_tasks.py:604-679',
     'prepare_protocol_no_backfill':'tools/stage2.py:174-200',
     'CLI_rejection_result_routing':'tools/stage2.py:276-293',
     'Registry_lock_owned_transition':'cloud/qresearch/registry.py:606-629'},
 'evidence':{'new_script':'native_boundaries.py','new_results':'main/results.json','new_first_stdout':'main/first.stdout',
     'new_first_stderr':'main/first.stderr','new_unittest':'main/unittest.txt','new_commands':'main/command_log.json',
     'compat_boundary_results':'compat_boundaries/result.json','compat_failure_results':'compat_failure/failure_settlement_result.json',
     'compat_raw_commands':'compat_boundaries/command_log.json and compat_failure/failure_command_log.json',
     'compat_original_script_hashes':'compat_script_hashes.json','all_native_inputs_and_stores':'main/cases/ and compatibility cases/',
     'capture_execution_records':['main/execution.json','compat_boundaries/execution.json','compat_failure/execution.json']},
 'source_and_authority_hashes_before_after_equal':True,'source_and_authority_hashes':source_hashes,
 'reviewed_receipts_static_raw_sha256':hashlib.sha256((SOURCE/'cloud/qresearch/engineering_receipts.py').read_bytes()).hexdigest(),
 'first_runs_preserved':True,'reviewer_measurement_corrections':[],
 'authoritative_ledger_scope':'Existing13-event source ledger was only read/hashed, never re-settled or reset. Fresh temporary fixture ledgers preserve aggregate baseline usage, not all prior engineering domain history.',
 'actions':{'actual_SDK':0,'QC':0,'Research':0,'LEAN':0,'market':0,'models':0,'network':0,'deployment':0,
     'actual_worker_executions':0,'production_source_edits':0,'authoritative_budget_changes':0,'authoritative_ledger_settlements':0},
 'remaining_unverified':['The other evidence agent reviews archived real old terminal provenance; this agent does not independently authenticate the remote source or make a new platform read.',
     'Actual native compile-rejection receipt is not obtained by these synthetic tests.',
     'Dedicated actual Research native execution exception and full failed-cell parser remain unverified.',
     'New live deployment/input readback, successful bounded Research/LEAN execution, complete data/financial certification and full stage2 acceptance remain separate.']}
(OUT/'report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
(OUT/'report.md').write_text('''固定源码 `66ff72ffaaff8c91c008898e6527c91131176c2a`：本代理覆盖的新失败封装、编译拒绝、协议/CLI与旧合同兼容在独立合成范围通过，未确认新增缺陷。

新增首跑 **6方法／62子例全部通过**，0 failure/error/skip，exit0，118.294秒。其中runtime解析20例、compile解析20例、v1/v2 started/ambiguous拒绝CLI4例、协议/已有接受/输入守卫14例、旧无marker runtime失败CLI2例及成功LEAN恢复CLI2例。每例及实际命令详见 `main/results.json` 和 `main/command_log.json`。

原3/28边界和原4个失败结算探针也原字节重放通过，三份原脚本/support SHA逐一相同，旧输出不覆盖。汇总为9个unittest方法／90子例，另1程序／4个参数化失败探针；实际CLI子进程102、synthetic metadata `_finish` 调用14、**实际worker和SDK均0**。原脚本旧81f/ae字面标签保留，实际argv与新源码哈希绑定66ff，不能据旧标签误认运行身份。

实际临时Filesystem链验证：原Research成功后才能准入LEAN；新prepare固定协议绑定identity和deployment/input_hash，恢复旧输入不补标记；编译拒绝只允许未接受任务，started/ambiguous失败不退款，同拒绝幂等、不同拒绝和失败后追加接受均拒绝。pending外部身份及单独接受指针的崩溃窗口都阻断拒绝覆盖。缺标记、foreign attempt/input标记、缺准入和输入字节篡改均拒绝且无文件/用量新增。

runtime严格封装、终态短语、诊断和原read参数绑定；transport、ID/project错配、矛盾载体、隐藏rows和非法诊断拒绝。旧无协议任务仍可按原接受提交结算synthetic runtime失败或成功，坏current/catalog、缺deployment/input和source漂移不妨碍原attempt恢复。runtime不补造completed/progress/订单观察；诊断/警告的合成敏感sentinel不进入Registry，只存hash/计数。这不是任意可信字符串隐编码的无泄漏证明。

上述回执全部自编合成：成功cell内的固定检查失败不是实际失败Research执行；Runtime Error对象和新isError失败封装也未调用平台。原真实13事件账本只读/哈希，不重新结算或重置；真实终态来源由其他证据代理审核。本代理不认证实际原生编译拒绝、新部署/输入读回、真实成功失败Research/LEAN、完整数据/金融或阶段2验收。

首跑脚本、逐CLI stdout/stderr、fixture原生输入和准入store、源码/权威预算/journal前后哈希完整保存。来源位置：`engineering_receipts.py:371-437,476-507`；`engineering_tasks.py:24-28,556-679`；`stage2.py:174-200,276-293`；`registry.py:606-629`。无生产源码/预算/真实账本改动，无QC/市场/模型/部署调用。
''',encoding='utf-8')
manifest=[]
for path in OUT.rglob('*'):
    if path.is_file() and 'cases' not in path.relative_to(OUT).parts and path.name!='manifest.json':
        manifest.append({'path':path.relative_to(OUT).as_posix(),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
(OUT/'manifest.json').write_text(json.dumps({'commit':report['commit'],'excluded':'copied synthetic cases/ trees; original scripts, command streams, execution captures and result summaries included',
    'files':manifest},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'counting':report['counting'],'manifest_files':len(manifest),'source_authority_unchanged':True},ensure_ascii=False))
