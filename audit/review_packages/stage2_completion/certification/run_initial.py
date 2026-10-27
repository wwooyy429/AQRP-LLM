from pathlib import Path
import subprocess,json,hashlib,sys
root=Path.cwd();scratch=root/'.git/repair-work/stage2-completion/certification'
for name in ('cloud/qresearch/data_certification.py','tools/data_certification.py','tests/test_data_certification.py'):
 (scratch/('initial_'+Path(name).name)).write_bytes((root/name).read_bytes())
cmd=[sys.executable,'-B','-m','unittest','discover','-s','tests','-p','test_data_certification.py','-v']
p=subprocess.run(cmd,capture_output=True,cwd=root)
(scratch/'initial.stdout').write_bytes(p.stdout);(scratch/'initial.stderr').write_bytes(p.stderr)
(scratch/'initial_execution.json').write_bytes((json.dumps({'command':cmd,'exit_code':p.returncode,'synthetic_only':True,'provider_calls':0,'real_budget_changes':0},indent=2)+'\n').encode())
print(json.dumps({'exit_code':p.returncode,'stderr':p.stderr.decode(errors='replace')}))
raise SystemExit(p.returncode)
