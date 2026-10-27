from pathlib import Path
import hashlib
import json
import subprocess

root=Path(__file__).resolve().parents[3]
current='268f420e9d066e7e7859566a65c0ce65523bec82'
old='75f24629d3b7f94ff3aa906c3ce8a2b8b9a8d3c4'
snapshot=json.loads((Path(__file__).parent/'cloud_source_observation.json').read_text(encoding='utf-8'))
def blob(commit,path):return subprocess.check_output(['git','show',commit+':'+path],cwd=root)
def norm(raw):return raw.decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n').rstrip('\n').encode('utf-8')+b'\n'
def digest(raw):return hashlib.sha256(raw).hexdigest()
deployment=json.loads(blob(old,'audit/deployment.json'))['source_files']
old_names=set(deployment)
source={x['filePath']:x['content'].encode('utf-8') for x in snapshot['files']}
assert len(source)==len(snapshot['files'])
paths=subprocess.check_output(['git','ls-tree','-r','--name-only',current,'cloud'],cwd=root).decode('utf-8').splitlines()
candidate={x[len('cloud/'):]:digest(norm(blob(current,x))) for x in paths if x.endswith('.py')}
records=[]
for name,raw in sorted(source.items()):
    reference_commit=current if name=='_engineering_task_input.py' else old
    reference_path='audit/task_inputs/bfd00f2611fd4496b9498d4597618a8e.py' if name=='_engineering_task_input.py' else 'cloud/'+name
    expected=blob(reference_commit,reference_path)
    records.append({'path':name,'UTF8_sha256':digest(raw),'normalized_sha256':digest(norm(raw)),
        'reference_commit':reference_commit,'reference_path':reference_path,
        'raw_equals_bound_Git_reference':raw==expected,'normalized_equals_bound_Git_reference':norm(raw)==norm(expected)})
same=sorted(k for k in candidate.keys() & source.keys() if candidate[k]==digest(norm(source[k])))
different=sorted(k for k in candidate.keys() & source.keys() if candidate[k]!=digest(norm(source[k])))
outside=sorted(candidate.keys()-source.keys())
report={'schema_version':1,'purpose':'read_only_source_preflight_not_runtime_or_inventory_certification',
    'observation_date':'2026-10-27','project_id':snapshot['projectId'],
    'tool':'mcp__quantconnect__read_project','observation_source_code_not_committed':True,
    'original_notebook_content_not_captured':True,'listed_excluded_files':snapshot['excluded_file_paths'],
    'read_python_files':len(source),'known_old_implementation_paths':len(old_names),
    'all_known_old_implementation_paths_returned':old_names <= source.keys(),
    'all_returned_python_normalized_equal_bound_Git_reference':all(x['normalized_equals_bound_Git_reference'] for x in records),
    'known_source_commit':old,'old_input_attempt':'bfd00f2611fd4496b9498d4597618a8e',
    'source_comparisons':records,
    'separate_fixed_candidate_comparison':{'candidate_commit':current,'candidate_paths':len(candidate),
        'same_normalized_paths':same,'different_normalized_paths':different,
        'paths_not_in_this_returned_reference':outside,
        'scope':'268f candidate versus this returned file reference; outside reference does not certify cloud absence'},
    'full_cloud_inventory_certified':False,'backtest_status_results_or_logs_requested':False,
    'old_backtest_terminal_confirmed':False,'cloud_writes':0,'new_real_executions':0,
    'budget_usage':{'configurations':6,'research':9,'lean':1},'final_test_enabled':False,'financial_evidence':False}
(root/'audit/stage2_next_preflight.json').write_bytes((json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
print(json.dumps({k:report[k] for k in ('read_python_files','known_old_implementation_paths','all_known_old_implementation_paths_returned','all_returned_python_normalized_equal_bound_Git_reference','old_backtest_terminal_confirmed')}))
