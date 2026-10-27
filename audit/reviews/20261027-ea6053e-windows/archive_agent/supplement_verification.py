from pathlib import Path
import hashlib,io,json,re,sys,tarfile,traceback
R=Path(__file__).resolve().parent;S=R.parent/'source'
prefix='audit/reviews/20261027-deb85d9-windows/'
checks=[]
def sha(b):return hashlib.sha256(b).hexdigest()
def norm(b):return b.decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n').encode()
def canonical(v):return json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
def read(p):return json.loads((S/p).read_bytes())
def check(name,ok,detail=None):checks.append({'name':name,'passed':bool(ok),'detail':detail})
def main():
    sys.path.insert(0,str(S/'cloud'))
    from qresearch.artifacts import MemoryArtifactStore
    from qresearch.registry import Registry
    store=MemoryArtifactStore()
    original={p.relative_to(S/'audit/runtime').as_posix():p.read_bytes() for p in (S/'audit/runtime').rglob('*') if p.is_file()}
    for key,b in original.items():store.write_once(key,b)
    registry=Registry(store,read('audit/runtime/registry/baseline.json'));snap=registry.snapshot()
    independent=json.loads((R/'report.json').read_bytes())['budget_replay']
    check('registry_in_memory_snapshot_matches_independent_replay',snap['usage']==independent['usage'],{'usage':snap['usage']})
    check('registry_replay_memory_only_no_journal_change',store.read_bytes('registry/events.jsonl')==original['registry/events.jsonl'])
    with tarfile.open(fileobj=io.BytesIO((R/'executed_git_archive.stdout').read_bytes())) as t:
        actual={m.name:t.extractfile(m).read() for m in t.getmembers() if m.isfile()}
    attempt='f5d05f5b964b4a1d924e4b70cd207386';admission=read('audit/runtime/engineering/admitted-inputs/'+attempt+'.json')
    actual_deploy={p[6:]:sha(norm(b)) for p,b in actual.items() if p.startswith('cloud/') and p.endswith('.py')}
    actual_deploy_hash=sha(canonical(actual_deploy))
    check('actual7fc31_deployment_matches_original_admission',len(actual_deploy)==31 and actual_deploy_hash==admission['deployment']['deployment_hash'],{'hash':actual_deploy_hash,'deployment':admission['deployment']})
    inputraw=(S/'audit/task_inputs'/ (attempt+'.py')).read_bytes()
    check('actual_original_input_raw_hash_matches_original_admission',sha(inputraw)==admission['deployment']['input_hash'],{'hash':sha(inputraw)})
    archived=read(prefix+'qc_python_source_read.json');rows=[]
    for record in archived['results']:
        native=record['value'];value=native['structuredContent'];texts=[json.loads(x['text']) for x in native.get('content',[]) if x.get('type')=='text']
        check('historical_QC_carriers:'+record['file'],record['status']=='fulfilled' and not native.get('isError',False) and all(v==value for v in texts))
        path=record['file'];raw=value['content'].encode();reference=inputraw if path=='_engineering_task_input.py' else actual['cloud/'+path]
        rows.append({'path':path,'raw_sha256':sha(raw),'matches7fc_or_original_input':raw==reference,'matches_current_candidate':raw==(S/'cloud'/path).read_bytes() if path!='_engineering_task_input.py' else None})
    check('historical_archived32_source_readback_reparsed_no_current_QC',len(rows)==32 and all(x['matches7fc_or_original_input'] for x in rows),{'readback_files':len(rows),'current_matches':sum(x['matches_current_candidate'] is True for x in rows)})
    cell=read(prefix+'qc_read_cell_source.json')['structuredContent'];cellbytes=''.join(cell['source']).encode()
    check('historical_archived_cell_source_hash',cell['cellType']=='code' and sha(cellbytes)=='33c34e9fbbf958f6518966cee185e947d96a4c610b7c0a942d206dec252e3340',{'raw_sha256':sha(cellbytes)})
    package='audit/review_packages/wr20_wr21/'
    dev=read(package+'developer_verification.json');output=read(package+'verification/final_verify.stdout')
    check('developer630_stdout_stage_manifest_claims_consistent',output['source_hash']==dev['source_manifest_hash'] and output['local_tests_passed'] is True and 'Ran 630 tests in 99.393s' in output['test_output'])
    provenance=[]
    for folder in ('wr20','wr21'):
        for p in sorted((S/package/folder).glob('*execution.json')):
            d=json.loads(p.read_bytes());stdout=p.with_name(p.name.replace('_execution.json','.stdout'));stderr=p.with_name(p.name.replace('_execution.json','.stderr'))
            if p.name in ('fixed_dedicated_execution.json',):stdout=p.with_name('fixed_dedicated.stdout');stderr=p.with_name('fixed_dedicated.stderr')
            b=stderr.read_bytes() if stderr.exists() else b''
            counts=re.findall(r'Ran (\d+) tests?',b.decode('utf-8','replace'))
            provenance.append({'path':p.relative_to(S).as_posix(),'exit_code':d.get('exit_code'),'reported_methods':d.get('methods'),'stderr_Ran':counts,'stderr_present':stderr.exists(),'stdout_present':stdout.exists(),'evidence_class':'developer_archived_outputs_not_current_independent_tests'})
    # Source hash provenance in the saved developer original-MRE and compatibility executions.
    devhashes=read(package+'wr21/independent_mre_execution.json')['current_production_file_raw_sha256']
    check('developer_current_MRE_source_raw_fingerprints',all(sha((S/p).read_bytes())==h for p,h in devhashes.items()),devhashes)
    original_mre=read(package+'wr21/independent_mre_execution.json')['original_MRE_scripts_raw_sha256']
    check('developer_original_MRE_script_fingerprints',all(sha((S/(prefix+'wr21_confirmation/'+p)).read_bytes())==h for p,h in original_mre.items()),original_mre)
    wr20=read(package+'wr20/summary.json')
    check('developer_WR20_current_source_raw_fingerprints',all(sha((S/p).read_bytes())==h for p,h in wr20['production_raw_sha256'].items()))
    check('developer_first_failures_preserved_and_not_hidden',(S/package/'wr20/targeted_first.stderr').is_file() and (S/package/'wr21/baseline.stderr').is_file() and 'ArtifactConflict' in (S/package/'wr20/targeted_first.stderr').read_text(encoding='utf-8') and 'TypeError' in (S/package/'wr21/baseline.stderr').read_text(encoding='utf-8') and any('missing new interface' in s for s in dev['notes']))
    check('source_read_only_supplement_no_runtime_original_write',all((S/'audit/runtime'/p).read_bytes()==b for p,b in original.items()))
    metadata_observation={'severity':'P3/nonblocking_documentation_observation','number_not_assigned':'root coordinates whether to assign WR-22','source_commit':'ea6053e3e9ef4be17db246daf18a4cf9b2e5be58',
      'file':'audit/stage2_current_readiness.json','lines':[124,242,264],
      'trigger':'Read the current readiness as the ea6053e WR20/WR21 repair metadata.',
      'actual':'source_configuration_budget_changed_scope at line242 still describes one new engineering configuration and Research precharge; source_changed_this_round124-134 includes four unchanged files and omits changed/new test files; read_or_polled_this_turn_scope264 still describes previous diagnostic platform reads.',
      'expected':'Put previous-round descriptions under an explicit historical SHA or update current-round descriptions to zero real admission/reads and actual deb85d9..ea6053e changes.',
      'impact':'Scope attribution ambiguity only. Current hashes, true ledger, zero-count fields, unaccepted status and not-cloud-deployed markers are correct; no evidence of actual new dispatch or quota change.',
      'contradictory_correct_lines':[84,92,237,261,262],
      'reproduction':'git diff --name-only deb85d9f27441b275ab8b108f0232ecd2707a1e8 ea6053e3e9ef4be17db246daf18a4cf9b2e5be58; compare listed fields and unchanged journal SHA.',
      'suggested_regression':'Static metadata consistency check should require an explicit historical scope when current new_configuration_count/new_Research_execution_count are zero.'}
    result={'reviewed_source_commit':'ea6053e3e9ef4be17db246daf18a4cf9b2e5be58','checks':checks,'checks_passed':sum(x['passed'] for x in checks),'static_byte_metadata_checks':len(checks),'historical_cloud_rows':rows,'developer_output_provenance':provenance,'metadata_observation':metadata_observation,'independent_product_test_methods':0,'current_QC_calls':0,'current_authoritative_registry_writes':0,'financial_evidence':False}
    (R/'supplement_report.json').write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode())
    print(json.dumps({k:v for k,v in result.items() if k not in ('checks','historical_cloud_rows','developer_output_provenance','metadata_observation')},ensure_ascii=False))
    print(json.dumps([x for x in checks if not x['passed']],ensure_ascii=False))
    return 0 if all(x['passed'] for x in checks) else 1
if __name__=='__main__':
    try:sys.exit(main())
    except Exception:
        (R/'supplement_first_reviewer_error.txt').write_text(traceback.format_exc(),encoding='utf-8')
        raise
