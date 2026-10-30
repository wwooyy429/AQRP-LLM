from pathlib import Path
import hashlib,json,os,subprocess,sys,time
root=Path(__file__).resolve().parents[2]
review=root.parent/'LLM审核/review-8f7236e-20261027'
phase=sys.argv[1]
source=review/'source' if phase=='before' else root
out=root/'.git/repair-work'/('wr17-original-'+phase)
out.mkdir(parents=True,exist_ok=True)
script=review/'admission_agent/minimal_pending_freeze.py'
# Original script copies a whole source tree; root's .git is not source.
# Its fixed pre-fix snapshot is used before edit. Candidate export below uses
# a permitted source-only copy under .git with the same actual ledger bytes.
if phase!='before':
    import shutil
    source=out/'candidate'
    if source.exists():raise RuntimeError('Use a new phase/output directory')
    shutil.copytree(root,source,ignore=shutil.ignore_patterns('.git','__pycache__','*.pyc'))
command=[sys.executable,'-B',str(script),str(source),str(out/'run')]
start=time.monotonic()
result=subprocess.run(command,cwd=root,env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8'),capture_output=True)
(out/'stdout').write_bytes(result.stdout);(out/'stderr').write_bytes(result.stderr)
record={'command':command,'cwd':str(root),'exit_code':result.returncode,'seconds':time.monotonic()-start,'script_sha256':hashlib.sha256(script.read_bytes()).hexdigest(),'phase':phase,'real_cloud_or_model_calls':0}
(out/'execution_record.json').write_bytes((json.dumps(record,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
print(json.dumps(record,ensure_ascii=True))
