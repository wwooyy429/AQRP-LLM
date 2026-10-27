"""Rerun already accepted protocol suites against new immutable source."""
import hashlib,json,os,shutil,subprocess,sys,time
from pathlib import Path
R=Path(__file__).resolve().parent;P=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-ccad61d-20261027\protocol_agent');E=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-ea6053e-20261027\dispatch_agent');S=R.parent/'source'
ENV=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1');bindings=[]
def cp(src,dst):
    dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst);bindings.append({'source':str(src),'destination':str(dst.relative_to(R)),'sha256':hashlib.sha256(dst.read_bytes()).hexdigest(),'raw_equal':dst.read_bytes()==src.read_bytes()})
cp(P/'run_legacy.py',R/'run_legacy_original.py')
# This orchestration-only change avoids overwriting the common original helper
# with its historical setup adapter while parallel independent suites import it.
raw=(R/'run_legacy_original.py').read_bytes();new=raw.replace(b"shutil.copy2(OLD/'legacy_adapted_scripts/independent_recovery_support.py',R/'independent_recovery_support.py')",b"# Each native script imports its own unchanged accepted setup helper.")
(R/'run_legacy.py').write_bytes(new)
cp(P/'protocol_boundaries.py',R/'protocol_boundaries.py');cp(E/'independent_recovery_support.py',R/'independent_recovery_support.py')
d=R/'wr23_original'
for name in ('minimal_prepare_entry_crash.py','independent_recovery_support.py'):cp(E/name,d/name)
d=R/'wr21_explicit_legacy'
for name in ('minimal_new_success_without_dispatch.py','independent_cli_gates.py','independent_wr16_boundaries.py','quick_joint_probes.py','fixture.diff'):cp(P/'wr21/legacy_shape_adapter'/name,d/name)
cp(P/'wr21/legacy_shape_adapter/launch.py',d/'launch_original.py')
(d/'launch.py').write_bytes(b"import sys,runpy,json\nfrom pathlib import Path\ns=Path(sys.argv[1]).resolve();folder=Path(__file__).parent\nsys.path[:0]=[str(s/'cloud'),str(s/'tools'),str(folder)]\nimport quick_joint_probes as h,independent_cli_gates as f\nf.SOURCE=s;h.SOURCE=s\ntry:\n runpy.run_path(str(folder/'minimal_new_success_without_dispatch.py'),run_name='__main__')\nfinally:\n (folder/'command_log.json').write_bytes(json.dumps(f.COMMANDS,indent=2).encode())\n")
(R/'script_bindings.json').write_bytes(json.dumps({'fixed_commit':'44676db609b3b7c2175fa7fa4f19c8ccf8165458','copied_original_bytes':bindings,'notes':['No test assertions changed; protocol_boundaries literal ccad is retained provenance, new source bound by actual argv/outer record','Only orchestration root-helper copy removed and WR21 source path resolved/capture added; accepted explicit legacy four-field fixture is unchanged']},indent=2).encode())
tasks=[('legacy',[sys.executable,'-B',str(R/'run_legacy.py')]),('boundaries',[sys.executable,'-B',str(R/'protocol_boundaries.py'),'--source',str(S),'--out',str(R/'boundaries')]),('wr23',[sys.executable,'-B',str(R/'wr23_original/minimal_prepare_entry_crash.py'),'--source',str(S),'--out',str(R/'wr23_original/results')]),('wr21',[sys.executable,'-B',str(R/'wr21_explicit_legacy/launch.py'),str(S)])]
started=[];records=[]
for name,argv in tasks:
    out=(R/(name+'_outer.stdout')).open('wb');err=(R/(name+'_outer.stderr')).open('wb');started.append((name,argv,subprocess.Popen(argv,cwd=R,env=ENV,stdout=out,stderr=err),out,err,time.time()))
for name,argv,p,out,err,t in started:
    code=p.wait();out.close();err.close();stdout=(R/(name+'_outer.stdout')).read_bytes();stderr=(R/(name+'_outer.stderr')).read_bytes();record={'name':name,'argv':argv,'cwd':str(R),'source':str(S),'source_commit':'44676db609b3b7c2175fa7fa4f19c8ccf8165458','exit_code':code,'elapsed_seconds':time.time()-t,'stdout_sha256':hashlib.sha256(stdout).hexdigest(),'stderr_sha256':hashlib.sha256(stderr).hexdigest()};records.append(record);(R/'outer_execution_records.json').write_bytes(json.dumps(records,indent=2).encode());print(json.dumps(record),flush=True)
sys.exit(0 if all(x['exit_code']==0 for x in records)else 1)
