"""Independent synthetic boundary probe; no real I/O or ledger mutation."""
from pathlib import Path
from copy import deepcopy
import hashlib
import json
import sys
import tempfile

ROOT=Path.cwd()
sys.path[:0]=[str(ROOT/'cloud'),str(ROOT/'tests')]
from qresearch.engineering_tasks import validate_joint_report
from qresearch.engineering_storage import encode_compressed_json
from test_engineering_storage import StorageRepairWorkerTests

guard_paths=['audit/runtime/registry/events.jsonl','config/budget.json']
before={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in guard_paths}
case=StorageRepairWorkerTests()
results=[]
with tempfile.TemporaryDirectory() as directory:
 root,qb,api,payload,capacity,old=case.fixture(directory)
 wrapper=case.execute(root,qb,api,payload,capacity)
 report=wrapper['cloud_report'];document=payload['plan']
 validate_joint_report(report,document)
 for name,mutate in (
  ('wrong_data_identity_hash',lambda x:x['evidence']['collection_storage'].update(data_identity_hash='0'*64)),
  ('cache_only_report_with_nonzero_history_calls',lambda x:x['statistics'].update(history_calls_first=1)),
 ):
  altered=deepcopy(report);mutate(altered)
  try:validate_joint_report(altered,document)
  except Exception as error:results.append({'case':name,'accepted':False,'error_class':type(error).__name__})
  else:results.append({'case':name,'accepted':True})
 lean=deepcopy(report)
 lean['identity']['stage']='lean'
 lean['evidence']={'storage_preflight':deepcopy(capacity)}
 stored,encoding=encode_compressed_json({'synthetic':'bounded-record'})
 lean['evidence']['receiver_storage']=encoding
 lean['evidence']['received_bar_ref']={'key':'synthetic/not-the-stored-hash.json.zlib','sha256':'f'*64}
 try:validate_joint_report(lean,document)
 except Exception as error:results.append({'case':'LEAN_encoding_ref_unbound','accepted':False,'error_class':type(error).__name__})
 else:results.append({'case':'LEAN_encoding_ref_unbound','accepted':True})
 assert lean['evidence']['received_bar_ref']['sha256']!=encoding['stored_sha256']
after={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in guard_paths}
assert after==before
output={'kind':'independent_synthetic_joint_report_binding_probe','results':results,
 'real_ledger_and_budget_unchanged':True,'cloud_calls':0,'actual_Research_executions':0,'actual_LEAN_submissions':0,
 'scope':'validate_joint_report component; synthetic fixtures construct a completed Research report, LEAN case tests component binding only.'}
Path(__file__).with_name('engineering_storage_binding_probe_result.json').write_text(json.dumps(output,indent=2)+'\n',encoding='utf-8')
print(json.dumps(output))
