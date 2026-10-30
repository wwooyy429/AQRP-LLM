"""Read-only verification of all sealed artifacts and both fixed source trees."""
from pathlib import Path
import hashlib,json
R=Path(__file__).resolve().parent
manifest=json.loads((R/'artifact_manifest.json').read_text(encoding='utf-8'))
for rel,expected in manifest.items():
    p=(R/rel).resolve();assert p.is_relative_to(R),rel
    assert p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==expected,rel
sources=json.loads((R/'source_git_manifest.json').read_text(encoding='utf-8'))
for name,item in sources.items():
    root=R/item['directory']
    actual={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
    assert actual==item['files'],name
print(json.dumps({'artifact_files_verified':len(manifest),'source_files':{k:v['count'] for k,v in sources.items()},'passed':True}))
