"""Nonblocking WR15: fixed Git manifest raw bytes versus declared raw hash."""
import hashlib,json,sys
from pathlib import Path
root=Path(sys.argv[1])/'audit/review_packages/wr14'
declared=json.loads((root/'developer_verification.json').read_text(encoding='utf-8'))['developer_outputs_manifest_raw_sha256']
raw=(root/'developer_outputs_manifest.json').read_bytes()
actual=hashlib.sha256(raw).hexdigest()
as_crlf=hashlib.sha256(raw.replace(b'\r\n',b'\n').replace(b'\n',b'\r\n')).hexdigest()
print(json.dumps({'declared':declared,'Git_raw':actual,'CRLF_representation':as_crlf}))
assert actual==declared,'Declared raw hash differs from fixed Git bytes'
