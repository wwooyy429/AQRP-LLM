from pathlib import Path
from hashlib import sha256
import json

root=Path(__file__).resolve().parent
manifest=json.loads((root/'artifact_manifest.json').read_text(encoding='utf-8'))
actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
assert actual==set(manifest['files'])|{'artifact_manifest.json'},'Artifact file set differs'
for name,item in manifest['files'].items():
    raw=(root/name).read_bytes()
    assert len(raw)==item['bytes'] and sha256(raw).hexdigest()==item['sha256'],name
source=json.loads((root/'source_git_manifest.json').read_text(encoding='utf-8'))
for folder,item in source.items():
    paths={p.relative_to(root/folder).as_posix() for p in (root/folder).rglob('*') if p.is_file()}
    assert paths==set(item['files']),folder
    for name,expected in item['files'].items():
        raw=(root/folder/name).read_bytes()
        assert len(raw)==expected['bytes'] and sha256(raw).hexdigest()==expected['sha256'],folder+'/'+name
print(json.dumps({'artifact_entries':len(manifest['files']),'fixed_sources_raw_verified':{k:len(v['files']) for k,v in source.items()},'passed':True}))
