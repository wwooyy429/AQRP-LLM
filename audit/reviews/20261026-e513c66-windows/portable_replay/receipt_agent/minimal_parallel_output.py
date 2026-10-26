"""Reproduce ignored MCP content through prepare-task/research-result CLI code.

All inputs, source rows, deployment files and Registry events are synthetic.
The CLI's current_bridge/export_usage are isolated in memory before use.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import socket
import sys
import tempfile
from types import SimpleNamespace as NS

ap=argparse.ArgumentParser(); ap.add_argument('--source',required=True); ap.add_argument('--out',required=True)
arg=ap.parse_args(); ROOT=Path(arg.source).resolve(); OUT=Path(arg.out).resolve()
sys.path[:0]=[str(ROOT/'cloud'),str(ROOT/'tools')]
import pandas as pd
from qresearch.artifacts import MemoryArtifactStore, canonical_json, content_hash
from qresearch.registry import Registry
from qresearch.collection_tasks import CollectionTaskPlan, CollectionTaskBridge
from qresearch.collection_execution import run_collection_task, stdout_marker
from qresearch.engineering_data import load_task_input
import collection_task_cli as cli
def no_network(*a,**kw): raise AssertionError('network prohibited')
socket.socket=no_network
CAT={'dollar_volume':{'kind':'number','role':'independent_synthetic','unit':'USD','period_accessor':None}}
LEAK='INDEPENDENT-PARALLEL-OUTPUT-ROW'; VALUE=123456789.75
BUDGET=json.loads((ROOT/'config/budget.json').read_text(encoding='utf-8'))
reports=[]
for variant in ('clean_control','equivalent_dual','extra_text_row','extra_display_row','extra_error'):
    with tempfile.TemporaryDirectory(prefix='parallel-',dir=OUT.parent) as folder:
        temp=Path(folder); (temp/'audit').mkdir()
        code='synthetic_deployment = True\n'; (temp/'worker_stub.py').write_text(code,encoding='utf-8')
        manifest={'worker_stub.py':hashlib.sha256(code.encode()).hexdigest()}
        (temp/'audit/deployment.json').write_text(json.dumps({'source_files':manifest}),encoding='utf-8')
        source_hash=content_hash({'source':'independent-minimal-v1'})
        cp={'schema_version':1,'plan_id':'independent-cp','scope':'engineering',
            'source':'quantconnect_fundamental_universe','data_version':'independent-v1',
            'start':'2018-01-03T00:00:00-05:00','end_exclusive':'2018-01-04T00:00:00-05:00',
            'timezone':'America/New_York','fields':list(CAT),'calendar_days_per_request':1,
            'max_batch_records':1,'max_records_per_window':3,'source_manifest_hash':source_hash}
        plan=CollectionTaskPlan.from_dict({'schema_version':1,'task_kind':'historical_collection','scope':'engineering',
            'plan_id':'independent-minimal','project_id':99281,'source_manifest_hash':source_hash,
            'deployment_hash':content_hash(manifest),'collection_plan':cp,'field_catalog':CAT,
            'report_namespace':'independent-minimal','max_retries':1},discovered_project_ids=(99281,),field_catalog=CAT)
        local=MemoryArtifactStore(); registry=Registry(local,BUDGET); bridge=CollectionTaskBridge(registry,plan)
        bridge.register(); attempt=bridge.claim()
        cli.ROOT=temp; cli.execution_source_manifest=lambda:{'source_hash':source_hash}
        cli.current_bridge=lambda **kw:bridge
        exports=[]; cli.export_usage=lambda reg:exports.append(reg.snapshot()['usage'])
        admission=cli.prepare_task(bridge,attempt.attempt_id)
        input_path=temp/admission['input_path']
        assert load_task_input(input_path)==admission['payload']
        assert hashlib.sha256(input_path.read_bytes()).hexdigest()==admission['deployment']['input_hash']
        class Source:
            calls=0
            def fetch(self,start,end,fields):
                self.calls+=1
                assert registry.snapshot()['usage']['research']['total']==BUDGET['usage']['research_execution_attempts']+1
                yield {'sid':'INDEPENDENT-CLOUD-SID','snapshot_at':start.isoformat(),'values':{'dollar_volume':0}}
        source=Source(); cloud=MemoryArtifactStore()
        wrapper=run_collection_task(admission['payload'],field_catalog=CAT,store=cloud,source=source,synthetic=True,source_root=temp)
        marker=stdout_marker(wrapper,payload=admission['payload'],field_catalog=CAT)
        result={'isError':False,'structuredContent':{'outputs':[{'output_type':'stream','name':'stdout','text':marker+'\n'}],
            'status':'ok','success':True}}
        if variant=='equivalent_dual': result['content']=[{'type':'text','text':json.dumps(result['structuredContent'])}]
        elif variant=='extra_text_row': result['content']=[{'type':'text','text':LEAK+' '+str(VALUE)}]
        elif variant=='extra_display_row': result['content']=[{'type':'text','text':json.dumps({'outputs':[{'output_type':'display_data','data':{'text/plain':LEAK+' '+str(VALUE)}}]})}]
        elif variant=='extra_error': result['content']=[{'type':'text','text':json.dumps({'outputs':[{'output_type':'error','ename':'RuntimeError','evalue':'synthetic execution failed','traceback':[]}],'status':'error','success':False})}]
        envelope={'tool_name':'mcp__quantconnect__jupyter_execute_cell','arguments':{'projectId':99281,'index':3},'result':result}
        file=temp/'native.json'; file.write_text(json.dumps(envelope),encoding='utf-8')
        completed=cli.execute_metadata_command(NS(command='research-result',attempt=attempt.attempt_id,tool_file=file),field_catalog=CAT)
        ledger_result=registry.read_result(attempt.attempt_id)
        completion=json.loads(local.read_bytes(ledger_result['platform_evidence_ref']['key']))
        positive=variant in {'clean_control','equivalent_dual'}
        report={'variant':variant,'expected':('completed' if positive else 'reject'),
            'actual_status':completed['status'],'passes_expected_gate':positive or completed['status']!='completed',
            'parsed_stdout_only':completion['platform']['raw_receipt']['stdout_only'],
            'parsed_marker_count':completion['platform']['raw_receipt']['marker_count'],
            'market_values_exported':ledger_result['cloud_report']['market_values_exported'],
            'extra_native_content':result.get('content'),'source_fetch_calls':source.calls,
            'row_sentinel_persisted_in_registry':LEAK.encode() in b''.join(local._data.values()),
            'input_sha256_matches':True,'usage_export_calls_are_in_memory_only':len(exports),
            'registry_research_usage':registry.snapshot()['usage']['research']['total'],
            'plan_hash':plan.hash,'attempt_id':attempt.attempt_id,'tool_envelope':envelope}
        reports.append(report)
summary={'fixed_commit':'e513c66e5965133fbe83fb0ab987eae853f96260','command_argv':sys.argv,
    'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'variants':reports,
    'confirmed_false_acceptances':sum(not x['passes_expected_gate'] for x in reports),
    'scope':'independent native-shape replay only; no actual SDK/Research call',
    'real_actions':{'Research':0,'SDK':0,'market':0,'LEAN':0,'models':0,'deploy':0,'budget_mutation':0,'source_edits':0}}
OUT.write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps({k:v for k,v in summary.items() if k!='variants'},ensure_ascii=False))
for r in reports: print(json.dumps({k:v for k,v in r.items() if k not in {'tool_envelope','extra_native_content'}},ensure_ascii=False))
sys.exit(1 if summary['confirmed_false_acceptances'] else 0)
