"""Actual synthetic adapter callbacks for unknown/rejected/worker-error paths."""
import argparse
import hashlib
import json
from pathlib import Path
import socket
import sys
import tempfile

p=argparse.ArgumentParser(); p.add_argument('--source',required=True); p.add_argument('--out',required=True)
arg=p.parse_args(); ROOT=Path(arg.source).resolve(); OUT=Path(arg.out).resolve()
sys.path.insert(0,str(ROOT/'cloud'))
from qresearch.artifacts import MemoryArtifactStore, canonical_json, content_hash
from qresearch.registry import Registry
from qresearch.collection_tasks import CollectionTaskPlan, CollectionTaskBridge
from qresearch.collection_execution import run_collection_task,stdout_marker,collection_research_observation
from qresearch.workflow import SubmissionRejected
def no_network(*a,**kw): raise AssertionError('network prohibited')
socket.socket=no_network
CAT={'dollar_volume':{'kind':'number','role':'independent_synthetic','unit':'USD','period_accessor':None}}
BUDGET=json.loads((ROOT/'config/budget.json').read_text(encoding='utf-8'))
SECRET='INDEPENDENT-ERROR-ROW-SENTINEL'
records=[]
for variant in ('unknown_then_late_complete','rejected_then_explicit_retry','worker_error_unknown_no_auto_refetch'):
    with tempfile.TemporaryDirectory(prefix='adapter-',dir=OUT.parent) as folder:
        temp=Path(folder); code='synthetic=True\n'; (temp/'stub.py').write_text(code,encoding='utf-8')
        manifest={'stub.py':hashlib.sha256(code.encode()).hexdigest()}; sh=content_hash({'offline':'adapter'})
        cp={'schema_version':1,'plan_id':'independent-cp','scope':'engineering','source':'quantconnect_fundamental_universe',
            'data_version':'synthetic-v1','start':'2018-01-03T00:00:00-05:00','end_exclusive':'2018-01-04T00:00:00-05:00',
            'timezone':'America/New_York','fields':list(CAT),'calendar_days_per_request':1,'max_batch_records':1,
            'max_records_per_window':3,'source_manifest_hash':sh}
        plan=CollectionTaskPlan.from_dict({'schema_version':1,'task_kind':'historical_collection','scope':'engineering',
            'plan_id':'independent-adapter','project_id':99485,'source_manifest_hash':sh,'deployment_hash':content_hash(manifest),
            'collection_plan':cp,'field_catalog':CAT,'report_namespace':'independent-adapter','max_retries':1},
            discovered_project_ids=(99485,),field_catalog=CAT)
        local=MemoryArtifactStore(); reg=Registry(local,BUDGET); cloud=MemoryArtifactStore()
        bridge=CollectionTaskBridge(reg,plan); bridge.register()
        class Source:
            calls=0
            def fetch(self,start,end,catalog):
                self.calls+=1
                if variant=='worker_error_unknown_no_auto_refetch':raise RuntimeError(SECRET)
                yield {'sid':'INDEPENDENT-ADAPTER-SID','snapshot_at':start.isoformat(),'values':{'dollar_volume':0}}
        source=Source(); completions={}; charged=[]
        def completed(payload):
            payload=dict(payload,deployment_manifest=manifest)
            text='TASK_INPUT_JSON = '+repr(canonical_json(payload).decode())+'\n'
            deploy={'source_manifest_hash':sh,'deployment_hash':content_hash(manifest),'input_hash':hashlib.sha256(text.encode()).hexdigest()}
            wrapper=run_collection_task(payload,field_catalog=CAT,store=cloud,source=source,synthetic=True,source_root=temp)
            marker=stdout_marker(wrapper,payload=payload,field_catalog=CAT)
            native={'tool_name':'mcp__quantconnect__jupyter_execute_cell','arguments':{'projectId':99485,'index':1},
                'result':{'outputs':[{'output_type':'stream','name':'stdout','text':marker}],'status':'ok'}}
            return collection_research_observation(payload,deploy,native,field_catalog=CAT)
        class Adapter:
            calls=0
            def submit_research(self,payload,*,operation_key):
                self.calls+=1; charged.append(reg.snapshot()['usage']['research']['total'])
                if self.calls==1 and variant=='unknown_then_late_complete':raise OSError('offline transport')
                if self.calls==1 and variant=='rejected_then_explicit_retry':raise SubmissionRejected(SECRET)
                parsed=completed(payload); completions[payload['identity']['attempt_id']]=parsed['completion']; return parsed['submission']
        adapter=Adapter(); bridge.adapter=adapter
        first=bridge.submit()
        assert charged==[10]
        assert first.status==('failed' if variant=='rejected_then_explicit_retry' else 'ambiguous')
        repeated=bridge.submit()
        assert not repeated.should_execute and adapter.calls==1
        assert SECRET.encode() not in b''.join(local._data.values())
        if variant=='unknown_then_late_complete':
            parsed=completed(bridge.payload(first)); bridge.record_submission(first,parsed['submission'])
            final=bridge.consume_completion(first,completion_source=lambda _:parsed['completion'])
            assert final.status=='completed' and reg.snapshot()['usage']['research']['total']==10
        elif variant=='rejected_then_explicit_retry':
            pending=bridge.submit(retry_of=first.attempt_id,reason='explicit synthetic repair',allocation='reserve')
            assert pending.status=='pending' and adapter.calls==2 and charged==[10,11]
            final=bridge.consume_completion(pending,completion_source=lambda _:completions[pending.attempt_id])
            assert final.status=='completed' and reg.snapshot()['usage']['research']['total']==11
        else:
            assert source.calls==1 and any('/intents/' in key for key in cloud._data)
            for _ in range(2):
                again=bridge.submit(retry_of=first.attempt_id,reason='must not retry unknown')
                assert again.status=='ambiguous' and not again.should_execute
            assert adapter.calls==1 and source.calls==1
            final=again
        records.append({'variant':variant,'passes':True,'first_status':first.status,'final_status':final.status,
            'adapter_calls':adapter.calls,'source_calls':source.calls,'usage_seen_before_callback':charged,
            'final_research_usage':reg.snapshot()['usage']['research']['total'],
            'error_row_sentinel_in_local_store':SECRET.encode() in b''.join(local._data.values()),
            'actual_execution_failure_marker_produced':False if variant=='worker_error_unknown_no_auto_refetch' else None})
summary={'fixed_commit':'e513c66e5965133fbe83fb0ab987eae853f96260','command_argv':sys.argv,
    'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'probes':records,'passed':len(records),
    'actual_SDK_executed':False,'real_Research':0,'real_budget_changes':0,'scope':'synthetic callback recovery only; actual failure receipt remains unverified'}
OUT.write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps(summary,indent=2,ensure_ascii=False))
