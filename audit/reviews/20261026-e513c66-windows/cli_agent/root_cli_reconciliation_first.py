"""Independent temporary-workspace CLI settlement probe; no real SDK or calls."""
from pathlib import Path
from types import SimpleNamespace as NS
from uuid import uuid4
import json,os,shutil,socket,sys
import pandas as pd

R=Path(__file__).parent
case=sys.argv[1]
if case not in {'pointer','catalog'}:raise ValueError(case)
work=R/'cli_agent'/('case-'+case+'-'+uuid4().hex);work.parent.mkdir(exist_ok=True)
shutil.copytree(R/'source',work)
sys.path.insert(0,str(work/'tools'));sys.path.insert(0,str(work/'cloud'))
from qresearch.collection_execution import run_collection_task,stdout_marker,collection_research_observation
from qresearch.artifacts import MemoryArtifactStore
import collection_task_cli as cli
import stage2_collection as entry

def deny(*a,**k):raise AssertionError('Offline CLI settlement probe forbids networking')
socket.socket.connect=deny
def command(name,**kw):
    args=NS(command=name,task_file=None,projects_file=None,tool_file=None,attempt=None,allocation='normal',retry_of=None,reason=None)
    for k,v in kw.items():setattr(args,k,v)
    return cli.execute_metadata_command(args,field_catalog=entry.catalog())

def raw_task(name,project):
    return {'schema_version':1,'task_kind':'historical_collection','scope':'engineering','plan_id':name,'project_id':project,
      'source_manifest_hash':None,'deployment_hash':None,'field_catalog':None,'report_namespace':'independent-cli/'+name,'max_retries':1,
      'collection_plan':{'schema_version':1,'plan_id':'independent-inner-'+name,'scope':'engineering','source':'quantconnect_fundamental_universe',
        'data_version':'synthetic-cli-settlement','start':'2018-01-03T00:00:00-05:00','end_exclusive':'2018-01-04T00:00:00-05:00',
        'timezone':'America/New_York','fields':['dollar_volume'],'calendar_days_per_request':1,'max_batch_records':2,
        'max_records_per_window':10,'source_manifest_hash':'0'*64}}

listing={'success':True,'projects':[{'projectId':38437839},{'projectId':38433336}]}
old_catalog=entry.catalog()
cli.freeze_task(raw_task('first',38437839),listing,field_catalog=old_catalog)
registered=command('register-task');claimed=command('claim-task');attempt_id=claimed['attempt_id']
assert claimed['should_execute']
admission=command('prepare-task',attempt=attempt_id)
bridge_first=cli.current_bridge(field_catalog=old_catalog)
class SyntheticSource:
    def fetch(self,start,end,catalog):
        yield {'sid':'SYNTHETIC-CLI-SID','snapshot_at':pd.Timestamp('2018-01-03 12:00',tz='America/New_York').isoformat(),
               'values':{'dollar_volume':0}}
wrapper=run_collection_task(admission['payload'],field_catalog=old_catalog,source=SyntheticSource(),store=MemoryArtifactStore(),synthetic=True,source_root=work/'cloud')
marker=stdout_marker(wrapper,payload=admission['payload'],field_catalog=old_catalog)
native={'tool_name':'mcp__quantconnect__jupyter_execute_cell','arguments':{'projectId':38437839,'index':2},
        'result':{'isError':False,'structuredContent':{'status':'completed','outputs':[{'output_type':'stream','name':'stdout','text':marker+'\n'}]}}}
tool_path=work/'synthetic_delivered_tool.json';tool_path.write_text(json.dumps(native),encoding='utf-8')
before=bridge_first.registry.snapshot()
if case=='pointer':
    cli.freeze_task(raw_task('second',38433336),listing,field_catalog=old_catalog)
else:
    path=work/'config/source_catalog.json';catalog=json.loads(path.read_text(encoding='utf-8'))
    catalog['fields']['dollar_volume']['unit']='independent-new-unit'
    path.write_text(json.dumps(catalog),encoding='utf-8')
try:
    observed=command('research-result',attempt=attempt_id,tool_file=tool_path)
    error=None
except Exception as exc:
    observed=None;error={'type':type(exc).__name__,'message':str(exc)}
after=bridge_first.registry.snapshot()
pending_record=after['attempts'][attempt_id]
# Positive control: the identical delivered observation validates and settles
# when the original frozen plan/catalog are used, with no new execution debit.
parsed=collection_research_observation(admission['payload'],admission['deployment'],native,field_catalog=old_catalog)
bridge_first.record_submission(attempt_id,parsed['submission'])
settled=bridge_first.consume_completion(attempt_id,completion_source=lambda _:parsed['completion'])
final=bridge_first.registry.snapshot()
result={'actual_source_commit':'e513c66e5965133fbe83fb0ab987eae853f96260','case':case,'workspace':str(work),
    'attempt_id':attempt_id,'original_plan_hash':admission['payload']['identity']['plan_hash'],
    'CLI_result':observed,'CLI_error':error,'status_after_CLI':pending_record['status'],
    'same_receipt_original_frozen_context_status':settled.status,
    'usage_before':before['usage'],'usage_after_CLI':after['usage'],'usage_after_control':final['usage'],
    'real_SDK_executed':False,'real_market_calls':0,'authoritative_ledger_touched':False}
(R/'cli_agent'/('result-'+case+'.json')).write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
assert error is None,'Delivered old-attempt evidence must remain reconcilable after local plan/catalog change'
