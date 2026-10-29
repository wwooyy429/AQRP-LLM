from pathlib import Path
import hashlib,json,platform,sys
R=Path(__file__).resolve().parent
first=json.loads((R/'first_results_preserved.json').read_text())
fixed=json.loads((R/'corrected_results.json').read_text())
extra=json.loads((R/'supplement_results.json').read_text())
records=[
 {'command':[sys.executable,'-B',str(R/'first_script.py')],
  'historical_command_executed_path':str(R/'independent_notifications.py'),
  'exit_code':1,'stdout':'first.stdout','stderr':'first.stderr','result':'first_results_preserved.json',
  'classification':'reviewer fixture malformed log chunks; protocol requires zero-based indexes and 500-byte non-final chunks, fixture used 1-based and400. No product edits.'},
 {'command':[sys.executable,'-B',str(R/'independent_notifications.py')],
  'exit_code':0,'stdout':'corrected.stdout','stderr':'corrected.stderr','result':'corrected_results.json'},
 {'command':[sys.executable,'-B',str(R/'supplement_notifications.py')],
  'exit_code':0,'stdout':'supplement.stdout','stderr':'supplement.stderr','result':'supplement_results.json'}]
(R/'execution_records.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
report={
 'reviewed_source_commit':'975f676d62b561689909744f9e7236290e3f5fcb',
 'materials_commit':'a6a5a165d87c172535cdea6cf495e3c1a850e6e4',
 'scope':'Independent bounded notification recovery, native-shaped metadata parsers and original Bridge/Registry settlement; synthetic data only.',
 'environment':{'os':platform.platform(),'python':sys.version,'executable':sys.executable},
 'actually_executed':True,
 'first_execution':{'methods':first['methods'],'failures':first['failures'],'errors':first['errors'],'skips':first['skips'],
   'named_scenarios_completed':first['named_scenarios'],'product_defects':0,
   'reviewer_fixture_error':'Log chunks independently authored with400bytes/1-based instead of existing500bytes/0-based protocol; first_script.py and outputs preserved.'},
 'corrected_execution':{k:fixed[k] for k in ['methods','failures','errors','skips','named_scenarios']},
 'supplement_first_execution':{k:extra[k] for k in ['methods','failures','errors','skips','named_scenarios']},
 'distinct_method_total':18,'named_scenario_total':106,
 'counts_do_not_include_as_extra_methods':'6 Windows processes/18 concurrent requests and24-thread history+24-thread completed-read requests are contained scenarios, not independent test methods. First and corrected executions overlap.',
 'cross_module_chain':'Independent pre-resolved EngineeringTaskPlan -> synthetic Research Bridge submission and completion -> accepted LEAN Registry pending -> follow-up3pages -> one reserved native completed read -> production backtest_observation parser with exact sameattempt native-shaped chunks/zero orders -> Bridge.consume_completion -> Registry.complete -> followup.sync. Separate RuntimeError flow fails sameattempt without refund.',
 'coverage':[
  'Strict policy, original pending timestamp1800second boundary incl1microsecond either side, UTCoffset equivalence, invalid/naive/backward clock, no CLI clock override.',
  'Actual-shaped project listing strict IDs, duplicates and carrier conflicts; no project discovery and foreign project deny dispatch.',
  'One reconciliation/at most3pages; page continuation requires original pagination evidence. Missing/error/running/queue/unknown and outstanding responses remain attention without redispatch after restart.',
  'Terminal summary alone leaves Registry pending and unchanged; reserved completed read onlyonce with24concurrent callers.',
  'Native completion rejects wrong project/backtest/attempt/source, missing logs and nonzero orders. Stored follow-up evidence excludes synthetic net-profit sentinel.',
  '24thread history requests1permit; native Windows6processes18requests across independent stores1permit, no Registry journal change.',
  'Durable reservation crash before/after append, original late response, write-watch failure, metadata register/sync/status no permissions, original pending deadline retained.',
  'Rehashed event tampering project/attempt/source/config/backtest/deadline/policy/unknown fields/pages/kinds/finished and clocks fails closed; identical observation idempotent/conflicting response rejected.'
 ],
 'findings':[],
 'verdict':'passed_for_actually_tested_local_software_scope',
 'not_verified':[
  'No production MCP host dispatch/scheduling/notification delivery, automatic push or live timeout reconciliation was exercised.',
  'Synthetic trusted metadata dispatcher boundary remains; no cryptographic native-source provenance claim.',
  'No live market/financial data, financial validity or full stage2 acceptance.',
  'OS kill/power loss and all filesystem races not exhaustively certified.'
 ],
 'cloud_calls':0,'market_calls':0,'model_calls':0,'authoritative_budget_writes':0,
 'source_or_materials_writes':0,
 'evidence_files':['execution_records.json','first_script.py','first.stdout','first.stderr','first_results_preserved.json',
  'first_process_outputs','independent_notifications.py','corrected.stdout','corrected.stderr','corrected_results.json',
  'process-0.stdout','process-1.stdout','process-2.stdout','process-3.stdout','process-4.stdout','process-5.stdout',
  'supplement_notifications.py','supplement.stdout','supplement.stderr','supplement_results.json'],
}
(R/'report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps({'report':str(R/'report.json'),'sha256':hashlib.sha256((R/'report.json').read_bytes()).hexdigest(),
 'methods':18,'named_scenarios':106,'findings':[]},indent=2))
