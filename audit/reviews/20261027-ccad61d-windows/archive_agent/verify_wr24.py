"""Independent metadata-only CLI/identity audit. All fixtures live here."""
from pathlib import Path
import copy,hashlib,importlib.util,json,os,shutil,subprocess,sys,time,traceback
R=Path(__file__).resolve().parent;S=R.parent/'source';G=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\repo')
B='ea6053e3e9ef4be17db246daf18a4cf9b2e5be58';C='ccad61d03ccf17bf2bdc2d7ffc88dfd11b6d3ca6'
commands=[];checks=[]
def sha(b):return hashlib.sha256(b).hexdigest()
def canonical(v):return json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode())
def check(name,ok,detail=None):checks.append({'name':name,'passed':bool(ok),'detail':detail})
def run(label,args,cwd=R,env=None):
    start=time.perf_counter();p=subprocess.run(args,cwd=cwd,capture_output=True,env=env or dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1',GIT_OPTIONAL_LOCKS='0'))
    (R/(label+'.stdout')).write_bytes(p.stdout);(R/(label+'.stderr')).write_bytes(p.stderr)
    commands.append({'label':label,'command':args,'cwd':str(cwd),'exit_code':p.returncode,'seconds':round(time.perf_counter()-start,3),'stdout_raw_sha256':sha(p.stdout),'stderr_raw_sha256':sha(p.stderr)});write(R/'metadata_commands.json',commands)
    return p
def manifest(root):
    paths=[p for name in ('cloud','config','templates','tests','tools','docs','.github') for p in (root/name).rglob('*') if p.is_file() and p.suffix in ('.py','.json','.md','.yml','.yaml') and '__pycache__' not in p.parts]
    paths += [root/n for n in ('requirements-test.txt','.gitattributes','.gitignore','AGENTS.md') if (root/n).is_file()]
    return {p.relative_to(root).as_posix():sha(p.read_bytes().decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n').encode()) for p in paths}
def main():
    original=(S/'audit/reviews/20261027-ea6053e-windows/archive_agent/minimal_wr24_metadata.py').read_bytes()
    work=R/'wr24_old_scope_negative';agent=work/'agent';agent.mkdir(parents=True,exist_ok=True);(agent/'minimal_wr24_metadata.py').write_bytes(original)
    for p in ('audit/stage2_current_readiness.json','audit/runtime/registry/events.jsonl'):
        raw=subprocess.check_output(['git','-C',str(G),'show',B+':'+p]);target=work/'source'/p;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
    old=run('original_wr24_ea_negative',[sys.executable,'-B',str(agent/'minimal_wr24_metadata.py')]);check('original_WR24_ea_negative_exit1_unchanged_bytes',old.returncode==1 and sha(original)==sha((agent/'minimal_wr24_metadata.py').read_bytes()) and b'WR-24' in old.stderr,{'raw_original_sha256':sha(original),'exit_code':old.returncode,'scope':'unchanged old deb..ea script, not renamed as current scope'})
    current=json.loads((S/'audit/stage2_current_readiness.json').read_bytes());baseline=json.loads((work/'source/audit/stage2_current_readiness.json').read_bytes())
    names=subprocess.check_output(['git','-C',str(G),'diff','--name-only','--no-renames',B,C],text=True).splitlines();delta=sorted(p for p in names if p.startswith(('cloud/','tests/','tools/')) and p.endswith('.py'))
    history=current['historical_activity_descriptions'];h=next(x for x in history if x.get('recorded_at_commit')==B)
    preserved=h['prior_current_fields'];check('independent_current9source_diff_matches',current['source_changed_this_round']==delta and len(delta)==9,delta)
    check('independent_historical_old_texts_and_extra_activity_preserved',h['actual_cloud_source_commit']=='7fc5ef2e9d2379d29f48d05a1f3cc760000884d6' and all(baseline[k]==v for k,v in preserved.items()),{'fields':list(preserved)})
    check('independent_current_zero_platform_and_execution_counters',current['current_activity']=={'kind':'offline_repair','baseline_commit':B,'source_roots':['cloud','tests','tools'],'source_suffix':'.py','quantconnect_reads':0,'quantconnect_writes':0,'new_deployments':0} and all(type(current[k]) is int and current[k]==0 for k in ('new_configuration_count','new_Research_execution_count','new_LEAN_submission_count','model_API_calls','completed_result_read_count','backtest_poll_count')))
    check('independent_source_hash_matches_current_metadata',current['candidate_source_manifest_hash']==sha(canonical(manifest(S))))
    # Raw export lacks .git. Reconstruct an index in this agent's output only;
    # production Git administrative files and the fixed source are read-only.
    index=R/'readonly_ccad.index';env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1',GIT_OPTIONAL_LOCKS='0',GIT_DIR=str(G/'.git'),GIT_WORK_TREE=str(S),GIT_INDEX_FILE=str(index))
    indexreal=G/'.git/index';before=sha(indexreal.read_bytes()) if indexreal.exists() else None
    prep=run('prepare_isolated_readonly_index',['git','read-tree',C],env=env);check('isolated_index_prepared_without_real_Git_index_write',prep.returncode==0 and before==(sha(indexreal.read_bytes()) if indexreal.exists() else None))
    positive=run('current_metadata_default_positive',[sys.executable,'-B',str(S/'tools/review_metadata.py')],env=env)
    check('actual_current_metadata_default_CLI_positive',positive.returncode==0,{'exit_code':positive.returncode,'stdout':positive.stdout.decode('utf-8','replace')})
    sys.path.insert(0,str(S/'tools'));spec=importlib.util.spec_from_file_location('review_metadata_under_audit',S/'tools/review_metadata.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    cases=[]
    def validate(d,paths=delta,historical=baseline,budget=True,journal=True):return module.validate_current(d,paths,historical,baseline_commit=B,budget_unchanged=budget,journal_unchanged=journal)
    for name,mutation in (
        ('stale_new_configuration_text',lambda d:d.__setitem__('source_configuration_budget_changed_scope',baseline['source_configuration_budget_changed_scope'])),
        ('stale_platform_read_text',lambda d:d.__setitem__('read_or_polled_this_turn_scope',baseline['read_or_polled_this_turn_scope'])),
        ('old_source_list',lambda d:d.__setitem__('source_changed_this_round',baseline['source_changed_this_round'])),
        ('missing_new_test',lambda d:d['source_changed_this_round'].remove('tests/test_wr23_prepare_protocol.py')),
        ('bool_alias_execution_count',lambda d:d.__setitem__('new_Research_execution_count',False)),
        ('bool_alias_QC_count',lambda d:d['current_activity'].__setitem__('quantconnect_reads',False)),
        ('new_platform_reads',lambda d:d['current_activity'].__setitem__('quantconnect_reads',1)),
        ('historical_text_changed',lambda d:d['historical_activity_descriptions'][0]['prior_current_fields'].__setitem__('source_configuration_budget_changed_scope','changed')),
        ('wrong_historical_cloud_SHA',lambda d:d['historical_activity_descriptions'][0].__setitem__('actual_cloud_source_commit','0'*40)),
    ):
        changed=copy.deepcopy(current);mutation(changed)
        try:validate(changed);accepted=True;error=None
        except ValueError as exc:accepted=False;error=str(exc)
        cases.append({'case':name,'correctly_rejected':not accepted,'error':error})
    for name,kwargs in (('budget_bytes_changed',{'budget':False}),('journal_bytes_changed',{'journal':False}),('out_of_scope_path',{'paths':delta+['config/research.json']})):
        try:validate(current,**kwargs);accepted=True;error=None
        except ValueError as exc:accepted=False;error=str(exc)
        cases.append({'case':name,'correctly_rejected':not accepted,'error':error})
    check('metadata_validator12_negative_case_rejections',all(x['correctly_rejected'] for x in cases),cases)
    # Independent --root semantic probe. This is a second synthetic working tree
    # in the review output, not a mutation of source or any live configuration.
    alternate=R/'alternate_root'
    for p in manifest(S):
        target=alternate/p;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(S/p,target)
    for p in ('audit/stage2_current_readiness.json','audit/runtime/registry/events.jsonl'):
        target=alternate/p;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(S/p,target)
    factor=alternate/'cloud/qresearch/factors.py';factor.write_bytes(factor.read_bytes()+b'\n# Independent alternate-root source identity probe.\n')
    altmeta=copy.deepcopy(current);altmeta['source_changed_this_round']=sorted(set(delta)|{'cloud/qresearch/factors.py'})
    alt_hash=sha(canonical(manifest(alternate)));write(alternate/'audit/stage2_current_readiness.json',altmeta)
    altenv=dict(env,GIT_WORK_TREE=str(alternate))
    stale=run('alternate_root_stale_manifest',[sys.executable,'-B',str(S/'tools/review_metadata.py'),'--root',str(alternate)],env=altenv)
    altmeta['candidate_source_manifest_hash']=alt_hash;write(alternate/'audit/stage2_current_readiness.json',altmeta)
    correct=run('alternate_root_correct_manifest',[sys.executable,'-B',str(S/'tools/review_metadata.py'),'--root',str(alternate)],env=altenv)
    check('alternate_root_rejects_stale_foreign_source_manifest',stale.returncode!=0,{'expected':'reject','actual_exit_code':stale.returncode,'target_source_hash':alt_hash,'incorrect_foreign_declared_hash':current['candidate_source_manifest_hash'],'stdout':stale.stdout.decode('utf-8','replace')})
    check('alternate_root_accepts_own_correct_source_manifest',correct.returncode==0,{'expected':'accept','actual_exit_code':correct.returncode,'target_source_hash':alt_hash,'stderr':correct.stderr.decode('utf-8','replace')})
    check('original_Git_index_unchanged',before==(sha(indexreal.read_bytes()) if indexreal.exists() else None))
    result={'reviewed_source_commit':C,'baseline_commit':B,'WR24_original_scope':'old raw ea negative reproduced; current fields/history/source lists and default metadata CLI corrected','checks':checks,'metadata_checks':len(checks),'checks_passed':sum(x['passed'] for x in checks),'negative_validator_scenarios':len(cases),'CLI_invocations':4,'original_MRE_invocations':1,'metadata_tool_invocations':3,'production_Git_or_source_writes':0,'market_QC_model_or_authoritative_registry_writes':0,'independent_product_unit_methods':0,'alternate_root_probe':{'default_source_hash':current['candidate_source_manifest_hash'],'target_actual_source_hash':alt_hash,'stale_manifest_exit':stale.returncode,'correct_manifest_exit':correct.returncode,'candidate_source_under_audit':str(S),'synthetic_target_root':str(alternate)},'financial_evidence':False}
    write(R/'wr24_report.json',result);print(json.dumps({k:v for k,v in result.items() if k!='checks'},ensure_ascii=False));print(json.dumps([x for x in checks if not x['passed']],ensure_ascii=False));return 0 if all(x['passed'] for x in checks) else 1
if __name__=='__main__':
    try:sys.exit(main())
    except Exception:
        (R/'metadata_first_reviewer_error.txt').write_text(traceback.format_exc(),encoding='utf-8');write(R/'metadata_first_error_checks.json',checks);raise
