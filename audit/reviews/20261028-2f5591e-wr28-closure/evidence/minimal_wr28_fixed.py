"""Standard-library raw-byte check of the manifest pinned by the review commit."""
from pathlib import Path
from hashlib import sha1,sha256
import json,sys
root=Path(sys.argv[1]).resolve()
package=root/'audit/review_packages/deployment-eof-v2'
old_raw=(package/'protected_before.json').read_bytes()
manifest=json.loads((package/'protected_git_baseline.json').read_bytes())
assert sha256(old_raw).hexdigest()==manifest['path_list_source']['sha256']=='26308901ada1f73a1fa9064bc76d4a55ec9ed53b820ab1dc9bcd2f529ad28677'
legacy=json.loads(old_raw);assert len(legacy)==len(manifest['files'])==122
old_mismatches=0
for name,item in manifest['files'].items():
    path=(root/name).resolve();assert path.is_relative_to(root)
    raw=path.read_bytes()
    assert len(raw)==item['byte_count'],name
    assert sha256(raw).hexdigest()==item['sha256'],name
    assert sha1(b'blob '+str(len(raw)).encode('ascii')+b'\0'+raw).hexdigest()==item['git_blob_oid'],name
    assert legacy[name]==item['legacy_declared_sha256']
    old_mismatches+=legacy[name]!=item['sha256']
assert old_mismatches==3
print(json.dumps({'new_Git_raw_records_verified':122,'old_mismatches_explicitly_retained':3,'financial_evidence':False}))
