from pathlib import Path
from hashlib import sha256,sha1
import base64,io,json,sys,subprocess,zipfile,platform
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parents[1]; A=Path(__file__).resolve().parent
S=R/'source'; M=R/'materials'; X=M/'audit/reviews/20261029-2d1d306-host010'; W=M/'audit/review_packages/wr29'
G=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\repo')
checks=[];commands=[]
def canonical(v):return json.dumps(v,sort_keys=True,ensure_ascii=True,separators=(',',':'),allow_nan=False).encode()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def h(raw):return sha256(raw).hexdigest()
def check(label,condition,detail=None):
    checks.append({'name':label,'passed':bool(condition),'details':detail})
    if not condition:raise AssertionError((label,detail))
def git(args):
    cmd=['git','-C',str(G),*args];p=subprocess.run(cmd,capture_output=True)
    commands.append({'command':cmd,'exit_code':p.returncode,'stdout_sha256':h(p.stdout),'stderr_sha256':h(p.stderr)})
    check('git_exit:'+str(len(commands)),p.returncode==0)
    return p.stdout
def tree(commit):
    result={}
    for row in git(['ls-tree','-r','-z',commit]).split(b'\0'):
        if not row:continue
        header,name=row.split(b'\t',1);mode,kind,oid=header.split()
        check('Git_tree_blob:'+commit[:7]+':'+name.decode(),kind==b'blob')
        result[name.decode()]=oid.decode()
    return result
index=read(X/'import_index.json'); manifest=read(X/'archive_manifest.json')
package=read(M/'audit/current_review_package.json'); dev=read(M/'audit/wr29_development_report.json')
oldzip=Path(index['source_bundle']['local_path'])
check('ZIP_exists',oldzip.is_file())
check('ZIP_full_raw_sha',h(oldzip.read_bytes())==index['source_bundle']['sha256']=='feffb44a08485c0ac7dd87b46f47b53e810964c270ae41a9446ae6980aba4723')
check('ZIP_size',oldzip.stat().st_size==42172794)
with zipfile.ZipFile(oldzip) as z:
    check('ZIP_CRC',z.testzip() is None)
    names=set(z.namelist()); fullraw=z.read('artifact_manifest.json'); full=json.loads(fullraw)
    check('ZIP_complete_set',names==set(full['files'])|{'artifact_manifest.json'})
    check('ZIP_counts',len(names)==14692 and len(full['files'])==14691)
    check('ZIP_manifest_original_hash',h(fullraw)==index['source_bundle']['original_manifest_sha256'])
    for name,item in full['files'].items():
        raw=z.read(name);check('ZIP_raw:'+name,len(raw)==item['bytes'] and h(raw)==item['sha256'])
    gitcounts={}
    for folder,commit in {'source':'2d1d3060dbc7eb136c1dee61f0647977528b8aad','materials':'fe088461e84586d7feb73f20be54a22d09706942'}.items():
        entries=tree(commit);cmd=['git','-C',str(G),'cat-file','--batch']
        result=subprocess.run(cmd,input=''.join(oid+'\n' for oid in entries.values()).encode(),capture_output=True)
        commands.append({'command':cmd,'requested_blobs':len(entries),'exit_code':result.returncode,'stderr_sha256':h(result.stderr)})
        check('Git_batch_exit:'+folder,result.returncode==0)
        stream=io.BytesIO(result.stdout)
        for name,wanted in entries.items():
            oid,kind,size=stream.readline().strip().split();raw=stream.read(int(size));separator=stream.read(1)
            check('Git_original_blob:'+folder+'/'+name,oid.decode()==wanted and kind==b'blob' and separator==b'\n' and sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==wanted and raw==z.read(folder+'/'+name))
        check('Git_batch_consumed:'+folder,stream.read()==b'');gitcounts[folder]=len(entries)
    check('selected_representation_counts',len(manifest['original_artifacts'])==161 and len(manifest['files'])==246)
    actual={p.relative_to(X).as_posix() for p in X.rglob('*') if p.is_file()}
    check('selected_complete_set',actual==set(manifest['files'])|{'archive_manifest.json'})
    for name,item in manifest['files'].items():
        raw=(X/name).read_bytes();check('selected_representation:'+name,len(raw)==item['bytes'] and h(raw)==item['sha256'])
    originals={};mirrors=plain=total=0
    for name,item in manifest['original_artifacts'].items():
        readable=(X/item['readable_path']).read_bytes()
        check('readable:'+name,len(readable)==item['readable_bytes'] and h(readable)==item['readable_sha256'])
        if 'raw_base64_path' in item:
            b64=(X/item['raw_base64_path']).read_bytes(); raw=base64.b64decode(b''.join(b64.split()),validate=True);mirrors+=1
            check('base64_representation:'+name,len(b64)==item['raw_base64_bytes'] and h(b64)==item['raw_base64_sha256'])
            check('LF_mirror_declared_not_raw:'+name,item['representation']=='readable_UTF8_LF_mirror_not_original_bytes' and b'\r' not in readable and not readable.startswith(b'\xef\xbb\xbf'))
            readable.decode('utf-8')
        else:raw=readable;plain+=1;check('unchanged_representation:'+name,item['representation']=='original_UTF8_LF_bytes_unchanged')
        check('restored_original:'+name,len(raw)==item['original_bytes'] and h(raw)==item['original_sha256'] and raw==z.read(item['zip_entry']))
        originals[name]=raw;total+=len(raw)
    check('selected_original_counts',plain==77 and mirrors==84 and total==614188)
    omitted=set(index['selection']['excluded']['exact_entries'])
    for prefix in index['selection']['excluded']['prefixes']:omitted|={n for n in names if n.startswith(prefix)}
    check('selected_omitted_partition',set(originals).isdisjoint(omitted) and set(originals)|omitted==names and len(omitted)==14531)
    for name,item in index['selection']['excluded']['exact_entries'].items():
        raw=z.read(name);check('omitted_raw_location:'+name,len(raw)==item['bytes'] and h(raw)==item['sha256'])
formal=json.loads(originals['formal_report.json']); registration=read(M/'audit/review_results/host010.json')
check('formal_old_raw_hash',h(originals['formal_report.json'])=='224a7b8a0e7667b6759e685f71dae0fd54ba0eb6c914ced1c9c1332deb009e14')
check('formal_old_failure_retained',formal['reviewed_source_commit']=='2d1d3060dbc7eb136c1dee61f0647977528b8aad' and len(formal['findings'])==1 and formal['findings'][0]['id']=='WR-29' and formal['findings'][0]['priority']=='P1' and formal['software_acceptance']['new_host_enabled_CLI_stdio']=='失败_WR29')
check('formal_readable_semantics',read(X/'formal_report.json')==formal)
check('formal_registration_keeps_tests_and_failure',registration['tests']==formal['tests'] and registration['findings']==formal['findings'] and registration['verdict']=='failed_enabled_CLI_stdio_WR29')
for name in ('minimum_execution.json','minimum.stdout','minimum.stderr','minimal_wr29.py','stdio_agent/first_script.py','stdio_agent/first.stderr','stdio_agent/report.json','host_api_agent/first_script.py','host_api_agent/report.json','host_api_agent/formal_QA.json','stdio_agent/formal_QA.json','archive_agent/formal_QA.json'):
    check('original_failures_QA_kept:'+name,name in originals)
check('original_minimum_failure_kept',json.loads(originals['minimum_execution.json'])['exit_code']==1)
check('original_stdio_2_failures_kept',json.loads(originals['stdio_agent/report.json'])['failed_methods']==2)
check('original_API_limited_pass_kept',json.loads(originals['host_api_agent/report.json'])['findings']==[])
check('selected_scope_not_complete',manifest['selected_archive_not_complete_original_bundle'] is True and index['selected_archive_not_complete_original_bundle'] is True and registration['archive_is_selected_not_complete_bundle'] is True)
check('actual_local_review_identity',index['actual_executing_review_task']['thread_id']=='01a175b6-fed2-77d0-a763-522b6fd695cf' and index['actual_executing_review_task']['kind']=='codex')
check('former_ChatGPT_only_handoff',index['previous_handoff_only']['this_thread_executed_the_current_review'] is False)

# Independently rebuild the normalized manifest and distinguish immutable Git
# bytes from the developer's before/after worktree representation.
files={}
for folder in ('cloud','config','templates','tests','tools','docs','.github'):
    for p in (S/folder).rglob('*'):
        if p.is_file() and p.suffix in {'.py','.json','.md','.yml','.yaml'} and '__pycache__' not in p.parts:
            files[p.relative_to(S).as_posix()]=h(p.read_bytes().decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n').encode())
for name in ('requirements-test.txt','.gitattributes','.gitignore','AGENTS.md'):
    files[name]=h((S/name).read_bytes().decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n').encode())
check('current_identity218',len(files)==218 and h(canonical(files))==package['source_manifest_hash']=='9d0d6da95815ee77d993d823df616d575a3ec4f00f5e40e859a7858de02dad5f')
for name in files:check('current_source_materials_raw:'+name,(S/name).read_bytes()==(M/name).read_bytes())
changed=git(['diff','--name-only','c2e63ac5f19901bd95e127069b5998452f7f9864','f698a38a99c3ed8388c9403f2eda723b579c5eaf']).decode().splitlines()
check('materials_only_audit',all(n.startswith('audit/') for n in changed),changed)
cloudchanges=git(['diff','--name-only','2d1d3060dbc7eb136c1dee61f0647977528b8aad','c2e63ac5f19901bd95e127069b5998452f7f9864','--','cloud','config']).decode().splitlines()
check('shared_cloud_config_unchanged',not cloudchanges,cloudchanges)
before=read(W/'full_offline_validation/main_guard_before.json');after=read(W/'full_offline_validation/main_guard_after.json')
check('developer348_before_after_raw_equal',len(before)==348 and before==after)
representations=[]
for name,digest in before.items():
    raw=(S/name).read_bytes()
    if h(raw)!=digest:
        crlf=raw.decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n').replace('\n','\r\n').encode()
        check('worktree_CRLF_not_Git:'+name,h(crlf)==digest);representations.append(name)
    else:check('guarded_raw:'+name,True)
proof=read(W/'protected_history.json')
check('five_disclosed_worktree_representations',sorted(representations)==sorted(proof['historical_worktree_representation_differences']) and len(representations)==5)
for name,item in proof['files'].items():
    raw=(S/name).read_bytes();old=git(['show',proof['prior_commit']+':'+name])
    check('protected_original_git:'+name,h(old)==item['prior_git_sha256'] and raw==old and raw==(M/name).read_bytes())
    if name=='audit/data_exposure.json':check('exposure_worktree_facts',json.loads(old)==json.loads(old.decode('utf-8').replace('\n','\r\n')) and item['worktree_raw_matches_git'] is False)

# Independent hash-chain and private Memory-only production replay.
journal=(S/'audit/runtime/registry/events.jsonl').read_bytes();events=[json.loads(line) for line in journal.splitlines()];previous=None
for number,event in enumerate(events,1):
    check('journal_chain:'+str(number),event['sequence']==number and event['previous_hash']==previous and h(canonical({k:event[k] for k in ('event','previous_hash','sequence')}))==event['hash']);previous=event['hash']
check('journal71_original_hash',len(events)==71 and h(journal)=='cea800e0fe5a0facc5f2aed238d105a6f3d1c80db40c1dc4b674efd3026cd48a')
prefix=h(b''.join(journal.splitlines(keepends=True)[:69]));check('old69_raw_prefix',prefix=='2d3131a32864434d22635f058ec3de8062e9b1b610a90185bf6ba6cf9c637934')
sys.path.insert(0,str(S/'cloud'))
from qresearch.artifacts import MemoryArtifactStore
from qresearch.registry import Registry
store=MemoryArtifactStore()
for p in (S/'audit/runtime').rglob('*'):
    if p.is_file():store.write_once(p.relative_to(S/'audit/runtime').as_posix(),p.read_bytes())
reg=Registry(store,read(S/'audit/runtime/registry/baseline.json'));snapshot=reg.snapshot();cycle=reg.configuration_cycle_snapshot()
check('private_replay_usage',tuple(snapshot['usage'][k]['total'] for k in ('configurations','research','lean'))==(16,17,3))
check('private_replay_cycle',cycle['usage']['total']==3 and cycle['capacity']['total']==13)
check('private_replay_journal_unchanged',store.read_bytes('registry/events.jsonl')==journal)
ready=read(M/'audit/stage2_current_readiness.json');tracking=read(M/'audit/review_tracking.json');plan=read(W/'next_engineering_preparation.json')
check('008_closed',ready['current_round_closed'] is True and ready['new_submit_allowed'] is False)
check('candidate_pending_not_developer_closed',ready['candidate_independent_acceptance'] is False and tracking['current_candidate']['independent_acceptance'] is False and dev['WR29_independently_closed'] is False)
check('candidate_exact_SHA',ready['candidate_runtime_source_commit']==package['source_commit']==tracking['current_candidate']['source_commit']=='c2e63ac5f19901bd95e127069b5998452f7f9864')
check('new_candidate_no_cloud',ready['candidate_cloud_deployed'] is False and dev['cloud_deployed'] is False)
check('new_plan_not_admitted',plan['registered'] is False and plan['execution_enabled'] is False and plan['no_admission_or_debit_performed'] is True and all(plan[k] is None for k in ('attempt_id','external_backtest_id','project_id')))
check('whole_stage_and_financial_closed',all(d['stage2_accepted'] is False and d['financial_evidence'] is False for d in (ready,tracking,registration,dev)))
check('execution_gates_closed',all(v is False for v in ready['execution_gates'].values()) and dev['final_test_enabled'] is False)
check('prior_exposure_preserved',ready['prior_2024_2025_exposure_preserved'] is True and ready['year2026_independence']=='not_certified')

# Developer auxiliary runs are preserved evidence, not independent passes.
devrecords=read(W/'developer_records_manifest.json'); recovered={}
for name,item in devrecords['records'].items():
    readable=(M/item['readable_path']).read_bytes();check('dev_readable:'+name,h(readable)==item['readable_sha256'])
    raw=base64.b64decode(b''.join((M/item['raw_base64_path']).read_bytes().split()),validate=True) if 'raw_base64_path' in item else readable
    if 'raw_base64_path' in item:check('dev_raw_b64:'+name,h((M/item['raw_base64_path']).read_bytes())==item['raw_base64_sha256'])
    check('dev_original_recovery:'+name,len(raw)==item['original_bytes'] and h(raw)==item['original_sha256']);recovered[name]=raw
selection=read(W/'boundary-selected_evidence.json');auxraw={}
for item in selection['files']:
    stem='boundary-'+item['path'].removeprefix('export/')
    p=W/stem; sidecar=p.with_name(p.name+'.raw.base64')
    raw=base64.b64decode(b''.join(sidecar.read_bytes().split()),validate=True) if sidecar.exists() else p.read_bytes()
    check('aux_original_selected:'+stem,len(raw)==item['bytes'] and h(raw)==item['sha256']);auxraw[stem]=raw
round1=json.loads(auxraw['boundary-02-round1.json']);round2=json.loads(auxraw['boundary-03-round2.json'])
check('aux_first79of84',len(round1['cases'])==84 and sum(c['passed'] for c in round1['cases'])==79 and len(round1['failures'])==5)
check('aux_second89of90',len(round2['cases'])==90 and sum(c['passed'] for c in round2['cases'])==89 and len(round2['failures'])==1)
trace=auxraw['boundary-04-eacces-trace.txt'].decode('utf-8');check('aux_exact_trace_append_EACCES','PermissionError: [Errno 13]' in trace and 'append_event' in trace and 'path.open("ab")' in trace)
summary=json.loads(auxraw['boundary-19-summary.json'])
check('aux_not_retrospective_same_cause',any('not retrospectively proven' in text for text in summary['limitations']))
focused=json.loads(auxraw['boundary-05-focused10.json']); recovery=json.loads(auxraw['boundary-06-recovery8.json'])
check('aux_recovery8',len(recovery['checks'])==8 and all(row['passed'] for row in recovery['checks']) and len(recovery['records'])==3)
check('aux_focused10',type(focused) is dict and len(focused['records'])==10 and all(row['exit']==0 and row['passed'] is True for row in focused['records']))
check('aux_all_before_after_host_source_hash',round1['source_sha256']==round1['source_sha256_after']==round2['source_sha256']==round2['source_sha256_after'])
check('developer_aux_not_independent',summary['scope']=='development_support_only_not_formal_GPT_acceptance_or_financial_evidence' and summary['real_operations']['production_store_access']==0 and summary['real_operations']['authoritative_budget_mutations']==0)

rawmaps=read(R/'source_git_manifest.json');guards={}
for folder,item in rawmaps.items():
    changed=[name for name,old in item['files'].items() if h((R/folder/name).read_bytes())!=old['sha256']]
    check('fixed_original_unchanged:'+folder,not changed,changed);guards[folder]={'files':len(item['files']),'changed':changed}
result={'source_commit':package['source_commit'],'materials_commit':'f698a38a99c3ed8388c9403f2eda723b579c5eaf','static_checks':checks,'static_logical_checks':len(checks),'unit_methods':0,'findings':[],
 'old_complete_ZIP':{'raw_sha256':h(oldzip.read_bytes()),'CRC':True,'manifest_entries':14691,'ZIP_entries':14692,'old_Git_blob_counts':gitcounts},
 'selected_archive':{'originals':161,'original_bytes':total,'direct_raw':plain,'mirrors_with_raw_base64':mirrors,'representation_files':len(manifest['files']),'actual_files':len(actual),'not_complete_bundle':True},
 'identity':{'managed_files':len(files),'source_hash':h(canonical(files)),'cloud_config_unchanged_from2d':True},
 'developer_guard':{'records':348,'before_after_exact_equal':True,'worktree_CRLF_vs_Git':representations,'developer_live_worktree_independently_read':False},
 'budget':{'events':71,'journal_sha256':h(journal),'prior69_prefix_sha256':prefix,'lifetime':snapshot['usage'],'configuration_cycle':cycle,'new_events':0,'new_debits':0,'refunds':0,'original_human_authorization_dialogue_independently_obtained':False},
 'developer_auxiliary':{'first':{'passed':79,'total':84,'untraced_receipt_failures':2,'fixture_errors':3},'second':{'passed':89,'total':90,'captured_append_EACCES':1},'recovery8':True,'focused_clones10':True,'not_all_runs_green':True,'first_two_cause_not_proven_same_as_EACCES':True,'original_historical_stores_not_replayed_here':True},
 'source_guard':guards,'scope':{'old_WR29_report_preserved_open_at2d':True,'old_API_and975_finite_passes_preserved':True,'new_WR29_independent_verdict':'not_determined_by_archive_checks','full_phase2_accepted':False},
 'limitations':['Raw provenance established only against immutable Git/local sealed ZIP, not a native remote signature.','Selected 161 original entries are not the complete original bundle; old full ZIP separately reverified here.','Developer auxiliary original stores are deliberately excluded; original historical store/cloned scripts were not executed from absent stores.','Budget authorization material is only replayed as existing metadata; original human dialogue not independently obtained.'],
 'external_calls':{'QC':0,'Research':0,'LEAN':0,'compile':0,'market':0,'model':0},'authoritative_budget_or_production_writes':0,'financial_evidence':False}
(A/'static_results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
(A/'git_execution.json').write_text(json.dumps(commands,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'checks':len(checks),'all_passed':True,'originals':len(originals),'raw_original_bytes':total,'old_Git_blobs':gitcounts,'source_identity_files':len(files),'guards':guards},ensure_ascii=False),flush=True)
