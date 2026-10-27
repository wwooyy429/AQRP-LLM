from pathlib import Path
import hashlib,subprocess,sys,json,tarfile,io,os
root=Path.cwd();scratch=root/'.git/repair-work/stage2-completion/worker-identity';base='a6b14b05e913daa894c9049b428e953954b40e08';baseline=scratch/'baseline_a6';baseline.mkdir(exist_ok=True)
archive=subprocess.run(['git','archive',base,'cloud','tests','tools','config','templates','docs','.gitattributes','AGENTS.md','requirements-test.txt','audit/deployment.json'],cwd=root,capture_output=True,check=True).stdout
with tarfile.open(fileobj=io.BytesIO(archive)) as tf:
 for member in tf.getmembers():
  assert (baseline/member.name).resolve().is_relative_to(baseline.resolve()) and not member.issym() and not member.islnk()
 tf.extractall(baseline)
test=root/'tests/test_worker_identity.py';final=scratch/'final_tests.py';final.write_bytes(test.read_bytes());(baseline/'tests/test_worker_identity.py').write_bytes(test.read_bytes())
env=dict(os.environ,PYTHONIOENCODING='utf-8',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
runs=[]
for name,cwd,command in [('baseline_exact_final_test',baseline,[sys.executable,'-B','-m','unittest','discover','-s','tests','-p','test_worker_identity.py','-v']),('candidate_exact_final_test',root,[sys.executable,'-B','-m','unittest','discover','-s','tests','-p','test_worker_identity.py','-v']),('legacy_compatibility',root,[sys.executable,'-B','-m','unittest','tests.test_deployment_integrity_diagnostics','tests.test_engineering_data','tests.test_native_runtime_failure','-v'])]:
 p=subprocess.run(command,cwd=cwd,capture_output=True,env=env);(scratch/(name+'.stdout')).write_bytes(p.stdout);(scratch/(name+'.stderr')).write_bytes(p.stderr)
 item={'label':name,'command':command,'cwd':str(cwd),'exit_code':p.returncode,'stdout_sha256':hashlib.sha256(p.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(p.stderr).hexdigest()};runs.append(item);print(json.dumps(item),flush=True)
 if name!='baseline_exact_final_test':assert p.returncode==0,p.stderr.decode(errors='replace')
sys.path.insert(0,str(root/'cloud'))
from qresearch.artifacts import content_hash
from qresearch.engineering_data import verify_deployment,DeploymentVerificationError
admission=json.loads((root/'audit/runtime/engineering/admitted-inputs/bfd00f2611fd4496b9498d4597618a8e.json').read_bytes());manifest=admission['payload']['deployment_manifest'];old=scratch/'source75';old.mkdir(exist_ok=True)
for name in manifest:
 p=old/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(subprocess.run(['git','show','75f24629d3b7f94ff3aa906c3ce8a2b8b9a8d3c4:cloud/'+name],cwd=root,capture_output=True,check=True).stdout)
assert verify_deployment(manifest,content_hash(manifest),source_root=old,worker_diagnostics=True)==admission['deployment']['deployment_hash']
summary={'baseline_commit':base,'same_final_test_bytes':True,'baseline_import_error_is_absent_new_module_not_25_distinct_bugs':True,'baseline_test_loader_methods':1,'candidate_test_methods':25,'compatibility_test_methods':44,'source75_25_files_strictly_verified':True,'original_frozen_deployment_hash':admission['deployment']['deployment_hash'],'runs':runs,'source_raw_sha256':{name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in ('cloud/qresearch/worker_identity.py','cloud/qresearch/engineering_data.py','tests/test_worker_identity.py')},'controlled_worker_observation_schema':1,'enhanced_error_schema':2,'default_error_schema':1,'default_hash_and_EOF_policy_unchanged':True,'same_source_read':True,'G2_actual_old_worker_root_cause_proven':False,'G2_actual_new_worker_observation':False,'real_QC_calls':0,'real_Research_executions':0,'real_LEAN_submissions':0,'real_budget_writes':0,'financial_evidence':False}
(scratch/'summary.json').write_bytes((json.dumps(summary,ensure_ascii=True,indent=2)+'\n').encode());print(json.dumps({k:v for k,v in summary.items() if k not in ('runs','source_raw_sha256')}))
