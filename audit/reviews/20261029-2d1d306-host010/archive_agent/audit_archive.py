from pathlib import Path
from hashlib import sha256, sha1
import base64, io, json, os, subprocess, sys, tarfile, zipfile
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parents[1];A=Path(__file__).resolve().parent
S=R/'source';M=R/'materials';G=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\repo')
ARCHIVE='audit/reviews/20261029-975f676-recovery009'
X=M/ARCHIVE
checks=[];git_records=[]
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def rawhash(p):return sha256(Path(p).read_bytes()).hexdigest()
def check(name,condition,detail=None):
    checks.append({'name':name,'passed':bool(condition),'detail':detail})
    if not condition:raise AssertionError(name+': '+repr(detail))
def git(args):
    cmd=['git','-C',str(G),*args];p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    git_records.append({'command':cmd,'exit_code':p.returncode,'stdout_sha256':sha256(p.stdout).hexdigest(),'stderr_sha256':sha256(p.stderr).hexdigest()})
    if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace'))
    return p.stdout
def canonical(v):return json.dumps(v,sort_keys=True,ensure_ascii=True,separators=(',',':'),allow_nan=False).encode()
def tree(commit):
    out={}
    for row in git(['ls-tree','-rz',commit]).split(b'\0'):
        if not row:continue
        head,name=row.split(b'\t',1);mode,kind,oid=head.split()
        check('Git_entry_blob:'+commit[:7]+':'+name.decode(),kind==b'blob')
        out[name.decode()]={'oid':oid.decode(),'mode':mode.decode()}
    return out

index=read(X/'import_index.json');manifest=read(X/'archive_manifest.json')
package=read(M/'audit/current_review_package.json');development=read(M/'audit/host010_development_report.json')
oldzip=Path(index['source_bundle']['local_path'])
check('original_zip_exists',oldzip.is_file())
check('original_zip_raw_sha',rawhash(oldzip)==index['source_bundle']['sha256']=='c4437f468fdb57797832df564eb917f3798cc1fe6b6f87dbe39bef6bf7bcace4')
check('original_zip_bytes',oldzip.stat().st_size==39715888)
with zipfile.ZipFile(oldzip) as z:
    check('ZIP_CRC',z.testzip() is None)
    names=set(z.namelist());prior_manifest_raw=z.read('artifact_manifest.json');prior_manifest=json.loads(prior_manifest_raw)
    check('ZIP_complete_entry_set',names==set(prior_manifest['files'])|{'artifact_manifest.json'})
    check('ZIP_entry_counts',len(names)==14331 and len(prior_manifest['files'])==14330)
    check('ZIP_manifest_raw_hash',sha256(prior_manifest_raw).hexdigest()==index['source_bundle']['original_manifest_sha256'])
    for name,item in prior_manifest['files'].items():
        raw=z.read(name);check('ZIP_raw:'+name,len(raw)==item['bytes'] and sha256(raw).hexdigest()==item['sha256'])
    # Reconstruct the old two complete exports from Git blobs using object IDs,
    # rather than treating an existing local worktree or normalized text as raw.
    gitcounts={}
    for folder,commit in {'source':'975f676d62b561689909744f9e7236290e3f5fcb','materials':'a6a5a165d87c172535cdea6cf495e3c1a850e6e4'}.items():
        entries=tree(commit)
        request=''.join(v['oid']+'\n' for v in entries.values()).encode()
        cmd=['git','-C',str(G),'cat-file','--batch'];p=subprocess.run(cmd,input=request,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        git_records.append({'command':cmd,'requested_blob_count':len(entries),'exit_code':p.returncode,'stderr_sha256':sha256(p.stderr).hexdigest()})
        check('Git_batch_exit:'+folder,p.returncode==0)
        stream=io.BytesIO(p.stdout)
        for name,item in entries.items():
            oid,kind,count=stream.readline().strip().split();raw=stream.read(int(count));sep=stream.read(1)
            check('Git_blob_raw:'+folder+'/'+name,oid.decode()==item['oid'] and kind==b'blob' and sep==b'\n' and sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==item['oid'] and raw==z.read(folder+'/'+name))
        check('Git_batch_consumed:'+folder,stream.read()==b'');gitcounts[folder]=len(entries)
    check('selected_counts',len(manifest['original_artifacts'])==205 and len(manifest['files'])==311)
    actual={p.relative_to(X).as_posix() for p in X.rglob('*') if p.is_file()}
    check('import_complete_representation_set',actual==set(manifest['files'])|{'archive_manifest.json'})
    for name,item in manifest['files'].items():
        raw=(X/name).read_bytes();check('representation_raw:'+name,len(raw)==item['bytes'] and sha256(raw).hexdigest()==item['sha256'])
    raw_originals={};mirrors=0;plain=0;totalbytes=0
    for name,item in manifest['original_artifacts'].items():
        readable=(X/item['readable_path']).read_bytes()
        check('readable_hash:'+name,len(readable)==item['readable_bytes'] and sha256(readable).hexdigest()==item['readable_sha256'])
        if 'raw_base64_path' in item:
            encoded=(X/item['raw_base64_path']).read_bytes();raw=base64.b64decode(b''.join(encoded.split()),validate=True);mirrors+=1
            check('base64_bytes:'+name,len(encoded)==item['raw_base64_bytes'] and sha256(encoded).hexdigest()==item['raw_base64_sha256'])
            check('mirror_declared_not_raw:'+name,item['representation']=='readable_UTF8_LF_mirror_not_original_bytes' and b'\r' not in readable and not readable.startswith(b'\xef\xbb\xbf'))
            readable.decode('utf-8')
        else:raw=readable;plain+=1;check('raw_mirror_identity:'+name,item['representation']=='original_UTF8_LF_bytes_unchanged')
        check('restored_original:'+name,len(raw)==item['original_bytes'] and sha256(raw).hexdigest()==item['original_sha256'] and raw==z.read(item['zip_entry']))
        raw_originals[name]=raw;totalbytes+=len(raw)
    check('restored_counts',mirrors==105 and plain==100 and totalbytes==1756416)
    selected=set(manifest['original_artifacts']);omitted=set(index['selection']['excluded']['exact_entries'])
    for prefix in index['selection']['excluded']['prefixes']:omitted|={n for n in names if n.startswith(prefix)}
    check('selected_omitted_exact_partition',selected.isdisjoint(omitted) and selected|omitted==names and len(omitted)==14126)
    for name,item in index['selection']['excluded']['exact_entries'].items():
        raw=z.read(name);check('excluded_record:'+name,len(raw)==item['bytes'] and sha256(raw).hexdigest()==item['sha256'])
formal=json.loads(raw_originals['formal_report.json']);registry_result=read(M/'audit/review_results/recovery009.json')
check('formal_original_hash',sha256(raw_originals['formal_report.json']).hexdigest()=='ef0fa58a5e87d0930ed7b6c6ddbd11a1b96ecc0ea56678dd7989dbee2a890057')
check('formal_source_and_tests',formal['reviewed_source_commit']=='975f676d62b561689909744f9e7236290e3f5fcb' and formal['tests'][0]['methods']==987)
check('formal_semantics_preserved',read(X/'formal_report.json')==formal)
check('review_registration_tests_exact',registry_result['tests']==formal['tests'] and registry_result['stage_results']==formal['stage_results'])
for name in ['notification_agent/first_script.py','notification_agent/first.stderr','notification_agent/first_results_preserved.json','history_agent/carriers_original.stdout','history_agent/carrier_budget_adapter.diff','history_agent/carrier_manifest_adapter.diff','formal_report_pre_QA.json','formal_report_pre_QA.txt','notification_agent/formal_QA_final.json','windows_lock_agent/formal_QA_final.json','history_agent/formal_QA_final.json','history_agent/WR_current_matrix.json']:
    check('first_failures_QA_WR_preserved:'+name,name in raw_originals)
check('old_notification_error_preserved',json.loads(raw_originals['notification_agent/report.json'])['first_execution']['errors']==1)
check('original_WR_matrix_28',len(json.loads(raw_originals['history_agent/WR_current_matrix.json']))==28)
check('selection_scope_not_complete',index['selected_archive_not_complete_original_bundle'] is True and manifest['selected_archive_not_complete_original_bundle'] is True and registry_result['archive_is_selected_not_complete_bundle'] is True)
check('actual_review_identity_local_Codex',index['actual_executing_review_task']['thread_id']=='01a175b6-fed2-77d0-a763-522b6fd695cf' and index['actual_executing_review_task']['kind']=='codex' and registry_result['actual_review_task']==index['actual_executing_review_task'])
check('ChatGPT_handoff_only',index['previous_handoff_only']['this_thread_executed_the_current_review'] is False and registry_result['previous_chatgpt_task_was_handoff_only'] is True)
task_raw=base64.b64decode((M/'audit/review_packages/host010/reviewer_followup_tasks.raw.base64').read_bytes())
check('followup_tasks_original_raw',sha256(task_raw).hexdigest()==registry_result['reviewer_followup_tasks_original_sha256']=='8ea41e8362494cac933a0817e7c9d674c4ed405e8731f9e8586b1969b07ab0cb')

# Independent manifest and version separation.
records={}
for folder in ('cloud','config','templates','tests','tools','docs','.github'):
    for p in (S/folder).rglob('*'):
        if p.is_file() and p.suffix in {'.py','.json','.md','.yml','.yaml'} and '__pycache__' not in p.parts:
            records[p.relative_to(S).as_posix()]=sha256(p.read_bytes().decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n').encode()).hexdigest()
for name in ('requirements-test.txt','.gitattributes','.gitignore','AGENTS.md'):
    records[name]=sha256((S/name).read_bytes().decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n').encode()).hexdigest()
check('candidate_identity_216',len(records)==216 and sha256(canonical(records)).hexdigest()==package['source_manifest_hash']=='74bbefc270a6bd0d1385db9624eaa2bd600e38503f5932a88267a02a11c76a07')
for name in records:check('source_materials_managed_raw:'+name,(S/name).read_bytes()==(M/name).read_bytes())
changes=git(['diff','--name-only','2d1d3060dbc7eb136c1dee61f0647977528b8aad','fe088461e84586d7feb73f20be54a22d09706942']).decode().splitlines()
check('source_to_materials_only_audit',all(n.startswith('audit/') for n in changes),changes)
cloud_changes=git(['diff','--name-only','975f676d62b561689909744f9e7236290e3f5fcb','2d1d3060dbc7eb136c1dee61f0647977528b8aad','--','cloud','config']).decode().splitlines()
check('production_cloud_config_unchanged_from975',not cloud_changes,cloud_changes)

# Check guarded development evidence without conflating working-tree CRLF with Git.
before=read(M/'audit/review_packages/host010/full_offline_validation/main_guard_before.json')
after=read(M/'audit/review_packages/host010/full_offline_validation/main_guard_after.json')
check('developer_guard_before_after346',len(before)==346 and before==after)
guard_representations=[]
for name,digest in before.items():
    p=S/name;raw=p.read_bytes()
    if sha256(raw).hexdigest()!=digest:
        try:
            crlf=raw.decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n').replace('\n','\r\n').encode()
        except UnicodeError:crlf=b''
        check('recorded_worktree_representation:'+name,sha256(crlf).hexdigest()==digest)
        guard_representations.append(name)
    else:check('guarded_candidate_raw:'+name,True)
proof=read(M/'audit/review_packages/host010/protected_history.json')
for name,item in proof['files'].items():
    old=git(['show',proof['prior_commit']+':'+name]);raw=(S/name).read_bytes()
    check('protected_original_Git_hash:'+name,sha256(old).hexdigest()==item['prior_git_sha256'])
    check('protected_current_Git_raw:'+name,old==raw and raw==(M/name).read_bytes())
    if name=='audit/data_exposure.json':check('disclosed_worktree_facts_equal',item['raw_equal'] is False and item['facts_equal'] is True)

# Independently recompute the event chain then use the production replay in private Memory.
journal=(S/'audit/runtime/registry/events.jsonl').read_bytes();events=[json.loads(line) for line in journal.splitlines()]
prev=None
for n,event in enumerate(events,1):
    content={k:event[k] for k in ('event','previous_hash','sequence')}
    check('event_chain:'+str(n),event['sequence']==n and event['previous_hash']==prev and sha256(canonical(content)).hexdigest()==event['hash'])
    prev=event['hash']
check('journal71_unchanged',len(events)==71 and sha256(journal).hexdigest()=='cea800e0fe5a0facc5f2aed238d105a6f3d1c80db40c1dc4b674efd3026cd48a')
check('prior69_raw_prefix',sha256(b''.join(journal.splitlines(keepends=True)[:69])).hexdigest()=='2d3131a32864434d22635f058ec3de8062e9b1b610a90185bf6ba6cf9c637934')
sys.path.insert(0,str(S/'cloud'))
from qresearch.artifacts import MemoryArtifactStore
from qresearch.registry import Registry
store=MemoryArtifactStore()
for p in (S/'audit/runtime').rglob('*'):
    if p.is_file():store.write_once(p.relative_to(S/'audit/runtime').as_posix(),p.read_bytes())
reg=Registry(store,json.loads((S/'audit/runtime/registry/baseline.json').read_bytes()))
snapshot=reg.snapshot();cycle=reg.configuration_cycle_snapshot()
check('Registry_usage_lifetime',tuple(snapshot['usage'][k]['total'] for k in ('configurations','research','lean'))==(16,17,3))
check('Registry_configuration_cycle',cycle['usage']['total']==3 and cycle['capacity']['total']==13)
check('Registry_journal_readonly_replay',store.read_bytes('registry/events.jsonl')==journal)
check('old_failed_research_preserved',any(a['status']=='failed' and a['stage']=='research' for a in snapshot['attempts']))
nextplan=read(M/'audit/review_packages/host010/next_engineering_preparation.json')
check('next_plan_not_admitted',nextplan['execution_enabled'] is False and nextplan['registered'] is False and nextplan['no_admission_or_debit_performed'] is True and all(nextplan[k] is None for k in ('attempt_id','external_backtest_id','project_id')))
for key in ('new_cloud_calls','new_budget_events'):
    check('development_no_actions:'+key,development[key]==0 and package[key]==0)
ready=read(M/'audit/stage2_current_readiness.json');tracking=read(M/'audit/review_tracking.json')
check('old_approval_not_rebound',tracking['reviewed_source_commit']=='975f676d62b561689909744f9e7236290e3f5fcb' and registry_result['new_host_implementation_inherits_this_acceptance'] is False)
check('new_candidate_pending',ready['candidate_independent_acceptance'] is False and ready['candidate_cloud_deployed'] is False and package['independent_review_status']=='pending')
check('all_closed_gates',all(v is False for v in ready['execution_gates'].values()))
check('stage2_financial_not_accepted',ready['stage2_accepted'] is False and ready['financial_evidence'] is False and registry_result['stage2_accepted'] is False and registry_result['financial_evidence'] is False)

# Preserve and independently verify provisional long-path generated evidence removal.
repair=read(M/'audit/review_packages/host010/delivery_import_repair.json');provisional=repair['prior_provisional_delivery_commit']
provisional_tree=tree(provisional);final_tree=tree('fe088461e84586d7feb73f20be54a22d09706942')
removed=[]
for item in repair['removed_generated_copies']:
    name='audit/review_packages/host010/'+item['path']
    check('provisional_synthetic_copy_present:'+name,name in provisional_tree and name not in final_tree)
    raw=git(['cat-file','blob',provisional_tree[name]['oid']])
    check('provisional_raw_kept_by_Git:'+name,sha256(raw).hexdigest()==item['original_sha256'])
    removed.append(name)
check('removed14_and_no_source_change',len(removed)==14 and repair['product_source_changed'] is False and repair['source_manifest_changed'] is False)
check('probe_retained',(M/'audit/review_packages/host010/provisional_checkout_probe.json').is_file())
check('no_remaining_synthetic_store_copies',not any('/host010/developer_boundary/synthetic-' in name for name in final_tree))
guards=json.loads((R/'source_git_manifest.json').read_text(encoding='utf-8'))
for folder,item in guards.items():
    check('fixed_export_unchanged:'+folder,all(rawhash(R/folder/name)==old['sha256'] for name,old in item['files'].items()))
result={'reviewed_source_commit':package['source_commit'],'materials_commit':'fe088461e84586d7feb73f20be54a22d09706942','static_checks':checks,'static_logical_checks':len(checks),'unit_methods':0,'findings':[],
 'old_ZIP':{'raw_sha256':rawhash(oldzip),'CRC':True,'manifest_entries':14330,'ZIP_entries':14331,'complete_old_Git_blob_counts':gitcounts},
 'selected_archive':{'originals':205,'original_bytes':totalbytes,'direct_raw':plain,'mirrors_with_raw_base64':mirrors,'representation_files':len(manifest['files']),'actual_files':len(actual),'scope_not_full_original_bundle':True,'actual_reviewer':'local Codex thread 01a175b6-fed2-77d0-a763-522b6fd695cf; former ChatGPT handoff only'},
 'identity':{'source_manifest_hash':sha256(canonical(records)).hexdigest(),'managed_files':len(records),'cloud_config_unchanged_from975':True},
 'development_guard':{'records':346,'before_after_exact_equal':True,'recorded_worktree_CRLF_vs_Git':guard_representations,'original_developer_worktree_live_observation':False},
 'budget':{'events':71,'journal_sha256':sha256(journal).hexdigest(),'prior69_prefix_preserved':True,'lifetime':snapshot['usage'],'configuration_cycle':cycle,'new_events':0,'new_debits':0,'refunds':0,'original_human_authorization_dialogue_independently_obtained':False},
 'provisional_import':{'commit':provisional,'removed_generated_copies':len(removed),'original_Git_blobs_verified':True,'Windows_long_path_checkout_not_repeated':True},
 'limitations':['Selected archive remains incomplete original bundle; full original old ZIP was separately reverified here.','Reviewer identity metadata compared to trusted inherited execution context and original artifacts; no external chat was read or messaged.','No actual platform/source authenticity proof beyond immutable Git/ZIP and archived metadata; no new cloud run.','346 developer before/after logs are archived evidence, not a new observation of the developers live worktree.'],
 'cloud_calls':0,'authoritative_budget_or_production_writes':0,'financial_evidence':False}
(A/'static_results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
(A/'git_execution.json').write_text(json.dumps(git_records,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'checks':len(checks),'all_passed':True,'originals':205,'raw_original_bytes':totalbytes,'Git_old_files':gitcounts,'source_files':len(records),'guard346_worktree_representations':guard_representations},ensure_ascii=False),flush=True)
