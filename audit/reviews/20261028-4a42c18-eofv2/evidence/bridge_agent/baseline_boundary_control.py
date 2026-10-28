import argparse,hashlib,json,sys,tempfile
from pathlib import Path
sys.dont_write_bytecode=True
p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--label',required=True);a=p.parse_args()
sys.path.insert(0,str(a.source/'cloud'))
from qresearch.artifacts import content_hash
from qresearch.engineering_data import verify_deployment
raw=b'REVIEW_SYNTHETIC = 41\n';sha=lambda b:hashlib.sha256(b).hexdigest()
v1={'entry.py':sha(raw)}
v2={'schema_version':2,'source_identity_policy':'utf8_sig_universal_newlines_terminal_lf_v1','files':{'entry.py':{'source_sha256':sha(raw),'canonical_sha256':sha(raw),'terminal_lf_count':1}}}
with tempfile.TemporaryDirectory()as d:
 root=Path(d);(root/'entry.py').write_bytes(raw);assert verify_deployment(v1,content_hash(v1),source_root=root)==content_hash(v1)
 (root/'entry.py').write_bytes(raw+b'\n')
 try:verify_deployment(v1,content_hash(v1),source_root=root)
 except ValueError:strict_rejected=True
 else:strict_rejected=False
 assert strict_rejected
 try:verify_deployment(v2,content_hash(v2),source_root=root)
 except ValueError:v2_accepted=False
 else:v2_accepted=True
 assert v2_accepted==(a.label=='candidate')
print(json.dumps({'label':a.label,'manual_cases':3,'v1_original_passed':True,'v1_extra_LF_rejected':strict_rejected,'v2_worker_extra_LF_accepted':v2_accepted,'market_calls':0}))
