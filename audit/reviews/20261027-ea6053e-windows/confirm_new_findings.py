from pathlib import Path
import hashlib,json,os,shutil,subprocess,sys,time
R=Path(__file__).parent;ENV=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
records=[]
O=R/'wr23_confirmation';O.mkdir(exist_ok=False)
for name in ['minimal_prepare_entry_crash.py','independent_recovery_support.py']:shutil.copyfile(R/'dispatch_agent'/name,O/name)
commands=[('WR22',[R/'cert_agent/minimal_wr22.py','--output',R/'wr22_confirmation/result.json']),('WR23',[O/'minimal_prepare_entry_crash.py','--source',R/'source','--out',O/'results'])]
for label,args in commands:
    folder=R/(label.lower()+'_confirmation');folder.mkdir(exist_ok=True)
    cmd=[sys.executable,'-B',*map(str,args)];t=time.monotonic();p=subprocess.run(cmd,cwd=R,env=ENV,capture_output=True)
    (folder/'stdout').write_bytes(p.stdout);(folder/'stderr').write_bytes(p.stderr)
    rec={'finding':label,'command':cmd,'cwd':str(R),'exit_code':p.returncode,'expected_defect_exit':1,'seconds':time.monotonic()-t,'stdout_sha256':hashlib.sha256(p.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(p.stderr).hexdigest(),'script_sha256':hashlib.sha256(Path(args[0]).read_bytes()).hexdigest(),'actual_provider_calls':0,'actual_authoritative_budget_writes':0,'actually_executed':True}
    records.append(rec);(folder/'execution.json').write_bytes((json.dumps(rec,indent=2)+'\n').encode());(R/'root_confirmation_records.json').write_bytes((json.dumps(records,indent=2)+'\n').encode());print(json.dumps(rec),flush=True);print((p.stdout+p.stderr).decode('utf-8',errors='replace')[-1400:],flush=True)
sys.exit(0 if all(x['exit_code']==1 for x in records)else 1)
