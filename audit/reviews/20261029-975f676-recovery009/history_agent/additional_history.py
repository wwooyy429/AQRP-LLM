from pathlib import Path
import subprocess,sys,os,json,hashlib,time,importlib.util,shutil
O=Path(__file__).resolve().parent;S=O/'replay_context/source';G=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\repo')
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',PYTHONPATH=str(S/'cloud'),GIT_DIR=str(G/'.git'),GIT_WORK_TREE=str(S),GIT_OPTIONAL_LOCKS='0')
records=[]
for label,args in [('wr15',[S/'audit/reviews/20261027-4a94430-windows/minimal_manifest_hash.py',S]),('wr28',[S/'audit/review_packages/wr28/test_git_protection.py','-q'])]:
    cmd=[sys.executable,'-B',*map(str,args)];t=time.monotonic();p=subprocess.run(cmd,cwd=S,capture_output=True,env=env)
    (O/(label+'.stdout')).write_bytes(p.stdout);(O/(label+'.stderr')).write_bytes(p.stderr)
    r={'label':label,'command':cmd,'cwd':str(S),'environment_GIT_object_source':str(G),'git_write_commands_executed':False,'current_source_commit':'975f676d62b561689909744f9e7236290e3f5fcb','exit_code':p.returncode,'seconds':time.monotonic()-t,'stdout_sha256':hashlib.sha256(p.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(p.stderr).hexdigest()};records.append(r)
    (O/'additional_execution.json').write_text(json.dumps(records,indent=2),encoding='utf-8');print(json.dumps(r),flush=True);print((p.stdout+p.stderr).decode('utf-8','replace')[-500:],flush=True)
summary=json.loads(subprocess.check_output(['git','-C',str(G),'show','84414ab49c39e25cb50ece1c1debeefa3993c874:audit/stage2_current_readiness.json']))['platform_comparison_from_independent_review']
manifest=json.loads((S/'audit/reviews/20261027-ae2b898-windows/source_git_manifest.json').read_bytes())['candidate']
comparison=json.loads((S/'audit/reviews/20261027-ae2b898-windows/cloud_comparison.json').read_bytes())
candidate={k[len('cloud/'):]:v for k,v in manifest['files'].items() if k.startswith('cloud/') and k.endswith('.py')}
reference={x['path']:x['cloud_utf8_sha256'] for x in comparison['files'] if x['path']!='_engineering_task_input.py'}
different=sorted(k for k in candidate.keys()&reference.keys() if candidate[k]!=reference[k]);outside=sorted(candidate.keys()-reference.keys())
assert len(different)==9 and len(outside)==4 and summary['candidate_different_or_missing_paths']==13
for refname in ('candidate_manifest_ref','archived_platform_comparison_ref'):
    ref=summary[refname];assert hashlib.sha256((S/ref['path']).read_bytes()).hexdigest()==ref['raw_sha256']
sys.path[:0]=[str(S/'tools'),str(S/'cloud')]
from stages import source_manifest
foreign=O/'foreign_identity_only';(foreign/'cloud').mkdir(parents=True,exist_ok=False)
raw=b'VALUE = 117\r\n';(foreign/'cloud/probe.py').write_bytes(raw)
expected_files={'cloud/probe.py':hashlib.sha256(b'VALUE = 117\n').hexdigest()}
expected_hash=hashlib.sha256(json.dumps(expected_files,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
result=source_manifest(root=foreign);assert result['source_files']==expected_files and result['source_hash']==expected_hash
own=source_manifest(root=S);assert own['source_hash']!=expected_hash
extra={'WR19':{'kind':'independent_historical_metadata_recomputation_not_current_CLI','fixed_summary_commit':'84414ab49c39e25cb50ece1c1debeefa3993c874','different_known':len(different),'outside_reference':len(outside),'computed':len(different)+len(outside),'declared':summary['candidate_different_or_missing_paths'],'referenced_raw_hashes_match':True,'current_cloud_state_authenticated':False},'WR27':{'kind':'current_underlying_explicit_root_helper_known_answer_only','source_manifest_explicit_root_matches_independent_raw_normalization_hash':True,'tool_tree_hash_differs':True,'full_cross_directory_metadata_CLI_rerun':False},'financial_evidence':False}
(O/'additional_static_results.json').write_text(json.dumps(extra,indent=2),encoding='utf-8');print(json.dumps(extra),flush=True)
