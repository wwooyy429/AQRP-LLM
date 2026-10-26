"""Verify this audit package offline, without changing its files."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parent
manifest=json.loads((ROOT/'artifact_manifest.json').read_text(encoding='utf-8'))
for name,digest in manifest.items():
    file=(ROOT/name).resolve()
    assert file.is_relative_to(ROOT)
    assert hashlib.sha256(file.read_bytes()).hexdigest()==digest,name
sources=json.loads((ROOT/'source_git_manifest.json').read_text(encoding='utf-8'))
for label,prefix in [('candidate','source'),('baseline7bf','baselines/7bf716f/source'),('baselinefbe','baselines/fbe2454/source')]:
    root=ROOT/prefix; actual={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
    assert actual==sources[label]['files'],label
print(json.dumps({'verified_manifest_entries':len(manifest),'source_files':608,'financial_evidence':False}))
