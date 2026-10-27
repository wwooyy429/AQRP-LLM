from pathlib import Path
import json,os,subprocess,urllib.request,hashlib,platform,sys
R=Path(__file__).parent
C='ccad61d03ccf17bf2bdc2d7ffc88dfd11b6d3ca6'
for name in ['run_regressions.py','run_worker_regressions.py']:
 p=R/name;s=p.read_text();s=s.replace('ea6053e3e9ef4be17db246daf18a4cf9b2e5be58',C)
 if name=='run_regressions.py':
  s=s.replace("('engineering_recovery_original',[R/'recovery_agent/independent_recovery.py','--source',S,'--out',out2]),",'')
 p.write_bytes(s.encode())
req=urllib.request.Request('https://api.github.com/repos/wwooyy429/AQRP-LLM/pulls/2',headers={'User-Agent':'AQRP-independent-offline-review','Accept':'application/vnd.github+json'})
with urllib.request.urlopen(req,timeout=40)as response:raw=response.read()
(R/'pr2_rest.json').write_bytes(raw)
obj=json.loads(raw)
print(json.dumps({k:obj.get(k)for k in ['number','state','draft','merged','mergeable','updated_at']}))
print('head',obj['head']['sha'],'base',obj['base']['sha'])
print(json.dumps({'platform':platform.platform(),'python':sys.version,'executable':sys.executable}))
