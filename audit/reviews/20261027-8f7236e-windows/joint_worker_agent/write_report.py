import hashlib
import json
from pathlib import Path

OUT=Path(__file__).resolve().parent;ROOT=OUT.parent/'source'
first=json.loads((OUT/'first_run_summary.json').read_text(encoding='utf-8'))
captured=json.loads((OUT/'captured_run/first_run_summary.json').read_text(encoding='utf-8'))
execution=json.loads((OUT/'captured_execution.json').read_text(encoding='utf-8'))
assert first['success'] and captured['success']
assert first['inputs']==captured['inputs']
assert first['actual_component_invocations']==captured['actual_component_invocations']
assert first['script_sha256']==captured['script_sha256']
after={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in first['source_raw_sha256_before']}
assert after==first['source_raw_sha256_before']==first['source_raw_sha256_after']==captured['source_raw_sha256_after']
helper=OUT/'independent_market_helper.py'
previous=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-4a94430-20261027\receipt_agent\independent_fractional_harness.py')
assert helper.read_bytes()==previous.read_bytes()
matrix={}
for case in first['inputs']:matrix[case['method']]=matrix.get(case['method'],0)+1
exe=r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\venv\Scripts\python.exe'
first_command="& '"+exe+"' -B "+' '.join("'"+arg.replace("'","''")+"'" for arg in first['command_argv'])
commands=[{'purpose':'首次独立joint-v2全链；原始unittest stream保留','command':first_command,
    'tool_chunk_id':'3e7e40','exit_code':0,'methods':9,'subcases':81,'stdout_tool_record':'3e7e40',
    'unittest_stream':'first_run_unittest.txt','summary':'first_run_summary.json'},
    {'purpose':'一次明确的原字节stdout/stderr捕获重放，不覆盖首跑；相同81子例不算新增独有案例',
        'capture_command':"& '"+exe+"' -B '"+str(OUT/'capture_run.py')+"'",
        'tool_chunk_id':'f9dd41',**execution}]
(OUT/'command_log.json').write_text(json.dumps(commands,indent=2,ensure_ascii=False),encoding='utf-8')
total={name:2*value for name,value in first['actual_component_invocations'].items()}
report={'reviewer':'joint_worker_agent independent joint-v2 review','commit':'8f7236ecbafcb514f07a6af4150a5afdbc1fd474',
    'date':'2026-10-27','verdict':'本代理实际worker/collector/cache/receipt/Bridge完成链在所测合成范围通过；未新增确认缺陷。不覆盖独立Registry准入/CLI问题或阶段2整体验收。',
    'findings':[],
    'first_run':{'methods':9,'passed_methods':9,'subcases':81,'failure_records':0,'error_records':0,'skipped':0,'exit_code':0,
        'first_failure':None,'actual_component_invocations':first['actual_component_invocations']},
    'captured_repeat':{'methods':9,'subcases':81,'failure_records':0,'error_records':0,'skipped':0,'exit_code':0,
        'same_inputs':True,'additional_unique_cases':0,'actual_component_invocations':captured['actual_component_invocations'],
        'stdout_raw':'captured_run/stdout.txt','stderr_raw':'captured_run/stderr.txt',
        'stdout_bytes':execution['stdout']['bytes'],'stderr_bytes':execution['stderr']['bytes']},
    'both_runs_actual_component_invocations':total,
    'invocation_interpretation':'Research count includes failing invocations and explicit local synthetic intent-reentry tests; only a fake SDK is used. Three successful native modes use independent Registry clones of one worker output, so they are not three new Research executions. No actual platform calls occurred.',
    'method_subcases':matrix,'counts_overlap_do_not_add':True,
    'known_answer_results':{'parent_market_history_calls':1,'joint_universe_native_calls':40,'joint_window_count':40,
        'joint_record_count':80,'joint_missing_values':{'dollar_volume':40,'has_fundamental_data':0,'time':0,'end_time':0},
        'retained_snapshot_rows_with_HasFundamentalData_false':40,
        'native_request_contract':'For each original daily [A,B), arguments are A-1us/B-1us, native inventory filters (start,end]; includes Jan1 and excludes Feb10.',
        'child_cache_only_provider_calls':0,'child_first_and_replay_refs_equal':True,
        'receipt_and_report_raw_hashes_verified':True,'receipt_identity_and_child_plan_hash_verified':True,
        'successful_receiver_data_event_count':6,'successful_receiver_dividend_event_count':1,
        'receiver_observation_window':'Invented three weekdays 2018-01-03 through 2018-01-05; parent raw cache still fetches full synthetic 2018.'},
    'coverage':['Actual run_research_task uses independent FakeQB for raw OHLCV and actual QuantConnectSnapshotSource/HistoricalSnapshotCollector for all 40 child windows, then native-shaped Research parsing→pending→Registry completed.',
        'Research→LEAN uses the completed parent resolution. Actual initialize_receiver/receive_slice/finish_receiver run against a shared fake Object Store, then native create/read/log chunks→Bridge/Registry completed in direct/content/equivalent-dual modes.',
        'Parent/child/attempt summary references, exact plan hash, count/boolean, missing totals, cache fetch, row arrays, financial/US200/availability/export flags and missing completed summary mutations reject before Registry writes.',
        'Wrong native project, conflicting carriers, hidden display rows, and annotation rows reject. No synthetic row sentinel enters Registry.',
        'Child helper replay returns the same summary/reference with zero fetch. Receipt identity corruption and payload corruption reject without refetch.',
        'All-empty child completes its 40 empty cache windows but yields a failed Research report and blocks LEAN.',
        'Native child raises/out-of-window/duplicate/mixed-universe responses retain intents; explicit same-attempt local worker reentry does not call native source again. Failure messages do not reveal the row sentinel.',
        'Actual trusted synthetic adapter callback sees Research debit before executing worker; worker failure yields ambiguous, repeat submit returns should_execute=false without another callback.',
        'Receiver permanent-SID mismatch rejects; a LEAN report carrying Research-only probe summary rejects; a changed resolution reference with recomputed bundle/report hashes fails exact Research binding.'],
    'source_locations':{'joint_worker':'cloud/qresearch/engineering_data.py:248-282,357-363',
        'summary_shape_and_parent_attempt_binding':'cloud/qresearch/engineering_tasks.py:157-206',
        'native_report_joint_validation':'cloud/qresearch/engineering_receipts.py:264-268',
        'receiver':'cloud/qresearch/engineering_data.py:366-472',
        'Research_to_LEAN_resolution':'cloud/qresearch/engineering_tasks.py:419-423,585'},
    'source_hashes_before_after_equal':True,'source_raw_sha256':after,
    'reviewer_helper':{'path':'independent_market_helper.py','byte_identical_to_previous_independent_helper':True,
        'raw_sha256':hashlib.sha256(helper.read_bytes()).hexdigest(),'developer_fixtures_imported':False},
    'commands':'command_log.json','raw_capture_record':'captured_execution.json','regression_inputs':'first_run_summary.json:inputs',
    'reviewer_measurement_corrections':[],
    'scope_limits':['FakeSDK/ObjectStore, invented weekdays, constant OHLCV, fabricated universe records and one synthetic dividend are engineering fixtures only.',
        'Repeated local failure/intent probes are not permission to rerun a real precharged Research attempt. No real SDK, Research, LEAN, models or market endpoint was called.',
        'References/hashes prove these observed synthetic bytes and shape/binding checks, not upstream provenance or signed platform execution.',
        'No true deployment/input readback, real native success/full failure, old pending LEAN terminal, US200/financial/company-action coverage, or economic evidence is established.',
        'Other agents independently review Registry admission and CLI lifecycle; this positive worker-chain result does not override their findings.'],
    'actions':{'network':0,'real_SDK':0,'Research':0,'LEAN':0,'market':0,'models':0,'deployment':0,'authoritative_budget_changes':0,'candidate_source_edits':0,'actual_final_market_data_opened':0}}
(OUT/'report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
(OUT/'report.md').write_text('''# Joint v2 worker 独立审核

固定 `8f7236ecbafcb514f07a6af4150a5afdbc1fd474`：本代理实际worker/collector/cache/receipt/Bridge完成链在所测合成范围通过，未新增确认缺陷。此结论不覆盖其他代理的Registry准入/CLI问题，也不代表阶段2或完整系统通过。

首跑9方法81子例，0失败/错误/跳过。为保存原字节stdout/stderr，另目录做1次明确捕获重放，仍9/81全过；首跑未覆盖，相同案例不累计成162个独有子例。原字节stdout3202B、stderr0B及完整argv/cwd/SHA在 `captured_execution.json`。

每次测试实际调用纯Python Research worker 11次（包含失败/intent重入）、receiver initialize 6次、finish 5次、receive_slice 15次，child helper重放3次。两次合计22/12/10/30/6；这些都是本地假SDK，不是实际Research/LEAN执行。三种成功回执模式用同一worker产物的独立Registry克隆，不冒称三次新Research。

成功链真实调用run_research_task：全2018假OHLCV缓存→40日真实Source/Collector→只读缓存→固定summary→原生形状Research parser→Registry完成→Research已验SID/refs→真实initialize/receive/finish_receiver→LEAN提交/读回/分块日志→Registry完成。direct/content/等价双表示均通过；假receiver仅观察3个发明weekday与1个合成dividend。

已知答案：40窗、80行、DollarVolume缺失40、另外3字段缺失0；False的HasFundamentalData成员40行保留。原生库存实现(start,end]；40个请求分别是原[A,B)端点各减1µs，保留Jan1、排除Feb10。父History一次、child原生40次，cache-only replay零新增；receipt/report原字节SHA、父identity/子plan hash/窗口refs一致。

跨父/attempt引用、summary计数/认证/行旁载荷、冲突载体、隐藏display/注解行、错误项目、LEAN挟带Research summary和改变SID/refs均拒绝。空child使Research报告failed并阻止LEAN；异常/越界/重复/混合响应保留intent、重入不重取；损坏receipt/payload不修复或重取。受信假adapter观察到先扣后执行，失败ambiguous且不免费派发重试。合成行sentinel不进入台账。

所用7份生产源码前后SHA一致，未导入作者fixture。FakeQB、ObjectStore、weekday日历、常量数值与dividend全部新造；无实际SDK/Research/LEAN/市场/模型/部署/网络/预算变更或最终行情读取。真实平台回执/输入读回、旧LEAN终态、市场覆盖与金融证据仍未验证。
''',encoding='utf-8')
manifest={p.relative_to(OUT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.rglob('*') if p.is_file() and p.name!='manifest.json'}
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps({'report':str(OUT/'report.json'),'first_methods':9,'first_subcases':81,'failures':0,'errors':0,'skipped':0,
    'same_input_capture_repeat':True,'first_invocations':first['actual_component_invocations'],'both_runs_invocations':total,
    'new_findings':0,'source_hashes_unchanged':True},ensure_ascii=False))
