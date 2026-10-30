from pathlib import Path
import hashlib,json,os,subprocess
O=Path(__file__).resolve().parent;PY=r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\venv\Scripts\python.exe';records=[]
for label,script in [('parser_first','parse_original.py'),('old_bridge_first','replay_old_bridge.py')]:
 cmd=[PY,'-B',str(O/script)];r=subprocess.run(cmd,cwd=O,env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1'),capture_output=True)
 for stream,b in [('stdout',r.stdout),('stderr',r.stderr)]:(O/(label+'.'+stream+'.txt')).write_bytes(b)
 records.append({'label':label,'command':cmd,'cwd':str(O),'exit_code':r.returncode,'stdout':label+'.stdout.txt','stdout_raw_sha256':hashlib.sha256(r.stdout).hexdigest(),'stderr':label+'.stderr.txt','stderr_raw_sha256':hashlib.sha256(r.stderr).hexdigest()})
 (O/'replay_command_log.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(label,'exit',r.returncode);print(r.stdout.decode('utf-8',errors='replace'));print(r.stderr.decode('utf-8',errors='replace'))
 if r.returncode:break
raise SystemExit(0 if len(records)==2 and all(x['exit_code']==0 for x in records) else 1)
