"""Independent synthetic collection worker/receipt review; no author fixtures."""
import argparse
import base64
from copy import deepcopy
from datetime import timedelta
import hashlib
import io
import json
from pathlib import Path
import platform
import socket
import sys
import tempfile
import unittest

parser=argparse.ArgumentParser()
parser.add_argument('--source',required=True)
parser.add_argument('--out',required=True)
args=parser.parse_args()
ROOT=Path(args.source).resolve(); OUT=Path(args.out).resolve(); OUT.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(ROOT/'cloud'))
import pandas as pd
import numpy as np
from qresearch.artifacts import MemoryArtifactStore, canonical_json, content_hash
from qresearch.registry import Registry
from qresearch.collection import CollectionError
from qresearch.collection_tasks import CollectionTaskPlan, CollectionTaskBridge, validate_report
from qresearch.collection_execution import context, run_collection_task, stdout_marker, collection_research_observation
from qresearch.engineering_tasks import EngineeringTaskError
from qresearch.engineering_receipts import ReceiptParseError
from qresearch.engineering_data import load_task_input

def network_forbidden(*a,**kw): raise AssertionError('network forbidden in independent review')
socket.socket=network_forbidden
CATALOG={'dollar_volume':{'kind':'number','role':'independent_synthetic','unit':'USD','period_accessor':None}}
API_ERRORS=(ValueError,RuntimeError,TypeError,KeyError)
INPUTS=[]
SECRET='INDEPENDENT-SYNTHETIC-CLOUD-ROW-SID'
SECRET_VALUE=987654321.25
BUDGET=json.loads((ROOT/'config/budget.json').read_text(encoding='utf-8'))

class SyntheticSource:
    def __init__(self,*,fail=False): self.calls=[]; self.fail=fail
    def fetch(self,start,end,selected):
        self.calls.append((start.isoformat(),end.isoformat(),deepcopy(selected)))
        if self.fail: raise RuntimeError(SECRET+' '+str(SECRET_VALUE))
        for stamp in pd.date_range(start,end-pd.DateOffset(days=1),freq='D'):
            yield {'sid':SECRET,'snapshot_at':stamp.isoformat(),'values':{'dollar_volume':SECRET_VALUE}}
            yield {'sid':'INDEPENDENT-OTHER-SID','snapshot_at':stamp.isoformat(),'values':{'dollar_volume':None}}

class Harness:
    def __init__(self,*,plan_name='independent',project=99173,days=2,retries=1):
        self.temp=tempfile.TemporaryDirectory(prefix='receipt-',dir=OUT)
        self.root=Path(self.temp.name)
        code='def synthetic_only():\n    return None\n'
        (self.root/'independent_deployment.py').write_text(code,encoding='utf-8')
        self.manifest={'independent_deployment.py':hashlib.sha256(code.encode()).hexdigest()}
        self.source_hash=content_hash({'independent_source':'offline_synthetic_v1'})
        collection={'schema_version':1,'plan_id':'independent-collection','scope':'engineering',
            'source':'quantconnect_fundamental_universe','data_version':'independent-frozen-v1',
            'start':'2018-03-09T00:00:00-05:00','end_exclusive':'2018-03-13T00:00:00-04:00',
            'timezone':'America/New_York','fields':list(CATALOG),'calendar_days_per_request':days,
            'max_batch_records':3,'max_records_per_window':30,'source_manifest_hash':self.source_hash}
        raw={'schema_version':1,'task_kind':'historical_collection','scope':'engineering','plan_id':plan_name,
            'project_id':project,'source_manifest_hash':self.source_hash,'deployment_hash':content_hash(self.manifest),
            'collection_plan':collection,'field_catalog':deepcopy(CATALOG),'report_namespace':'independent-collection-tasks',
            'max_retries':retries}
        self.plan=CollectionTaskPlan.from_dict(raw,discovered_project_ids=(project,),field_catalog=CATALOG)
        self.local=MemoryArtifactStore(); self.registry=Registry(self.local,BUDGET)
        self.bridge=CollectionTaskBridge(self.registry,self.plan)
        self.bridge.register(); self.attempt=self.bridge.claim()
        assert self.attempt.should_execute
        self.payload=dict(self.bridge.payload(self.attempt),deployment_manifest=self.manifest)
        self.input_text='TASK_INPUT_JSON = '+repr(canonical_json(self.payload).decode())+'\n'
        self.deployment={'source_manifest_hash':self.source_hash,'deployment_hash':content_hash(self.manifest),
            'input_hash':hashlib.sha256(self.input_text.encode()).hexdigest()}
        self.cloud=MemoryArtifactStore(); self.source=SyntheticSource()
    def close(self): self.temp.cleanup()
    def run(self,source=None):
        return run_collection_task(self.payload,field_catalog=CATALOG,store=self.cloud,
            source=self.source if source is None else source,synthetic=True,source_root=self.root)
    def marker(self,wrapper): return stdout_marker(wrapper,payload=self.payload,field_catalog=CATALOG)
    def envelope(self,wrapper,*,mode='structured'):
        native={'outputs':[{'output_type':'stream','name':'stdout','text':self.marker(wrapper)+'\n'}],
            'execution_count':1,'status':'ok','success':True}
        if mode=='structured': result={'isError':False,'structuredContent':native}
        elif mode=='content': result={'content':[{'type':'text','text':json.dumps(native)}]}
        else: result=native
        return {'tool_name':'mcp__quantconnect__jupyter_execute_cell',
            'arguments':{'projectId':self.plan.to_dict()['project_id'],'index':4},'result':result}
    def parse(self,envelope):
        return collection_research_observation(self.payload,self.deployment,envelope,field_catalog=CATALOG)
    def finish(self,parsed):
        acknowledged=self.bridge.record_submission(self.attempt,parsed['submission'])
        assert acknowledged.status=='pending'
        return self.bridge.consume_completion(self.attempt,completion_source=lambda _:parsed['completion'])

class IndependentReceiptTests(unittest.TestCase):
    def setUp(self): self.harnesses=[]
    def tearDown(self):
        for h in self.harnesses: h.close()
    def harness(self,**kw):
        h=Harness(**kw); self.harnesses.append(h); return h
    def case(self,**params): INPUTS.append({'method':self._testMethodName,**params}); return self.subTest(**params)
    def test_complete_worker_native_parser_registry_chain(self):
        for mode in ('structured','content','direct'):
            with self.case(native_mode=mode):
                h=self.harness(); before=h.registry.snapshot()['usage']['research']['total']
                self.assertEqual(before,BUDGET['usage']['research_execution_attempts']+1)
                wrapper=h.run(); parsed=h.parse(h.envelope(wrapper,mode=mode)); final=h.finish(parsed)
                self.assertEqual(final.status,'completed')
                self.assertEqual(len(h.source.calls),2)
                result=h.bridge.read_result(final)
                self.assertFalse(result['financial_evidence'])
                report=result['cloud_report']
                self.assertEqual(report['statistics'],{'window_count':2,'record_count':8,'source_fetch_calls':2,
                    'reused_windows':0,'empty_windows':0,'cache_only_source_fetch_calls':0})
                self.assertEqual(report['evidence']['missing_values'],{'dollar_volume':4})
                local_bytes=b''.join(h.local._data.values())
                self.assertNotIn(SECRET.encode(),local_bytes); self.assertNotIn(str(SECRET_VALUE).encode(),local_bytes)
                self.assertTrue(any(SECRET.encode() in data for data in h.cloud._data.values()))
                calls=len(h.source.calls)
                self.assertEqual(h.bridge.consume_completion(final,completion_source=lambda _:self.fail('should not reread')).status,'completed')
                self.assertFalse(h.bridge.claim().should_execute)
                self.assertEqual(len(h.source.calls),calls)
                self.assertEqual(h.registry.snapshot()['usage']['research']['total'],before)
    def test_context_rejects_cross_identity_and_report_paths(self):
        h=self.harness()
        changes={'attempt_id':'f'*32,'plan_hash':'f'*64,'config_id':'f'*64,'project_id':99174,
            'source_manifest_hash':'f'*64,'deployment_hash':'f'*64,'data_request_hash':'f'*64,'stage':'lean'}
        for key,value in changes.items():
            with self.case(identity_key=key):
                payload=deepcopy(h.payload); payload['identity'][key]=value
                with self.assertRaises(API_ERRORS): context(payload,field_catalog=CATALOG)
        for label,value in [('report_key','other/report.json'),('external_identity_kind','quantconnect_backtest_id')]:
            with self.case(payload_key=label):
                payload=deepcopy(h.payload); payload[label]=value
                with self.assertRaises(API_ERRORS): context(payload,field_catalog=CATALOG)
    def test_cross_attempt_report_replay_rejected(self):
        with self.case(cross_attempt=True):
            first=self.harness(); second=self.harness(); wrapper=first.run()
            foreign=first.envelope(wrapper)
            with self.assertRaises(API_ERRORS): second.parse(foreign)
            self.assertEqual(second.bridge._record(second.attempt)['status'],'started')
    def test_deployment_and_input_bindings_reject_changes(self):
        for key in ('source_manifest_hash','deployment_hash'):
            with self.case(deployment_key=key):
                h=self.harness(); wrapper=h.run(); envelope=h.envelope(wrapper)
                altered=deepcopy(h.deployment); altered[key]='f'*64
                with self.assertRaises(API_ERRORS):
                    collection_research_observation(h.payload,altered,envelope,field_catalog=CATALOG)
        with self.case(deployment_key='input_hash_completion_mismatch'):
            h=self.harness(); parsed=h.parse(h.envelope(h.run()))
            h.bridge.record_submission(h.attempt,parsed['submission'])
            altered=deepcopy(parsed['completion']); altered['platform']['deployment']['input_hash']='f'*64
            with self.assertRaises(API_ERRORS): h.bridge.consume_completion(h.attempt,completion_source=lambda _:altered)
            self.assertEqual(h.bridge._record(h.attempt)['status'],'pending')
    def test_deployment_source_bytes_checked_before_source_fetch(self):
        with self.case(source_file='changed'):
            h=self.harness(); (h.root/'independent_deployment.py').write_text('changed=1\n',encoding='utf-8')
            with self.assertRaises(API_ERRORS): h.run()
            self.assertEqual(h.source.calls,[]); self.assertEqual(h.cloud._data,{})
    def test_native_errors_extra_stdout_and_displays_rejected(self):
        h=self.harness(); wrapper=h.run(); good=h.envelope(wrapper)
        mutations={
            'wrong_project':lambda x:x['arguments'].__setitem__('projectId',99174),
            'wrong_tool':lambda x:x.__setitem__('tool_name','mcp__quantconnect__create_backtest'),
            'isError_true':lambda x:x['result'].__setitem__('isError',True),
            'pending_status':lambda x:x['result']['structuredContent'].__setitem__('status','running'),
            'error_output':lambda x:x['result']['structuredContent']['outputs'].append({'output_type':'error','ename':'RuntimeError','evalue':SECRET,'traceback':[]}),
            'display_row':lambda x:x['result']['structuredContent']['outputs'].append({'output_type':'display_data','data':{'text/plain':SECRET}}),
            'extra_stdout':lambda x:x['result']['structuredContent']['outputs'].append({'output_type':'stream','name':'stdout','text':SECRET}),
            'duplicate_marker':lambda x:x['result']['structuredContent']['outputs'].extend(deepcopy(x['result']['structuredContent']['outputs'])),
            'stderr':lambda x:x['result']['structuredContent']['outputs'].append({'output_type':'stream','name':'stderr','text':'warning'}),
            'free_completed':lambda x:x['result'].__setitem__('structuredContent',{'completed':True}),
        }
        for label,mutate in mutations.items():
            with self.case(native_mutation=label):
                envelope=deepcopy(good); mutate(envelope)
                with self.assertRaises(API_ERRORS): h.parse(envelope)
    def test_report_metadata_whitelist_and_false_limitations(self):
        h=self.harness(); wrapper=h.run()
        changes={
            'market_flag':lambda r:r.__setitem__('market_values_exported',True),
            'economic_flag':lambda r:r.__setitem__('economic_factor_tested',True),
            'final_flag':lambda r:r.__setitem__('final_data_accessed',True),
            'coverage_flag':lambda r:r.__setitem__('full_US200_coverage_certified',True),
            'availability_flag':lambda r:r.__setitem__('actual_availability_verified',True),
            'row_array':lambda r:r.__setitem__('rows',[{'sid':SECRET,'value':SECRET_VALUE}]),
            'evidence_rows':lambda r:r['evidence'].__setitem__('rows',[SECRET]),
            'statistics_row':lambda r:r['statistics'].__setitem__('rows',[SECRET]),
            'bad_receipt_path':lambda r:r['evidence']['collection_receipt_ref'].__setitem__('key','other/receipts/'+'f'*32+'.json'),
            'count_bool':lambda r:r['statistics'].__setitem__('source_fetch_calls',True),
            'missing_exceeds':lambda r:r['evidence']['missing_values'].__setitem__('dollar_volume',9),
            'checks_false_but_completed':lambda r:r['checks'].__setitem__('source_identity_matches',False),
        }
        for label,change in changes.items():
            with self.case(report_mutation=label):
                altered=deepcopy(wrapper); change(altered['cloud_report'])
                altered['report_ref']['sha256']=content_hash(altered['cloud_report'])
                with self.assertRaises(API_ERRORS): stdout_marker(altered,payload=h.payload,field_catalog=CATALOG)
                # Bypass the marker-builder to check delivered hostile text too.
                marker='AQRP_ENGINEERING_JSON '+base64.b64encode(canonical_json(altered)).decode()
                env=h.envelope(wrapper); env['result']['structuredContent']['outputs'][0]['text']=marker
                with self.assertRaises(API_ERRORS): h.parse(env)
    def test_reentry_is_cache_only_and_same_report(self):
        with self.case(reentry='complete_receipt_saved'):
            h=self.harness(); wrapper=h.run(); before=deepcopy(h.cloud._data)
            class MustNotFetch:
                def fetch(self,*a,**k): raise AssertionError('reentry fetched source')
            self.assertEqual(h.run(MustNotFetch()),wrapper)
            self.assertEqual(h.cloud._data,before)
            self.assertEqual(len(h.source.calls),2)
            # Simulate the receipt write having succeeded and final report write
            # not yet happening. Reconstruct exactly the original metadata.
            del h.cloud._data[h.payload['report_key']]
            self.assertEqual(h.run(MustNotFetch()),wrapper)
            self.assertEqual(h.cloud._data,before)
    def test_corrupt_cache_or_receipt_never_refetches(self):
        for target in ('receipt_identity','window_bytes','payload_bytes','missing_payload'):
            with self.case(corruption=target):
                h=self.harness(); wrapper=h.run()
                if target=='receipt_identity':
                    key=wrapper['cloud_report']['evidence']['collection_receipt_ref']['key']
                    data=json.loads(h.cloud._data[key]); data['identity']['attempt_id']='f'*32
                    h.cloud._data[key]=canonical_json(data)
                elif target=='window_bytes':
                    key=next(k for k in h.cloud._data if '/windows/' in k); h.cloud._data[key]=b'{}'
                else:
                    key=next(k for k in h.cloud._data if '/objects/' in k)
                    if target=='payload_bytes': h.cloud._data[key]=b'{}'
                    else: del h.cloud._data[key]
                calls=len(h.source.calls)
                with self.assertRaises(API_ERRORS): h.run()
                self.assertEqual(len(h.source.calls),calls)
    def test_source_failure_suppresses_rows_and_blocks_same_attempt_retry(self):
        with self.case(source_failure='raises_value_bearing_exception'):
            h=self.harness(); source=SyntheticSource(fail=True)
            for invocation in range(2):
                with self.assertRaises(API_ERRORS) as err: h.run(source)
                self.assertNotIn(SECRET,str(err.exception)); self.assertNotIn(str(SECRET_VALUE),str(err.exception))
            self.assertEqual(len(source.calls),1)
            self.assertTrue(any('/intents/' in key for key in h.cloud._data))
            self.assertNotIn(h.payload['report_key'],h.cloud._data)
            self.assertEqual(h.bridge._record(h.attempt)['status'],'started')
    def test_unknown_adapter_and_late_success_reconciliation(self):
        with self.case(submission='unknown_then_delivered_success'):
            h=self.harness()
            class Adapter:
                calls=0
                def submit_research(self,*a,**kw): self.calls+=1; raise OSError('transport')
            adapter=Adapter(); h.bridge.adapter=adapter
            # Already precharged claim is deliberately not re-dispatched.
            self.assertFalse(h.bridge.submit().should_execute)
            self.assertEqual(adapter.calls,0)
            h.registry.ambiguous(h.attempt,reason='independent synthetic unknown submit')
            self.assertFalse(h.bridge.claim().should_execute)
            parsed=h.parse(h.envelope(h.run()))
            self.assertEqual(h.bridge.record_submission(h.attempt,parsed['submission']).status,'ambiguous')
            self.assertEqual(h.bridge.consume_completion(h.attempt,completion_source=lambda _:parsed['completion']).status,'completed')
    def test_valid_shape_failed_marker_marks_registry_failed(self):
        with self.case(failure='synthetically_modified_fixed_check_not_actual_worker_exception'):
            h=self.harness(); wrapper=h.run(); report=wrapper['cloud_report']
            report['checks']['source_identity_matches']=False; report['status']='failed'
            wrapper['report_ref']['sha256']=content_hash(report)
            parsed=h.parse(h.envelope(wrapper)); final=h.finish(parsed)
            self.assertEqual(final.status,'failed')
            self.assertEqual(h.registry.snapshot()['usage']['research']['total'],BUDGET['usage']['research_execution_attempts']+1)
    def test_inert_input_loader_never_executes_additional_code(self):
        h=self.harness()
        for label,text in [('valid',h.input_text),('extra_statement',h.input_text+'raise RuntimeError("executed")\n'),
            ('call_expression','TASK_INPUT_JSON = str({})\n'),('wrong_name','OTHER = "{}"\n')]:
            with self.case(input_kind=label):
                path=h.root/(label+'.py'); path.write_text(text,encoding='utf-8')
                if label=='valid': self.assertEqual(load_task_input(path),h.payload)
                else:
                    with self.assertRaises(API_ERRORS): load_task_input(path)
    def test_native_parallel_content_row_leak_must_be_rejected(self):
        # Regression claim: validating structuredContent must not disregard an
        # additional MCP content output carrying printed/displayed row values.
        for label,extra in [('text_row',[{'type':'text','text':SECRET+' '+str(SECRET_VALUE)}]),
            ('display_row',[{'type':'text','text':json.dumps({'outputs':[{'output_type':'display_data','data':{'text/plain':SECRET}}]})}])]:
            with self.case(parallel_content=label):
                h=self.harness(); wrapper=h.run(); envelope=h.envelope(wrapper)
                envelope['result']['content']=extra
                # Actual behavior must reject before claiming stdout_only.
                with self.assertRaises(API_ERRORS): h.parse(envelope)

class AuditResult(unittest.TextTestResult):
    def __init__(self,*a,**kw):
        super().__init__(*a,**kw); self.subcases=0; self.first_failure=None
    def addSubTest(self,test,subtest,err):
        self.subcases+=1
        if err and self.first_failure is None:
            self.first_failure={'method':str(test),'subtest':str(subtest),'traceback':self._exc_info_to_string(err,test)}
        super().addSubTest(test,subtest,err)
    def addError(self,test,err):
        if self.first_failure is None:self.first_failure={'method':str(test),'traceback':self._exc_info_to_string(err,test)}
        super().addError(test,err)
    def addFailure(self,test,err):
        if self.first_failure is None:self.first_failure={'method':str(test),'traceback':self._exc_info_to_string(err,test)}
        super().addFailure(test,err)

stream=io.StringIO()
result=unittest.TextTestRunner(stream=stream,verbosity=2,resultclass=AuditResult).run(unittest.defaultTestLoader.loadTestsFromTestCase(IndependentReceiptTests))
raw=stream.getvalue(); (OUT/'first_run_unittest.txt').write_text(raw,encoding='utf-8')
files=['cloud/qresearch/collection_execution.py','cloud/qresearch/collection_tasks.py',
    'cloud/qresearch/engineering_receipts.py','cloud/qresearch/engineering_tasks.py',
    'cloud/qresearch/engineering_data.py','cloud/qresearch/collection.py','tools/collection_task_cli.py']
summary={'fixed_commit':'e513c66e5965133fbe83fb0ab987eae853f96260','source_root':str(ROOT),'command_argv':sys.argv,
    'python':sys.version,'platform':platform.platform(),'numpy':np.__version__,'pandas':pd.__version__,
    'source_raw_sha256':{x:hashlib.sha256((ROOT/x).read_bytes()).hexdigest() for x in files},
    'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'methods':result.testsRun,'subcases':result.subcases,'failure_records':len(result.failures),'error_records':len(result.errors),
    'skipped':len(result.skipped),'success':result.wasSuccessful(),'first_failure':result.first_failure,'inputs':INPUTS,
    'actions':{'market':0,'real_SDK':0,'Research':0,'LEAN':0,'model':0,'deployment':0,'real_budget_change':0,'candidate_source_edits':0},
    'limits':'synthetic public worker/native-shape/Registry chain only; actual run and actual execution-failure receipt unavailable'}
(OUT/'first_run_summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf-8')
print(raw); print(json.dumps({k:v for k,v in summary.items() if k not in {'inputs','first_failure'}},ensure_ascii=False))
sys.exit(0 if result.wasSuccessful() else 1)
