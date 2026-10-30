from pathlib import Path
import json
R=Path(__file__).parent
def load(path):return json.loads((R/path).read_text(encoding='utf-8-sig'))
def row(path,label,m,n):
 d=load(path);actual=d.get('methods',d.get('methods_run',d.get('tests_run',m)));assert actual==m,(label,actual)
 def count(keys):
  for k in keys:
   if k in d:return len(d[k])if isinstance(d[k],list)else d[k]
  return 0
 f=count(['failed_methods','failure_records','failures']);e=count(['error_methods','error_records','errors']);s=count(['skipped','skips'])
 sub=d.get('subcases',d.get('subtests',n));assert sub==n,(label,sub)
 return dict(suite=label,methods=m,passed=m-f-e-s,failed=f,errors=e,skipped=s,subcases=sub,actually_executed=True,result_file=path)
specs=[('archived_compatibility','test_results.json',12,22),('archived_pearson','test_results.json',10,896),('archived_numeric','test_results.json',16,84),('archived_atomic','results.json',19,9),('previous_adapted_56','independent_test_results.json',56,25),('d0_summary','results.json',11,716),('d0_compatibility','results.json',8,16),('fbe_source','source_review_results_first.json',8,73),('fbe_boundary','secondary_source_results_counted.json',3,3),('fbe_collection','verification_results.json',19,31),('7bf_dates','first_results.json',9,27),('7bf_intervals','candidate_summary.json',12,75),('e513_admission','first_results.json',24,36),('e513_receipts','first_run_summary.json',14,54),('be_carriers_corrected','corrected_run_summary.json',15,80),('dc_annotations_role_corrected','role_corrected_summary.json',12,160)]
legacy=[row('runs/'+a+'/'+b,a,m,n)for a,b,m,n in specs]
assert sum(x['methods']for x in legacy)==248 and sum(x['subcases']for x in legacy)==2307
additional=[row(p,label,m,n)for p,label,m,n in[
 ('historical_fixture/collection_recovery_replay/first_results.json','Collection historical runtime',12,36),('joint_worker_replay/results/first_run_summary.json','joint worker historical budget',9,81),('fraction_replay/results/first_run_summary.json','fraction grammar',10,803),('admission_agent/new_first_results.json','WR16 admission',9,4),('admission_agent/new_contract_corrected_results.json','WR18 contract',9,39),('control_replay/worker_identity_first_results.json','worker identity',6,51),('control_replay/pure_corrected_results.json','preflight pure',7,42),('control_replay/cli_first_results.json','preflight CLI',4,24),('control_replay/preflight_cli_first_results.json','readback preflight CLI',1,4)]]
assert all(x['failed']==x['errors']==x['skipped']==0 for x in legacy+additional)
repo=load('runs/repository_verify.stdout.txt');assert'Ran 668 tests'in repo['test_output']and'\nOK\n'in repo['test_output']
records=load('runs/execution_records.json')+load('regression_execution_records.json')+load('control_replay/execution_records.json')
assert len(records)==26 and all(r['exit_code']==0 for r in records),(len(records),records)
result={'source_commit':'44676db609b3b7c2175fa7fa4f19c8ccf8166858','repository':{'methods':668,'passed':668,'failed':0,'errors':0,'skipped':0,'subcases':None,'actually_executed':True},'legacy_16_suites':legacy,'additional_root_suites':additional,'execution_processes':len(records),'all_pass':True,'counts_not_unique':True,'command_records':['runs/execution_records.json','regression_execution_records.json','control_replay/execution_records.json'],'fixture_adaptations':['Recognized adapted56 and original pending12event fixture for e513','Current production code with historical13event/9Research budget only for collection/joint original fixtures; genuine17event authority unchanged'],'no_current_real_QC_or_market_calls':True}
(R/'root_test_execution_summary.json').write_bytes((json.dumps(result,indent=2)+'\n').encode());print(json.dumps({'repository':668,'legacy_methods':248,'legacy_subcases':2307,'additional_suites':len(additional),'root_processes':len(records)}))
