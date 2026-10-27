from pathlib import Path
import subprocess,json,hashlib,os,sys
root=Path.cwd();scratch=root/'.git/repair-work/stage2-completion';scratch.mkdir(exist_ok=True,parents=True)
protected=[p for p in (root/'audit/runtime').rglob('*') if p.is_file()]+list((root/'config').glob('*.json'))+[root/'audit/data_exposure.json',root/'audit/tool_observations/bfd00f2611fd4496b9498d4597618a8e-terminal-runtime-error.json']
original={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
(scratch/'protected_before_execution.json').write_bytes((json.dumps(original,indent=2)+'\n').encode())
records=[]
for label,command in [('full_build',[sys.executable,'-B','tools/research.py','build']),('full_verify',[sys.executable,'-B','tools/stages.py','verify'])]:
 p=subprocess.run(command,cwd=root,capture_output=True)
 (scratch/(label+'.stdout')).write_bytes(p.stdout);(scratch/(label+'.stderr')).write_bytes(p.stderr)
 records.append({'label':label,'command':command,'exit_code':p.returncode});print(json.dumps(records[-1]),flush=True)
 if p.returncode:raise SystemExit(p.returncode)
current={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in protected};assert original==current
v=json.loads((root/'audit/stage_verification.json').read_bytes())
summary={'baseline_commit':'a6b14b05e913daa894c9049b428e953954b40e08','runs':records,'protected_originals_count':len(original),'all_protected_bytes_unchanged':True,'source_hash':v['source_hash'],'local_tests_passed':v['local_tests_passed'],'test_output':v['test_output'],'new_configurations':0,'new_Research_executions':0,'new_LEAN_submissions':0,'financial_evidence':False}
(scratch/'developer_verification.json').write_bytes((json.dumps(summary,ensure_ascii=True,indent=2)+'\n').encode());print(json.dumps(summary),flush=True)
