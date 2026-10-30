"""Hand-built same v2 manifest against old and new verifiers; no providers."""
import argparse,hashlib,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--expected-v2',choices=['yes','no'],required=True);a=p.parse_args()
sys.path.insert(0,str(a.source.resolve()/'cloud'))
from qresearch.artifacts import content_hash
from qresearch.engineering_data import verify_deployment
def H(b):return hashlib.sha256(b).hexdigest()
root=a.out.resolve();root.mkdir(parents=True,exist_ok=True);path=root/'a.py'
original=b'VALUE = 101\n'
legacy={'a.py':H(original)}
new={'schema_version':2,'source_identity_policy':'utf8_sig_universal_newlines_terminal_lf_v1','files':{'a.py':{'source_sha256':H(original),'canonical_sha256':H(original),'terminal_lf_count':1}}}
def accepted(manifest):
 try:verify_deployment(manifest,content_hash(manifest),source_root=root)
 except ValueError:return False
 return True
path.write_bytes(original);legacy_original=accepted(legacy)
path.write_bytes(original+b'\n');legacy_extra=accepted(legacy);v2_extra=accepted(new)
path.write_bytes(b'VALUE = 102\n\n');v2_changed_body=accepted(new)
assert legacy_original is True and legacy_extra is False and v2_changed_body is False
assert v2_extra is(a.expected_v2=='yes')
result={'legacy_original_accepted':legacy_original,'legacy_extra_LF_accepted':legacy_extra,'v2_extra_LF_accepted':v2_extra,'v2_body_change_accepted':v2_changed_body,'manifest_sha256':content_hash(new),'original_sha256':H(original),'worker_sha256':H(original+b'\n'),'financial_evidence':False}
(root/'mre_result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result))
