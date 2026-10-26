import ast
import difflib
import hashlib
import json
from pathlib import Path

OUT=Path(__file__).resolve().parent;ROOT=OUT.parent/'source'
summary=json.loads((OUT/'first_run_summary.json').read_text(encoding='utf-8'))
OLD=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-dc49f0f-20261027\source')
name='cloud/qresearch/engineering_receipts.py'
old=(OLD/name).read_text(encoding='utf-8');new=(ROOT/name).read_text(encoding='utf-8')
diff=''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='dc49f0f/'+name,tofile='4a94430/'+name))
(OUT/'production_change_readonly.diff').write_text(diff,encoding='utf-8')
def grammar(text):
    tree=ast.parse(text)
    fn=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='_annotations')
    return [node.args[0].value for node in ast.walk(fn) if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute)
        and node.func.attr=='fullmatch' and node.args and isinstance(node.args[0],ast.Constant)]
assert grammar(old)==grammar(new)
schema=(OUT/'official_mcp_schema_2025-11-25.json').read_bytes()
helper=(OUT/'independent_fractional_harness.py').read_bytes()
assert hashlib.sha256(schema).hexdigest()=='268a5f82ba70fd7e4b6dc4aa1e64f116f74b4d0edcb69dc046829c79dd4e97e7'
assert helper==Path(r'C:\Users\11638\.codex\tmp\aqrp-review-dc49f0f-20261027\receipt_agent\independent_fractional_harness.py').read_bytes()
after={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in summary['source_raw_sha256_before']}
assert after==summary['source_raw_sha256_before']==summary['source_raw_sha256_after']
matrix={}
for case in summary['inputs']:matrix[case['method']]=matrix.get(case['method'],0)+1
exe=r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\venv\Scripts\python.exe'
command="& '"+exe+"' -B "+' '.join("'"+s.replace("'","''")+"'" for s in summary['command_argv'])
commands=[{'command':command,'tool_chunk_id':'720632','exit_code':0,'purpose':'首次独立10方法803子例完整执行，0失败/错误/跳过'},
    {'tool_chunk_id':'07d21a','exit_code':0,'purpose':'复制前轮审核者自建helper及已固定官方schema原字节并校验SHA；无网络',
        'from_helper':r'C:\Users\11638\.codex\tmp\aqrp-review-dc49f0f-20261027\receipt_agent\independent_fractional_harness.py',
        'from_schema':r'C:\Users\11638\.codex\tmp\aqrp-review-dc49f0f-20261027\receipt_agent\official_mcp_schema_2025-11-25.json'},
    {'tool_chunk_id':'a78446','exit_code':0,'purpose':'只读定位实际修复及共享校验调用行号',
        'command':r"rg -n 'datetime\(int|grammar already|def _annotations|def _text_node|_text_node\(block|visit\(_text_node' source/cloud/qresearch/engineering_receipts.py"}]
(OUT/'command_log.json').write_text(json.dumps(commands,indent=2,ensure_ascii=False),encoding='utf-8')
report={'reviewer':'receipt_agent independent WR-14 repair review','commit':'4a94430144cd3d9e4b5469bd2b6e4a48d80d5fc7',
    'baseline_commit':'dc49f0f3037918f3ce4413665c59b164a8d6e2b7','date':'2026-10-27',
    'verdict':'WR-14在本次独立登记语法/边界及新旧worker回执链范围修复后通过；未发现可证实新缺陷。不是阶段2或完整系统验收。',
    'findings':[],
    'first_run':{'methods':10,'passed_methods':10,'subcases':803,'failure_records':0,'error_records':0,'skipped':0,'first_failure':None,'exit_code':0},
    'method_subcases':matrix,'counts_are_overlapping_not_unique':True,
    'production_analysis':{'file':name,'calendar_validation_line':77,'annotation_validator_line':43,'text_validator_line':82,
        'outer_shared_call_line':157,'recursive_shared_call_line':316,'registered_regex_unchanged':True,
        'mechanism':'严格regex继续验证时间/offset/数字fraction；datetime(int年,int月,int日)只校验历法，不解析、舍入或改写小数。文本及注解原对象/字符串不变。',
        'readonly_diff':'production_change_readonly.diff'},
    'known_answers':{'lexical_and_string_preservation':351,'calendar_and_long_registered_fractions':53,
        'invalid_calendar_time_offset_rejections':75,'WR13_annotation_priority_text_rejections':29,
        'deep_json_width_and_side_load_checks':15},
    'worker_and_ledger_design':{'actual_pure_python_worker_executions':2,
        'families':['run_collection_task with independent SyntheticSource','run_research_task with independent SyntheticQB/ObjectStore'],
        'observation_ledger_branches':'Each gets a fresh independent MemoryArtifactStore/Registry copy at the same prepaid attempt. Actual worker output is shared immutable input, not rerun per branch.',
        'legal_branch_cases':234,'legal_completed':234,'illegal_branch_cases':36,'illegal_rejected':36,
        'same_attempt_reject_then_corrected_recovery_cases':2,'recovery_passed':2,
        'source_fetches_total':{'collection':3,'old_research':1},
        'original_base_ledgers_remain_started':True,'parse_or_complete_adds_budget_charge':False,
        'row_sentinel_persisted_in_ledger':False,
        'fake_calendar':'Invented weekdays and constant numbers, not real exchange coverage or market data'},
    'old_LEAN_receipt_regression':{'subcases':4,'result':'submission/read/logs outer .7Z, comma .70+05:45, .70000-03:30 all accepted; checked full receipt→Bridge/Registry completed',
        'real_LEAN_execution':False},
    'string_scope':['0–6 digits, point/comma, T/t/space, Z/z, valid signed offsets, naive hints and date-only controls retain strings byte-for-byte.',
        '1/2/4/5-digit forms now pass alongside 3/6-digit controls.',
        '9/17/410/4096-digit fractions are tested only as numeric strings within the declared grammar; no other ISO variant requirement.',
        'Century leap-year/year/month/day known answers, invalid calendar and invalid time/offset still reject.',
        'Unknown rows/errors/_meta/outputs, nonstring text, bad roles/boolean or nonfinite/out-of-range priority still reject.'],
    'source_hashes_before_after_equal':True,'source_raw_sha256':after,
    'primary_schema':{'repository':'modelcontextprotocol/modelcontextprotocol','file_commit':'c4c367f9f58296a7053f5c78a52fd02bfbb56a49',
        'path':'schema/2025-11-25/schema.json','raw_sha256':hashlib.sha256(schema).hexdigest(),
        'source':'Copied byte-identical fixed official primary from prior independent review; no network this round.',
        'scope':'Annotation field semantics only; declared narrower adapter subset, not arbitrary MCP/SDK certification.'},
    'reviewer_helper':{'source':'previous independently authored helper, no developer fixtures','raw_sha256':hashlib.sha256(helper).hexdigest(),'byte_equal_to_previous':True},
    'commands':'command_log.json','regression_inputs':'first_run_summary.json:inputs',
    'first_run_files':['independent_fraction_boundaries.py','first_run_summary.json','first_run_unittest.txt'],
    'reviewer_measurement_corrections_this_round':[],
    'limits':['Only actual pure-Python synthetic workers and native-shaped receipts executed; no real AlgorithmImports/Python.NET/SDK.',
        'No real deployment/input readback, native success/full failure receipt, old pending LEAN terminal or market data certification.',
        'Formal research, final test and trading remain closed; this result does not expand previous numerical or data-exposure claims.'],
    'actions':{'network':0,'real_SDK':0,'Research':0,'LEAN':0,'market':0,'models':0,'deployment':0,'real_budget_changes':0,'candidate_source_edits':0,'actual_final_market_data_opened':0}}
(OUT/'report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
(OUT/'report.md').write_text('''# WR-14 独立修复复验

固定 `4a94430144cd3d9e4b5469bd2b6e4a48d80d5fc7`：**WR-14在本次独立覆盖范围修复后通过，未发现可证实新缺陷。** 不等于阶段2或完整系统验收。

新增独立首跑10方法、803子例，0失败、0错误、0跳过，无审核器修正或重跑覆盖。已知答案覆盖0–6位点/逗号、T/t/空格、Z/z、有效偏移/naive提示、世纪闰年与有效年/月/日，注解和text原字符串不变。9–4096位数字fraction仅测试已登记数字串语法，不强加其他ISO形式。

新采集及旧run_research_task各实际执行一次纯Python合成worker；后者用审核者自建FakeQB、ObjectStore、发明weekday日历和常量数值。对同一预扣attempt的独立MemoryRegistry克隆，234个合法原生观察分支完成，36个非法日历/offset/旁载荷分支拒绝且台账字节/usage不变。2个同attempt先拒绝再纠正的恢复例完成，无重取/再扣费；行sentinel不进入台账。上述是2次worker加独立回执/ledger分支，不冒称234次独立worker执行。

旧LEAN提交/读回/logs三段外层短fraction正例及完整receipt→Bridge/Registry完成保留。WR-13未知rows/errors/outputs/_meta、非字符串text、非法priority/角色/时钟及深层JSON旁载荷拒绝继续有效。

源码 `engineering_receipts.py:77` 改为只构造年/月/日；严格regex经AST核对与dc49相同。小数不再交给运行时ISO解析，也没有补零、截断、舍入或改写原hint字符串。外层157行、递归316行仍经过共用text校验器。只读差异见 `production_change_readonly.diff`。

官方schema沿用固定c4c367f9f58296a7053f5c78a52fd02bfbb56a49，原字节SHA `268a5f82ba70fd7e4b6dc4aa1e64f116f74b4d0edcb69dc046829c79dd4e97e7`；审核者自建helper原hash一致，未导入作者测试夹具。七份所用生产文件运行前后hash一致。

真实SDK、Research、LEAN、市场、模型、部署、网络、实际预算变更和最终行情读取均为0。新版真实运行、完整实际失败回执、云端输入读回、旧LEAN终态、历史覆盖和金融证据仍缺证据；正式研究、最终测试和交易保持关闭。
''',encoding='utf-8')
manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.iterdir() if p.is_file() and p.name!='manifest.json'}
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps({'report':str(OUT/'report.json'),'WR14':'passed_in_tested_scope','methods':10,'subcases':803,'failures':0,'errors':0,'skipped':0,
    'actual_worker_executions':2,'legal_ledger_branches':234,'rejected_ledger_branches':36,'new_findings':0,'source_hashes_unchanged':True},ensure_ascii=False))
