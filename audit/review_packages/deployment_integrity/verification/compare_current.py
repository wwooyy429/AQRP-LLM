from pathlib import Path
import hashlib,json,sys
root=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(root/'cloud'))
from qresearch.engineering_data import source_bytes_sha256
from qresearch.artifacts import content_hash
p=json.loads((Path(__file__).parent/'current_source_projection.json').read_bytes())
a=json.loads((root/'audit/runtime/engineering/admitted-inputs/bfd00f2611fd4496b9498d4597618a8e.json').read_bytes())
manifest=a['payload']['deployment_manifest']
observed={f['filePath']:source_bytes_sha256(f['content'].encode('utf-8')) for f in p['python_files']}
assert len(observed)==len(p['python_files'])
records=[{'path':name,'expected_sha256':expected,'observed_sha256':observed.get(name),'matches':observed.get(name)==expected}
         for name,expected in sorted(manifest.items())]
input_file=next(f for f in p['python_files'] if f['filePath']=='_engineering_task_input.py')
input_hash=hashlib.sha256(input_file['content'].encode('utf-8')).hexdigest()
assert all(x['matches'] for x in records)
assert input_hash==a['deployment']['input_hash']
report={'schema_version':1,'kind':'Actual current read_project Python-source projection versus original frozen manifest',
    'project_id':p['projectId'],'source_carriers_semantically_equal_before_projection':True,
    'original_tool_envelope_not_rewritten_or_archived':True,'notebook_content_persisted':False,
    'expected_manifest_hash':content_hash(manifest),'known_implementation_files':len(records),'all_known_hashes_match':True,
    'separately_bound_input_hash':input_hash,'original_frozen_deployment_hash':a['deployment']['deployment_hash'],
    'records':records,'extra_returned_Python_paths':sorted(set(observed)-set(manifest)-{'_engineering_task_input.py'}),
    'old_backtest_id':'39cafa1e9b11f91b27e396b66d033a6d','old_snapshot_id':38457775,
    'snapshot_id_is_not_used_as_project_id':True,'worker_file_bytes_or_hashes_observed':False,
    'runtime_transform_root_cause_proven':False,'original_runtime_failure_repaired':False,
    'new_configurations':0,'new_Research_executions':0,'new_LEAN_submissions':0,'financial_evidence':False}
(root/'audit/stage2_deployment_root_cause.json').write_bytes((json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
print(json.dumps({k:report[k] for k in ('known_implementation_files','all_known_hashes_match','worker_file_bytes_or_hashes_observed','original_runtime_failure_repaired')}))
