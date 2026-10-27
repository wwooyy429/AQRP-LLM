from pathlib import Path
import copy,difflib,hashlib,importlib.util,json,os,subprocess,sys,time,traceback
R=Path(__file__).resolve().parent;S=R.parent/'source';G=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\repo')
OLD=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-ccad61d-20261027\source')
C='44676db609b3b7c2175fa7fa4f19c8ccf8165458';B='ccad61d03ccf17bf2bdc2d7ffc88dfd11b6d3ca6'
commands=[];checks=[]
def sha(b):return hashlib.sha256(b).hexdigest()
def canonical(v):return json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode())
def check(name,ok,detail=None):checks.append({'name':name,'passed':bool(ok),'detail':detail})
def run(label,args,cwd=R,env=None):
    start=time.perf_counter();p=subprocess.run(args,cwd=cwd,capture_output=True,env=env or dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1',GIT_OPTIONAL_LOCKS='0'))
    (R/(label+'.stdout')).write_bytes(p.stdout);(R/(label+'.stderr')).write_bytes(p.stderr)
    commands.append({'label':label,'command':args,'cwd':str(cwd),'exit_code':p.returncode,'seconds':round(time.perf_counter()-start,3),'stdout_raw_sha256':sha(p.stdout),'stderr_raw_sha256':sha(p.stderr)});write(R/'wr27_commands.json',commands);return p
def independent_manifest(root):
    paths=[p for n in ('cloud','config','templates','tests','tools','docs','.github') for p in (root/n).rglob('*') if p.is_file() and p.suffix in ('.py','.json','.md','.yml','.yaml') and '__pycache__' not in p.parts]
    paths += [root/n for n in ('requirements-test.txt','.gitattributes','.gitignore','AGENTS.md') if (root/n).is_file()]
    return {p.relative_to(root).as_posix():sha(p.read_bytes().decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n').encode()) for p in paths}
def main():
    original=(S/'audit/reviews/20261027-ccad61d-windows/archive_agent/minimal_wr27_root_manifest.py').read_bytes();script=R/'original_minimal_wr27.py';script.write_bytes(original)
    old=run('original_ccad_negative',[sys.executable,'-B',str(script),'--source',str(OLD),'--git-repository',str(G),'--output',str(R/'ccad_negative')])
    oldresult=json.loads((R/'ccad_negative/result.json').read_bytes())
    check('original_byte_MRE_ccad_negative',sha(original)=='915a642e63991ebe0971bdbb120721605ff334c9309c204dc60b73eb18d97d23' and old.returncode==1 and oldresult['default_legal_control_exit']==0 and oldresult['foreign_hash_actual_exit']==0 and oldresult['own_hash_actual_exit']==1,{'raw_sha256':sha(original),'exit_code':old.returncode,'case_results':oldresult})
    firstnew=run('original_new_fixed_scope_failure',[sys.executable,'-B',str(script),'--source',str(S),'--git-repository',str(G),'--output',str(R/'original_new_scope')])
    check('unchanged_MRE_new_fixed_literal_baseline_incompatibility_saved',firstnew.returncode==1 and b"metadata['current_activity']['baseline_commit']==B" in firstnew.stderr and not (R/'original_new_scope/commands.json').exists(),{'reason':'Old byte MRE asserts its fixed ea baseline before executing any product CLI. This is a harness scope mismatch, not a new product defect.','product_CLI_run':False})
    adapted=original.decode().replace("C='ccad61d03ccf17bf2bdc2d7ffc88dfd11b6d3ca6'", "C='"+C+"'").replace("B='ea6053e3e9ef4be17db246daf18a4cf9b2e5be58'", "B='"+B+"'")
    fixedscript=R/'adapted_minimal_wr27.py';fixedscript.write_bytes(adapted.encode())
    diff=''.join(difflib.unified_diff(original.decode().splitlines(True),adapted.splitlines(True),fromfile='original byte MRE',tofile='same assertions; exact baseline/current binding only'))
    (R/'wr27_scope_adapter.diff').write_bytes(diff.encode());write(R/'wr27_scope_adapter.json',{'original_raw_sha256':sha(original),'adapted_raw_sha256':sha(adapted.encode()),'only_changes':['C: ccad ->44676db','B: ea ->ccad'],'assertions_and_expected_answers_unchanged':True,'original_new_scope_failure_saved':True})
    fixed=run('adapted_new_fixed_positive',[sys.executable,'-B',str(fixedscript),'--source',str(S),'--git-repository',str(G),'--output',str(R/'fixed_positive')]);fixedresult=json.loads((R/'fixed_positive/result.json').read_bytes())
    check('adapted_new_fixed_default_absolute_T_wrongS_correctT',fixed.returncode==0 and fixedresult['default_legal_control_exit']==0 and fixedresult['foreign_hash_actual_exit']==1 and fixedresult['own_hash_actual_exit']==0 and fixedresult['source_original_raw_unchanged'] and fixedresult['actual_repository_index_unchanged'],fixedresult)
    target=R/'fixed_positive/alternate_root';metapath=target/'audit/stage2_current_readiness.json';originalmeta=metapath.read_bytes();metadata=json.loads(originalmeta)
    env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1',GIT_OPTIONAL_LOCKS='0',GIT_DIR=str(G/'.git'),GIT_WORK_TREE=str(target),GIT_INDEX_FILE=str(R/'fixed_positive/fixed_source.index'))
    relative=run('relative_root_correct_T',[sys.executable,'-B',str(S/'tools/review_metadata.py'),'--root','alternate_root'],cwd=R/'fixed_positive',env=env)
    check('relative_T_CLI_legal_positive',relative.returncode==0,{'exit_code':relative.returncode,'stdout':relative.stdout.decode('utf-8','replace')})
    sys.path.insert(0,str(S/'tools'));spec=importlib.util.spec_from_file_location('stages_under_audit',S/'tools/stages.py');stages=importlib.util.module_from_spec(spec);spec.loader.exec_module(stages)
    root_before=stages.ROOT;source_expected=independent_manifest(S);target_expected=independent_manifest(target)
    source1=stages.source_manifest();target1=stages.source_manifest(root=target);source2=stages.source_manifest();targetrel=stages.source_manifest(root=os.path.relpath(target,R));source3=stages.source_manifest(root=None)
    check('stages_default_absolute_relative_independent_known_hashes',source1['source_files']==source2['source_files']==source3['source_files']==source_expected and target1['source_files']==targetrel['source_files']==target_expected and source1['source_hash']==sha(canonical(source_expected)) and target1['source_hash']==sha(canonical(target_expected)) and source1['source_hash']!=target1['source_hash'],{'S':source1['source_hash'],'T':target1['source_hash'],'S_files':len(source_expected),'T_files':len(target_expected)})
    check('target_calls_do_not_pollute_global_ROOT_or_default_manifest',stages.ROOT==root_before==S and source1==source2==source3)
    rejection=[]
    def metadata_case(label,mutate):
        changed=copy.deepcopy(metadata);mutate(changed);write(metapath,changed)
        try:p=run(label,[sys.executable,'-B',str(S/'tools/review_metadata.py'),'--root',str(target)],env=env)
        finally:metapath.write_bytes(originalmeta)
        rejection.append({'case':label,'exit_code':p.returncode,'correctly_rejected':p.returncode!=0,'stderr':p.stderr.decode('utf-8','replace')})
    metadata_case('wrong_target_random_source_hash',lambda d:d.__setitem__('candidate_source_manifest_hash','0'*64))
    metadata_case('target_diff_missing_changed_file',lambda d:d['source_changed_this_round'].remove('tools/stages.py'))
    def bad_history(d):
        h=next(x for x in d['historical_activity_descriptions'] if x['recorded_at_commit']==B);h['prior_current_fields']['source_configuration_budget_changed_scope']='changed prior text'
    metadata_case('target_history_wrong_prior_text',bad_history)
    metadata_case('target_Git_missing_baseline_object',lambda d:d['current_activity'].__setitem__('baseline_commit','0'*40))
    metadata_case('target_Git_baseline_diff_mismatch',lambda d:d['current_activity'].__setitem__('baseline_commit','ea6053e3e9ef4be17db246daf18a4cf9b2e5be58'))
    for label,path in (('target_budget_raw_changed','config/budget.json'),('target_journal_raw_changed','audit/runtime/registry/events.jsonl')):
        p=target/path;before=p.read_bytes();p.write_bytes(before+b'\n')
        try:result=run(label,[sys.executable,'-B',str(S/'tools/review_metadata.py'),'--root',str(target)],env=env)
        finally:p.write_bytes(before)
        rejection.append({'case':label,'exit_code':result.returncode,'correctly_rejected':result.returncode!=0,'stderr':result.stderr.decode('utf-8','replace')})
    check('same_target_hash_Git_diff_history_budget_journal7_rejections',all(x['correctly_rejected'] for x in rejection),rejection)
    check('target_mutations_restored_default_S_stays_unchanged',metapath.read_bytes()==originalmeta and stages.source_manifest()==source1 and stages.source_manifest(root=target)==target1)
    current=json.loads((S/'audit/stage2_current_readiness.json').read_bytes());baseline=json.loads(subprocess.check_output(['git','-C',str(G),'show',B+':audit/stage2_current_readiness.json']))
    names=subprocess.check_output(['git','-C',str(G),'diff','--name-only','--no-renames',B,C],text=True).splitlines();changed=sorted(p for p in names if p.startswith(('cloud/','tools/','tests/')) and p.endswith('.py'))
    history=next(x for x in current['historical_activity_descriptions'] if x['recorded_at_commit']==B)
    check('current6_source_paths_and_historical_exact_ccad_text_preserved',current['source_changed_this_round']==changed and len(changed)==6 and history['actual_cloud_source_commit']=='7fc5ef2e9d2379d29f48d05a1f3cc760000884d6' and all(v==baseline[k] for k,v in history['prior_current_fields'].items()),{'source_changes':changed,'historical_fields':list(history['prior_current_fields'])})
    result={'reviewed_source_commit':C,'baseline_commit':B,'WR27_acceptance':'修复后通过（原反例及当前默认/绝对/相对/不同root源码身份、同root原件拒绝和globalROOT隔离范围）' if all(x['passed'] for x in checks) else '失败项待判断','checks':checks,'metadata_check_groups':len(checks),'groups_passed':sum(x['passed'] for x in checks),'negative_target_CLI_scenarios':len(rejection),'original_byte_MRE_negative_exit':old.returncode,'unchanged_original_new_scope_exit':firstnew.returncode,'unchanged_original_new_scope_product_CLI':0,'adapted_MRE_positive_exit':fixed.returncode,'MRE_runs':3,'MRE_internal_metadata_CLI':6,'additional_metadata_CLI':1+len(rejection),'metadata_CLI_total':6+1+len(rejection),'stages_manifest_calls_are_static_checks_not_unit_tests':True,'independent_product_unit_methods':0,'production_Git_source_or_authoritative_registry_writes':0,'current_QC_Research_LEAN_model_deployment_calls':0,'financial_evidence':False}
    write(R/'wr27_report.json',result);print(json.dumps({k:v for k,v in result.items() if k!='checks'},ensure_ascii=False));print(json.dumps([x for x in checks if not x['passed']],ensure_ascii=False));return 0 if all(x['passed'] for x in checks) else 1
if __name__=='__main__':
    try:sys.exit(main())
    except Exception:
        (R/'wr27_first_reviewer_error.txt').write_text(traceback.format_exc(),encoding='utf-8');write(R/'wr27_error_partial_checks.json',checks);raise
