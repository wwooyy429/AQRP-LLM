from pathlib import Path
import subprocess,json,sys,hashlib
root=Path.cwd();scratch=root/'.git/repair-work/stage2-completion';sys.path[:0]=[str(root/'cloud'),str(root/'tools')]
from research import open_registry
from collection_task_cli import execution_source_manifest
reg=open_registry();before=reg.snapshot();assert len((root/'audit/runtime/registry/events.jsonl').read_bytes().splitlines())==13
assert execution_source_manifest()['source_hash']=='89bc58058beab1315d3fa82fee8c0f22d6272fd80152b1938987453acc78a8c6'
commands=[('freeze',['freeze','--plan-file','config/engineering_joint_pilot.json','--projects-file','audit/stage2_completion_projects.json']),('register',['register','--allocation','reserve']),('claim_research',['claim','--stage','research','--allocation','reserve'])]
records=[];claim=None
for label,args in commands:
 p=subprocess.run([sys.executable,'-B','tools/stage2.py',*args],capture_output=True,cwd=root)
 (scratch/(label+'.stdout')).write_bytes(p.stdout);(scratch/(label+'.stderr')).write_bytes(p.stderr);assert p.returncode==0,(label,p.stderr.decode())
 value=json.loads(p.stdout);records.append({'label':label,'command':args,'exit_code':0,'result':value})
 if label=='register':assert value['config_id']=='8552b4c1f96caf63b56fc95c8ebcd5e43598b81e14e7c5ae62eb21913225f5b1'
 if label=='claim_research':claim=value;assert value['should_execute'] is True
attempt=claim['attempt_id'];p=subprocess.run([sys.executable,'-B','tools/stage2.py','prepare','--attempt',attempt],capture_output=True,cwd=root)
(scratch/'prepare_research.stdout').write_bytes(p.stdout);(scratch/'prepare_research.stderr').write_bytes(p.stderr);assert p.returncode==0,p.stderr.decode();admission=json.loads(p.stdout)
assert admission['deployment']['deployment_hash']=='3227c82d09fde3aaddeea61e82aa7e7845ca67b4ff817e932edd145b82b64118'
assert (root/'audit/runtime/engineering/research-entry-protocol'/f'{attempt}.json').is_file()
record={'software_commit':'7fc5ef2e9d2379d29f48d05a1f3cc760000884d6','plan_hash':'4c67e2b61b6d1955a7f94948756aa7277b6f076adfaab5e1fbc14470ec599da7','config_id':claim['config_id'],'research_attempt_id':attempt,'allocation':'reserve','before_event_count':13,'after_event_count':len((root/'audit/runtime/registry/events.jsonl').read_bytes().splitlines()),'Research_tool_not_yet_called':True,'LEAN_tool_not_yet_called':True,'input_hash':admission['deployment']['input_hash'],'input_path':admission['input_path'],'commands':records,'financial_evidence':False}
(root/'audit/stage2_completion_admission.json').write_bytes((json.dumps(record,ensure_ascii=False,indent=2)+'\n').encode());(scratch/'admission.json').write_bytes((json.dumps(admission,ensure_ascii=True,indent=2)+'\n').encode())
print(json.dumps({k:record[k] for k in ('config_id','research_attempt_id','allocation','before_event_count','after_event_count','Research_tool_not_yet_called','input_hash','input_path')}))
