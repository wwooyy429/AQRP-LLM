"""Reproduce the published protected-file assertion on an untouched Git export."""
from pathlib import Path
from hashlib import sha256
import json,sys
root=Path(sys.argv[1]).resolve()
declared=json.loads((root/'audit/review_packages/deployment-eof-v2/protected_before.json').read_bytes())
bad=[{'path':name,'declared':expected,'actual':sha256((root/name).read_bytes()).hexdigest()}
     for name,expected in declared.items()if sha256((root/name).read_bytes()).hexdigest()!=expected]
print(json.dumps({'protected_files':len(declared),'mismatches':bad},indent=2))
assert not bad,'Published protected-file hashes do not match fixed Git bytes'
