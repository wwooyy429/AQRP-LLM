from pathlib import Path
import json,shutil,urllib.request
R=Path(__file__).parent;O=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-ccad61d-20261027')
C='44676db609b3b7c2175fa7fa4f19c8ccf8165458';B='ccad61d03ccf17bf2bdc2d7ffc88dfd11b6d3ca6'
for name in ['run_main_checks.py','replay_archived_script.py','replay_public_class.py','run_worker_regressions.py','run_regressions.py','environment_capture.py','capture_git_context.py','summarize_root_tests.py','verify_artifacts.py']:
 s=(O/name).read_text(encoding='utf-8-sig')
 if name=='capture_git_context.py':s=s.replace(B,C).replace('ea6053e3e9ef4be17db246daf18a4cf9b2e5be58',B)
 else:s=s.replace(B,C)
 if name=='summarize_root_tests.py':s=s.replace('654','668')
 (R/name).write_bytes(s.encode())
for name in ['legacy_adapter','legacy_pending_runtime']:shutil.copytree(O/name,R/name)
req=urllib.request.Request('https://api.github.com/repos/wwooyy429/AQRP-LLM/pulls/2',headers={'User-Agent':'AQRP-independent-offline-review','Accept':'application/vnd.github+json'})
with urllib.request.urlopen(req,timeout=40)as response:raw=response.read()
(R/'pr2_rest.json').write_bytes(raw);d=json.loads(raw)
print(json.dumps({'head':d['head']['sha'],'base':d['base']['sha'],'draft':d['draft'],'state':d['state'],'merged':d['merged']}))
