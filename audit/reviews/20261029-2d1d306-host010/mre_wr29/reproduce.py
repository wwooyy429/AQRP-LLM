from pathlib import Path
import subprocess,sys,os,json,hashlib
R=Path(__file__).resolve().parent
S=R.parent/'source'
sys.dont_write_bytecode=True
env=dict(os.environ,PYTHONPATH=str(R),PYTHONDONTWRITEBYTECODE='1')
command=[sys.executable,'-B',str(S/'tools/followup_host.py'),'serve','--enable-dispatch','--host-factory','factory_wr29:build']
result=subprocess.run(command,cwd=S,env=env,input=b'',capture_output=True)
(R/'actual.stdout').write_bytes(result.stdout);(R/'actual.stderr').write_bytes(result.stderr)
report={'reviewed_source_commit':'2d1d3060dbc7eb136c1dee61f0647977528b8aad','command':command,'PYTHONPATH':str(R),'expected_exit':0,'actual_exit':result.returncode,'expected':'A valid enabled same-source factory plus empty stdin must start and exit normally without a tool call.','actual_stderr':result.stderr.decode(errors='replace'),'cloud_calls':0,'production_or_budget_writes':0,'explanation':'The CLI defines FollowupHost as __main__.FollowupHost; the factory imports the same source as followup_host.FollowupHost. Exact class identity differs.'}
(R/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False))
# Keep the actual normal-path assertion: the fixed candidate is expected to fail.
assert result.returncode==0,report
