from pathlib import Path
import hashlib,json
r=Path(__file__).parent;m=json.loads((r/'artifact_manifest.json').read_text(encoding='utf-8'))
bad=[n for n,h in m['files'].items() if not (r/n).is_file() or hashlib.sha256((r/n).read_bytes()).hexdigest()!=h]
print(json.dumps({'files':len(m['files']),'bad':bad}));raise SystemExit(bool(bad))
