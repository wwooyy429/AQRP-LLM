from pathlib import Path
import hashlib,importlib.util,json,os,runpy,subprocess,sys,time
OUT=Path(__file__).resolve().parent
SOURCE=OUT/'fixed_source'
ENV=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
if len(sys.argv)>1 and sys.argv[1]=='child':
    _,_,case,attempt,command,gate,ready,*extra=sys.argv
    Path(ready).write_text('ready',encoding='ascii')
    deadline=time.monotonic()+30
    while not Path(gate).exists():
        if time.monotonic()>deadline:raise TimeoutError('Synthetic process gate did not open')
        time.sleep(.01)
    sys.argv=[str(Path(case)/'tools/stage2.py'),command,'--attempt',attempt,*extra]
    sys.path.insert(0,str(Path(case)/'tools'))
    runpy.run_path(str(Path(case)/'tools/stage2.py'),run_name='__main__')
    raise SystemExit(0)

runner=OUT/'fixed_runner/independent_recovery_support.py'
sys.argv=[str(runner),'--source',str(SOURCE),'--out',str(OUT/'process_prepare')]
spec=importlib.util.spec_from_file_location('wr23_process_support',runner);h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
case,listing=h.fresh('two-process-first-prepare')
h.okay(h.invoke(case,['freeze','--plan-file','config/independent-v2.json','--projects-file',listing],'freeze'))
h.okay(h.invoke(case,['register'],'register'))
attempt=h.okay(h.invoke(case,['claim','--stage','research'],'claim'))['attempt_id']
registry=h.registry(case);usage=registry.snapshot()['usage'];journal=case/'audit/runtime/registry/events.jsonl';journal_before=journal.read_bytes()

def race(command,extra=()):
    label=OUT/'process_prepare'/command;label.mkdir()
    gate=label/'gate';children=[]
    for i in range(2):
        ready=label/('ready'+str(i));cmd=[sys.executable,'-B',str(Path(__file__).resolve()),'child',str(case),attempt,command,str(gate),str(ready),*map(str,extra)]
        p=subprocess.Popen(cmd,cwd=case,env=ENV,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        children.append((p,ready,cmd))
    deadline=time.monotonic()+30
    while not all(ready.exists() for _,ready,_ in children):
        if time.monotonic()>deadline:raise TimeoutError('Both Windows children did not reach barrier')
        time.sleep(.01)
    gate.write_text('go',encoding='ascii')
    values=[];records=[]
    for i,(p,ready,cmd) in enumerate(children):
        stdout,stderr=p.communicate(timeout=45)
        (label/(str(i)+'.stdout')).write_bytes(stdout);(label/(str(i)+'.stderr')).write_bytes(stderr)
        records.append({'command':cmd,'exit_code':p.returncode,'stdout_sha256':hashlib.sha256(stdout).hexdigest(),'stderr_sha256':hashlib.sha256(stderr).hexdigest()})
        assert p.returncode==0,stderr.decode('utf-8',errors='replace')
        values.append(json.loads(stdout))
    return values,records

admissions,prepare_records=race('prepare')
assert admissions[0]==admissions[1]
admission=admissions[0];assert 'research_entry_protocol' in admission
store=registry.store;entry=store.read_bytes('engineering/research-entry-protocol/'+attempt+'.json')
assert entry==h.canonical_json(admission['research_entry_protocol'])
assert store.read_bytes(h.admission_key(attempt))==h.canonical_json(admission)
text='TASK_INPUT_JSON = '+repr(h.canonical_json(admission['payload']).decode('utf-8'))+'\n'
assert (case/admission['input_path']).read_bytes()==text.encode('utf-8')
cell=h.okay(h.invoke(case,['research-cell','--attempt',attempt],'read-fixed-cell'))['source']
tool=case.parent/'synthetic-read-cell.json';h.dump(tool,{'tool_name':'mcp__quantconnect__jupyter_read_cell',
    'arguments':{'projectId':admission['payload']['identity']['project_id'],'index':4},
    'result':{'structuredContent':{'cellType':'code','source':cell.splitlines(keepends=True)}}})
permits,dispatch_records=race('research-dispatch',['--tool-file',str(tool)])
assert sum(p['should_execute'] for p in permits)==1
assert registry.snapshot()['usage']==usage and journal.read_bytes()==journal_before
report={'actual_Windows_processes':4,'first_prepare_competing_processes':2,'dispatch_competing_processes':2,
    'prepare_admissions_identical':True,'input_admission_entry_complete_and_consistent':True,
    'dispatch_permission_count':1,'usage_and_journal_unchanged':True,'prepare_records':prepare_records,
    'dispatch_records':dispatch_records,'new_QC_calls':0,'new_authoritative_budget_writes':0,'independent_acceptance':False}
(OUT/'process_prepare_summary.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report))
