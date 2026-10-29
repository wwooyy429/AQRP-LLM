from pathlib import Path
from hashlib import sha256
import json,sys,platform
sys.dont_write_bytecode=True
D=Path(__file__).resolve().parent;R=D.parent;S=R/'source'
def read(p):return json.loads((D/p).read_text(encoding='utf-8'))
first=read('first_results.json');current=read('results.json');supp=read('supplement_results.json')
maps=json.loads((R/'source_git_manifest.json').read_text(encoding='utf-8'))
changed=[name for name,v in maps['source']['files'].items() if sha256((S/name).read_bytes()).hexdigest()!=v['sha256']]
commands=[
 {'command':[sys.executable,'-B',str(D/'independent_stdio.py')],'original_script_preserved':'first_script.py','exit_code':1,'stdout':'first.stdout','stderr':'first.stderr','result':'first_results.json','note':'Original execution before reviewer size fixture correction;2failures+1downstream CLI parsing error.'},
 {'command':[sys.executable,'-B',str(D/'independent_stdio.py')],'exit_code':1,'stdout':'corrected.stdout','stderr':'corrected.stderr','result':'results.json','note':'One reviewer UTF8 size stimulus corrected;CLI factory expectations remain0, two product failures retained.'},
 {'command':[sys.executable,'-B',str(D/'minimal_cli_factory_repro.py'),str(S)],'exit_code':1,'stdout':'minimal.stdout','stderr':'minimal.stderr','note':'Intentionally retains expected0 assertion;control factory passes and both actual enabled CLI launches exit2.'},
 {'command':[sys.executable,'-B',str(D/'supplement_stdio.py')],'exit_code':0,'stdout':'supplement.stdout','stderr':'supplement.stderr','result':'supplement_results.json'}]
(D/'execution_records.json').write_text(json.dumps(commands,ensure_ascii=False,indent=2),encoding='utf-8')
finding={
 'id':'WR-29','priority':'P1','reviewed_source_commit':'2d1d3060dbc7eb136c1dee61f0647977528b8aad',
 'title':'Enabled CLI rejects a valid trusted factory because its host class is imported under a different module identity',
 'file':'tools/followup_host.py','line':469,'related_lines':[468,469,470],
 'trigger':'Execute documented python tools/followup_host.py serve --enable-dispatch --host-factory valid_factory:create; valid_factory normally imports FollowupHost from followup_host and returns an explicitly enabled real host/controller/authority. Empty stdin is sufficient.',
 'expected':'Valid explicitly enabled trusted factory is accepted; empty serve input exits0 without reading Registry attempts or dispatching.',
 'actual':'Both script and python -m followup_host launch create a distinct __main__.FollowupHost. The valid factory returns followup_host.FollowupHost. Exact type identity comparison fails; argparse exits2 before serve/clock assignment.',
 'independent_control':'The identical factory called through canonical Python import exits0 and prints True followup_host. Imported product.main with the identical fixture also succeeds and overrides the future factory clock; real CLI remains rejected.',
 'impact':'The new documented enabled stdio/CLI deployment path cannot start with normal import-based factories, blocking executable host integration in that scope. Default off and canonical Python API remain usable;this is not a permission bypass or evidence of cloud execution.',
 'minimal_reproducer':'python -B stdio_agent/minimal_cli_factory_repro.py source',
 'minimum_expected_exit':0,'minimum_actual_cli_exits':{'script':2,'module':2},'minimum_script_assertion_exit':1,
 'minimal_fix':'Give the host/controller authority types one canonical import identity and keep a thin executable wrapper, or otherwise make the documented factory import path share that identity before loading factories. Retain strict enabled/controller/authority validation and default-off gating;do not accept arbitrary duck types or require an undocumented __main__ workaround.',
 'required_regressions':['Actual subprocess enabled script serve and module serve with an ordinary import-based valid factory and stdin EOF return0.','Actual enabled plan/serve against a private already-pending attempt preserves UTC override,discovery/response/restart paths.','Malformed/incompatible/disabled factory remains rejected;default-off does not import factory or open Registry.','Preserve both current product failure expectations and minimum failure when reviewing the repaired newSHA.']}
report={
 'reviewed_source_commit':'2d1d3060dbc7eb136c1dee61f0647977528b8aad','materials_commit':'fe088461e84586d7feb73f20be54a22d09706942',
 'scope':'Independent CLI/stdin/response boundary and public Python API checks;private synthetic Registry only.',
 'environment':{'platform':platform.platform(),'python':sys.version,'executable':sys.executable},
 'actually_executed':True,
 'first_execution':{'methods':first['methods'],'failure_records':len(first['failures']),'error_records':len(first['errors']),'skips':len(first['skips']),'completed_named_scenarios':first['named_scenarios'],'exit_code':1},
 'corrected_execution':{'methods':15,'passed_methods':13,'failed_methods':2,'failure_records':len(current['failures']),'error_records':len(current['errors']),'skips':len(current['skips']),'completed_named_scenarios':57,'exit_code':1},
 'supplement_first_execution':{'methods':4,'passed_methods':4,'failures':0,'errors':0,'skips':0,'named_scenarios':12,'exit_code':0},
 'distinct_method_total':19,'passed_methods':17,'failed_methods':2,'completed_successful_named_scenarios':69,
 'counting':'Methods/subscenarios/subprocesses and repeated first/corrected executions overlap.57+12 are successfully completed named scenarios, not all expected positiveCLI steps;two CLI methods are blocked before their downstream steps. Minimal two-mode checker is additional overlapping reproduction,not two extra unit methods.',
 'reviewer_correction':{'size_fixture':'Initial direct-API probe used400000 Chinese chars;canonical_json ensure_ascii=False is about1.2MB and is below2MiB. Corrected independently authored stimulus to700000 chars exceeding2MiB;production/expected gate unchanged.','failed_CLI_parser_followon':'Initial restart method attempted JSON parse after actual exit2,causing JSONDecodeError. Added an explicit expected0 return-code assertion before parsing;the same product rejection remains a failure.','files':['first_script.py','first_results.json','first.stdout','first.stderr','first_subprocess_records.json']},
 'coverage_passed':['Actual default-off script plan/serve never imports supplied factory or touches private store;no controller property access in disabled Python instance.','ActualCLI rejects missing enable factory/malformed factory selector/--now;strict JSON duplicate keys,NaN/Infinity/nesting,unknown fields and authority proposals redact to closed statuses.','Framing covers unterminated input,UTF8 byte overflow,character truncated tail stop andmultiple complete frames;direct API oversize before store access preserves durable original request.','Exact correlation/tool/page/boolean-page/arguments/message shape rejects;identical accepted and rejected responses add no event;conflicts fail closed.','Wrong attempt cannot bind foreign stream;native carrier conflicts/consistent unknown project data reject without raw storage.','Directory Completed with no trusted read grant cannot dispatch;permitted read onlyawaiting_native_receipt and original Registry journal unchanged.','Native completed result identity/type/progress/status and runtime-error shape boundaries;native statistics/error sentinel values are never persisted or echoed.','Calling main through canonical Python import is a passing control for validfactory andreal UTC clock override;this does not waive the actual enabled CLI failure.'],
 'findings':[finding],
 'verdict':'failed_for_enabled_CLI_stdio_factory_scope_WR29;other actually executed protocol/Python scopes passed',
 'unverified':['Actual enabled subprocess discovery/restart/response loop and its factory-clock override cannot be certified untilWR29 fixed;the first request is blocked.','No real MCP transport,production factory,live scheduling/native notification transfer,cloud execution or financial evaluation.','No claim of remote provenance authentication or comprehensive hostile filesystem/power-loss durability.'],
 'source_guard':{'source_files_checked':len(maps['source']['files']),'changed':changed,'source_write_attempts':0},
 'external_calls':{'QC':0,'Research':0,'LEAN':0,'compile':0,'market':0,'model':0},'authoritative_budget_or_production_writes':0,'financial_evidence':False,
 'artifacts':{'scripts':['independent_stdio.py','supplement_stdio.py','minimal_cli_factory_repro.py'],'execution_records':'execution_records.json','actual_subprocess_frames':'subprocess_records.json','first_subprocess_frames':'first_subprocess_records.json','minimum_stdout':'minimal.stdout','minimum_stderr':'minimal.stderr'}
}
assert not changed
(D/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'sha256':sha256((D/'report.json').read_bytes()).hexdigest(),'methods':19,'passed':17,'failed':2,'completed_successful_scenarios':69,'source_files_checked':len(maps['source']['files'])}))
