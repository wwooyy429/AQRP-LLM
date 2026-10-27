from pathlib import Path
import ast,copy,hashlib,io,json,subprocess,sys,tarfile
R=Path(__file__).parent;S=R/'source';G=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\repo')
C='deb85d9f27441b275ab8b108f0232ecd2707a1e8';B='66ff72ffaaff8c91c008898e6527c91131176c2a';A='7fc5ef2e9d2379d29f48d05a1f3cc760000884d6'
checks=[]
def sha(raw):return hashlib.sha256(raw).hexdigest()
def norm(raw):return raw.decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n').encode()
def canonical(obj):return json.dumps(obj,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def check(name,ok,detail=None):checks.append({'name':name,'passed':bool(ok),'detail':detail})
def tree(commit):
    raw=subprocess.check_output(['git','-C',str(G),'archive',commit])
    with tarfile.open(fileobj=io.BytesIO(raw))as t:return{m.name:t.extractfile(m).read()for m in t.getmembers()if m.isfile()}
files=tree(C);base=tree(B);actual=tree(A);disk={p.relative_to(S).as_posix():p.read_bytes()for p in S.rglob('*')if p.is_file()}
check('all4270_candidate_Git_raw_bytes',len(files)==4270 and disk==files)
manifest={p:sha(norm(b))for p,b in files.items()if((Path(p).parts[0]in('cloud','config','templates','tests','tools','docs','.github')and Path(p).suffix in('.py','.json','.md','.yml','.yaml')and'__pycache__'not in Path(p).parts)or p in('requirements-test.txt','.gitattributes','.gitignore','AGENTS.md'))}
stage=json.loads(files['audit/stage_verification.json']);review_hash=sha(canonical(manifest))
check('source_manifest_recomputed',manifest==stage['source_files']and review_hash==stage['source_hash'],{'files':len(manifest),'hash':review_hash})
check('developer612_log_identity',stage['local_tests_passed']is True and'Ran 612 tests'in stage['test_output'])
def assignments(raw):return{n.targets[0].id:ast.literal_eval(n.value)for n in ast.parse(raw).body if isinstance(n,ast.Assign)}
generated=assignments(files['cloud/research_config.py']);old=assignments(base['cloud/research_config.py'])
deploy={p[6:]:sha(norm(b))for p,b in files.items()if p.startswith('cloud/')and p.endswith('.py')}
impl={Path(p).name:sha(norm(b))for p,b in files.items()if p.startswith('cloud/qresearch/')and p.endswith('.py')}
deployment=json.loads(files['audit/deployment.json']);dh=sha(canonical(deploy))
check('local31_deployment_and_implementation',len(deploy)==31 and deployment['source_files']==deploy and generated['IMPLEMENTATION_SHA256']==deployment['implementation_hash']==sha(canonical(impl)))
check('active_configuration_unchanged',generated['SOURCE_SHA256']==old['SOURCE_SHA256']==deployment['configuration_hash']and generated['CONFIGURATION']==old['CONFIGURATION'])
budget=json.loads(files['config/budget.json']);policy=copy.deepcopy(budget);policy.pop('usage');exmap=dict(manifest);exmap['config/budget.json']=sha(canonical(policy));exhash=sha(canonical({'schema':'collection_execution_sources_v1','source_files':exmap}))
integrity=json.loads(files['audit/stage2_completion_final_integrity.json']);check('delivery_hash_claims',review_hash==integrity['final_controller_source_manifest_hash']and exhash==integrity['final_execution_hash'])
preserved=[p for p in base if p.startswith(('audit/reviews/','audit/review_packages/'))]
check('all_prior_archived_evidence_raw_preserved',all(files.get(p)==base[p]for p in preserved),{'count':len(preserved)})
new_package_counts={}
for name in['stage2_completion','stage2_completion_runtime']:
    doc=json.loads(files['audit/review_packages/'+name+'/developer_outputs_manifest.json']);rows=doc['entries'];new_package_counts[name]=len(rows)
    for row in rows:
        p=row['path'];raw=files[p];check('developer_raw:'+p,len(raw)==row['bytes']and sha(raw)==row['raw_sha256'])
journal=files['audit/runtime/registry/events.jsonl'];prior=base['audit/runtime/registry/events.jsonl'];events=[json.loads(line)for line in journal.splitlines()];check('17events_raw13prefix',len(events)==17 and journal.startswith(prior))
previous=None
for i,e in enumerate(events,1):
    body={k:v for k,v in e.items()if k!='hash'}
    check('journal_chain_'+str(i),e['sequence']==i and e['previous_hash']==previous and sha(canonical(body))==e['hash']);previous=e['hash']
sys.path.insert(0,str(S/'cloud'))
from qresearch.artifacts import MemoryArtifactStore
from qresearch.registry import Registry
store=MemoryArtifactStore()
for p,b in files.items():
    if p.startswith('audit/runtime/'):store.write_once(p[len('audit/runtime/'):],b)
registry=Registry(store,json.loads(files['audit/runtime/registry/baseline.json']));snapshot=registry.snapshot()
usage=snapshot['usage'];check('budget_replay7_10_1',[usage[k]['total']for k in('configurations','research','lean')]==[7,10,1])
attempt='f5d05f5b964b4a1d924e4b70cd207386';attempts={x['attempt_id']:x for x in snapshot['attempts']};check('old_and_new_failed_no_success',attempts[attempt]['status']=='failed'and attempts['bfd00f2611fd4496b9498d4597618a8e']['status']=='failed'and not store.exists(attempts[attempt]['result_key']))
check('config_budget_usage_projection',[budget['usage'][k]for k in('configuration_budget_charges','research_execution_attempts','lean_submission_attempts')]==[7,10,1])
live=json.loads((R/'qc_python_source_read.json').read_bytes());rows=[];cloud={}
for record in live['results']:
    assert record['status']=='fulfilled';native=record['value'];value=native['structuredContent'];texts=[json.loads(x['text'])for x in native.get('content',[])if x.get('type')=='text'];check('cloud_carrier:'+record['file'],not native.get('isError',False)and all(x==value for x in texts))
    path=record['file'];raw=value['content'].encode();reference=files['audit/task_inputs/'+attempt+'.py']if path=='_engineering_task_input.py'else actual['cloud/'+path]
    if path!='_engineering_task_input.py':cloud[path]=sha(norm(raw))
    rows.append({'path':path,'raw_sha256':sha(raw),'matches_executed_7fc_or_original_input':raw==reference,'matches_delivered_controller':raw==files.get('cloud/'+path)if path!='_engineering_task_input.py'else None})
check('all32_readback_raw_match_executed_source_and_original_input',len(rows)==32 and all(x['matches_executed_7fc_or_original_input']for x in rows))
admission=json.loads(files['audit/runtime/engineering/admitted-inputs/'+attempt+'.json']);check('actual31_manifest_identity',sha(canonical(cloud))==admission['deployment']['deployment_hash'])
cell=json.loads((R/'qc_read_cell_source.json').read_bytes())['structuredContent'];text=''.join(cell['source']);cell_packet=json.loads(files['audit/tool_observations/'+attempt+'-cell-source.json'])
check('live_cell_source_matches_original_frozen_hash',cell['cellType']=='code'and sha(text.encode())=='33c34e9fbbf958f6518966cee185e947d96a4c610b7c0a942d206dec252e3340')
check('actual_source_unchanged_after_readonly_checks',disk=={p.relative_to(S).as_posix():p.read_bytes()for p in S.rglob('*')if p.is_file()})
result={'reviewed_source_commit':C,'baseline':B,'actual_cloud_source_commit':A,'raw_git_files':len(files),'review_source_count':len(manifest),'source_manifest_hash':review_hash,'execution_source_manifest_hash':exhash,'deployment_hash':dh,'implementation_hash':generated['IMPLEMENTATION_SHA256'],'active_configuration_hash':generated['SOURCE_SHA256'],'local_deployment_files':len(deploy),'actual_cloud_deployment_hash':sha(canonical(cloud)),'actual_input_hash':admission['deployment']['input_hash'],'actual_cell_source_hash':sha(text.encode()),'developer_package_counts':new_package_counts,'prior_evidence_files_unchanged':len(preserved),'checks':checks,'checks_run':len(checks),'checks_passed':sum(x['passed']for x in checks),'usage':usage,'events':len(events),'journal_raw_sha256':sha(journal),'cloud_rows':rows,'current_controller_readback_matches':sum(x['matches_delivered_controller']is True for x in rows),'QC_read_calls':{'list_projects':1,'read_open_project':1,'read_file':32,'jupyter_read_cell_source_only':1},'independent_current_failure_output_read':False,'raw_original_failure_scope':'developer archived native packet; independently parsed offline by native_agent','worker_source_verified':False,'full_inventory_certified':False,'financial_evidence':False,'actual_registry_writes':0,'new_market_model_calls':0}
(R/'source_evidence_verification.json').write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode())
print(json.dumps({k:v for k,v in result.items()if k not in('checks','cloud_rows','usage')},ensure_ascii=False))
print(json.dumps([x for x in checks if not x['passed']],ensure_ascii=False))
sys.exit(0 if all(x['passed']for x in checks)else 1)
