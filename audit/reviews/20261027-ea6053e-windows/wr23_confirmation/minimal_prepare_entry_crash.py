"""Independent prepare write-gap counterexample; synthetic store only."""
import hashlib,importlib.util,json,sys
from unittest.mock import patch
import independent_recovery_support as h

case,listing=h.fresh('prepare-entry-write-gap')
h.okay(h.invoke(case,['freeze','--plan-file','config/independent-v2.json','--projects-file',listing],'gap-freeze'))
h.okay(h.invoke(case,['register'],'gap-register'))
attempt=h.okay(h.invoke(case,['claim','--stage','research'],'gap-claim'))['attempt_id']
registry=h.registry(case);record=next(row for row in registry.snapshot()['attempts'] if row['attempt_id']==attempt)
package=json.loads(registry.store.read_bytes('configurations/'+record['config_id']+'.json'))
plan=h.EngineeringTaskPlan.from_dict(package['plan'],discovered_project_ids=(package['plan']['project_id'],))
bridge=h.EngineeringTaskBridge(registry,plan)
sys.path.insert(0,str(case/'tools'));spec=importlib.util.spec_from_file_location('independent_stage2_gap',case/'tools/stage2.py')
stage=importlib.util.module_from_spec(spec);spec.loader.exec_module(stage)
entry='engineering/research-entry-protocol/'+attempt+'.json';dispatch='engineering/research-dispatch/'+attempt+'.json'
write=registry.store.write_once;order=[]
class InjectedWriteFailure(RuntimeError):pass
def writing(key,data):
    order.append(key)
    if key==entry:raise InjectedWriteFailure('Research entry marker write failed')
    return write(key,data)
try:
    with patch.object(registry.store,'write_once',side_effect=writing):stage.prepare(bridge,attempt)
except InjectedWriteFailure:pass
else:raise AssertionError('Expected actual protocol-write injection')
assert registry.store.exists(h.admission_key(attempt)) and not registry.store.exists(entry)
admission=h.okay(h.invoke(case,['prepare','--attempt',attempt],'gap-recover-prepare'))
assert not registry.store.exists(entry) and not registry.store.exists(dispatch)
context={'case':case,'attempt':attempt,'admission':admission}
native=h.envelopes(context,admission,'research');before=registry.snapshot();files_before=h.files(case)
response=h.invoke(case,['research-result','--attempt',attempt,'--tool-file',native['result']],'gap-unbound-success')
after=registry.snapshot();completed=json.loads(response.stdout) if response.returncode==0 else None
lean=h.invoke(case,['claim','--stage','lean'],'gap-downstream-lean') if completed is not None else None
report={'commit':'ea6053e3e9ef4be17db246daf18a4cf9b2e5be58','boundary':'actual first prepare admission-write then entry-marker-write exception',
    'write_order':order,'admission_persisted':True,'entry_after_recovery':registry.store.exists(entry),'dispatch_exists':registry.store.exists(dispatch),
    'unbound_result_exit':response.returncode,'unbound_status':None if completed is None else completed['status'],
    'ledger_usage_before':before,'ledger_after_result':after,'files_changed_by_result':files_before!=h.files(case),
    'downstream_lean_exit':None if lean is None else lean.returncode,
    'downstream_lean':None if lean is None or lean.returncode else json.loads(lean.stdout),'stats':h.STATS,
    'actual_provider_calls':0,'authoritative_ledger_writes':0}
(h.OUT/'results.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
(h.OUT/'command_log.json').write_text(json.dumps(h.LOG,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
assert response.returncode!=0,'A new admission whose entry-marker write failed was reclassified as legacy and completed without dispatch'
