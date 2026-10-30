from pathlib import Path
import hashlib,json,os,subprocess,sys
R=Path(__file__).parent;O=R/'wr21_confirmation'
commands,_=json.JSONDecoder().raw_decode((O/'new_success_without_dispatch_commands.json').read_text(encoding='utf-8-sig'))
case=Path(commands[-1]['cwd']).resolve();assert case.is_relative_to((O/'cli_cases').resolve())
first=json.loads((O/'strict_result.json').read_bytes());attempt=json.loads(commands[-1]['stdout'])['attempt_id']
before=json.loads((case/'config/budget.json').read_bytes())['usage']
assert first['new_entry_protocol_exists']is True and first['dispatch_exists_before_and_after']is False and first['unbound_result']=='completed'
cmd=[sys.executable,'-B',str(case/'tools/stage2.py'),'claim','--stage','lean']
p=subprocess.run(cmd,cwd=case,capture_output=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1'))
(O/'downstream.stdout').write_bytes(p.stdout);(O/'downstream.stderr').write_bytes(p.stderr)
record={'command':cmd,'cwd':str(case),'exit_code':p.returncode,'stdout_sha256':hashlib.sha256(p.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(p.stderr).hexdigest(),
 'synthetic_case_only':True,'original_research_attempt':attempt,'entry_protocol_exists':(case/('audit/runtime/engineering/research-entry-protocol/'+attempt+'.json')).exists(),
 'dispatch_exists':(case/('audit/runtime/engineering/research-dispatch/'+attempt+'.json')).exists(),'before_usage':before,'after_usage':json.loads((case/'config/budget.json').read_bytes())['usage'],
 'actual_provider_calls':0,'actual_authoritative_budget_changes':0}
record['result']=json.loads(p.stdout)if p.returncode==0 else None
(O/'downstream_execution.json').write_bytes((json.dumps(record,indent=2)+'\n').encode());print(json.dumps(record))
assert p.returncode==0 and record['result']['stage']=='lean'and record['result']['status']=='started'and record['result']['should_execute']is True
