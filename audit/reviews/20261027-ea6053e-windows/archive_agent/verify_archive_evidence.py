from pathlib import Path
import ast, collections, copy, hashlib, io, json, os, platform, subprocess, sys, tarfile, time, traceback, zipfile

R = Path(__file__).resolve().parent
S = R.parent / 'source'
G = Path(r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\repo')
O = Path('B:/BaiduSyncdisk/学习/投资/量化/量化交易比赛/LLM审核/review-deb85d9-20261027')
C = 'ea6053e3e9ef4be17db246daf18a4cf9b2e5be58'
B = 'deb85d9f27441b275ab8b108f0232ecd2707a1e8'
A = '7fc5ef2e9d2379d29f48d05a1f3cc760000884d6'
checks = []
commands = []
def sha(raw): return hashlib.sha256(raw).hexdigest()
def canonical(value): return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()
def norm(raw): return raw.decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n').encode()
def read(raw): return json.loads(raw.decode('utf-8-sig'))
def write(path, value): path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2)+'\n').encode())
def check(name, passed, detail=None):
    row = {'name':name, 'passed':bool(passed)}
    if detail is not None: row['detail'] = detail
    checks.append(row)
def run(label,args):
    start=time.perf_counter(); p=subprocess.run(args,capture_output=True)
    out=R/(label+'.stdout'); err=R/(label+'.stderr');out.write_bytes(p.stdout);err.write_bytes(p.stderr)
    commands.append({'label':label,'command':args,'cwd':str(R),'exit_code':p.returncode,'elapsed_seconds':round(time.perf_counter()-start,3),
                     'stdout':out.name,'stdout_raw_sha256':sha(p.stdout),'stderr':err.name,'stderr_raw_sha256':sha(p.stderr)})
    write(R/'commands.json',commands)
    if p.returncode: raise RuntimeError('Command failed: '+label)
    return p.stdout
def tree(commit,label):
    raw=run(label,['git','-C',str(G),'archive',commit])
    with tarfile.open(fileobj=io.BytesIO(raw)) as t:
        return {m.name:t.extractfile(m).read() for m in t.getmembers() if m.isfile()}
def assignments(raw):
    return {n.targets[0].id:ast.literal_eval(n.value) for n in ast.parse(raw).body if isinstance(n,ast.Assign)}
def manifest(files):
    return {p:sha(norm(b)) for p,b in files.items() if ((Path(p).parts[0] in ('cloud','config','templates','tests','tools','docs','.github')
        and Path(p).suffix in ('.py','.json','.md','.yml','.yaml') and '__pycache__' not in Path(p).parts)
        or p in ('requirements-test.txt','.gitattributes','.gitignore','AGENTS.md'))}

def main():
    files=tree(C,'candidate_git_archive');base=tree(B,'baseline_git_archive');actual=tree(A,'executed_git_archive')
    disk={p.relative_to(S).as_posix():p.read_bytes() for p in S.rglob('*') if p.is_file()}
    check('raw4541_files_equal_pinned_Git',len(files)==4541 and disk==files, {'git_count':len(files),'disk_count':len(disk)})
    patch=run('baseline_to_candidate_full_patch',['git','-C',str(G),'diff','--no-ext-diff','--binary',B,C])
    names=run('baseline_to_candidate_name_status',['git','-C',str(G),'diff','--name-status',B,C])
    m=manifest(files);mh=sha(canonical(m));stage=read(files['audit/stage_verification.json'])
    check('full_review_source_manifest',m==stage['source_files'] and mh==stage['source_hash'],{'files':len(m),'hash':mh})
    budget=read(files['config/budget.json']);policy=copy.deepcopy(budget);policy.pop('usage',None)
    em=dict(m);em['config/budget.json']=sha(canonical(policy));eh=sha(canonical({'schema':'collection_execution_sources_v1','source_files':em}))
    gen=assignments(files['cloud/research_config.py']);old=assignments(base['cloud/research_config.py'])
    implementation={Path(p).name:sha(norm(b)) for p,b in files.items() if p.startswith('cloud/qresearch/') and p.endswith('.py')}
    deploy={p[6:]:sha(norm(b)) for p,b in files.items() if p.startswith('cloud/') and p.endswith('.py') and '__pycache__' not in Path(p).parts}
    ih=sha(canonical(implementation));dh=sha(canonical(deploy));deployment=read(files['audit/deployment.json'])
    check('normalized_keepEOF_implementation_and_deployment',deployment['source_files']==deploy and len(deploy)==31 and ih==gen['IMPLEMENTATION_SHA256']==deployment['implementation_hash'],{'implementation_hash':ih,'deployment_hash':dh,'deployment_files':len(deploy)})
    cfgdocs={k:read(files['config/'+k+'.json']) for k in ('research','universe','data','workflow','budget')}
    cfg={k:v for k,v in cfgdocs.items() if k!='budget'}|{'configuration_id':cfgdocs['research']['configuration_id'],'budget_limits':cfgdocs['budget']['limits'],'budget_allocations':cfgdocs['budget']['allocations'],'active_factor':cfgdocs['research']['active_factor_spec'],'active_model':cfgdocs['research']['active_model_spec'],'active_trading_rules':cfgdocs['research']['active_trading_spec']}
    ch=sha(canonical(cfg))
    check('configuration_generated_from_authority_and_unchanged',cfg==gen['CONFIGURATION']==old['CONFIGURATION'] and ch==gen['SOURCE_SHA256']==old['SOURCE_SHA256']==deployment['configuration_hash'],{'configuration_hash':ch})
    check('active_config_all_raw_files_unchanged',all(files[p]==b for p,b in base.items() if p.startswith('config/')))
    dev=read(files['audit/review_packages/wr20_wr21/developer_verification.json'])
    check('developer_identity_claims',{dev['source_manifest_hash'],mh}=={mh} and dev['execution_source_manifest_hash']==eh and dev['implementation_hash']==ih and dev['deployment_hash']==dh and dev['active_economic_configuration_hash']==ch)
    check('developer630_test_claim_log_bound',dev['test_methods']==630 and stage['local_tests_passed'] is True and 'Ran 630 tests' in stage['test_output'] and dev['independent_acceptance'] is False and dev['financial_evidence'] is False)
    previous_packages=[p for p in base if p.startswith(('audit/reviews/','audit/review_packages/'))]
    check('all_prior_archived_evidence_raw_preserved',all(files.get(p)==base[p] for p in previous_packages),{'files':len(previous_packages)})
    protect=[p for p in base if p.startswith(('audit/runtime/','audit/task_inputs/','audit/tool_observations/')) or p=='config/budget.json']
    check('runtime_inputs_observations_budget_originals_preserved',all(files.get(p)==base[p] for p in protect),{'files':len(protect)})
    rawmanifest=read(files['audit/review_packages/wr20_wr21/developer_outputs_manifest.json'])
    rawrows=rawmanifest['entries'];bad=[]
    for row in rawrows:
        p=row['path'];b=files.get(p)
        if b is None or len(b)!=row['bytes'] or sha(b)!=row['raw_sha256']: bad.append(p)
    check('developer_package_raw_manifest',not bad,{'entries':len(rawrows),'bad':bad,'kind':rawmanifest['kind']})
    package_paths={p for p in files if p.startswith('audit/review_packages/wr20_wr21/')}
    not_manifested=sorted(package_paths-{r['path'] for r in rawrows})
    check('developer_package_unmanifested_are_described_meta',set(not_manifested)=={'audit/review_packages/wr20_wr21/.gitattributes','audit/review_packages/wr20_wr21/README.md','audit/review_packages/wr20_wr21/developer_outputs_manifest.json','audit/review_packages/wr20_wr21/developer_verification.json'},not_manifested)
    journal=files['audit/runtime/registry/events.jsonl'];events=[json.loads(line) for line in journal.splitlines()]
    check('17event_bytes_equal_deb85d9',len(events)==17 and journal==base['audit/runtime/registry/events.jsonl'],{'raw_sha256':sha(journal),'events':len(events)})
    old13commit='66ff72ffaaff8c91c008898e6527c91131176c2a'
    old13=run('old13_registry_blob',['git','-C',str(G),'show',old13commit+':audit/runtime/registry/events.jsonl'])
    check('old13_raw_prefix_preserved',len(old13.splitlines())==13 and journal.startswith(old13),{'old13_raw_sha256':sha(old13)})
    previous=None
    for i,e in enumerate(events,1):
        check('journal_hash_chain_'+str(i),e['sequence']==i and e['previous_hash']==previous and sha(canonical({k:v for k,v in e.items() if k!='hash'}))==e['hash'])
        previous=e['hash']
    usage=copy.deepcopy(events[0]['event']['initial_usage']);configs=set();engineering=set();attempts={}
    for envelope in events[1:]:
        e=envelope['event'];kind=e['kind']
        if kind in ('config_registered','config_imported'):
            cid=e['config_id'];configs.add(cid)
            package=read(files['audit/runtime/configurations/'+cid+'.json'])
            if package.get('engineering_task_schema_version')==1 and isinstance(package.get('plan'),dict) and package['plan'].get('scope')=='engineering':engineering.add(cid)
            if kind=='config_registered':usage['configurations'][e['allocation']]+=1;usage['configurations']['total']+=1
        if kind=='attempt_started':
            attempts[e['attempt_id']]=dict(e,status='started');usage[e['stage']][e['allocation']]+=1;usage[e['stage']]['total']+=1
        if kind in ('pending','completed','failed','submission_unknown'): attempts[e['attempt_id']].update(e,status=kind)
    limits=events[0]['event']['limits'];engineering_usage={'configurations':len(engineering),**{k:sum(a['config_id'] in engineering and a['stage']==k for a in attempts.values()) for k in ('research','lean')}}
    check('independent_event_budget_replay_7_10_1', [usage[k]['total'] for k in ('configurations','research','lean')]==[7,10,1],{'usage':usage,'limits':limits})
    check('budget_projection_matches_replay',[budget['usage'][k] for k in ('configuration_budget_charges','research_execution_attempts','lean_submission_attempts')]==[7,10,1])
    check('engineering_round_2_2_1_stopped',engineering_usage=={'configurations':2,'research':2,'lean':1},{'usage':engineering_usage,'caps':2,'stopped_for_config_and_research':True})
    attempt='f5d05f5b964b4a1d924e4b70cd207386';packet='audit/tool_observations/'+attempt+'-research.json'
    check('original_f5d_native_packet_raw14ae',sha(files[packet])=='14ae4a18636496737862a1ce314d90ae7fcf1abaf35f8a0f27145e0e839af8f3',{'path':packet,'hash':sha(files[packet])})
    check('failed_attempts_remain_failed_no_result',attempts[attempt]['status']=='failed' and attempts['bfd00f2611fd4496b9498d4597618a8e']['status']=='failed' and 'audit/runtime/'+attempts[attempt]['result_key'] not in files)
    # Archive verification reads bytes only. It does not execute archived scripts.
    orig={p.relative_to(O).as_posix():p for p in O.rglob('*') if p.is_file()};om=read((O/'artifact_manifest.json').read_bytes())
    check('complete_original_manifest12474_and_directory12475',len(om)==12474 and set(orig)==set(om)|{'artifact_manifest.json'})
    bad=[p for p,d in om.items() if p not in orig or sha(orig[p].read_bytes())!=d]
    check('complete_original_directory_hashes',not bad,{'verified':len(om),'bad':bad})
    zpath=O.with_suffix('.zip');zraw=zpath.read_bytes();zh=sha(zraw)
    check('complete_original_ZIP_identity',len(zraw)==33811222 and zh=='19d2614008caf209c18b79e16220826de0394ee9a86f585f32ccce5a9bfd6b49',{'bytes':len(zraw),'raw_sha256':zh})
    with zipfile.ZipFile(io.BytesIO(zraw)) as z:
        names=z.namelist();prefix=O.name+'/';bad=[]
        check('complete_original_ZIP_inventory',len(names)==12475 and len(names)==len(set(names)) and set(names)=={prefix+p for p in orig})
        for path in names:
            rel=path[len(prefix):];expected=om.get(rel) or sha(orig[rel].read_bytes())
            if sha(z.read(path))!=expected:bad.append(rel)
        check('complete_original_ZIP_all_bytes',not bad,{'verified':len(names),'bad':bad})
    sm=read((O/'source_git_manifest.json').read_bytes());git_manifests={}
    for label,item in sm.items():
        fixed={'candidate':base,'actual_cloud7fc':actual}.get(label)
        if fixed is None: fixed=tree(item['commit'],'original_'+label+'_git_archive')
        computed={p:sha(b) for p,b in fixed.items()};git_manifests[label]={'commit':item['commit'],'count':len(computed),'match':computed==item['files']}
        check('complete_original_git_manifest_'+label,len(computed)==item['count'] and computed==item['files'],git_manifests[label])
    selectionpath='audit/reviews/20261027-deb85d9-windows/developer_archive_selection.json';selection=read(files[selectionpath]);prefix='audit/reviews/20261027-deb85d9-windows/'
    selected=selection['selected_originals'];bad=[]
    for row in selected:
        path=row['path'];b=files.get(prefix+path)
        if b is None or len(b)!=row['bytes'] or sha(b)!=row['raw_sha256'] or b!=orig[path].read_bytes():bad.append(path)
    check('selective_archive216_raw_originals',len(selected)==216 and not bad,{'entries':len(selected),'bytes':sum(r['bytes'] for r in selected),'bad':bad})
    selected_names={r['path'] for r in selected};omitted=set(orig)-selected_names
    check('selective_archive_correct_omission_count',len(omitted)==selection['omitted_original_count']==12259)
    groups=collections.defaultdict(lambda:{'files':0,'bytes':0});expected_selected=set()
    for p in orig:
        parts=Path(p).parts
        reason=('fixed_Git_source_snapshot_reconstructible_from_verified_commit' if parts[0] in ('source','baselines') else
            'complete_original_inventory_retained_in_original_hash_verified_package' if p in ('artifact_manifest.json','source_git_manifest.json') else
            'redundant_full_patch_retained_in_original_hash_verified_package' if p in ('change.diff','PR_complete_patch.stdout') else
            'historical_replay_or_individual_native_command_output_retained_in_original_hash_verified_package' if len(parts)>1 and parts[0] not in ('cert_agent','entry_agent','entry_additional','wr20_confirmation','wr21_confirmation') and not(parts[0]=='native_agent' and 'commands' not in parts) else None)
        if reason:groups[reason]['files']+=1;groups[reason]['bytes']+=orig[p].stat().st_size
        else:expected_selected.add(p)
    check('selective_archive_selection_rule_exact',expected_selected==selected_names and dict(groups)==selection['omitted_groups'],{'groups':dict(groups)})
    for p,row in selection['verified_external_inventory_refs'].items():
        b=orig[p].read_bytes();check('selective_external_inventory_'+p,sha(b)==row['raw_sha256'] and len(b)==row['bytes'])
    archived_actual={p[len(prefix):] for p in files if p.startswith(prefix)}
    expected_extra={'DEVELOPER_ARCHIVE_README.md','developer_archive.py','developer_archive_selection.json','.gitattributes',selection['pasted_report']['path']}
    check('selective_no_undeclared_files',archived_actual==selected_names|expected_extra,{'extra':sorted(archived_actual-selected_names)})
    pasted=files[prefix+selection['pasted_report']['path']];check('pasted_report_raw_hash',sha(pasted)==selection['pasted_report']['raw_sha256'] and len(pasted)==selection['pasted_report']['bytes'])
    ac=read(files['audit/deb85d9_review_archive_check.json']);of=read(orig['formal_report.json'].read_bytes())
    check('archive_check_summary_matches_independent_bytes',ac['original_zip_sha256']==zh and ac['original_package_files']==len(orig) and ac['original_manifest_registered_files']==len(om) and ac['archived_original_count']==len(selected) and ac['archived_original_raw_bytes']==sum(r['bytes'] for r in selected) and ac['omitted_original_count']==len(omitted) and ac['archive_selection_ref']['raw_sha256']==sha(files[selectionpath]) and ac['review_formal_json_raw_sha256']==sha(orig['formal_report.json'].read_bytes()) and ac['review_formal_txt_raw_sha256']==sha(orig['formal_report.txt'].read_bytes()))
    check('archive_retains_failed_previous_verdict',ac['software_acceptance']==of['software_acceptance'] and of['financial_evidence'] is False and ac['stage2_whole_accepted'] is False)
    development=read(files['config/development.json']);check('real_market_model_final_live_switches_disabled',all(development['execution'][k] is False for k in ('market_research_enabled','llm_runtime_enabled','final_test_enabled','live_trading_enabled')))
    # Historical independent cloud readback is explicitly previous-review evidence.
    oldread=read(files[prefix+'source_evidence_verification.json'])
    check('prior_independent_readback_scoped_to_old_executed_SHA',oldread['actual_cloud_source_commit']==A and oldread['reviewed_source_commit']==B and oldread['QC_read_calls']['read_file']==32 and oldread['current_controller_readback_matches']!=31,{'old_readback_QC_calls':oldread['QC_read_calls'],'old_current_controller_matches':oldread['current_controller_readback_matches']})
    check('source_original_bytes_unchanged_after_offline_verification',disk=={p.relative_to(S).as_posix():p.read_bytes() for p in S.rglob('*') if p.is_file()})
    result={'review_id':'ea6053e-20261027-archive-evidence','reviewed_source_commit':C,'baseline_commit':B,'actual_cloud_source_commit':A,
        'evidence_level':'审查者离线重算源码/预算/归档原字节；旧平台材料仅离线重解析，本轮无QC访问',
        'environment':{'os':platform.platform(),'python':sys.version,'executable':sys.executable},
        'raw_git_files':len(files),'review_source_count':len(m),'source_manifest_hash':mh,'execution_source_manifest_hash':eh,'deployment_hash':dh,'implementation_hash':ih,'active_configuration_hash':ch,
        'full_git_patch':{'path':'baseline_to_candidate_full_patch.stdout','raw_sha256':sha(patch),'bytes':len(patch)},
        'budget_replay':{'events':len(events),'journal_raw_sha256':sha(journal),'usage':usage,'limits':limits,'engineering_usage':engineering_usage,'engineering_stop_caps':2,'engineering_stopped':True},
        'developer_package_manifest_entries':len(rawrows),'prior_archived_files_unchanged':len(previous_packages),'protected_runtime_input_observation_files':len(protect),
        'archive':{'original_ZIP_bytes':len(zraw),'original_ZIP_raw_sha256':zh,'original_manifest_registered_files':len(om),'original_directory_files':len(orig),'selected_originals':len(selected),'selected_raw_bytes':sum(r['bytes'] for r in selected),'omitted_originals':len(omitted),'original_git_manifests':git_manifests},
        'checks':checks,'static_byte_metadata_checks':len(checks),'checks_passed':sum(c['passed'] for c in checks),'independent_product_test_methods':0,
        'current_QC_read_calls':0,'current_real_Research_executions':0,'current_LEAN_submissions':0,'current_model_calls':0,'current_deployments':0,'current_registry_writes':0,'financial_evidence':False,
        'conclusion':'通过' if all(c['passed'] for c in checks) else '存在失败项，需逐项判断',
        'limitations':['不验证本轮修复代码动态行为；root及其他审查者承担合成测试。','本轮没有独立访问QC；旧版独立只读源码读回是历史证据。','完整US200/财务/真实可用时钟和金融有效性未认证。']}
    write(R/'report.json',result);write(R/'review_source_manifest.json',m);write(R/'execution_source_manifest.json',em)
    print(json.dumps({k:v for k,v in result.items() if k not in ('checks','budget_replay','environment')},ensure_ascii=False))
    print(json.dumps([c for c in checks if not c['passed']],ensure_ascii=False))
    return 0 if all(c['passed'] for c in checks) else 1

if __name__=='__main__':
    try: sys.exit(main())
    except Exception:
        (R/'first_reviewer_error.txt').write_text(traceback.format_exc(),encoding='utf-8')
        write(R/'partial_checks_first_error.json',checks)
        raise
