from pathlib import Path
from hashlib import sha256
import json,base64,sys
sys.dont_write_bytecode=True
OUT=Path(__file__).resolve().parent;R=OUT.parent
P=R/'materials/audit/review_packages/wr29'
checks=[]
def check(value,label,detail=None):
    checks.append({'label':label,'passed':bool(value),'detail':detail})
    if not value:raise AssertionError(label)
def original(name):
    p=P/name;raw64=Path(str(p)+'.raw.base64')
    return base64.b64decode(raw64.read_bytes(),validate=False) if raw64.exists() else p.read_bytes()
def read(name):return json.loads(original(name))
index=read('boundary-selected_evidence.json')
for item in index['files']:
    name='boundary-'+Path(item['path']).name
    raw=original(name)
    check(len(raw)==item['bytes'] and sha256(raw).hexdigest()==item['sha256'],'original_auxiliary_raw:'+name)
first=read('boundary-02-round1.json');second=read('boundary-03-round2.json')
checksums={}
for label,value,expected_cases,expected_pass,expected_processes in [('initial',first,84,79,68),('corrected',second,90,89,71)]:
    check(len(value['cases'])==expected_cases,label+'_assertion_count')
    passed=sum(bool(row['passed']) for row in value['cases'])
    check(passed==expected_pass,label+'_passed_count')
    check(len(value['subprocesses'])==expected_processes,label+'_subprocess_count')
    checksums[label]={'assertions':len(value['cases']),'passed':passed,'failed':len(value['cases'])-passed,'subprocesses':len(value['subprocesses']),'failed_labels':[row['label'] for row in value['cases'] if not row['passed']]}
late_first=[row for row in first['subprocesses'] if row['label'] in ('canonical-late-original','module-late-original')]
check(len(late_first)==2,'two_initial_late_original_records')
check(all(not row.get('exception_trace') for row in late_first),'initial_two_exception_trace_absent')
traced=[row for row in second['subprocesses'] if row['label']=='module-late-original']
check(len(traced)==1,'one_corrected_late_original_record')
trace=original('boundary-04-eacces-trace.txt').decode('utf-8')
check('PermissionError' in trace and 'path.open("ab")' in trace and '[Errno 13]' in trace,'exact_captured_append_EACCES_trace')
check(traced[0]['exception_trace'].replace('\r\n','\n')==trace.replace('\r\n','\n'),'trace_matches_corrected_run_record')
summary=read('boundary-19-summary.json')
check(summary['product_commit']=='c2e63ac5f19901bd95e127069b5998452f7f9864','summary_pins_candidate')
check(summary['host_sha256']==sha256((R/'source/tools/followup_host.py').read_bytes()).hexdigest(),'summary_host_raw_SHA_matches_new_Git_source')
check(any('two first-round' in s.lower() and 'not retrospectively' in s for s in summary['limitations']),'summary_retains_untraced_cause_limit')
check(any('stores' in s and 'excluded' in s for s in summary['limitations']),'summary_discloses_missing_original_stores')
result={'kind':'independent_static_raw_and_metadata_audit_not_unit_methods','logical_checks':len(checks),'checks':checks,'first_and_corrected_counts':checksums,'findings':[],
 'executed_developer_original_store_recovery_program':False,'executed_developer_original_response_clone_program':False,
 'reason':'Referenced generated run/stores directories are explicitly excluded from selected archive. Raw metadata is recoverable and checked, but the original private store initial state is unavailable; programs depending on that state were not run.',
 'independent_replacement':'New reviewer-authored Memory fault injections and actual Win32/CLI equivalent private-store append denial and same-response cross-entry recovery are separately actually executed; never substitute them as original historical runs.',
 'unverified':['First-round two untraced exact exceptions and causes.','Underlying cause of developer traced EACCES (sharing/sync/ACL/other) beyond the captured append failure.','No direct access or replay of developer original stores.'],
 'developer_evidence_grade':'developer_archived_private_synthetic_metadata_independently_reparsed_not_independent_execution',
 'source_or_production_writes':0,'external_calls':0}
(OUT/'auxiliary_metadata_verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'logical_checks':len(checks),'counts':checksums,'original_store_programs_executed':False,'findings':[]}))
