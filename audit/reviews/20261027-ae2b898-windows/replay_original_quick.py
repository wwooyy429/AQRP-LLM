from pathlib import Path
import hashlib,json,os,shutil,subprocess,sys,time
R=Path(__file__).parent;OUT=R/'original_quick_full';OUT.mkdir(exist_ok=False)
old=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-8f7236e-20261027\admission_agent\quick_joint_probes.py')
script=OUT/old.name;shutil.copyfile(old,script);assert script.read_bytes()==old.read_bytes()
cmd=[sys.executable,'-B',str(script)];t=time.monotonic()
p=subprocess.run(cmd,cwd=R,capture_output=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8',OPENBLAS_NUM_THREADS='1'))
(OUT/'stdout.txt').write_bytes(p.stdout);(OUT/'stderr.txt').write_bytes(p.stderr)
record={'reviewed_source_commit':'ae2b8985f3799c246e90341370f86d80483f63ed','source_directory':str(R/'source'),'command':cmd,'cwd':str(R),'exit_code':p.returncode,'seconds':time.monotonic()-t,'original_script_sha256':hashlib.sha256(old.read_bytes()).hexdigest(),'original_script_unchanged':True,'historical_commit_literal_is_not_actual_current_source_identity':True}
(OUT/'execution_record.json').write_bytes(json.dumps(record,indent=2).encode());print(json.dumps(record));print(p.stdout.decode('utf-8')[-700:]);raise SystemExit(p.returncode)
