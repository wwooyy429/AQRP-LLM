from pathlib import Path
import json,re
R=Path(__file__).parent
paths={
'archived_compatibility':'test_results.json','archived_pearson':'test_results.json','archived_numeric':'test_results.json',
'archived_atomic':'results.json','previous_adapted_56':'independent_test_results.json','d0_summary':'results.json',
'd0_compatibility':'results.json','fbe_source':'source_review_results_first.json','fbe_boundary':'secondary_source_results_counted.json',
'fbe_collection':'verification_results.json','7bf_dates':'first_results.json','7bf_intervals':'candidate_summary.json',
'e513_admission':'first_results.json','e513_receipts':'first_run_summary.json','be_carriers_corrected':'corrected_run_summary.json',
'dc_annotations_role_corrected':'role_corrected_summary.json'}
records=json.loads((R/'runs/execution_records.json').read_text())
out=[]
for rec in records:
    label=rec['label'];j=R/'runs'/label/paths[label] if label in paths else None
    if label=='repository_verify':
        result=json.loads((R/'runs/repository_verify.stdout.txt').read_text())
        methods=int(re.search(r'Ran (\d+) tests',result['test_output']).group(1));subcases=None
        failures=0 if rec['exit_code']==0 else None;errors=0 if rec['exit_code']==0 else None;skipped=0 if rec['exit_code']==0 and 'skipped=' not in result['test_output'] else None
    else:
        result=json.loads(j.read_text(encoding='utf-8-sig'))
        methods=result.get('methods',result.get('methods_run',result.get('tests_run',None)))
        if methods is None and label=='previous_adapted_56':methods=result['passed_methods']+result['failures']+result['errors']
        assert isinstance(methods,int), (label,result.keys())
        subcases=result.get('subcases',result.get('subtests',None))
        failures=result.get('failed_methods',0 if rec['exit_code']==0 else None)
        errors=result.get('error_methods',0 if rec['exit_code']==0 else None)
        skipped=result.get('skipped',result.get('skips',0 if rec['exit_code']==0 else None))
    assert failures==errors==skipped==0, (label,result)
    out.append(dict(rec,methods=methods,passed=methods,failed=failures,errors=errors,skipped=skipped,subcases=subcases,
                    result_file=str(j.relative_to(R)) if j else 'runs/repository_source/audit/stage_verification.json',actually_executed=True))
summary={'reviewed_source_commit':'8f7236ecbafcb514f07a6af4150a5afdbc1fd474','suites':out,
 'repository_methods':out[0]['methods'],'archived_regression_methods':sum(x['methods'] for x in out[1:]),
 'archived_subcases':sum(x['subcases'] for x in out[1:] if x['subcases'] is not None),
 'scope':'方法与子例分列；跨套件有重复，不声称均为独有测试。原raw56历史异常未被改写；只重放认可adapted版本。'}
(R/'regression_summary.json').write_bytes(json.dumps(summary,ensure_ascii=False,indent=2).encode())
print(json.dumps({k:v for k,v in summary.items() if k!='suites'},ensure_ascii=False))
