from pathlib import Path
import subprocess, json, hashlib, tarfile, io, sys, shutil
sys.dont_write_bytecode = True
R = Path(__file__).resolve().parent
G = Path(r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\repo')
commits = {'source':'975f676d62b561689909744f9e7236290e3f5fcb','materials':'a6a5a165d87c172535cdea6cf495e3c1a850e6e4'}
maps = {}
for label, commit in commits.items():
    dest = R / label
    if dest.exists(): raise RuntimeError('Refuse overwrite '+str(dest))
    dest.mkdir()
    raw = subprocess.check_output(['git','-C',str(G),'archive','--format=tar',commit])
    manifest = {}
    with tarfile.open(fileobj=io.BytesIO(raw),mode='r:') as tf:
        for member in tf:
            if member.isdir(): continue
            if not member.isfile(): raise RuntimeError('Unexpected Git entry '+member.name)
            path = dest / member.name
            if not path.resolve().is_relative_to(dest.resolve()): raise ValueError(member.name)
            data = tf.extractfile(member).read()
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(data)
            manifest[member.name]={'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}
    maps[label] = {'commit':commit,'tree':subprocess.check_output(['git','-C',str(G),'rev-parse',commit+'^{tree}'],text=True).strip(),'files':manifest}
    print(label,commit,len(manifest),flush=True)
(R/'source_git_manifest.json').write_text(json.dumps(maps,ensure_ascii=False,indent=2),encoding='utf-8')
for filename, refs in {'since_WR28.diff':['2f5591e28c0748ac42caeae7bbf3977141d031cb',commits['source']], 'source_to_materials.diff':[commits['source'],commits['materials']], 'PR_full.diff':['6a1edbf07fa8fc6cf774084094f4beacc28ff60b',commits['materials']]}.items():
    (R/filename).write_bytes(subprocess.check_output(['git','-C',str(G),'diff','--no-ext-diff',*refs]))
shutil.copytree(R/'source',R/'work_source')
shutil.copyfile(Path(r'C:\Users\11638\.codex\attachments\c42c723c-86e8-4968-9d6d-f71a219c5d39\已粘贴的文本.txt'),R/'user_review_charter.txt')
print('READY',R,flush=True)
