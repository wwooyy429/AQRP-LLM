"""Execute unchanged archived script and helpers against a selected source."""
from pathlib import Path
import argparse,hashlib,json,os,shutil,subprocess,sys,tempfile
def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--script',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    source=a.source.resolve();script=a.script.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    raw=script.read_bytes();hashes={f.relative_to(source).as_posix():hashlib.sha256(f.read_bytes()).hexdigest() for folder in ['cloud','config','tools'] for f in (source/folder).rglob('*') if f.is_file() and f.suffix in ['.py','.json']}
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
    with tempfile.TemporaryDirectory(prefix='aqrp-unchanged-review-script-') as directory:
        work=Path(directory);shutil.copytree(source,work/'source');job=work/script.parent.name;job.mkdir()
        for f in script.parent.glob('*.py'):shutil.copy2(f,job/f.name)
        (work/'sitecustomize.py').write_text('import socket\ndef denied(*a,**k): raise AssertionError("Offline script replay prohibits network")\nsocket.socket.connect=denied\n',encoding='utf-8')
        env['PYTHONPATH']=str(work)
        cmd=[sys.executable,'-B',str(job/script.name)]
        r=subprocess.run(cmd,cwd=work,env=env,capture_output=True,text=True,encoding='utf-8')
        (out/'stdout.txt').write_text(r.stdout,encoding='utf-8');(out/'stderr.txt').write_text(r.stderr,encoding='utf-8')
        outputs=[]
        for f in job.iterdir():
            if f.is_file() and f.suffix in ['.json','.txt','.diff']:
                shutil.copy2(f,out/f.name);outputs.append(f.name)
        unchanged=all(hashlib.sha256((work/'source'/n).read_bytes()).hexdigest()==h for n,h in hashes.items())
        result={'actually_executed':True,'entrypoint':'unchanged original script main','script_sha256':hashlib.sha256(raw).hexdigest(),'script_changed':False,
            'source_files':hashes,'source_unchanged':unchanged,'process_exit_code':r.returncode,'output_files':outputs,'financial_evidence':False,'real_SDK_executed':False}
        (out/'replay.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps({'script':script.name,'exit_code':r.returncode,'source_unchanged':unchanged,'outputs':outputs}))
        return r.returncode if unchanged else 2
if __name__=='__main__':raise SystemExit(main())
