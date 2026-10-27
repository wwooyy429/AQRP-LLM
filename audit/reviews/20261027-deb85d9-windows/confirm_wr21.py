from pathlib import Path
import hashlib,json,os,shutil,subprocess,sys,time
R=Path(__file__).parent;O=R/'wr21_confirmation';O.mkdir(exist_ok=False)
names=['minimal_new_success_without_dispatch.py','quick_joint_probes.py','independent_cli_gates.py','independent_wr16_boundaries.py']
for name in names:shutil.copyfile(R/'entry_agent'/name,O/name)
cmd=[sys.executable,'-B',str(O/names[0])];t=time.monotonic()
p=subprocess.run(cmd,cwd=R,capture_output=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1'))
(O/'stdout').write_bytes(p.stdout);(O/'stderr').write_bytes(p.stderr)
record={'command':cmd,'cwd':str(R),'exit_code':p.returncode,'expected_defect_exit':1,'seconds':time.monotonic()-t,'stdout_sha256':hashlib.sha256(p.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(p.stderr).hexdigest(),'scripts_raw_equal_original':all((O/n).read_bytes()==(R/'entry_agent'/n).read_bytes()for n in names),'provider_calls':0,'actually_executed':True}
(O/'execution.json').write_bytes(json.dumps(record,indent=2).encode());print(json.dumps(record));print(p.stdout.decode('utf-8')[-1200:]);print(p.stderr.decode('utf-8')[-700:])
# The original reviewer script emits literal backslash-n after its JSON file.
# Preserve it exactly; parse and separately serialize a strict JSON projection.
raw=(O/'new_success_without_dispatch_first.json').read_text(encoding='utf-8-sig');obj,end=json.JSONDecoder().raw_decode(raw)
assert raw[end:]in('\\n','\n','');(O/'strict_result.json').write_bytes((json.dumps(obj,indent=2)+'\n').encode())
assert obj['positive_bound_result']==obj['legacy_without_marker_result']=='completed'
assert obj['new_entry_protocol_exists']is True and obj['dispatch_exists_before_and_after']is False
assert obj['unbound_CLI_exit_code']==0 and obj['unbound_result']=='completed'
sys.exit(0 if p.returncode==1 else 1)
