from pathlib import Path
from hashlib import sha256
import json, platform, sys
sys.dont_write_bytecode=True
O=Path(__file__).resolve().parent;R=O.parent
def read(name):return json.loads((O/name).read_text(encoding='utf-8'))
first=read('first_results_preserved.json');fixed=read('corrected_results.json');supp=read('supplement_results.json')
assert not fixed['errors'] and not fixed['failures'] and not supp['errors'] and not supp['failures']
maps=json.loads((R/'source_git_manifest.json').read_text(encoding='utf-8'))
guard={}
for folder,item in maps.items():
    changed=[name for name,value in item['files'].items() if sha256((R/folder/name).read_bytes()).hexdigest()!=value['sha256']]
    guard[folder]={'files':len(item['files']),'changed':changed}
    assert not changed,folder
records=[
 {'command':[sys.executable,'-B',str(O/'independent_host_api.py')],'first_script_preserved_as':'first_script.py','exit_code':1,'stdout':'first.stdout','stderr':'first.stderr','result':'first_results_preserved.json','classification':'reviewer API-call fixture error: used invalid orders_envelope keyword and wrong parser/Bridge call signatures'},
 {'command':[sys.executable,'-B',str(O/'independent_host_api.py')],'exit_code':0,'stdout':'corrected.stdout','stderr':'corrected.stderr','result':'corrected_results.json'},
 {'command':[sys.executable,'-B',str(O/'supplement_host_api.py')],'exit_code':0,'stdout':'supplement.stdout','stderr':'supplement.stderr','result':'supplement_results.json'}]
(O/'execution_records.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
report={
 'source_commit':'2d1d3060dbc7eb136c1dee61f0647977528b8aad','materials_commit':'fe088461e84586d7feb73f20be54a22d09706942',
 'scope':'Independent Python FollowupHost API, trusted transport grants, at-most-once synthetic dispatch and original parser/Bridge/Registry chain. No developer test fixtures imported.',
 'environment':{'os':platform.platform(),'python':sys.version,'executable':sys.executable},
 'actually_executed':True,'distinct_methods':18,'named_scenarios':89,
 'main_corrected':{'methods':12,'named_scenarios':63,'failures':0,'errors':0,'skips':0},
 'supplement_first_run':{'methods':6,'named_scenarios':26,'failures':0,'errors':0,'skips':0},
 'first_run_preserved':{'methods':12,'named_scenarios_completed':62,'failures':0,'errors':1,'skips':0,'cause':'Reviewer wrote backtest_observation with unsupported orders_envelope and omitted its original deployment/external_id arguments; fixed only to existing five-argument parser and Bridge completion_source protocol. Product and assertions unchanged.','script':'first_script.py','results':'first_results_preserved.json'},
 'findings':[],
 'verdict':'passed_for_independently_tested_local_Python_host_and_synthetic_chain_scope',
 'coverage':[
   'Default-off host never touches supplied bomb controller/store/authority; enabled must be exact bool. register/sync/status do not dispatch.',
   'Original pending+1800seconds at1microsecond before and exact deadline; discovery exactlypage1 once; unanswered reservation status/prepare/restart attention.',
   'Discovery/history require explicit attempt grants. Chat directoryCompleted does not grant read; exact attempt/project/backtest plus trusted evidence basis required. transport-completed basis denied in chat mode.',
   'Tool/correlation/arguments/bool-page/extra fields mismatches refused; identical rejected and accepted observations idempotent; conflicts stop.',
   'Invalid/duplicate/foreign project IDs and native failures deny dispatch; target running/queued, missing page count, changed pagination and threepage exhaustion stop.',
   'Actual production functions: accepted synthetic LEAN→host project discovery→three bounded pages→one trusted read→awaiting_native_receipt without Registry success→original native-shaped backtest_observation with500byte zero-based AQRP logs and native Total Orders0→Bridge completion→Registry→watch sync.',
   'Native raw/synthetic finance sentinels absent from host/watch events; host read is only handoff, no financial evidence or market rows.',
   'Client response-loss consumes reservation across new host instances; original late bound response allowed. Crash between controller and host reservations fails closed without reconstructed request.',
   '24thread discovery and24thread completed-read attempts each yieldone request; six native Windows processes each makethree requests (18total) yieldone request and unchanged Registry journal.',
   'Wrong/boolean project, wrong backtest, noncompleted, wrongprogress, running, unknown top-level and conflicting carrier completed responses refuse without settlement. RuntimeError native success anderror-envelope variants only await receipt, not Registry success.',
   'Late independently parsed true Registry completion dominates unknown host response; subsequent original discovery cannot reopen or change Registry.',
   'Independently rehashed altered host-bound attempt/project/backtest/deadline streams refuse before dispatch.'
 ],
 'process_scope':{'native_Windows_processes':6,'requests_each':3,'dispatch_permissions':1,'thread_discovery_requests':24,'thread_discovery_permissions':1,'thread_read_requests':24,'thread_read_permissions':1,'counts_are_contained_scenarios_not_extra_methods':True},
 'production_locations':[{'file':'tools/followup_host.py','line':103,'symbol':'TransportAuthority'},{'file':'tools/followup_host.py','line':130,'symbol':'permits_read'},{'file':'tools/followup_host.py','line':247,'symbol':'inspect'},{'file':'tools/followup_host.py','line':265,'symbol':'prepare'},{'file':'tools/followup_host.py','line':327,'symbol':'accept_response'},{'file':'tools/followup_host.py','line':417,'symbol':'run_once'},{'file':'cloud/qresearch/engineering_receipts.py','line':732,'symbol':'backtest_observation'}],
 'source_guard':guard,'cloud_calls':0,'market_model_or_compile_calls':0,'authoritative_budget_or_production_writes':0,
 'trust_boundary':'TransportAuthority/ReadGrant supplied by a separately trusted Python factory and client are inputs, not cryptographic remote authentication. Synthetic evidence hashes and fixtures do not prove a real notification or human authorization. Arbitrary privileged rewrites of the store are outside this bounded local claim.',
 'unverified':['No actual installed production factory/transport, MCP host, native notification delivery or real timeout reconciliation exercised.','No hard OS kill/power-loss/all filesystem-race durability certification; storage failure injection and ordinary process exit/restart covered.','No full automatic receipt/log/order collection or native cloud deployment; manual synthetic fixed-parser handoff only.','No live market data, complete US200/financial certification, full stage2 or stages3-7/financial acceptance.','Stdio framing/JSON line encoding is delegated to the separate stdio reviewer and is not counted here.'],
 'financial_evidence':False,'artifacts':['independent_host_api.py','supplement_host_api.py','first_script.py','first_results_preserved.json','corrected_results.json','supplement_results.json','first.stdout','first.stderr','corrected.stdout','corrected.stderr','supplement.stdout','supplement.stderr','first_process_outputs','process-*.stdout','process-*.stderr','execution_records.json']}
(O/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'report_sha256':sha256((O/'report.json').read_bytes()).hexdigest(),'methods':18,'scenarios':89,'source_files':guard['source']['files'],'source_changed':False}))
