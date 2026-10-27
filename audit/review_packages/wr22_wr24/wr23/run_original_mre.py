from pathlib import Path
import hashlib,json,os,shutil,subprocess,sys,tarfile,io

ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent
REVIEW=Path('B:/BaiduSyncdisk/学习/投资/量化/量化交易比赛/LLM审核/review-ea6053e-20261027/dispatch_agent')
label=sys.argv[1]
source=OUT/(label+'_source');source.mkdir()
folders=['cloud','config','templates','tests','tools','docs','.github']
if label=='baseline':
    names=folders+['AGENTS.md','requirements-test.txt','.gitattributes','.gitignore','README.md']
    data=subprocess.check_output(['git','archive','ea6053e3e9ef4be17db246daf18a4cf9b2e5be58',*names],cwd=ROOT)
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        for member in archive.getmembers():
            assert (source/member.name).resolve().is_relative_to(source.resolve())
        archive.extractall(source)
else:
    for folder in folders:shutil.copytree(ROOT/folder,source/folder,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    for name in ['AGENTS.md','requirements-test.txt','.gitattributes','.gitignore','README.md']:shutil.copyfile(ROOT/name,source/name)
(source/'audit/runtime/registry').mkdir(parents=True)
for name in ['audit/deployment.json','audit/stage_verification.json','audit/runtime/registry/events.jsonl']:
    (source/name).parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,source/name)
runner=OUT/(label+'_runner');runner.mkdir()
script_hashes={}
for name in ['minimal_prepare_entry_crash.py','independent_recovery_support.py']:
    raw=(REVIEW/name).read_bytes();(runner/name).write_bytes(raw);script_hashes[name]=hashlib.sha256(raw).hexdigest()
env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
build=subprocess.run([sys.executable,'-B','tools/research.py','build'],cwd=source,env=env,capture_output=True)
(OUT/(label+'_build.stdout')).write_bytes(build.stdout);(OUT/(label+'_build.stderr')).write_bytes(build.stderr);assert build.returncode==0
cmd=[sys.executable,'-B',str(runner/'minimal_prepare_entry_crash.py'),'--source',str(source),'--out',str(OUT/(label+'_original_mre'))]
run=subprocess.run(cmd,cwd=runner,env=env,capture_output=True)
(OUT/(label+'_mre.stdout')).write_bytes(run.stdout);(OUT/(label+'_mre.stderr')).write_bytes(run.stderr)
record={'command':cmd,'exit_code':run.returncode,'original_script_hashes':script_hashes,'originals_unchanged':True,
    'source':str(source),'source_kind':'fixed_ea6053e_git_bytes' if label=='baseline' else 'current_source_copy',
    'source_adaptation':['fresh isolated copy','isolated build before freeze','fresh output'],
    'new_QC_calls':0,'new_authoritative_budget_writes':0,'independent_acceptance':False}
record['actual_production_file_raw_sha256']={name:hashlib.sha256((source/name).read_bytes()).hexdigest() for name in ['tools/stage2.py','cloud/qresearch/engineering_receipts.py']}
record['original_script_hardcoded_commit_is_historical_label']='ea6053e3e9ef4be17db246daf18a4cf9b2e5be58'
(OUT/(label+'_mre_execution.json')).write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
print(json.dumps(record))
