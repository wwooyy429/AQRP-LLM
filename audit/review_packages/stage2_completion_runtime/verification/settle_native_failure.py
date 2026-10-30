from pathlib import Path
from unittest.mock import patch
import json,sys,shutil,tempfile,hashlib
root=Path.cwd();scratch=root/'.git/repair-work/stage2-completion';sys.path[:0]=[str(root/'cloud'),str(root/'tools')]
import research,stage2
from qresearch.artifacts import canonical_json,content_hash
attempt='f5d05f5b964b4a1d924e4b70cd207386';packet=root/'audit/tool_observations'/f'{attempt}-research.json';tool=json.loads(packet.read_bytes())
journal=root/'audit/runtime/registry/events.jsonl';before=journal.read_bytes();assert len(before.splitlines())==15
budget=(root/'config/budget.json').read_bytes();protected=json.loads((scratch/'protected_before_execution.json').read_bytes());old_hashes={name:digest for name,digest in protected.items() if name!='config/budget.json' and name!='audit/runtime/registry/events.jsonl'}
with tempfile.TemporaryDirectory(prefix='aqrp-native-error-replay-') as d:
 temp=Path(d);shutil.copytree(root/'audit/runtime',temp/'audit/runtime');(temp/'config').mkdir();(temp/'config/budget.json').write_bytes(budget);(temp/'audit/task_inputs').mkdir();shutil.copyfile(root/'audit/task_inputs'/f'{attempt}.py',temp/'audit/task_inputs'/f'{attempt}.py')
 with patch.object(research,'ROOT',temp),patch.object(stage2,'ROOT',temp):
  reg=research.open_registry();bridge=stage2.bridge_for_attempt(attempt,registry=reg);usage0=reg.snapshot()['usage'];first=stage2.settle_research_result(bridge,attempt,tool);assert first.status=='failed';n1=len((temp/'audit/runtime/registry/events.jsonl').read_bytes().splitlines());assert n1==17
  again=stage2.settle_research_result(bridge,attempt,tool);assert again.status=='failed';n2=len((temp/'audit/runtime/registry/events.jsonl').read_bytes().splitlines());assert n2==17 and reg.snapshot()['usage']==usage0
  before_bad=(temp/'audit/runtime/registry/events.jsonl').read_bytes();bad=json.loads(canonical_json(tool));bad['arguments']['index']=2
  try:stage2.settle_research_result(bridge,attempt,bad)
  except ValueError:pass
  else:raise AssertionError('Mismatched cell accepted')
  assert (temp/'audit/runtime/registry/events.jsonl').read_bytes()==before_bad
  try:bridge._research_result()
  except ValueError:blocked=True
  else:blocked=False
  assert blocked
assert journal.read_bytes()==before and (root/'config/budget.json').read_bytes()==budget
reg=research.open_registry();bridge=stage2.bridge_for_attempt(attempt,registry=reg);usage_before=reg.snapshot()['usage'];result=stage2.settle_research_result(bridge,attempt,tool);assert result.status=='failed';research.export_usage(reg);after=journal.read_bytes();assert after.startswith(before) and len(after.splitlines())==17;assert reg.snapshot()['usage']==usage_before
for name,digest in old_hashes.items():assert hashlib.sha256((root/name).read_bytes()).hexdigest()==digest,name
record=bridge._record(attempt);observed=json.loads(bridge.store.read_bytes(record['error']['evidence_ref']['key']));raw=observed['platform']['raw_receipt'];assert raw['error_output_count']==1 and raw['native_error_representation_count']==2 and raw['traceback_line_count']==9
report={'schema_version':1,'actual_cloud_source_commit':'7fc5ef2e9d2379d29f48d05a1f3cc760000884d6','controller_parser_source_sha256':hashlib.sha256((root/'cloud/qresearch/engineering_receipts.py').read_bytes()).hexdigest(),'controller_repair_was_not_cloud_executed':True,'project_id':38436695,'research_attempt_id':attempt,'configuration_id':record['config_id'],'plan_hash':'4c67e2b61b6d1955a7f94948756aa7277b6f076adfaab5e1fbc14470ec599da7','actual_tool_observation_raw_sha256':hashlib.sha256(packet.read_bytes()).hexdigest(),'native_response_sha256':raw['response_sha256'],'actual_MCP_isError':False,'native_error_class':'CollectionError','native_error_message':'Historical source iteration failed; unfinished intent retained','underlying_source_cause_known':False,'logical_failure_tasks':1,'MCP_error_representations':2,'traceback_line_count':9,'cell_source_sha256':'33c34e9fbbf958f6518966cee185e947d96a4c610b7c0a942d206dec252e3340','input_sha256':'03dd4dcc9cf99c44496236b70370cb8785105d05523cd098798408bfa17c917b','original_13event_prefix_unchanged':True,'real_journal_events_before_call':15,'real_journal_events_after_settlement':17,'isolated_replay_events':[15,17,17],'isolated_mismatched_cell_rejected_without_writes':True,'isolated_LEAN_dependency_blocked':True,'actual_registry_status':'failed','completion_evidence_ref':record['error']['evidence_ref'],'no_success_result_created':not bridge.store.exists(record['result_key']),'new_Research_tool_calls':1,'new_LEAN_submissions':0,'global_usage':{'configurations':7,'research':10,'lean':1},'allocation':'reserve','engineering_used':{'configurations':2,'research':2,'lean':1},'engineering_stop_reached':True,'automatic_retries':0,'raw_market_values_persisted_locally':False,'final_test_enabled':False,'financial_evidence':False}
(root/'audit/stage2_completion_reconciliation.json').write_bytes((json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode());print(json.dumps({k:report[k] for k in ('actual_registry_status','real_journal_events_after_settlement','isolated_replay_events','no_success_result_created','new_Research_tool_calls','new_LEAN_submissions','engineering_stop_reached')}))
