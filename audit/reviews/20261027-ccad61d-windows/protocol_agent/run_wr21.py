import os,json,hashlib,shutil,subprocess,time,sys,difflib
from pathlib import Path
R=Path(__file__).resolve().parent;O=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-ea6053e-20261027\dispatch_agent\mre_candidate\agent');S=R.parent/'source';records=[]
ENV=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
wrapper="""import sys,runpy\nfrom pathlib import Path\ns=Path(sys.argv[1]);folder=Path(__file__).parent\nsys.path[:0]=[str(s/'cloud'),str(s/'tools'),str(folder)]\nimport quick_joint_probes as h,independent_cli_gates as f\nf.SOURCE=s;h.SOURCE=s\nrunpy.run_path(str(folder/'minimal_new_success_without_dispatch.py'),run_name='__main__')\n"""
for mode in ('original','legacy_shape_adapter'):
    d=R/'wr21'/mode;d.mkdir(parents=True,exist_ok=True)
    for name in ('minimal_new_success_without_dispatch.py','independent_cli_gates.py','independent_wr16_boundaries.py','quick_joint_probes.py'):shutil.copy2(O/name,d/name)
    script=d/'minimal_new_success_without_dispatch.py'
    if mode!='original':
        raw=script.read_bytes();needle=b"    # Only this isolated fixture models an old admission that never promised entry semantics.\r\n"
        if needle not in raw:needle=needle.replace(b'\r\n',b'\n')
        insert=b"    oldadm.pop('research_entry_protocol',None)\n    oldr.store._path('engineering/admitted-inputs/'+oldid+'.json').write_bytes(canonical_json(oldadm))\n"
        fixed=raw.replace(needle,needle+insert);assert fixed!=raw;script.write_bytes(fixed)
        (d/'fixture.diff').write_bytes(''.join(difflib.unified_diff(raw.decode().splitlines(True),fixed.decode().splitlines(True),fromfile='original',tofile='explicit_legacy_shape')).encode())
    (d/'launch.py').write_bytes(wrapper.encode());argv=[sys.executable,'-B',str(d/'launch.py'),str(S)];t=time.time();p=subprocess.run(argv,cwd=d,env=ENV,capture_output=True)
    (d/'first.stdout').write_bytes(p.stdout);(d/'first.stderr').write_bytes(p.stderr)
    row={'mode':mode,'argv':argv,'source':str(S),'exit_code':p.returncode,'elapsed_seconds':time.time()-t,'script_sha256':hashlib.sha256(script.read_bytes()).hexdigest(),'stdout_sha256':hashlib.sha256(p.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(p.stderr).hexdigest()};(d/'execution.json').write_bytes(json.dumps(row,indent=2).encode());records.append(row);(R/'wr21_execution_records.json').write_bytes(json.dumps(records,indent=2).encode());print(json.dumps(row),flush=True)
