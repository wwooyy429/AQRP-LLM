import collections,hashlib,json
from pathlib import Path
OUT=Path(__file__).resolve().parent;SOURCE=OUT.parent/'source'
def read(path):return json.loads((OUT/path).read_text(encoding='utf-8-sig'))
new=read('research_first/results.json');old=read('main/results.json');compat=read('compat_boundaries/result.json')
failure=read('compat_failure/failure_settlement_result.json');crash=read('crash_addendum/results.json');copies=read('legacy_script_hashes.json')
assert all(item['old_sha256']==item['new_sha256'] for item in copies)
assert new['success'] and old['success'] and compat['success'] and failure['passed']==4 and crash['passed']==4
allstats=[new['stats'],old['stats'],compat['stats'],failure['stats'],crash['stats']]
stats={key:sum(value[key] for value in allstats) for key in new['stats']}
assert stats['actual_CLI_processes']==134 and stats['synthetic_metadata_finish_calls']==14 and stats['actual_worker_executions']==0
before=new['source_hashes_before'];assert before==new['source_hashes_after']==old['source_hashes_before']==old['source_hashes_after']
assert before=={name:hashlib.sha256((SOURCE/name).read_bytes()).hexdigest() for name in before}
folders={'research_first':'command_log.json','main':'command_log.json','compat_boundaries':'command_log.json',
    'compat_failure':'failure_command_log.json','crash_addendum':'command_log.json'}
actual_commands=[];breakdown={}
for folder,filename in folders.items():
    records=read(folder+'/'+filename);breakdown[folder]=dict(collections.Counter(record['argv'][3] for record in records))
    for record in records:
        for stream in ('stdout','stderr'):assert (OUT/folder/record[stream]).is_file()
        actual_commands.append(dict(record,evidence_folder=folder))
assert len(actual_commands)==134
(OUT/'all_CLI_commands.json').write_text(json.dumps(actual_commands,ensure_ascii=False,indent=2),encoding='utf-8')
admission=json.loads((SOURCE/'audit/runtime/engineering/admitted-inputs/f5d05f5b964b4a1d924e4b70cd207386.json').read_bytes())
binding=json.loads((SOURCE/'audit/runtime/engineering/research-dispatch/f5d05f5b964b4a1d924e4b70cd207386.json').read_bytes())
report={
 'reviewer':'native_agent independent Research native failure and legacy receipt review',
 'commit':'deb85d9f27441b275ab8b108f0232ecd2707a1e8','baseline':'66ff72ffaaff8c91c008898e6527c91131176c2a',
 'verdict':'本代理负责的Research原生失败解析、原attempt失败恢复及旧native/合同/故障回归在已测范围通过，未确认新增该模块缺陷。entry_agent的WR21为新入口成功fallback另案，不能据本局部通过判定候选整体通过。',
 'findings':[],
 'new_first_run':{'methods':6,'subcases':91,'passed_methods':6,'failure_records':0,'error_records':0,'skipped':0,
     'first_failure':None,'exit_code':read('research_first/execution.json')['exit_code'],'seconds':35.779,'stats':new['stats'],
     'method_subcases':{
       'test_01_supported_carriers_full_original_hash_and_projection':16,
       'test_02_reject_carrier_annotations_transport_and_error_grammar':42,
       'test_03_binding_and_typed_boolean_context':22,
       'test_04_actual_archive_9_entries_43_physical_lines_and_original_hash':1,
       'test_05_actual_original_attempt_15_17_17_and_refusal_guards':8,
       'test_06_actual_settlement_write_faults_no_refund_or_success':2}},
 'new_coverage':[
   'Independently authored nbformat errors and direct/list/explicit-cell wrapper/single carrier/typed-equivalent mirrored carriers plus standard equal annotations. Full unchanged result content_hash is retained; each internal single-carrier projection has a different hash and is never substituted for the raw observation.',
   'Different or extra carriers, one JSON containing two errors, mirrored wrapper arrays, structured conflict, unknown annotations/rows/metadata, differing annotations, bool priority, duplicate JSON keys, integer isError, transport failure and successful stdout printing an error dictionary reject.',
   'Empty/blank/nonstring/129-entry/overlong traceback and unknown error fields reject. The registered wrapper has strict positive int execution count and exact int cell index; bool aliases reject.',
   'Original dispatch identity/attempt/project/input/cell/source hash and exact typed arguments are checked; schema/index bool aliases and missing binding reject.',
   'Actual f5d packet is read offline byte-identically, parsed as one error with two representations, then settled only in copies reconstructed at15 events. Normal15→17→17, wrong cell/project/attempt binding/input/entry evidence refuses without file or usage change; changed full response or projected-substitution after failure refuses.',
   'Injected actual completion-write and failed-journal exceptions leave pending16; actual CLI recovery reaches failed18 and repeats18 with no new debit/success. The extra pending acknowledgement is a generic audit replay event, not an execution charge.'
 ],
 'actual_archived_packet':new['actual_archive'],
 'actual_original_bindings':{'attempt_id':'f5d05f5b964b4a1d924e4b70cd207386',
     'input_hash':admission['deployment']['input_hash'],'cell_source_sha256':binding['cell_source_sha256'],
     'cell_read_response_sha256':binding['cell_read_response_sha256'],'arguments':binding['arguments'],
     'raw_original_packet':'source/audit/tool_observations/f5d05f5b964b4a1d924e4b70cd207386-research.json'},
 'event_trajectories':new['event_trajectories'],
 'event_count_caveat':'Normal replay is15→17→17. Two injected-fault paths are15→16→18→18 because record_submission replays a pending audit acknowledgement before failure. Usage never changes, no refund/new execution/success is claimed; the authoritative17-event ledger was not changed.',
 'legacy_byte_identical_replay':{'files':copies,'fixture_adaptations':[],
     'native':{'methods':6,'subcases':62,'passed_methods':6,'stats':old['stats']},
     'completion_contract':{'methods':3,'subcases':28,'passed_methods':3,'stats':compat['stats']},
     'manual_failure':{'programs':1,'probes':4,'passed':4,'stats':failure['stats']},
     'manual_write_faults':{'programs':1,'probes':4,'passed':4,'stats':crash['stats']},
     'all_first_exit_codes':[row['exit_code'] for row in read('legacy_execution.json')],
     'all_first_failures':None,
     'commit_literal_caveat':'The byte-identical original scripts retain66ff/81f/ae literal commit fields; actual --source argv and current source hashes bind these runs todeb85d9. No prior output was overwritten.'},
 'counting':{'new_unit_methods':6,'new_unit_subcases':91,'legacy_unit_methods':9,'legacy_unit_subcases':90,
     'unit_methods':15,'unit_subcases':181,'legacy_manual_probe_programs':2,'legacy_manual_probe_subcases':8,
     'new_write_fault_subcases':2,'new_write_faults_already_included_in_6_91':True,'bug_MRE_programs_owned':0,**stats,
     'new_CLI_processes':25,'legacy_CLI_processes':109,
     'limits':'Method/subcase/manual-probe/CLI/metadata_finish counters differ. New2 write faults are unit subcases, not an extra manual2. Cross-suite overlap is not a unique-test or financial-sample sum. Entry agent MRE commands are not included in this agent134.'},
 'commands':{'complete_134_CLI_argv_cwd_raw_stream_references':'all_CLI_commands.json','per_program_breakdown':breakdown,
     'top_level_captures':['capture_legacy.py','capture_research.py'],
     'executions':[read('research_first/execution.json'),*read('legacy_execution.json')],
     'in_process_fault_injected_production_calls':'Two new settle_research_result calls inside test06; four legacy record_submission/prepare calls inside legacy crash probes. These are not CLI/SDK/worker calls.'},
 'source_locations':{'narrow_nbformat_error_grammar':'cloud/qresearch/engineering_receipts.py:451-483',
     'duplicate_error_carriers_annotations_and_full_hash':'cloud/qresearch/engineering_receipts.py:486-523',
     'failure_projection':'cloud/qresearch/engineering_receipts.py:526-545',
     'dispatch_typed_context_binding':'cloud/qresearch/engineering_receipts.py:427-448',
     'success_legacy_and_failure_split':'cloud/qresearch/engineering_receipts.py:548-574',
     'immutable_dispatch_entry_reads':'tools/stage2.py:245-266','failed_replay_original_evidence':'tools/stage2.py:305-329'},
 'first_results_preserved':True,'reviewer_test_measurement_corrections':[],
 'non_test_lookup_note':'Initial REVIEW_INSTRUCTIONS lookup at source root was absent; located and read audit/review_packages/stage2_completion_runtime/REVIEW_INSTRUCTIONS.md. No tests or product operation occurred in that lookup.',
 'WR21_peer_QA':'entry_qa.txt confirms new-marker/no-dispatch success path is distinct from allowed marker-free legacy success. This agent did not rerun the peer MRE or count its commands.',
 'source_and_authority_hashes_before_after_equal':True,'source_and_authority_hashes':before,
 'engineering_receipts_raw_sha256':hashlib.sha256((SOURCE/'cloud/qresearch/engineering_receipts.py').read_bytes()).hexdigest(),
 'actual_ledger_scope':'Source17-event ledger and actual7/10/1 projection read/hashed only. Replay copies retain the original13-event prefix and reconstruct first15 bytes; future f5d ack/completion artifacts are removed only from those copies.',
 'actions':{'actual_worker':0,'actual_SDK':0,'QC':0,'Research':0,'LEAN':0,'market':0,'models':0,'network':0,
     'production_source_edits':0,'authoritative_ledger_writes':0,'actual_budget_changes':0},
 'acceptance_limits':[
   'No new remote source, execution or notebook output was read by this agent. Actual packet provenance is archived evidence, not a new SDK execution.',
   'Actual deployed/failed source identity is7fc5ef2e9d2379d29f48d05a1f3cc760000884d6; deb85d9 contains post-failure local parser changes and was not cloud-executed.',
   'CollectionError/source-iteration failure is not Research success, normal missing data, a repaired root cause or LEAN qualification. Underlying cause not provided; history/window/received-record/order/financial counts remain null.',
   'G3 failure parser/recovery evidence passes this local scope; whole candidate entry issue WR21 and other agents findings are separate. G1 successful run, G2 worker root cause, G4 full authenticated data and full stage2/financial acceptance are not granted.',
   'No OS-kill/power-loss durability certification; fault injections are synchronous exceptions at controlled production call boundaries.']}
# Keep the packet metadata unchanged and add the identity without a raw body.
report['actual_archived_packet']=dict(new['actual_archive'],attempt_id='f5d05f5b964b4a1d924e4b70cd207386')
(OUT/'report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
(OUT/'report.md').write_text('''固定源码 `deb85d9f27441b275ab8b108f0232ecd2707a1e8`：本代理负责的 Research 原生失败解析、原attempt失败恢复和旧native回归通过；未确认本模块新缺陷。entry_agent的WR21新入口成功fallback另案，局部通过不等于候选整体通过。

新增首跑 **6方法／91子例全过**，0 failure/error/skip，35.779秒，25个实际CLI、0 finish/worker。内容为16载体/完整hash/投影正例、42语法/注解/transport/隐藏输出拒绝、22原identity/cell/input及typed-bool边界、1实际原件计数、8正常恢复/拒绝分支和2写故障恢复。原packet raw SHA14ae4a…、完整result SHA6a5371…匹配；2个MCP表示是1次逻辑错误，traceback9条目、43物理行，旧traceback_line_count=9是条目数。

真实f5d原件仅在隔离15事件副本结算：正常15→17→17，失败不退款、不生成成功结果。错cell/project/attempt/input/entry及已失败后改变response/用内部单载体投影替换原件均拒绝无写。两个同步写故障恢复实际为15→16→18→18；多出的pending是重放确认审计事件，不是新扣费，不能误写所有轨迹都17。真实17事件账本、预算7/10/1及原13事件前缀未改。

旧6/62、compat3/28及两程序8manual原字节首跑全过，无夹具适配。总为15个unit方法／181子例，另旧manual8；新增2个写故障已在6/91中，不再加作manual。旧109+新25=134个CLI、metadata_finish14、实际worker/SDK/QC/Research/LEAN执行均0。原旧脚本commit字面量保留，actual --source和源码SHA绑定本轮；所有逐CLI argv/cwd/stdout/stderr见`all_CLI_commands.json`。

新增错误是独立自编夹具，实际原件只离线读取；不导入作者tests。完整原result hash保留，每个载体及annotation都验证；内部验证projection不冒充原件。单个JSON两error、成功stdout打印error字典、网络transport错误、typed-bool别名、side rows、矛盾镜像和坏traceback等拒绝。合法注册单载体/list/wrapper及相等双载体保留。

只读QA另案WR21：有新entry marker却无dispatch的新attempt不能沿legacy成功fallback；无marker的旧成功恢复仍应保留。详见`entry_qa.txt`，未重跑其MRE，未把其命令计入134。

部署执行身份仍是7fc，当前deb是失败后本地修补，不能称已云端成功。CollectionError底层cause未知；本代理不推断SDK形状/正常缺失/根因修复，不补造请求数、记录、窗口、订单或金融统计。G1成功运行/G2worker根因/G4完整数据认证、候选整体及阶段2仍由主审综合，不授予金融验收或最终测试许可。
''',encoding='utf-8')
manifest=[]
for path in OUT.rglob('*'):
    if path.is_file() and 'cases' not in path.relative_to(OUT).parts and path.name!='manifest.json':
        manifest.append({'path':path.relative_to(OUT).as_posix(),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
(OUT/'manifest.json').write_text(json.dumps({'commit':report['commit'],'excludes':'copied cases/ stores and source trees; raw captures, scripts, results, all command streams included','files':manifest},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'counting':report['counting'],'manifest_files':len(manifest)},ensure_ascii=False))
