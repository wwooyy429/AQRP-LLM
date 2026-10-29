from pathlib import Path
import subprocess, json, hashlib, tarfile, io, sys, shutil
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parent
G=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\repo')
maps={}
for label,commit in {'source':'c2e63ac5f19901bd95e127069b5998452f7f9864','materials':'f698a38a99c3ed8388c9403f2eda723b579c5eaf'}.items():
    dest=R/label
    assert not dest.exists(),dest
    dest.mkdir()
    raw=subprocess.check_output(['git','-C',str(G),'archive','--format=tar',commit])
    files={}
    with tarfile.open(fileobj=io.BytesIO(raw),mode='r:') as archive:
        for member in archive:
            if member.isdir():continue
            assert member.isfile(),member.name
            p=dest/member.name
            assert p.resolve().is_relative_to(dest.resolve()),member.name
            data=archive.extractfile(member).read();p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
            files[member.name]={'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}
    maps[label]={'commit':commit,'tree':subprocess.check_output(['git','-C',str(G),'rev-parse',commit+'^{tree}'],text=True).strip(),'files':files}
    print(label,commit,len(files),flush=True)
(R/'source_git_manifest.json').write_text(json.dumps(maps,ensure_ascii=False,indent=2),encoding='utf-8')
for name,first,last in [('baseline_to_source.diff','2d1d3060dbc7eb136c1dee61f0647977528b8aad',maps['source']['commit']),('source_to_materials.diff',maps['source']['commit'],maps['materials']['commit']),('PR_full.diff','6a1edbf07fa8fc6cf774084094f4beacc28ff60b',maps['materials']['commit'])]:
    (R/name).write_bytes(subprocess.check_output(['git','-C',str(G),'diff','--no-ext-diff',first,last]))
shutil.copytree(R/'source',R/'work_source')
shutil.copyfile(Path(r'C:\Users\11638\.codex\tmp\aqrp-review-975f676-20261029\user_review_charter.txt'),R/'user_review_charter.txt')
print('READY',R,flush=True)
