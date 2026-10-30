from pathlib import Path
import sys,json,hashlib
from copy import deepcopy
root=Path.cwd();sys.path[:0]=[str(root/'cloud'),str(root/'tests')]
from qresearch.artifacts import canonical_json,content_hash
import qresearch.data_certification as cert
from test_data_certification import DataCertificationTests,SID,RANKED
out=root/'.git/repair-work/stage2-completion/peer-certification'
DataCertificationTests.setUpClass()
def fixture():
 x=DataCertificationTests('test_known_answer_201_candidates_21_sessions_200_members_and_no_approval');x.setUp();return x
c=fixture();observed=c.audit()
def manifest(report):
 m={name:report[name] for name in ('source_manifest_hash','ingestion_namespace','data_version_hash','financial_catalog_hash')};m.update(schema_version=1,start=report['scope_start'],end_exclusive=report['scope_end_exclusive'],partitions=[{'plan_hash':report['plan_hash'],'start':report['scope_start'],'end_exclusive':report['scope_end_exclusive'],'report_ref':report['report_ref']}]);return m
def store_report(c,body):
 raw=canonical_json(body);digest=hashlib.sha256(raw).hexdigest();ref={'key':'data-certification/v1/reports/'+digest+'.json','sha256':digest};c.store.write_once(ref['key'],raw);return ref
results=[]
for mutation in ('zero_counts_all_checks_true','empty_refs_all_checks_true'):
 body={k:deepcopy(v) for k,v in observed.items() if k!='report_ref'}
 if mutation=='zero_counts_all_checks_true':body['counts']={k:0 for k in body['counts']}
 else:body['evidence_refs']={k:[] for k in body['evidence_refs']}
 m=manifest(observed);m['partitions'][0]['report_ref']=store_report(c,body)
 try:
  result=cert.summarize_certification_scope(c.store,m,content_hash(m),calendar=c.calendar,synthetic=True)
  results.append({'probe':mutation,'rejected':False,'status':result['status'],'formation_count':result['counts']['formation_count'],'research_certified':result['research_certified']})
 except cert.DataCertificationError:results.append({'probe':mutation,'rejected':True})
c=fixture();missing=c.calendar.sessions[0].isoformat();c.change_source('liquidity',[r for r in c.liquid if not(r['sid']==SID[-1] and r['session']==missing)])
members=deepcopy(c.table_rows['membership']);members[0]['sids']=list(reversed(SID[:-1]));c.change_table('membership',members)
prices=deepcopy(c.table_rows['prices']);old=next(r for r in prices if r['sid']==SID[-1]);prices.remove(old);old['sid']=SID[0];prices.append(old);c.change_table('prices',prices)
result=c.audit();results.append({'probe':'missing_known_top_candidate_session_with_rank201_substitution','status':result['status'],'observed_member_cells':result['counts']['observed_member_cells'],'unavailable_liquidity_formations':result['counts']['unavailable_liquidity_formations'],'research_certified':result['research_certified']})
(out/'after_findings.json').write_bytes((json.dumps({'source_raw_sha256':hashlib.sha256((root/'cloud/qresearch/data_certification.py').read_bytes()).hexdigest(),'results':results,'QC_calls':0,'real_ledger_writes':0},indent=2)+'\n').encode());print(json.dumps(results))

assert all(row["rejected"] for row in results[:2])
assert results[2]["status"] == "insufficient_evidence"
