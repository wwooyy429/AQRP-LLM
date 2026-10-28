from pathlib import Path
import hashlib,io,json,subprocess,tarfile,shutil,platform,sys,importlib.metadata,time
R=Path(__file__).resolve().parent;G=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\repo')
versions={'candidate':('4a42c18f0b78bea2068d589bc12f1615712354c6','source'),'baseline':('8d65c290773547c83549c098172f1eb8c3376cd7','baselines/8d65c29/source'),'archive':('1cf26578da59eebd37e138ca5d6d076991386470','archive_source')}
maps={};records=[]
for name,(commit,folder)in versions.items():
 dest=R/folder;dest.mkdir(parents=True,exist_ok=False);argv=['git','-C',str(G),'archive',commit];t=time.monotonic();p=subprocess.run(argv,capture_output=True);assert p.returncode==0,p.stderr
 records.append({'name':name,'command':argv,'exit_code':p.returncode,'seconds':time.monotonic()-t,'archive_sha256':hashlib.sha256(p.stdout).hexdigest(),'stderr':p.stderr.decode()})
 with tarfile.open(fileobj=io.BytesIO(p.stdout))as tf:
  for m in tf.getmembers():
   if m.isfile():
    q=(dest/m.name).resolve();assert q.is_relative_to(dest.resolve());q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(tf.extractfile(m).read())
 files={q.relative_to(dest).as_posix():hashlib.sha256(q.read_bytes()).hexdigest()for q in dest.rglob('*')if q.is_file()};maps[name]={'commit':commit,'directory':folder,'count':len(files),'files':files}
 (R/'source_git_manifest.json').write_text(json.dumps(maps,indent=2)+'\n',encoding='utf-8');print(json.dumps({'exported':name,'count':len(files),'commit':commit}),flush=True)
(R/'git_archive_execution.json').write_text(json.dumps(records,indent=2)+'\n',encoding='utf-8')
diffs={}
for label,left,right in [('fixed_to_archive',versions['candidate'][0],versions['archive'][0]),('baseline_to_fixed',versions['baseline'][0],versions['candidate'][0]),('previous_review_to_baseline','4520fd1a4421a9b764d2bfd61e5fb5cf4b59a9c8',versions['baseline'][0])]:
 argv=['git','-C',str(G),'diff','--name-status',left,right];p=subprocess.run(argv,capture_output=True);assert p.returncode==0;(R/(label+'.txt')).write_bytes(p.stdout);diffs[label]=p.stdout.decode()
print(json.dumps({'fixed_to_archive_changes':diffs['fixed_to_archive']}),flush=True)
shutil.copyfile(Path(r'C:\Users\11638\.codex\attachments\c42c723c-86e8-4968-9d6d-f71a219c5d39\已粘贴的文本.txt'),R/'user_review_charter.txt')
(R/'environment.json').write_text(json.dumps({'os':platform.platform(),'python':sys.version,'executable':sys.executable,'dependencies':{n:importlib.metadata.version(n)for n in ['numpy','pandas','python-dateutil','pytz','six','tzdata']}},indent=2)+'\n',encoding='utf-8')
(R/'EXPORT_COMPLETE').write_text('complete\n',encoding='ascii')
