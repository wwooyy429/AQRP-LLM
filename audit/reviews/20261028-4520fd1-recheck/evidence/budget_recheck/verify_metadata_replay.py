from pathlib import Path
import hashlib,json,subprocess,sys
from frontier_support import *
R=Path(__file__).resolve().parent
m,b,t,a=copied_context();book=m.read_bytes(b.JOURNAL);events=rows(b);rounds=b.engineering_rounds_snapshot();snap=b.snapshot()
G=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\repo');checks=[];commands=[]
def check(name,value,detail=None):
 checks.append({'name':name,'passed':bool(value),'detail':detail});assert value,name
check('exact46events',len(events)==46)
check('exact12_15_2_with_allocations',snap['usage']==EXPECTED,snap['usage'])
for name,c,count in [('eaf34','eaf6b70aca485a292b4575fc99df312dc9560510',34),('accepted446_17','44676db609b3b7c2175fa7fa4f19c8ccf8165458',17)]:
 command=['git','-C',str(G),'show',c+':audit/runtime/registry/events.jsonl'];p=subprocess.run(command,capture_output=True);assert p.returncode==0
 commands.append({'command':command,'exit_code':p.returncode,'stdout_sha256':hashlib.sha256(p.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(p.stderr).hexdigest()})
 prefix=b''.join(book.splitlines(keepends=True)[:count]);check('preserved_'+name,prefix==p.stdout,{'count':count,'raw_sha256':hashlib.sha256(prefix).hexdigest()})
round=rounds[ROUND];check('round_actual_vs_recorded',round['usage']=={'configurations':2,'research':2,'lean':1}and round['grant']['limits']=={'configurations':2,'research':4,'lean':2},round)
usage=json.loads((SOURCE/'config/budget.json').read_bytes())['usage'];check('generated_budget_usage_projection',usage['configuration_budget_charges']==12 and usage['research_execution_attempts']==15 and usage['lean_submission_attempts']==2)
check('pending_bound_original_frozen_task',a['status']=='pending'and a['attempt_id']==ATTEMPT and a['external_id']=='3e68866a46ca88ff16481c31b3c2c822'and a['config_id']==t.config_id)
check('required_checks_research13_lean7',len(t.plan.to_dict()['required_checks']['research'])==13 and len(t.plan.to_dict()['required_checks']['lean'])==7)
out={'reviewed_source_commit':'4520fd1a4421a9b764d2bfd61e5fb5cf4b59a9c8','static_checks':len(checks),'all_passed':all(x['passed']for x in checks),'checks':checks,'commands':commands,'journal_raw_sha256':hashlib.sha256(book).hexdigest(),'config_capacity_remaining':0,'open_round':ROUND,'trusted_authority_boundary':'Latest direct user statement supports already executed2/2/1. Recorded2/4/2 ceiling is metadata; original external human message not independently obtained; no new authorization issued here.','current_platform_calls':0,'financial_evidence':False,'counting_note':'Same8 logical static checks were first executed through an interactive script, then preserved as this portable script with exact Git command evidence; not16 distinct checks.'}
(R/'metadata_replay_portable.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8');print(json.dumps({'static_checks':len(checks),'all_passed':out['all_passed'],'journal_raw_sha256':out['journal_raw_sha256']}))
