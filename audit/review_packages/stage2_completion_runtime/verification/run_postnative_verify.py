from pathlib import Path
import subprocess,json,hashlib,sys
root=Path.cwd();scratch=root/'.git/repair-work/stage2-completion'
original={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'audit/runtime').rglob('*') if p.is_file()}
original.update({p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'config').glob('*.json')});original['audit/data_exposure.json']=hashlib.sha256((root/'audit/data_exposure.json').read_bytes()).hexdigest()
records=[]
for label,args in [('postnative_build',['tools/research.py','build']),('postnative_verify',['tools/stages.py','verify'])]:
 p=subprocess.run([sys.executable,'-B',*args],capture_output=True,cwd=root);(scratch/(label+'.stdout')).write_bytes(p.stdout);(scratch/(label+'.stderr')).write_bytes(p.stderr);records.append({'label':label,'command':args,'exit_code':p.returncode});print(json.dumps(records[-1]),flush=True)
 if p.returncode:raise SystemExit(p.returncode)
assert all(hashlib.sha256((root/name).read_bytes()).hexdigest()==digest for name,digest in original.items())
v=json.loads((root/'audit/stage_verification.json').read_bytes());report={'actual_cloud_source_commit':'7fc5ef2e9d2379d29f48d05a1f3cc760000884d6','controller_repair_after_native_failure':True,'runs':records,'local_tests_passed':v['local_tests_passed'],'test_output':v['test_output'],'source_hash':v['source_hash'],'protected_files_count':len(original),'all_protected_bytes_unchanged':True,'new_QC_calls':0,'new_Research_executions':0,'new_LEAN_submissions':0,'financial_evidence':False};(scratch/'postnative_verification.json').write_bytes((json.dumps(report,ensure_ascii=True,indent=2)+'\n').encode());print(json.dumps(report),flush=True)
