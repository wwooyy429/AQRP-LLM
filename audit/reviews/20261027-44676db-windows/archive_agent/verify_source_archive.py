from pathlib import Path
import ast,collections,copy,hashlib,io,json,os,platform,subprocess,sys,tarfile,time,traceback,zipfile
R=Path(__file__).resolve().parent;S=R.parent/'source'
G=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\repo')
O=Path('B:/BaiduSyncdisk/学习/投资/量化/量化交易比赛/LLM审核/review-ccad61d-20261027')
C='44676db609b3b7c2175fa7fa4f19c8ccf8165458';B='ccad61d03ccf17bf2bdc2d7ffc88dfd11b6d3ca6';A='7fc5ef2e9d2379d29f48d05a1f3cc760000884d6'
checks=[];commands=[];cache={}
def sha(b):return hashlib.sha256(b).hexdigest()
def canonical(v):return json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
def norm(b):return b.decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n').encode()
def doc(b):return json.loads(b.decode('utf-8-sig'))
def write(p,v):p.write_bytes((json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode())
def check(name,ok,detail=None):checks.append({'name':name,'passed':bool(ok),'detail':detail})
def run(label,args,binary=False):
    start=time.perf_counter();p=subprocess.run(args,capture_output=True,env=dict(os.environ,GIT_OPTIONAL_LOCKS='0'))
    row={'label':label,'command':args,'exit_code':p.returncode,'seconds':round(time.perf_counter()-start,3),'stdout_raw_sha256':sha(p.stdout),'stdout_bytes':len(p.stdout),'stderr_raw_sha256':sha(p.stderr),'stderr_bytes':len(p.stderr),'binary_stdout_reconstructible_not_retained':binary}
    if not binary or p.returncode:(R/(label+'.stdout')).write_bytes(p.stdout)
    (R/(label+'.stderr')).write_bytes(p.stderr);commands.append(row);write(R/'git_commands.json',commands)
    if p.returncode:raise RuntimeError(label)
    return p.stdout
def tree(c,label):
    if c not in cache:
        raw=run(label,['git','-C',str(G),'archive',c],True)
        with tarfile.open(fileobj=io.BytesIO(raw)) as t:cache[c]={m.name:t.extractfile(m).read() for m in t.getmembers() if m.isfile()}
    return cache[c]
def manifest(files):return {p:sha(norm(b)) for p,b in files.items() if (Path(p).parts[0] in ('cloud','config','templates','tests','tools','docs','.github') and Path(p).suffix in ('.py','.json','.md','.yml','.yaml') and '__pycache__' not in Path(p).parts) or p in ('requirements-test.txt','.gitattributes','.gitignore','AGENTS.md')}
def assignments(b):return {n.targets[0].id:ast.literal_eval(n.value) for n in ast.parse(b).body if isinstance(n,ast.Assign)}
def main():
    files=tree(C,'candidate_archive');base=tree(B,'baseline_archive');actual=tree(A,'actual7fc_archive')
    disk={p.relative_to(S).as_posix():p.read_bytes() for p in S.rglob('*') if p.is_file()}
    check('all_candidate_raw_files_equal_fixed_Git',disk==files,{'files':len(files)})
    delta=run('baseline_to_candidate_name_status',['git','-C',str(G),'diff','--name-status','--no-renames',B,C])
    patch=run('baseline_to_candidate_full_patch',['git','-C',str(G),'diff','--no-ext-diff','--binary',B,C])
    m=manifest(files);mh=sha(canonical(m));stage=doc(files['audit/stage_verification.json'])
    check('full_review_manifest_matches_actual_sources',m==stage['source_files'] and mh==stage['source_hash'],{'count':len(m),'hash':mh})
    budget=doc(files['config/budget.json']);policy=copy.deepcopy(budget);policy.pop('usage',None);em=dict(m);em['config/budget.json']=sha(canonical(policy));eh=sha(canonical({'schema':'collection_execution_sources_v1','source_files':em}))
    generated=assignments(files['cloud/research_config.py']);old=assignments(base['cloud/research_config.py']);deploy={p[6:]:sha(norm(b)) for p,b in files.items() if p.startswith('cloud/') and p.endswith('.py')};impl={Path(p).name:sha(norm(b)) for p,b in files.items() if p.startswith('cloud/qresearch/') and p.endswith('.py')}
    ih=sha(canonical(impl));dh=sha(canonical(deploy));deployment=doc(files['audit/deployment.json'])
    check('normalized_LF_keep_EOF31_deployment',len(deploy)==31 and deployment['source_files']==deploy and deployment['implementation_hash']==generated['IMPLEMENTATION_SHA256']==ih,{'implementation_hash':ih,'deployment_hash':dh})
    configs={k:doc(files['config/'+k+'.json']) for k in ('research','universe','data','workflow','budget')}
    cfg={k:v for k,v in configs.items() if k!='budget'}|{'configuration_id':configs['research']['configuration_id'],'budget_limits':configs['budget']['limits'],'budget_allocations':configs['budget']['allocations'],'active_factor':configs['research']['active_factor_spec'],'active_model':configs['research']['active_model_spec'],'active_trading_rules':configs['research']['active_trading_spec']}
    ch=sha(canonical(cfg));check('active_economic_configuration_recomputed_and_unchanged',cfg==generated['CONFIGURATION']==old['CONFIGURATION'] and ch==generated['SOURCE_SHA256']==old['SOURCE_SHA256']==deployment['configuration_hash'],{'hash':ch})
    check('all_config_raw_bytes_unchanged',all(files.get(p)==b for p,b in base.items() if p.startswith('config/')))
    protected=[p for p in base if p.startswith(('audit/runtime/','audit/task_inputs/','audit/tool_observations/')) or p in ('config/budget.json','audit/data_exposure.json')]
    check('all_runtime_input_observation_budget_exposure_raw_preserved',all(files.get(p)==base[p] for p in protected),{'files':len(protected)})
    archived=[p for p in base if p.startswith(('audit/reviews/','audit/review_packages/'))]
    check('all_previous_archived_evidence_raw_preserved',all(files.get(p)==base[p] for p in archived),{'files':len(archived)})
    pack='audit/review_packages/wr25_wr27/';dev=doc(files[pack+'developer_verification.json']);rawmanifest=doc(files[pack+'developer_outputs_manifest.json']);rows=rawmanifest['entries'];bad=[]
    for row in rows:
        b=files.get(row['path'])
        if b is None or sha(b)!=row['raw_sha256'] or len(b)!=row['bytes']:bad.append(row['path'])
    check('developer_raw_output_manifest_all_files',not bad,{'entries':len(rows),'bad':bad})
    extras=sorted({p for p in files if p.startswith(pack)}-{r['path'] for r in rows})
    check('developer_unmanifested_only_explicit_meta',set(extras)=={pack+s for s in ('.gitattributes','README.md','developer_verification.json','developer_outputs_manifest.json')},extras)
    check('developer_identity_claims_match_fixed_candidate',dev['source_manifest_hash']==mh and dev['execution_source_manifest_hash']==eh and dev['implementation_hash']==ih and dev['deployment_hash']==dh and dev['active_economic_configuration_hash']==ch)
    check('developer668_final_report_not_independent_acceptance',dev['test_methods']==668 and stage['local_tests_passed'] is True and 'Ran 668 tests' in stage['test_output'] and dev['independent_acceptance'] is False and dev['financial_evidence'] is False)
    tested=[p for p in m if p not in ('requirements-test.txt','.gitattributes','.gitignore','AGENTS.md')]
    check('developer_tested_source_count_scope141',dev['tested_source_file_count']==len(tested),{'tested':len(tested),'review_including_four_roots':len(m)})
    check('developer_single_final_source_freeze', 'One final frozen version' in dev['source_freeze_note'] and dev['all_tested_source_bytes_unchanged'] is True)
    journal=files['audit/runtime/registry/events.jsonl'];events=[json.loads(line) for line in journal.splitlines()]
    check('17events_raw_equal_ea',len(events)==17 and journal==base['audit/runtime/registry/events.jsonl'],{'raw_sha256':sha(journal)})
    prior13=run('old13_registry',['git','-C',str(G),'show','66ff72ffaaff8c91c008898e6527c91131176c2a:audit/runtime/registry/events.jsonl'])
    check('old13_raw_prefix_preserved',len(prior13.splitlines())==13 and journal.startswith(prior13))
    previous=None
    for i,e in enumerate(events,1):
        check('journal_chain_'+str(i),e['sequence']==i and e['previous_hash']==previous and sha(canonical({k:v for k,v in e.items() if k!='hash'}))==e['hash']);previous=e['hash']
    usage=copy.deepcopy(events[0]['event']['initial_usage']);engineering=set();attempts={}
    for envelope in events[1:]:
        e=envelope['event'];kind=e['kind']
        if kind in ('config_registered','config_imported'):
            p=doc(files['audit/runtime/configurations/'+e['config_id']+'.json'])
            if p.get('engineering_task_schema_version')==1 and p.get('plan',{}).get('scope')=='engineering':engineering.add(e['config_id'])
            if kind=='config_registered':usage['configurations']['total']+=1;usage['configurations'][e['allocation']]+=1
        if kind=='attempt_started':attempts[e['attempt_id']]=dict(e,status='started');usage[e['stage']]['total']+=1;usage[e['stage']][e['allocation']]+=1
        if kind in ('pending','completed','failed','submission_unknown'):attempts[e['attempt_id']].update(e,status=kind)
    eng={'configurations':len(engineering),**{k:sum(a['config_id'] in engineering and a['stage']==k for a in attempts.values()) for k in ('research','lean')}}
    check('independent_budget_replay_7_10_1',[usage[k]['total'] for k in ('configurations','research','lean')]==[7,10,1],usage)
    check('budget_projection_7_10_1',[budget['usage'][k] for k in ('configuration_budget_charges','research_execution_attempts','lean_submission_attempts')]==[7,10,1])
    check('engineering_2_2_1_stopped',eng=={'configurations':2,'research':2,'lean':1},eng)
    sys.path.insert(0,str(S/'cloud'));from qresearch.artifacts import MemoryArtifactStore;from qresearch.registry import Registry
    store=MemoryArtifactStore()
    for p,b in files.items():
        if p.startswith('audit/runtime/'):store.write_once(p[len('audit/runtime/'):],b)
    snap=Registry(store,doc(files['audit/runtime/registry/baseline.json'])).snapshot()
    check('memory_Registry_snapshot_matches_independent_replay',snap['usage']==usage and store.read_bytes('registry/events.jsonl')==journal)
    a='f5d05f5b964b4a1d924e4b70cd207386';ad=doc(files['audit/runtime/engineering/admitted-inputs/'+a+'.json']);dispatch=doc(files['audit/runtime/engineering/research-dispatch/'+a+'.json']);nativebytes=files['audit/tool_observations/'+a+'-research.json'];native=doc(nativebytes);carriers=[json.loads(c['text']) for c in native['result']['content'] if c['type']=='text'];trace=carriers[0]['traceback']
    check('original_native_packet14ae_and_2_identical_carriers',sha(nativebytes)=='14ae4a18636496737862a1ce314d90ae7fcf1abaf35f8a0f27145e0e839af8f3' and len(carriers)==2 and carriers[0]==carriers[1],{'packet_hash':sha(nativebytes),'logical_failures':1,'representations':len(carriers)})
    check('native_CollectionError9entries43physical',carriers[0]['ename']=='CollectionError' and len(trace)==9 and sum(len(x.splitlines()) for x in trace)==43,{'entries':len(trace),'physical_lines':sum(len(x.splitlines()) for x in trace),'isError':native['result']['isError']})
    response_hash=sha(canonical(native['result']));check('native_response_6a537',response_hash=='6a5371b3ff243998baded6dc2f9627b110af793a94907a4a73859ced3d5f4f0b',response_hash)
    completionpath='audit/runtime/'+events[-1]['event']['error']['evidence_ref']['key'];submissionpath='audit/runtime/'+events[-2]['event']['details']['receipt_ref']['key'];completion=doc(files[completionpath]);submission=doc(files[submissionpath]);identity=ad['payload']['identity']
    check('original_receipt_content_addressed_bytes',sha(files[completionpath])==events[-1]['event']['error']['evidence_ref']['sha256'] and sha(files[submissionpath])==events[-2]['event']['details']['receipt_ref']['sha256'])
    check('original_dispatch_admission_native_arguments_identity',dispatch['identity']==identity==submission['identity'] and dispatch['deployment']==ad['deployment']==submission['deployment'] and native['arguments']==dispatch['arguments']==submission['raw_receipt']['arguments'] and native['tool_name']==submission['raw_receipt']['tool_name'] and native['arguments']=={'projectId':38436695,'index':1})
    platform_record=completion['platform'];check('original_failed_completion_same_identity_and_response',all(platform_record['identity'][k]==v for k,v in identity.items()) and platform_record['deployment']==ad['deployment'] and platform_record['status']=='runtime_error' and platform_record['terminal'] is True and platform_record['raw_receipt']['response_sha256']==response_hash and platform_record['raw_receipt']['dispatch_binding_sha256']==sha(canonical(dispatch)))
    check('original_failure_no_success_result',attempts[a]['status']=='failed' and attempts['bfd00f2611fd4496b9498d4597618a8e']['status']=='failed' and 'audit/runtime/'+attempts[a]['result_key'] not in files)
    actualdeploy={p[6:]:sha(norm(b)) for p,b in actual.items() if p.startswith('cloud/') and p.endswith('.py')}
    check('actual7fc31_deployment_and_original_input',len(actualdeploy)==31 and sha(canonical(actualdeploy))==ad['deployment']['deployment_hash'] and actualdeploy==ad['payload']['deployment_manifest'] and sha(files[ad['input_path']])==ad['deployment']['input_hash'])
    readback=doc(files['audit/reviews/20261027-deb85d9-windows/qc_python_source_read.json']);cloudrows=[]
    for row in readback['results']:
        value=row['value']['structuredContent'];path=row['file'];b=value['content'].encode();ref=files[ad['input_path']] if path=='_engineering_task_input.py' else actual['cloud/'+path]
        cloudrows.append({'path':path,'raw_sha256':sha(b),'matches_actual7fc_or_original_input':b==ref,'matches_current_candidate':b==files.get('cloud/'+path) if path!='_engineering_task_input.py' else None})
    check('old_independent32_source_readback_only_offline_reparsed',len(cloudrows)==32 and all(x['matches_actual7fc_or_original_input'] for x in cloudrows))
    matches=sum(deploy[p]==actualdeploy[p] for p in deploy);comparison=doc(files['audit/wr25_wr27_source_reference_comparison.json'])
    check('current28_same3_different_vs_archived31_not_live',matches==28 and comparison['same']==28 and comparison['different']==3 and comparison['candidate_source_manifest_hash']==mh and comparison['new_QC_call'] is False and all(r['candidate_sha256']==deploy[r['path']] and r['deployed_7fc_reference_sha256']==actualdeploy[r['path']] and r['matches']==(deploy[r['path']]==actualdeploy[r['path']]) for r in comparison['paths']),{'same':matches,'different':len(deploy)-matches})
    # Verify full ccad sealed originals and the developer's explicitly selective copy.
    original={p.relative_to(O).as_posix():p for p in O.rglob('*') if p.is_file()};om=doc((O/'artifact_manifest.json').read_bytes());bad=[p for p,h in om.items() if p not in original or sha(original[p].read_bytes())!=h]
    check('old_complete15119_manifest_and15120_directory',len(om)==15119 and len(original)==15120 and set(original)==set(om)|{'artifact_manifest.json'} and not bad,{'bad':bad})
    zpath=O.with_suffix('.zip');zh=sha(zpath.read_bytes());selpath='audit/reviews/20261027-ccad61d-windows/developer_archive_selection.json';selection=doc(files[selpath]);prefix='audit/reviews/20261027-ccad61d-windows/'
    check('old_completeZIP39319686_identity',zh=='2ffc9089ad19a5675d18cafb5379262db7c99a431e518ae4f52cb2dd094b313c' and zpath.stat().st_size==selection['original_zip_bytes']==39319686,{'bytes':zpath.stat().st_size,'raw_sha256':zh})
    with zipfile.ZipFile(zpath) as z:
        names=z.namelist();prefixz=O.name+'/';bad=[]
        check('old_completeZIP15120_inventory',len(names)==15120 and len(names)==len(set(names)) and set(names)=={prefixz+p for p in original})
        for name in names:
            p=name[len(prefixz):];h=om.get(p) or sha(original[p].read_bytes())
            if sha(z.read(name))!=h:bad.append(p)
        check('old_completeZIP_all_member_raw_hashes',not bad,{'verified':len(names),'bad':bad})
    old_git={}
    for label,item in doc((O/'source_git_manifest.json').read_bytes()).items():
        fixed=tree(item['commit'],'old_original_'+label+'_archive');computed={p:sha(b) for p,b in fixed.items()};old_git[label]={'commit':item['commit'],'files':len(computed)}
        check('old_original_Git_manifest_'+label,len(computed)==item['count'] and computed==item['files'] and all(om[item['directory']+'/'+p]==h for p,h in computed.items()),old_git[label])
    selected=selection['selected_originals'];bad=[]
    for row in selected:
        b=files.get(prefix+row['path'])
        if b is None or sha(b)!=row['raw_sha256'] or len(b)!=row['bytes'] or b!=original[row['path']].read_bytes():bad.append(row['path'])
    check('selective381_original_raw1581651',len(selected)==381 and sum(x['bytes'] for x in selected)==1581651 and not bad,{'bad':bad})
    def reason(p):
        parts=Path(p).parts;base=parts[-1]
        if parts[0] in ('source','baselines'):return 'omitted_duplicate_fixed_Git_snapshot'
        if base.endswith('.index'):return 'omitted_reconstructible_Git_index'
        if p in ('artifact_manifest.json','source_git_manifest.json','archive_agent/source_raw_git_manifest.json'):return 'omitted_complete_large_manifest_retained_in_ZIP'
        if p in ('change.diff','PR_complete_patch.stdout','archive_agent/baseline_to_candidate_full_patch.stdout'):return 'omitted_large_full_patch_retained_in_ZIP'
        if base in ('current_complete_name_status.stdout','PR_complete_name_status.stdout','change.names'):return 'omitted_redundant_full_name_list'
        if p=='archive_agent/old_cloud_source_rows.json':return 'omitted_existing_archived_cloud_reference_copy'
        if len(parts)==1:return 'selected'
        if parts[0] in ('cert_agent','wr25_confirmation','wr26_confirmation','wr27_confirmation','archive_agent'):return 'selected'
        if parts[0]=='protocol_agent':
            if len(parts)==2 or parts[1] in ('legacy_adapted_scripts','recovery_adapted_scripts','original_mre','wr21'):return 'selected'
            if parts[1] in ('boundaries_first','research_failure') and ((len(parts)==3 and base!='command_log.json') or (parts[1]=='boundaries_first' and parts[2]=='parallel')):return 'selected'
            if base in ('results.json','test_results.json','execution.json','execution_records.json','summary.json'):return 'selected'
        if p=='runs/execution_records.json':return 'selected'
        if parts[0] in ('admission_agent','control_replay','recovery_agent') and len(parts)==2 and (base.endswith('.py') or base in ('report.json','report.txt','execution_records.json','new_first_results.json','new_contract_corrected_results.json','script_bindings.json','worker_identity_first_results.json','pure_corrected_results.json','cli_first_results.json','preflight_cli_first_results.json')):return 'selected'
        return 'omitted_historical_replay_detail_retained_in_ZIP'
    expected=set();groups=collections.Counter();nonutf=[]
    for p,path in original.items():
        why=reason(p)
        if why=='selected':
            try:path.read_bytes().decode('utf-8');expected.add(p)
            except UnicodeDecodeError:groups['omitted_non_UTF8_original_retained_in_ZIP']+=1;nonutf.append(p)
        else:groups[why]+=1
    check('selective_exact_rules_and14739_omitted',expected=={r['path'] for r in selected} and dict(groups)==selection['omitted_groups'] and len(original)-len(selected)==selection['omitted_original_count']==14739,{'groups':dict(groups),'non_UTF8_omitted':nonutf})
    for row in selection['verified_external_inventory_refs']:
        p=row['path'];b=original[p].read_bytes();check('external_manifest:'+p,sha(b)==row['raw_sha256'] and len(b)==row['bytes'])
    for row in selection['verified_external_non_UTF8_refs']:
        p=row['path'];b=original[p].read_bytes();check('external_non_UTF8:'+p,sha(b)==row['raw_sha256'] and len(b)==row['bytes'])
    ext={'.gitattributes','ARCHIVE_SCOPE.md','developer_archive_helper.py','developer_archive_selection.json','developer_archive_validation.json','developer_archive_inventory.json','user_pasted_report_original.txt'}
    check('selective_only381_originals_plus7_declared_metadata',{p[len(prefix):] for p in files if p.startswith(prefix)}==expected|ext)
    inv=doc(files[prefix+'developer_archive_inventory.json']);bad=[]
    for row in inv['files']:
        b=files.get(prefix+row['path'])
        if b is None or sha(b)!=row['raw_sha256'] or len(b)!=row['bytes']:bad.append(row['path'])
    check('local_selective_inventory387_plus_itself388',not bad and len(inv['files'])==387 and inv['selected_review_original_count']==381 and inv['developer_metadata_count_including_this_manifest']==6,{'bad':bad})
    pasted=selection['pasted_report'];check('pasted_report_raw_bytes',sha(files[prefix+pasted['path']])==pasted['raw_sha256'] and len(files[prefix+pasted['path']])==pasted['bytes'])
    ac=doc(files['audit/ccad61d_review_archive_check.json']);origreport=doc(original['formal_report.json'].read_bytes())
    check('archive_check_exact_selected_complete_metadata',ac['original_zip_sha256']==zh and ac['original_package_files']==len(original) and ac['original_manifest_registered_files']==len(om) and ac['archived_original_count']==len(selected) and ac['archived_original_raw_bytes']==sum(x['bytes'] for x in selected) and ac['omitted_original_count']==len(original)-len(selected) and ac['archive_selection_ref']['raw_sha256']==sha(files[selpath]) and ac['review_formal_json_raw_sha256']==sha(original['formal_report.json'].read_bytes()) and ac['review_formal_txt_raw_sha256']==sha(original['formal_report.txt'].read_bytes()))
    check('ccad_previous_failed_overall_original_fixes_preserved',ac['software_acceptance']==origreport['software_acceptance'] and ac['stage2_whole_accepted'] is False and origreport['software_acceptance']['overall_status']=='失败' and origreport['financial_evidence'] is False)
    omitted=doc(files[pack+'verification/omitted_working_artifacts.json']);preflight=doc(files[pack+'verification/publication_preflight_first.json']);omitted_details=[]
    devroot=Path('B:/BaiduSyncdisk/学习/投资/量化/量化交易比赛/LLM 因子生成器')
    for row in omitted['entries']:
        originalpath=devroot/row['original_retained_at'];exists=originalpath.is_file();b=originalpath.read_bytes() if exists else None
        omitted_details.append({'path':row['path'],'original_retained_at':str(originalpath),'exists':exists,'bytes':len(b) if b is not None else None,'raw_sha256':sha(b) if b is not None else None,'claimed_raw_sha256':row['raw_sha256']})
        check('omitted_developer_binary_original_preserved:'+row['path'],row['path'] not in files and exists and len(b)==row['bytes'] and sha(b)==row['raw_sha256'],omitted_details[-1])
    check('binary_preflight_failure_and_nonsource_correction_explicit',preflight['exit_code']==1 and preflight['error_class']=='UnicodeDecodeError' and preflight['source_or_test_changes'] is False and preflight['original_bytes_preserved'] is True and 'not_a_review_original' in omitted['entries'][0]['kind'])
    write(R/'omitted_developer_artifact_verification.json',omitted_details)
    development=doc(files['config/development.json']);check('real_market_model_final_live_gates_disabled',all(development['execution'][k] is False for k in ('market_research_enabled','llm_runtime_enabled','final_test_enabled','live_trading_enabled')))
    check('immutable_source_all_raw_unchanged_after_checks',disk=={p.relative_to(S).as_posix():p.read_bytes() for p in S.rglob('*') if p.is_file()})
    result={'review_id':'44676db-20261027-source-budget-archive','reviewed_source_commit':C,'baseline_commit':B,'actual_cloud_execution_commit':A,'raw_git_files':len(files),'review_source_count':len(m),'source_manifest_hash':mh,'execution_source_manifest_hash':eh,'implementation_hash':ih,'deployment_hash':dh,'active_economic_configuration_hash':ch,'local_deployment_files':len(deploy),'source_change_files':[line.split('\t')[-1] for line in delta.decode().splitlines() if line.split('\t')[-1].startswith(('cloud/','tests/','tools/')) and line.endswith(b'.py'.decode())],'full_patch':{'bytes':len(patch),'raw_sha256':sha(patch)},'protected_originals':len(protected),'prior_archived_files_preserved':len(archived),'developer_raw_output_entries':len(rows),'budget':{'events':len(events),'journal_raw_sha256':sha(journal),'usage':usage,'limits':events[0]['event']['limits'],'engineering_usage':eng,'engineering_cap':2,'stopped':True},'native_failure':{'packet_raw_sha256':sha(nativebytes),'response_hash':response_hash,'representations':2,'logical_failures':1,'traceback_entries':len(trace),'traceback_physical_lines':sum(len(x.splitlines()) for x in trace),'source_cause_known':False},'old_cloud_source_comparison':{'same':matches,'different':31-matches,'scope':'only archived old independent readback reparsed offline, not new QC or current inventory','readback_files':32},'old_review_archive':{'ZIP_raw_sha256':zh,'ZIP_bytes':zpath.stat().st_size,'registered_manifest_files':len(om),'complete_files':len(original),'selected_originals':len(selected),'selected_raw_bytes':sum(x['bytes'] for x in selected),'omitted_originals':len(original)-len(selected),'git_manifests':old_git},'checks':checks,'static_byte_metadata_checks':len(checks),'checks_passed':sum(x['passed'] for x in checks),'independent_product_unit_methods':0,'current_QC_Research_LEAN_model_deployment_actual_registry_writes':0,'financial_evidence':False,'environment':{'os':platform.platform(),'python':sys.version,'executable':sys.executable}}
    write(R/'report.json',result);write(R/'review_source_manifest.json',m);write(R/'execution_source_manifest.json',em);write(R/'source_raw_git_manifest.json',{p:sha(b) for p,b in files.items()});write(R/'old_cloud_source_rows.json',cloudrows)
    print(json.dumps({k:v for k,v in result.items() if k not in ('checks','environment')},ensure_ascii=False));print(json.dumps([x for x in checks if not x['passed']],ensure_ascii=False));return 0 if all(x['passed'] for x in checks) else 1
if __name__=='__main__':
    try:sys.exit(main())
    except Exception:
        (R/'first_reviewer_error.txt').write_text(traceback.format_exc(),encoding='utf-8');write(R/'first_error_partial_checks.json',checks);raise
