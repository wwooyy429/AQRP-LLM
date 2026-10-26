from pathlib import Path
from hashlib import sha256
import json
root=Path(__file__).resolve().parent
data=json.loads((root/'first_results.json').read_text(encoding='utf-8'))
verified={}
for name,value in data['observations'].items():
    if name.startswith('thread_') or name=='cli_mixed_race':
        rejected=[x for x in value if x['kind']=='rejected']
    elif name.startswith('process_'):
        rejected=[x['outcome'] for x in value['answers'] if x['outcome']['kind']=='rejected']
    else:continue
    expected={'RegistryError','EngineeringTaskError'} if 'project' in name else {'BudgetExceeded'}
    assert len(rejected)==1 and rejected[0]['error'] in expected,(name,rejected)
    verified[name]=rejected[0]
report={
 'commit':data['commit'],'verdict_in_tested_scope':'No confirmed new admission/occupancy bypass found.',
 'methods':data['methods'],'passed_methods':data['passed_methods'],'subcases':data['subcases'],
 'failed_methods':data['failed_methods'],'error_methods':data['error_methods'],'skipped':data['skipped'],
 'first_output':'first_output.txt','first_results':'first_results.json','original_script':'independent_admission.py',
 'command':data['command'],'minimal_failing_reproduction':None,'confirmed_new_findings':[],
 'verified_race_rejections':verified,
 'source_locations':data['source_locations'],
 'evidence':[
  'Six mixed thread races cover registration remaining-one-slot, Research remaining-one-slot and same-project open-work exclusion, for Memory and separate FilesystemArtifactStore instances. Each observed exactly one grant and one expected refusal.',
  'Three separate Windows spawn-process races use readiness messages plus a shared release event. Each observed exactly one grant and one expected refusal. Both successful debits and refusing predicates were read back from the event-sourced ledger.',
  'An actual metadata CLI temporary workspace freezes/registers a collection task and races its claim against an old Bridge explicit repair. CLI ROOT and research ROOT point only to that audit workspace. Synthetic source-manifest discovery is injected, while real CLI branches, source/deployment binding, Registry opening and export_usage run unchanged.',
  'Open started/pending/ambiguous work prevents new same-project collection registration before configuration charging. Both task directions and old Research/LEAN occupied stages prevent new same-project attempt charges through Bridge and direct Registry.',
  'Retry bounds zero/one/two, wrong or missing retry identity/reason, fixed Research operation, forbidden LEAN, reserved schema mutations, allocation switching, rename and restart do not reset charges. Failures remain charged; unknown submissions remain ambiguous and do not call adapters twice.',
  'A completed collection logical operation can still be reused/read free while the other registered task occupies the same project; reuse never returns should_execute=True.',
  'Source audit/runtime files were copied byte-for-byte into MemoryArtifactStore only. Existing 6/9/1 usage replayed as 6/9/1; same-project pending rejected a new collection registration; a different-project collection consumed the one remaining engineering configuration and Research slots, giving 7/10/1 in this isolated copy only.',
  'Global Research initial usage 19 still allowed only one remaining global charge, ending 20; a second engineering attempt was rejected despite a remaining engineering-domain slot.'
 ],
 'static_reasoning':{
  'register':'registry.py:268-282 encodes identity then performs collection project protection, engineering configuration cap, global charge and journal publication under Registry.LOCK.',
  'candidate_validation':'registry.py:285-326 preserves the reserved collection shape and validates its frozen canonical plan when callers bypass the Bridge.',
  'project_and_cap':'registry.py:328-372 checks all old/new engineering open states and counts every engineering registration/attempt, across normal and reserve allocations.',
  'attempt':'registry.py:461-505 validates fixed collection operation, handles free existing-operation reuse, then checks project, retry, engineering cap and global charge before persisting attempt_started.',
  'new_bridge':'collection_tasks.py uses the existing engineering marker, Registry, payload/evidence/transition machinery; its claim calls Registry directly, with no separate counter.'
 },
 'limits':['This is local metadata/accounting evidence, not actual provider or platform execution.',
           'Process coverage is cooperating Windows processes sharing the same physical local ledger; no cross-node ObjectStore CAS is claimed.',
           'Full worker/completion verification and actual deployment/source readbacks are assigned separately.',
           'No production ledger/budget/configuration/source file was modified; no SDK, market, model, project or task operation was called.'],
 'observations':data['observations'],
 'artifact_sha256':{p.name:sha256(p.read_bytes()).hexdigest() for p in root.glob('*') if p.is_file() and p.name!='review_report.json'}
}
(root/'review_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'methods':data['methods'],'subcases':data['subcases'],'race_rejections_verified':len(verified),'new_findings':0}))
