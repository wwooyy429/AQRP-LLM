"""WR-27: metadata --root must hash that root, not the CLI's source tree.

Run against a saved fixed source and a local Git object repository. Writes only
new isolated fixture files and index metadata under --output. No market calls.
"""
from pathlib import Path
import argparse,copy,hashlib,json,os,shutil,subprocess,sys,time
C='ccad61d03ccf17bf2bdc2d7ffc88dfd11b6d3ca6'
B='ea6053e3e9ef4be17db246daf18a4cf9b2e5be58'
def sha(b):return hashlib.sha256(b).hexdigest()
def canonical(v):return json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
def manifest(root):
    paths=[p for n in ('cloud','config','templates','tests','tools','docs','.github') for p in (root/n).rglob('*') if p.is_file() and p.suffix in ('.py','.json','.md','.yml','.yaml') and '__pycache__' not in p.parts]
    paths += [root/n for n in ('requirements-test.txt','.gitattributes','.gitignore','AGENTS.md') if (root/n).is_file()]
    return {p.relative_to(root).as_posix():sha(p.read_bytes().decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n').encode()) for p in paths}
def main():
    p=argparse.ArgumentParser();p.add_argument('--source',required=True,type=Path);p.add_argument('--git-repository',required=True,type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
    source=a.source.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    original_manifest=manifest(source);original_raw={p:sha((source/p).read_bytes()) for p in original_manifest}
    metadata=json.loads((source/'audit/stage2_current_readiness.json').read_bytes())
    assert metadata['current_activity']['baseline_commit']==B
    assert metadata['candidate_source_manifest_hash']==sha(canonical(original_manifest))
    gitdir=subprocess.check_output(['git','-C',str(a.git_repository),'rev-parse','--absolute-git-dir'],text=True).strip()
    actual_index=Path(gitdir)/'index';index_before=sha(actual_index.read_bytes()) if actual_index.exists() else None
    env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1',GIT_OPTIONAL_LOCKS='0',GIT_DIR=gitdir,GIT_WORK_TREE=str(source),GIT_INDEX_FILE=str(out/'fixed_source.index'))
    commands=[]
    def run(label,cmd,runenv=env):
        start=time.perf_counter();r=subprocess.run(cmd,cwd=out,env=runenv,capture_output=True)
        (out/(label+'.stdout')).write_bytes(r.stdout);(out/(label+'.stderr')).write_bytes(r.stderr)
        commands.append({'label':label,'command':cmd,'cwd':str(out),'exit_code':r.returncode,'seconds':round(time.perf_counter()-start,3),'stdout_raw_sha256':sha(r.stdout),'stderr_raw_sha256':sha(r.stderr)})
        (out/'commands.json').write_bytes((json.dumps(commands,ensure_ascii=False,indent=2)+'\n').encode())
        return r
    assert run('own_index_setup',['git','read-tree',C]).returncode==0
    default=run('default_legal_control',[sys.executable,'-B',str(source/'tools/review_metadata.py')])
    alternate=out/'alternate_root'
    for path in original_manifest:
        target=alternate/path;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source/path,target)
    for path in ('audit/stage2_current_readiness.json','audit/runtime/registry/events.jsonl'):
        target=alternate/path;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source/path,target)
    probe=alternate/'cloud/qresearch/factors.py';probe.write_bytes(probe.read_bytes()+b'\n# Isolated WR27 target-root identity probe.\n')
    names=subprocess.check_output(['git','-C',str(a.git_repository),'diff','--name-only','--no-renames',B],text=True,env=env).splitlines()
    altmeta=copy.deepcopy(metadata);altmeta['source_changed_this_round']=sorted({p for p in names if p.startswith(('cloud/','tests/','tools/')) and p.endswith('.py')}|{'cloud/qresearch/factors.py'})
    target_hash=sha(canonical(manifest(alternate)));assert target_hash!=metadata['candidate_source_manifest_hash']
    meta_path=alternate/'audit/stage2_current_readiness.json'
    def write_meta():meta_path.write_bytes((json.dumps(altmeta,ensure_ascii=False,indent=2)+'\n').encode())
    write_meta();alternate_env=dict(env,GIT_WORK_TREE=str(alternate))
    stale=run('foreign_hash_false_accept',[sys.executable,'-B',str(source/'tools/review_metadata.py'),'--root',str(alternate)],alternate_env)
    altmeta['candidate_source_manifest_hash']=target_hash;write_meta()
    correct=run('own_hash_false_reject',[sys.executable,'-B',str(source/'tools/review_metadata.py'),'--root',str(alternate)],alternate_env)
    source_unchanged=all(sha((source/path).read_bytes())==h for path,h in original_raw.items())
    index_unchanged=index_before==(sha(actual_index.read_bytes()) if actual_index.exists() else None)
    result={'finding':'WR-27','priority':'P3','blocking':False,'reviewed_source_commit':C,'baseline_commit':B,'scope':'Only explicit --root pointing at a distinct valid synthetic source tree; default path remains correct.',
        'default_legal_control_exit':default.returncode,'default_source_hash':metadata['candidate_source_manifest_hash'],'alternate_actual_source_hash':target_hash,
        'foreign_hash_expected_exit':'nonzero','foreign_hash_actual_exit':stale.returncode,'foreign_hash_stdout':stale.stdout.decode('utf-8','replace'),
        'own_hash_expected_exit':0,'own_hash_actual_exit':correct.returncode,'own_hash_stderr':correct.stderr.decode('utf-8','replace'),
        'source_original_raw_unchanged':source_unchanged,'actual_repository_index_unchanged':index_unchanged,'independent_product_unit_methods':0,
        'QC_Research_LEAN_model_deployment_authoritative_budget_calls':0,'financial_evidence':False}
    (out/'result.json').write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode());print(json.dumps(result,ensure_ascii=False,indent=2))
    assert source_unchanged and index_unchanged and default.returncode==0
    assert stale.returncode!=0 and correct.returncode==0,'WR-27: --root checked the CLI source tree instead of the selected target'
if __name__=='__main__':main()
