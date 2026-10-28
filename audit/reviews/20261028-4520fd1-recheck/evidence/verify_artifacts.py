"""Portable read-only strict file-set, raw-hash and complete fixed-source check."""
from pathlib import Path
import hashlib,json
R=Path(__file__).resolve().parent
manifest=json.loads((R/'artifact_manifest.json').read_bytes())
assert {p.relative_to(R).as_posix()for p in R.rglob('*')if p.is_file()}==set(manifest)|{'artifact_manifest.json'}
for name,digest in manifest.items():
 p=(R/name).resolve();assert p.is_relative_to(R)
 assert hashlib.sha256(p.read_bytes()).hexdigest()==digest,name
source=json.loads((R/'source_git_manifest.json').read_bytes());S=R/source['directory']
actual={p.relative_to(S).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()for p in S.rglob('*')if p.is_file()}
assert actual==source['files']and len(actual)==source['count']==5976
print(json.dumps({'artifact_files_verified':len(manifest),'fixed_source_files':len(actual),'passed':True}))
