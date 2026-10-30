"""Verify this independent review seal, not approval of the reviewed product."""
from pathlib import Path
import hashlib,json
R=Path(__file__).resolve().parent
manifest=json.loads((R/'artifact_manifest.json').read_bytes())
assert {p.relative_to(R).as_posix()for p in R.rglob('*')if p.is_file()}==set(manifest)|{'artifact_manifest.json'}
for name,digest in manifest.items():
 p=(R/name).resolve();assert p.is_relative_to(R)
 assert hashlib.sha256(p.read_bytes()).hexdigest()==digest,name
sources=json.loads((R/'source_git_manifest.json').read_bytes())
for name,item in sources.items():
 S=R/item['directory'];actual={p.relative_to(S).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()for p in S.rglob('*')if p.is_file()}
 assert actual==item['files']and len(actual)==item['count'],name
print(json.dumps({'artifact_files_verified':len(manifest),'fixed_Git_source_counts':{k:v['count']for k,v in sources.items()},'review_seal_passed':True,'candidate_delivery_passed':False,'open_WR28':True}))
