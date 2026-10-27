from pathlib import Path
import json,re
R=Path(__file__).parent
def read(rel):return json.loads((R/rel).read_text(encoding='utf-8-sig'))
def count(path,label,methods=None,subcases=None):
    x=read(path);m=x.get('methods',x.get('methods_run',x.get('tests_run',methods)))
    if m is None and 'passed_methods'in x:m=x['passed_methods']+x.get('failed_methods',x.get('failures',0))+x.get('error_methods',x.get('errors',0))
    f=x.get('failed_methods',x.get('failure_records',0));e=x.get('error_methods',x.get('error_records',0));s=x.get('skipped',x.get('skips',0))
    return {'suite':label,'methods':m,'subcases':x.get('subcases',x.get('subtests',subcases)),'passed_methods':m-f-e-s,'failed_methods':f,'errors':e,'skipped':s,'actually_executed':True,'result_file':path}
paths={
 'archived_compatibility':'test_results.json','archived_pearson':'test_results.json','archived_numeric':'test_results.json','archived_atomic':'results.json',
 'previous_adapted_56':'independent_test_results.json','d0_summary':'results.json','d0_compatibility':'results.json',
 'fbe_source':'source_review_results_first.json','fbe_boundary':'secondary_source_results_counted.json','fbe_collection':'verification_results.json',
 '7bf_dates':'first_results.json','7bf_intervals':'candidate_summary.json','e513_admission':'first_results.json','e513_receipts':'first_run_summary.json',
 'be_carriers_corrected':'corrected_run_summary.json','dc_annotations_role_corrected':'role_corrected_summary.json'}
expected=[(12,22),(10,896),(16,84),(19,9),(56,25),(11,716),(8,16),(8,73),(3,3),(19,31),(9,27),(12,75),(24,36),(14,54),(15,80),(12,160)]
original=[]
for (label,filename),(m,n)in zip(paths.items(),expected):
    row=count('runs/'+label+'/'+filename,label,m,n);assert(row['methods'],row['subcases'])==(m,n),row;original.append(row)
assert sum(x['methods']for x in original)==248 and sum(x['subcases']for x in original)==2307
accepted=[dict(x)for x in original]
adapt=count('preflight_agent/e513_adapted_replay/first_results.json','e513_admission_historical_pending_fixture')
assert (adapt['methods'],adapt['subcases'])==(24,36)
accepted[list(paths).index('e513_admission')]=adapt
assert all(x['failed_methods']==x['errors']==x['skipped']==0 for x in accepted)
additional=[]
for path,label,m,n in [
 ('collection_recovery_replay/first_results.json','collection_recovery',12,36),
 ('joint_worker_replay/results/summary.json','joint_worker',9,81),
 ('fraction_replay/results/summary.json','fraction',10,803),
 ('recovery_agent/results_helper_corrected/first_run_summary.json','engineering_recovery',5,46),
 ('preflight_agent/quick_fixture_workspace/admission_agent/quick_first_results.json','historical_quick',7,0),
 ('admission_agent/new_first_results.json','wr16_original',9,4),
 ('admission_agent/new_contract_corrected_results.json','wr18_contract',9,39)]:
    if not (R/path).exists()and label in {'joint_worker','fraction'}:
        found=list((R/path).parent.glob('*summary*.json'));assert len(found)==1,found;path=str(found[0].relative_to(R))
    row=count(path,label,m,n);assert(row['methods'],row['subcases'])==(m,n),row
    assert row['failed_methods']==row['errors']==row['skipped']==0,row;additional.append(row)
repository=read('runs/repository_verify.stdout.txt');assert 'Ran 530 tests'in repository['test_output']and '\nOK\n'in repository['test_output']
result={'reviewed_source_commit':'66ff72ffaaff8c91c008898e6527c91131176c2a',
 'repository':{'methods':530,'passed_methods':530,'failed_methods':0,'errors':0,'skipped':0,'subcases':None,'actually_executed':True,'command':'python -B tools/stages.py verify'},
 'legacy_original_first':original,'legacy_accepted_replay':accepted,'legacy_methods':248,'legacy_subcases':2307,'additional_accepted':additional,
 'method_totals_not_unique':True,'notes':['Method and subcase counts are distinct. Suites overlap; no aggregate unique-test claim.',
 'Raw original56 historical failures remain archived; only the explicitly recognized adapted56 suite was rerun.',
 'Old scripts may retain old commit literals; outer command, current source directory and hashes identify this execution.',
 'e513 and quick historical pending-only fixtures use the unchanged archived12-event ledger, not the new settled13-event authority.',
 'Engineering recovery first attempt omitted helper at its required output path; original results kept; exact helper and test bytes replayed separately.']}
(R/'test_execution_summary.json').write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode())
print(json.dumps({'repository':result['repository'],'legacy_methods':248,'legacy_subcases':2307,'additional':additional},ensure_ascii=False))
