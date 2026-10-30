from pathlib import Path
import subprocess,json,hashlib,os,sys
root=Path.cwd(); scratch=root/'.git/repair-work/deployment-repair'; scratch.mkdir(exist_ok=True,parents=True)
protected=[p for p in (root/'audit/runtime').rglob('*') if p.is_file()]+list((root/'config').glob('*.json'))+[root/'audit/data_exposure.json',root/'audit/tool_observations/bfd00f2611fd4496b9498d4597618a8e-terminal-runtime-error.json']
original={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
records=[]
for label,command in [('build',[sys.executable,'-B','tools/research.py','build']),('verify',[sys.executable,'-B','tools/stages.py','verify'])]:
 p=subprocess.run(command,cwd=root,capture_output=True)
 (scratch/(label+'.stdout')).write_bytes(p.stdout);(scratch/(label+'.stderr')).write_bytes(p.stderr)
 records.append({'label':label,'command':command,'exit_code':p.returncode})
 print(json.dumps(records[-1]),flush=True)
 if p.returncode:raise SystemExit(p.returncode)
current={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
assert original==current
ver=json.loads((root/'audit/stage_verification.json').read_bytes())
summary={'baseline_commit':'f37340415ff080ae44310c912044f683e9986e96','runs':records,'protected_files':original,'all_protected_bytes_unchanged':True,'source_hash':ver['source_hash'],'local_tests_passed':ver['local_tests_passed'],'test_output':ver['test_output'],'new_configurations':0,'new_Research_executions':0,'new_LEAN_submissions':0,'financial_evidence':False}
(scratch/'verification.json').write_bytes((json.dumps(summary,ensure_ascii=True,indent=2)+'\n').encode())
print(json.dumps({k:summary[k] for k in ('source_hash','local_tests_passed','all_protected_bytes_unchanged','test_output')}))
