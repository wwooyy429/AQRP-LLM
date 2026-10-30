"""Full synthetic worker→native→Registry proof for nested TextContent annotations."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import socket
import sys
import tempfile

p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--out',required=True)
arg=p.parse_args();ROOT=Path(arg.source).resolve();OUT=Path(arg.out).resolve()
sys.path.insert(0,str(ROOT/'cloud'))
from qresearch.artifacts import MemoryArtifactStore,canonical_json,content_hash
from qresearch.registry import Registry
from qresearch.collection_tasks import CollectionTaskPlan,CollectionTaskBridge
from qresearch.collection_execution import run_collection_task,stdout_marker,collection_research_observation
def forbidden(*a,**kw):raise AssertionError('network prohibited')
socket.socket=forbidden
CAT={'dollar_volume':{'kind':'number','role':'independent_synthetic','unit':'USD','period_accessor':None}}
BUDGET=json.loads((ROOT/'config/budget.json').read_text(encoding='utf-8'))
SECRET='INDEPENDENT-NESTED-ANNOTATION-SYNTHETIC-ROW';ROWS=[{'sid':SECRET,'dollar_volume':123456.75}]
cases=[('no_annotation_control','content_wrapper',None,True),
    ('standard_annotation_control','content_wrapper',{'audience':['assistant'],'priority':0.25,'lastModified':'2026-10-26T00:00:00Z'},True),
    ('hidden_rows_in_content_wrapper','content_wrapper',{'rows':ROWS},False),
    ('hidden_rows_in_outputs_wrapper','outputs_wrapper',{'rows':ROWS},False),
    ('hidden_rows_at_native_text_root','text_root',{'rows':ROWS},False)]
records=[]
for label,shape,annotation,positive in cases:
    with tempfile.TemporaryDirectory(prefix='nested-',dir=OUT.parent) as folder:
        temp=Path(folder);code='synthetic=True\n';(temp/'stub.py').write_text(code,encoding='utf-8')
        manifest={'stub.py':hashlib.sha256(code.encode()).hexdigest()};sh=content_hash({'source':'nested-independent-v1'})
        cp={'schema_version':1,'plan_id':'independent-nested-collection','scope':'engineering','source':'quantconnect_fundamental_universe',
            'data_version':'synthetic-v1','start':'2018-01-03T00:00:00-05:00','end_exclusive':'2018-01-04T00:00:00-05:00',
            'timezone':'America/New_York','fields':list(CAT),'calendar_days_per_request':1,'max_batch_records':1,
            'max_records_per_window':3,'source_manifest_hash':sh}
        plan=CollectionTaskPlan.from_dict({'schema_version':1,'task_kind':'historical_collection','scope':'engineering',
            'plan_id':'independent-nested-task','project_id':99791,'source_manifest_hash':sh,'deployment_hash':content_hash(manifest),
            'collection_plan':cp,'field_catalog':CAT,'report_namespace':'independent-nested','max_retries':1},
            discovered_project_ids=(99791,),field_catalog=CAT)
        local=MemoryArtifactStore();reg=Registry(local,BUDGET);bridge=CollectionTaskBridge(reg,plan)
        bridge.register();attempt=bridge.claim();payload=dict(bridge.payload(attempt),deployment_manifest=manifest)
        text='TASK_INPUT_JSON = '+repr(canonical_json(payload).decode())+'\n'
        deployment={'source_manifest_hash':sh,'deployment_hash':content_hash(manifest),'input_hash':hashlib.sha256(text.encode()).hexdigest()}
        class Source:
            calls=0
            def fetch(self,start,end,catalog):
                self.calls+=1;yield {'sid':'INDEPENDENT-CLOUD-SID','snapshot_at':start.isoformat(),'values':{'dollar_volume':0}}
        cloud=MemoryArtifactStore();source=Source()
        wrapper=run_collection_task(payload,field_catalog=CAT,store=cloud,source=source,synthetic=True,source_root=temp)
        marker=stdout_marker(wrapper,payload=payload,field_catalog=CAT)
        node={'type':'text','text':marker}
        if annotation is not None:node['annotations']=annotation
        if shape=='text_root':native=node
        else:native={('content' if shape=='content_wrapper' else 'outputs'):[node],'status':'ok','success':True}
        # Both MCP output carriers have identical full decoded JSON. The outer
        # TextContent annotations are empty; the suspect sidecar is deeper.
        envelope={'tool_name':'mcp__quantconnect__jupyter_execute_cell','arguments':{'projectId':99791,'index':2},
            'result':{'isError':False,'structuredContent':native,
                'content':[{'type':'text','text':json.dumps(native,indent=2),'annotations':{}}]}}
        parsed=collection_research_observation(payload,deployment,envelope,field_catalog=CAT)
        bridge.record_submission(attempt,parsed['submission'])
        final=bridge.consume_completion(attempt,completion_source=lambda _:parsed['completion'])
        result=bridge.read_result(final)
        record={'case':label,'native_shape':shape,'expected':('completed' if positive else 'reject'),
            'actual_status':final.status,'passes_expected_gate':positive or final.status!='completed',
            'parsed_stdout_only':parsed['completion']['platform']['raw_receipt']['stdout_only'],
            'parsed_marker_count':parsed['completion']['platform']['raw_receipt']['marker_count'],
            'market_values_exported':result['cloud_report']['market_values_exported'],
            'row_sentinel_persisted_in_registry':SECRET.encode() in b''.join(local._data.values()),
            'native_envelope':envelope,'source_fetch_calls':source.calls,'research_usage':reg.snapshot()['usage']['research']['total']}
        records.append(record)
summary={'commit':'be9442603a31481a9a71e51ca794df77650c7411','command_argv':sys.argv,
    'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'method':'synthetic full-chain parameterized probe',
    'subcases':len(records),'negative_false_acceptances':sum(not x['passes_expected_gate'] for x in records),
    'positive_controls':sum(x['expected']=='completed' for x in records),'cases':records,
    'limits':'parser-supported nested text shapes only; no claim actual QC SDK emits arbitrary annotation row keys',
    'real_actions':{'SDK':0,'Research':0,'LEAN':0,'market':0,'models':0,'deploy':0,'real_budget_changes':0,'source_edits':0}}
OUT.write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps({k:v for k,v in summary.items() if k!='cases'},ensure_ascii=False))
for r in records:print(json.dumps({k:v for k,v in r.items() if k!='native_envelope'},ensure_ascii=False))
sys.exit(1 if summary['negative_false_acceptances'] else 0)
