from pathlib import Path
import hashlib,json,os,shutil,subprocess,sys,time
R=Path(__file__).parent;O=R/'entry_additional';O.mkdir(exist_ok=False)
for name in ['quick_joint_probes.py','independent_cli_gates.py']:shutil.copyfile(R/'entry_agent'/name,O/name)
sys.path.insert(0,str(O));import independent_cli_gates as f
from qresearch.artifacts import FilesystemArtifactStore
from qresearch.registry import Registry
ENV=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
observations=[];parallel=[]
def setup(tag):
    case=f.case(2,tag);a=f.prefix(case,'prepare');adm=f.accepted(f.cli(case,'prepare','--attempt',a))
    cell=f.accepted(f.cli(case,'research-cell','--attempt',a))
    native={'tool_name':'mcp__quantconnect__jupyter_read_cell','arguments':{'projectId':adm['payload']['identity']['project_id'],'index':3},'result':{'cellType':'code','source':cell['source'].splitlines(keepends=True)}}
    tool=case/'read-cell.json';f.dump(tool,native);return case,a,adm,tool,native
def files(case):return{p.relative_to(case).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()for p in case.rglob('*')if p.is_file()}
case,a,adm,tool,native=setup('two-process-permit')
before=(case/'audit/runtime/registry/events.jsonl').read_bytes();usage=(case/'config/budget.json').read_bytes()
cmd=[sys.executable,'-B',str(case/'tools/stage2.py'),'research-dispatch','--attempt',a,'--tool-file',str(tool)]
procs=[subprocess.Popen(cmd,cwd=case,env=ENV,stdout=subprocess.PIPE,stderr=subprocess.PIPE)for _ in range(2)]
results=[]
for i,p in enumerate(procs):
    stdout,stderr=p.communicate(timeout=60);(O/('parallel'+str(i)+'.stdout')).write_bytes(stdout);(O/('parallel'+str(i)+'.stderr')).write_bytes(stderr)
    parallel.append({'command':cmd,'cwd':str(case),'exit_code':p.returncode,'stdout_sha256':hashlib.sha256(stdout).hexdigest(),'stderr_sha256':hashlib.sha256(stderr).hexdigest()});assert p.returncode==0,stderr;results.append(json.loads(stdout))
assert sum(x['should_execute']is True for x in results)==1 and sum(x['should_execute']is False for x in results)==1
assert before==(case/'audit/runtime/registry/events.jsonl').read_bytes()and usage==(case/'config/budget.json').read_bytes()
native['arguments']['index']=4;f.dump(tool,native);unchanged=files(case)
assert f.cli(case,'research-dispatch','--attempt',a,'--tool-file',tool).returncode!=0 and files(case)==unchanged
observations.append({'probe':'two actual Windows processes: one permission; retarget refused','passed':True})
case,a,adm,tool,native=setup('unknown-before-permission')
store=FilesystemArtifactStore(case/'audit/runtime');registry=Registry(store,json.loads(store.read_bytes('registry/baseline.json')));registry.ambiguous(a,reason='Independent synthetic unknown dispatch outcome')
unchanged=files(case);assert f.cli(case,'research-dispatch','--attempt',a,'--tool-file',tool).returncode!=0 and files(case)==unchanged
observations.append({'probe':'unknown prior outcome does not acquire a first permission','passed':True})
case,a,adm,tool,native=setup('existing-admission-no-backfill')
marker=case/('audit/runtime/engineering/research-entry-protocol/'+a+'.json');marker.unlink()
unchanged=files(case);assert f.accepted(f.cli(case,'prepare','--attempt',a))==adm and not marker.exists()and files(case)==unchanged
assert f.cli(case,'research-dispatch','--attempt',a,'--tool-file',tool).returncode!=0 and files(case)==unchanged
observations.append({'probe':'old admission restoration does not backfill entry protocol','passed':True})
result={'fixed_commit':'deb85d9f27441b275ab8b108f0232ecd2707a1e8','manual_probe_chains':3,'passed':3,'unit_methods':0,'ordinary_CLI_processes':len(f.COMMANDS),'parallel_CLI_processes':2,'actual_QC_market_model_worker_calls':0,'observations':observations}
(O/'results.json').write_bytes((json.dumps(result,indent=2)+'\n').encode());(O/'commands.json').write_bytes((json.dumps({'ordinary':f.COMMANDS,'parallel':parallel},indent=2)+'\n').encode());print(json.dumps(result))
