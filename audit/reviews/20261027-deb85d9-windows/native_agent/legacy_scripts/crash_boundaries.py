"""Four additional fault-injection probes; no unit methods or real process kill."""
import hashlib,importlib.util,json,shutil,sys,traceback
from unittest.mock import patch
import independent_recovery_support as h
from qresearch.engineering_receipts import backtest_submission

AGENT=h.OUT.parent;PROBES=[]
class InjectedCrash(RuntimeError):pass

def case(label,version=2):
    template=AGENT/'main/cases'/('native-base-v'+str(version))/'source'
    target=h.OUT/'cases'/label/'source';shutil.copytree(template,target,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    registry=h.registry(target);record=next(item for item in registry.snapshot()['attempts'] if item['stage']=='lean')
    attempt=record['attempt_id'];admission=json.loads(registry.store.read_bytes(h.admission_key(attempt)))
    plan=h.EngineeringTaskPlan.from_dict(admission['payload']['plan'],discovered_project_ids=(admission['payload']['identity']['project_id'],))
    return {'case':target,'registry':registry,'bridge':h.EngineeringTaskBridge(registry,plan),'attempt':attempt,'admission':admission,
        'accepted_native':template.parent/'native/submission.json'}

def state(c):return next(row for row in c['registry'].snapshot()['attempts'] if row['attempt_id']==c['attempt'])
def key(c):return 'engineering/submission-protocol/'+c['attempt']+'.json'
def reject(c,label):
    manifest=c['admission']['payload']['deployment_manifest'];source_name=sorted(manifest)[0]
    native={'tool_name':'mcp__quantconnect__create_backtest','arguments':{'projectId':c['admission']['payload']['identity']['project_id'],
        'backtestName':'independent-crash-boundary'},'result':{'success':False,'errors':{source_name:['1:1 SYNTHETIC-CRASH-DIAGNOSTIC']}}}
    path=c['case'].parent/'rejection.json';h.dump(path,native)
    before=h.files(c['case']);r=h.invoke(c['case'],['backtest-rejection','--attempt',c['attempt'],'--tool-file',path],label)
    assert r.returncode!=0 and h.files(c['case'])==before
    return r.stderr.decode('utf-8',errors='replace').splitlines()[-1]

def accepted_fault(boundary):
    c=case(boundary);reg=c['registry'];store=reg.store;usage=reg.snapshot()['usage'];events=store.read_bytes('registry/events.jsonl');order=[]
    observed=backtest_submission(c['admission']['payload'],c['admission']['deployment'],json.loads(c['accepted_native'].read_bytes()))
    digest=h.content_hash(observed);original='engineering/evidence/'+c['attempt']+'/submission/'+digest+'.json'
    summary='engineering/submissions/'+c['attempt']+'.json'
    write=store.write_once;append=reg._append
    def writing(name,data):
        order.append(name)
        if boundary=='accepted_pointer_before_original' and name==original:raise InjectedCrash(boundary)
        return write(name,data)
    def appending(event):
        if boundary=='accepted_original_before_pending' and event['kind']=='pending':
            order.append('journal:pending');raise InjectedCrash(boundary)
        return append(event)
    with patch.object(store,'write_once',side_effect=writing),patch.object(reg,'_append',side_effect=appending):
        try:c['bridge'].record_submission(c['attempt'],observed)
        except InjectedCrash:pass
        else:raise AssertionError('Expected injected publication exception')
    assert store.exists(summary) and state(c)['status']=='started'
    assert store.exists(original)==(boundary=='accepted_original_before_pending')
    assert store.read_bytes('registry/events.jsonl')==events and reg.snapshot()['usage']==usage
    refusal=reject(c,boundary+'-rejection-refused');assert 'Accepted submission identities' in refusal
    restored=h.okay(h.invoke(c['case'],['backtest-submission','--attempt',c['attempt'],'--tool-file',c['accepted_native']],boundary+'-repair'))
    assert restored['status']=='pending' and store.read_bytes(original)==h.canonical_json(observed)
    assert reg.snapshot()['usage']==usage and state(c)['external_id']==observed['external_id']
    assert len(store.read_bytes('registry/events.jsonl').splitlines())==len(events.splitlines())+1
    return {'version':2,'write_order':order,'publication_pointer_present':True,
        'original_present_at_fault':boundary=='accepted_original_before_pending','pre_replay_state':'started',
        'rejection_error':refusal,'actual_CLI_repair':'pending','usage_unchanged':True,'one_pending_event_after_repair':True}

def load_stage(c):
    # The production tools use sibling module imports; isolate their module
    # roots for this copied source case without changing any source files.
    for name in ('research','stages','collection_task_cli','stage2_collection'):sys.modules.pop(name,None)
    sys.path.insert(0,str(c['case']/'tools'))
    spec=importlib.util.spec_from_file_location('independent_stage2_'+c['attempt'],c['case']/'tools/stage2.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def prepare_fault(boundary):
    c=case(boundary);reg=c['registry'];store=reg.store;attempt=c['attempt'];admission_key=h.admission_key(attempt)
    store._path(admission_key).unlink();store._path(key(c)).unlink();local=c['case']/c['admission']['input_path'];local.unlink()
    usage=reg.snapshot()['usage'];events=store.read_bytes('registry/events.jsonl');original=store.write_once;order=[]
    failed_key=admission_key if boundary=='prepare_input_before_admission' else key(c)
    def writing(name,data):
        order.append(name)
        if name==failed_key:raise InjectedCrash(boundary)
        return original(name,data)
    stage=load_stage(c)
    with patch.object(store,'write_once',side_effect=writing):
        try:stage.prepare(c['bridge'],attempt)
        except InjectedCrash:pass
        else:raise AssertionError('Expected injected prepare exception')
    assert local.exists() and not store.exists(key(c)) and state(c)['status']=='started'
    assert store.exists(admission_key)==(boundary=='prepare_admission_before_protocol')
    before=h.files(c['case'])
    recovered=h.okay(h.invoke(c['case'],['prepare','--attempt',attempt],boundary+'-recover'))
    assert recovered==c['admission'] and reg.snapshot()['usage']==usage and store.read_bytes('registry/events.jsonl')==events
    if boundary=='prepare_admission_before_protocol':
        assert not store.exists(key(c)) and h.files(c['case'])==before
        refusal=reject(c,boundary+'-rejection-refused')
    else:
        expected={'schema_version':1,'protocol':'accepted_identity_before_original_receipt_v1',
            'identity':c['admission']['payload']['identity'],'deployment':c['admission']['deployment']}
        assert store.read_bytes(key(c))==h.canonical_json(expected);refusal=None
    return {'version':2,'write_order':order,'local_input_present_at_fault':True,
        'admission_present_at_fault':boundary=='prepare_admission_before_protocol','marker_present_at_fault':False,
        'marker_after_recovery':store.exists(key(c)),'usage_journal_unchanged':True,'rejection_error':refusal,
        'meaning':'No returned admission before first write failure may be retried; an already persisted old admission never receives a backfilled marker.'}

for name in ('accepted_pointer_before_original','accepted_original_before_pending','prepare_input_before_admission','prepare_admission_before_protocol'):
    try:
        details=accepted_fault(name) if name.startswith('accepted') else prepare_fault(name)
        PROBES.append({'name':name,'passed':True,'details':details})
    except Exception:
        PROBES.append({'name':name,'passed':False,'traceback':traceback.format_exc()})
after={path:hashlib.sha256((h.ROOT/path).read_bytes()).hexdigest() for path in h.CHECK_FILES}
result={'commit':'66ff72ffaaff8c91c008898e6527c91131176c2a','unit_methods':0,'programs':1,'manual_probes':4,
    'passed':sum(item['passed'] for item in PROBES),'failed':sum(not item['passed'] for item in PROBES),
    'first_failure':next((item for item in PROBES if not item['passed']),None),'probes':PROBES,'stats':h.STATS,
    'source_and_authority_unchanged':h.BEFORE==after,'source_before':h.BEFORE,'source_after':after,
    'limits':'Synchronous injected exceptions at actual write_once and Registry._append boundaries; no OS kill, power-loss or storage-durability certification. All stores are copies of reviewer synthetic v2 fixture.'}
(h.OUT/'results.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
(h.OUT/'command_log.json').write_text(json.dumps(h.LOG,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps(result,indent=2,ensure_ascii=False))
sys.exit(0 if result['failed']==0 and result['source_and_authority_unchanged'] else 1)
