from pathlib import Path
from hashlib import sha256
import base64, json, sys
sys.dont_write_bytecode=True
A=Path(__file__).resolve().parent;R=A.parent;S=R/'source';M=R/'materials'
sys.path.insert(0,str(S/'cloud'))
from qresearch.data_certification import certification_capabilities
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
checks=[]
def check(name,condition,detail=None):
    checks.append({'name':name,'passed':bool(condition),'detail':detail})
    if not condition:raise AssertionError(name)
records=read(M/'audit/review_packages/host010/developer_records_manifest.json')['records']
for name,item in records.items():
    readable=(M/item['readable_path']).read_bytes()
    check('developer_readable_hash:'+name,sha256(readable).hexdigest()==item['readable_sha256'])
    if 'raw_base64_path' in item:
        encoded=(M/item['raw_base64_path']).read_bytes();raw=base64.b64decode(b''.join(encoded.split()),validate=True)
        check('developer_base64_hash:'+name,sha256(encoded).hexdigest()==item['raw_base64_sha256'] and item['readable_is_original_bytes'] is False)
    else:raw=readable;check('developer_raw_representation:'+name,item['readable_is_original_bytes'] is True)
    check('developer_original_recovery:'+name,len(raw)==item['original_bytes'] and sha256(raw).hexdigest()==item['original_sha256'])
check('developer_initial_boundaries_preserved',all(k in records for k in ('developer_agent/first-tests.txt','developer_agent/utf8-first-failure.txt','developer_boundary/additional-first-run.txt','developer_boundary/final-run.txt','developer_boundary/NOTES.md','developer_boundary/result.json')))
packet=read(M/'audit/review_packages/host010/packet_manifest.json')
for name,digest in packet['raw_files'].items():check('packet_raw:'+name,sha256((M/name).read_bytes()).hexdigest()==digest)
catalog=read(S/'config/source_catalog.json')
check('capabilities_recomputed_by_production',certification_capabilities(catalog['fields'])==read(M/'audit/review_packages/host010/data_capabilities.json'))
check('independent_financial_count0',sum(x.get('role')=='as_reported_financial_value' for x in catalog['fields'].values())==0)
ready=read(M/'audit/stage2_current_readiness.json')
old=ready['historical_real_runtime']
check('old_runtime_b1a_only',old['source_commit']=='b1a4041ce98867047294b8f0830292af5d7ec56e' and old['new_candidate_cloud_evidence'] is False)
check('old43_EOF_scope',old['LEAN_source_verification']['eof_normalized_file_count']==43 and old['LEAN_source_verification']['original_source_identity_match'] is False and old['automatic_push_observed'] is False)
check('old_round_closed',old['current_round_closed'] is True)
check('native_new_source_not_deployed',ready['candidate_cloud_deployed'] is False)
result={'static_checks':checks,'logical_checks':len(checks),'unit_methods':0,'developer_records':len(records),'packet_files':len(packet['raw_files']),'no_cloud_calls':True,'financial_evidence':False}
(A/'extra_results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k!='static_checks'}),flush=True)
