from pathlib import Path
import json,re
R=Path(__file__).parent
def load(p):return json.loads((R/p).read_text(encoding='utf-8-sig'))
def row(path,label,m,n=None):
    d=load(path);methods=d.get('methods',d.get('methods_run',d.get('tests_run',m)));assert methods==m
    def number(keys,default=0):
        for k in keys:
            if k in d:return len(d[k])if isinstance(d[k],list)else d[k]
        return default
    failed=number(['failed_methods','failure_records','failures']);errors=number(['error_methods','error_records','errors']);skips=number(['skipped','skips'])
    sub=d.get('subcases',d.get('subtests',n));assert n is None or sub==n,(label,sub)
    return {'suite':label,'methods':methods,'passed':methods-failed-errors-skips,'failed':failed,'errors':errors,'skipped':skips,'subcases':sub,'actually_executed':True,'result_file':path}
paths=[('archived_compatibility','test_results.json',12,22),('archived_pearson','test_results.json',10,896),('archived_numeric','test_results.json',16,84),('archived_atomic','results.json',19,9),('previous_adapted_56','independent_test_results.json',56,25),('d0_summary','results.json',11,716),('d0_compatibility','results.json',8,16),('fbe_source','source_review_results_first.json',8,73),('fbe_boundary','secondary_source_results_counted.json',3,3),('fbe_collection','verification_results.json',19,31),('7bf_dates','first_results.json',9,27),('7bf_intervals','candidate_summary.json',12,75),('e513_admission','first_results.json',24,36),('e513_receipts','first_run_summary.json',14,54),('be_carriers_corrected','corrected_run_summary.json',15,80),('dc_annotations_role_corrected','role_corrected_summary.json',12,160)]
legacy=[row('runs/'+a+'/'+b,a,m,n)for a,b,m,n in paths];assert sum(x['methods']for x in legacy)==248 and sum(x['subcases']for x in legacy)==2307
more=[row(p,label,m,n)for p,label,m,n in[
 ('collection_historical_fixture/collection_recovery_replay/first_results.json','Collection historical13-event fixture',12,36),
 ('joint_worker_replay/historical_budget_results/first_run_summary.json','joint worker historical budget fixture',9,81),
 ('fraction_replay/results/first_run_summary.json','fractional grammar',10,803),('recovery_agent/results/first_run_summary.json','engineering recovery',5,46),
 ('admission_agent/new_first_results.json','WR16 admission',9,4),('admission_agent/new_contract_corrected_results.json','WR18 contract',9,39),
 ('entry_agent/pure_corrected_results.json','old preflight pure',7,42),('entry_agent/cli_first_results.json','old preflight CLI',4,24),('entry_agent/preflight_cli_first_results.json','old readback CLI',1,4),
 ('entry_agent/worker_identity_first_results.json','new worker identity',6,51)]]
assert all(x['failed']==x['errors']==x['skipped']==0 for x in legacy+more)
n=load('native_agent/report.json');cert=load('cert_agent/first_results.json')
for key,label in [('new_first_run','new Research native failure')]:
    d=n[key];more.append({'suite':label,'methods':d['methods'],'passed':d['passed_methods'],'failed':d['failure_records'],'errors':d['error_records'],'skipped':d['skipped'],'subcases':d['subcases'],'actually_executed':True})
more.append({'suite':'old native compatibility','methods':9,'passed':9,'failed':0,'errors':0,'skipped':0,'subcases':90,'actually_executed':True})
more.append({'suite':'new data conformance audit','methods':cert['methods'],'passed':cert['passed_methods'],'failed':cert['failed_methods'],'errors':cert['error_methods'],'skipped':0,'subcases':None,'scenario_checks':cert['scenario_checks'],'failure_records':cert['failure_records'],'actually_executed':True})
repo=load('runs/repository_verify.stdout.txt');assert'Ran 612 tests'in repo['test_output']and'\nOK\n'in repo['test_output']
result={'reviewed_source_commit':'deb85d9f27441b275ab8b108f0232ecd2707a1e8','repository':{'methods':612,'passed':612,'failed':0,'errors':0,'skipped':0,'subcases':None,'actually_executed':True},'legacy_16_suites':legacy,'legacy_methods':248,'legacy_subcases':2307,'additional_suites':more,'counts_not_unique':True,'first_nonproduct_failures':[
 {'suite':'Collection original','methods_run':0,'setup_errors':1,'original_report_passed_methods':-1,'accepted_passed_methods':0,'cause':'Original harness copied authoritative17 events, already2 engineering configurations. Setup correctly refused. Historical13-event fixture replay12/36 passes; original negative passed-count is harness bookkeeping and not accepted.'},
 {'suite':'joint worker original','methods':9,'passed':8,'failed':1,'subcases':81,'cause':'Old fixture expected cumulativeResearch10 from9 baseline; current10+1 becomes11. Original assertions/script unchanged; only independent helper BUDGET uses archived9 baseline in separate replay9/81.'},
 {'suite':'static source reader','cause':'First reader treated public snapshot attempts list as dict. Original script/trace preserved; corrected reader227/227 twice, not counted twice.'}],
 'MREs':{'WR20_root_exit':1,'WR21_first_exit':1,'WR21_root_exit':1,'all_expected_failure_exits':True,'WR21_root_cli':17,'WR21_downstream_synthetic_CLI':1,'original_entry_CLI':17,'original_message14_corrected_by_saved_commands':True},
 'manual_probes':{'old_native':8,'new_entry_controls':3,'entry_actual_cli':21,'entry_controls_passed':True},'notes':['Recognized adapted56 and e513 historical pending fixture are explicit; raw historical failure outputs remain preserved.','Method, scenario, subcase, CLI, worker and static counts are separate; no aggregate unique count.','Only saved entry-agent results are counted; its uncompleted expansion is not claimed. Root independent MRE and dispatch controls cover the conclusions.']}
(R/'test_execution_summary.json').write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode());print(json.dumps({'repository':612,'legacy_methods':248,'legacy_subcases':2307,'additional':len(more),'new_defects':['WR20','WR21']},ensure_ascii=False))
