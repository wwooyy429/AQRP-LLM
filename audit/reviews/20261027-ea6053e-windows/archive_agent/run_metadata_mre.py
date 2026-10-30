from pathlib import Path
import hashlib,json,os,subprocess,sys,time
R=Path(__file__).resolve().parent
script=R/'minimal_wr24_metadata.py';cmd=[sys.executable,'-B',str(script)]
start=time.perf_counter();p=subprocess.run(cmd,cwd=R,capture_output=True,env=dict(os.environ,PYTHONIOENCODING='utf-8'))
(R/'wr24_first.stdout').write_bytes(p.stdout);(R/'wr24_first.stderr').write_bytes(p.stderr)
sha=lambda b:hashlib.sha256(b).hexdigest()
record={'command':cmd,'cwd':str(R),'exit_code':p.returncode,'expected_exit_code':1,'elapsed_seconds':round(time.perf_counter()-start,3),'script_raw_sha256':sha(script.read_bytes()),'stdout':'wr24_first.stdout','stdout_raw_sha256':sha(p.stdout),'stderr':'wr24_first.stderr','stderr_raw_sha256':sha(p.stderr),'scope':'read-only current metadata vs pinned Git diff and unchanged authoritative ledger','independent_product_test_methods':0,'actual_QC_Research_LEAN_model_deployment_registry_writes':0}
(R/'wr24_first_execution.json').write_bytes((json.dumps(record,ensure_ascii=False,indent=2)+'\n').encode())
sys.stdout.buffer.write(p.stdout);sys.stderr.buffer.write(p.stderr)
sys.exit(p.returncode)
