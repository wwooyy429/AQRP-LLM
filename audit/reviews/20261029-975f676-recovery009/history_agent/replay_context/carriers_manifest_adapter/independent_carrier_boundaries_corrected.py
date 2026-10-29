"""Independent WR-11 repair boundaries; synthetic native shapes only."""
import argparse
import base64
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import platform
import socket
import sys
import tempfile
import unittest

cli=argparse.ArgumentParser(); cli.add_argument('--source',required=True); cli.add_argument('--out',required=True)
arg=cli.parse_args(); ROOT=Path(arg.source).resolve(); OUT=Path(arg.out).resolve(); OUT.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(ROOT/'cloud'))
import pandas as pd
import numpy as np
from qresearch.artifacts import MemoryArtifactStore,canonical_json,content_hash
from qresearch.registry import Registry
from qresearch.engineering_tasks import EngineeringTaskPlan,EngineeringTaskBridge
from qresearch.engineering_data import _finish
from qresearch.engineering_receipts import (_native,ReceiptParseError,research_observation,
    backtest_submission,backtest_observation)
from qresearch.collection_tasks import CollectionTaskPlan,CollectionTaskBridge
from qresearch.collection_execution import run_collection_task,stdout_marker,collection_research_observation

def forbidden(*a,**kw):raise AssertionError('network prohibited in independent review')
socket.socket=forbidden
BUDGET=json.loads((ROOT/'audit/runtime/registry/baseline.json').read_text(encoding='utf-8'))
CAT={'dollar_volume':{'kind':'number','role':'independent_synthetic','unit':'USD','period_accessor':None}}
SECRET='INDEPENDENT-BE94426-CLOUD-ROW-DO-NOT-EXPORT'
INPUTS=[]
ERRORS=(ReceiptParseError,ValueError,TypeError,RuntimeError)

def encoded(wrapper):return base64.b64encode(canonical_json(wrapper)).decode('ascii')
def marker(wrapper):return 'AQRP_ENGINEERING_JSON '+encoded(wrapper)
def native_stdout(wrapper):
    return {'status':'ok','success':True,'execution_count':1,
        'outputs':[{'output_type':'stream','name':'stdout','text':marker(wrapper)+'\n'}]}
def wrapped(value,mode='dual'):
    if mode=='direct':return deepcopy(value)
    if mode=='structured':return {'isError':False,'structuredContent':deepcopy(value)}
    if mode=='content':return {'isError':False,'content':[{'type':'text','text':json.dumps(value,indent=1)}]}
    # Reversed key order, whitespace and Unicode spellings are the same JSON.
    reverse={k:value[k] for k in reversed(list(value))} if isinstance(value,dict) else value
    return {'isError':False,'structuredContent':deepcopy(value),
        'content':[{'type':'text','text':json.dumps(reverse,indent=2,ensure_ascii=True),'annotations':{}}],'_meta':{}}
def envelope(name,payload,value,*,mode='dual',backtest=None):
    args={'projectId':payload['identity']['project_id']}
    if name.endswith('jupyter_execute_cell'):args['index']=8
    elif name.endswith('create_backtest'):args['backtestName']='independent-offline'
    else:
        args['backtestId']=backtest
        if name.endswith('search_backtest_logs'):args.update(query='AQRP_ENGINEERING '+payload['identity']['attempt_id'],page=1)
    return {'tool_name':name,'arguments':args,'result':wrapped(value,mode)}

class Base:
    def __init__(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='wr11-',dir=OUT);self.root=Path(self.tmp.name)
        code='independent_synthetic = True\n';(self.root/'stub.py').write_text(code,encoding='utf-8')
        self.manifest={'stub.py':hashlib.sha256(code.encode()).hexdigest()}
        self.sh=content_hash({'independent':'be94426-new-cases'})
        self.local=MemoryArtifactStore();self.reg=Registry(self.local,BUDGET);self.cloud=MemoryArtifactStore()
    def close(self):self.tmp.cleanup()
    def deployment(self,payload):
        text='TASK_INPUT_JSON = '+repr(canonical_json(payload).decode())+'\n'
        return {'source_manifest_hash':self.sh,'deployment_hash':content_hash(self.manifest),
            'input_hash':hashlib.sha256(text.encode()).hexdigest()}
    def assert_no_rows(self,test):
        test.assertNotIn(SECRET.encode(),b''.join(self.local._data.values()))

class Collection(Base):
    def __init__(self):
        super().__init__()
        cp={'schema_version':1,'plan_id':'independent-collection','scope':'engineering',
            'source':'quantconnect_fundamental_universe','data_version':'independent-new-v1',
            'start':'2018-11-02T00:00:00-04:00','end_exclusive':'2018-11-07T00:00:00-05:00',
            'timezone':'America/New_York','fields':list(CAT),'calendar_days_per_request':2,
            'max_batch_records':2,'max_records_per_window':30,'source_manifest_hash':self.sh}
        plan=CollectionTaskPlan.from_dict({'schema_version':1,'task_kind':'historical_collection','scope':'engineering',
            'plan_id':'independent-new-collection-task','project_id':99681,'source_manifest_hash':self.sh,
            'deployment_hash':content_hash(self.manifest),'collection_plan':cp,'field_catalog':CAT,
            'report_namespace':'independent-new-collection','max_retries':1},discovered_project_ids=(99681,),field_catalog=CAT)
        self.bridge=CollectionTaskBridge(self.reg,plan);self.bridge.register();self.attempt=self.bridge.claim()
        self.payload=dict(self.bridge.payload(self.attempt),deployment_manifest=self.manifest)
        self.deploy=self.deployment(self.payload)
        class Source:
            calls=0
            def fetch(self,start,end,catalog):
                self.calls+=1
                for stamp in pd.date_range(start,end-pd.DateOffset(days=1),freq='D'):
                    yield {'sid':SECRET,'snapshot_at':stamp.isoformat(),'values':{'dollar_volume':17.25}}
                    yield {'sid':'INDEPENDENT-MISSING-SID','snapshot_at':stamp.isoformat(),'values':{'dollar_volume':None}}
        self.source=Source()
        self.wrapper=run_collection_task(self.payload,field_catalog=CAT,store=self.cloud,source=self.source,
            synthetic=True,source_root=self.root)
    def env(self,mode='dual'):
        return envelope('mcp__quantconnect__jupyter_execute_cell',self.payload,native_stdout(self.wrapper),mode=mode)
    def parse(self,env):return collection_research_observation(self.payload,self.deploy,env,field_catalog=CAT)
    def finish(self,parsed):
        self.bridge.record_submission(self.attempt,parsed['submission'])
        return self.bridge.consume_completion(self.attempt,completion_source=lambda _:parsed['completion'])

class OldEngineering(Base):
    def __init__(self):
        super().__init__()
        plan=EngineeringTaskPlan.from_dict({'schema_version':1,'plan_id':'independent-old-engineering',
            'scope':'engineering','project_id':99682,'source_manifest_hash':self.sh,'deployment_hash':content_hash(self.manifest),
            'request_mode':'symbol_resolution','request_template':{'dataset':'US Equities','fields':['close'],
                'start':'2018-01-01T00:00:00-05:00','end':'2019-01-01T00:00:00-05:00',
                'data_version':'independent-v1','universe_hash':'9'*64,'normalization':'raw','timezone':'America/New_York'},
            'symbol_resolution':{'tickers':['AAPL','MSFT'],'as_of':'2019-01-01T00:00:00-05:00','method':'QuantBook.add_equity/as-of fixed fixture'},
            'observation_window':{'start':'2018-01-02T00:00:00-05:00','end_exclusive':'2018-01-05T00:00:00-05:00'},
            'required_checks':{'research':['raw_data_received','second_prefetch_no_history'], 'lean':['raw_data_received','no_orders']},
            'max_retries':{'research':1,'lean':1},'report_namespace':'independent-old-engineering',
            'orders_enabled':False,'financial_metrics_enabled':False,'economic_factor':None,'economic_model':None},discovered_project_ids=(99682,))
        self.bridge=EngineeringTaskBridge(self.reg,plan);self.bridge.register();self.research=self.bridge.claim('research')
        self.rpayload=dict(self.bridge.payload(self.research),deployment_manifest=self.manifest);self.rdeploy=self.deployment(self.rpayload)
        refs={}
        for name in ('resolved_registry_ref','resolved_request_ref'):
            doc={'synthetic_secret':SECRET,'purpose':name};key='synthetic-cloud/'+name+'.json'
            self.cloud.write_once(key,canonical_json(doc));refs[name]={'key':key,'sha256':content_hash(doc)}
        self.resolution={'resolved_registry_hash':refs['resolved_registry_ref']['sha256'],
            'resolved_request_hash':refs['resolved_request_ref']['sha256'],'resolution_artifact_hash':content_hash(refs),
            'tickers':['AAPL','MSFT'],'ticker_count':2,'permanent_sid_count':2,
            'method':'QuantBook.add_equity/as-of fixed fixture',**refs}
        self.rwrapper=_finish(self.cloud,self.rpayload,{'raw_data_received':True,'second_prefetch_no_history':True},
            {'record_count':6,'history_calls_first':1,'history_calls_second':0,'expected_formation_count':3},self.resolution)
    def research_parse(self,mode='dual',env=None):
        native=env or envelope('mcp__quantconnect__jupyter_execute_cell',self.rpayload,native_stdout(self.rwrapper),mode=mode)
        return research_observation(self.rpayload,self.rdeploy,native)
    def complete_research(self,mode='dual'):
        parsed=self.research_parse(mode);self.bridge.record_submission(self.research,parsed['submission'])
        return self.bridge.consume_completion(self.research,completion_source=lambda _:parsed['completion'])
    def lean_context(self,mode='dual'):
        self.complete_research(mode)
        self.lean=self.bridge.claim('lean');self.lpayload=dict(self.bridge.payload(self.lean),deployment_manifest=self.manifest);self.ldeploy=self.deployment(self.lpayload)
        self.lwrapper=_finish(self.cloud,self.lpayload,{'raw_data_received':True,'no_orders':True},
            {'data_event_count':6,'slice_count':3,'orders_submitted':0,'runtime_error_count':0},self.resolution)
        self.external='independent-native-backtest-id'
        self.subenv=envelope('mcp__quantconnect__create_backtest',self.lpayload,
            {'success':True,'errors':[],'backtestId':self.external},mode=mode)
        self.readenv=envelope('mcp__quantconnect__read_backtest',self.lpayload,{'success':True,'errors':[],
            'backtest':{'backtestId':self.external,'projectId':99682,'completed':True,'hasInitializeError':False,
                'progress':1,'status':'Completed.','statistics':{'Total Orders':'0'}}},mode=mode,backtest=self.external)
        text=encoded(self.lwrapper);chunks=[text[i:i+500] for i in range(0,len(text),500)]
        lines=['AQRP_ENGINEERING '+self.lpayload['identity']['attempt_id']+' '+str(i)+'/'+str(len(chunks))+' '+chunk for i,chunk in enumerate(chunks)]
        self.logenvs=[envelope('mcp__quantconnect__search_backtest_logs',self.lpayload,
            {'success':True,'errors':[],'logs':lines,'totalPages':1},mode=mode,backtest=self.external)]

class IndependentCarrierTests(unittest.TestCase):
    def setUp(self):self.objects=[]
    def tearDown(self):
        for obj in self.objects:obj.close()
    def collection(self):h=Collection();self.objects.append(h);return h
    def old(self):h=OldEngineering();self.objects.append(h);return h
    def case(self,**params):INPUTS.append({'method':self._testMethodName,**params});return self.subTest(**params)
    def test_equivalent_wrapped_json_controls(self):
        base={'nested':{'unicode':'审核','bool':True,'int':3,'float':3.5,'null':None},'array':[1,'two',False]}
        for mode in ('direct','structured','content','dual'):
            with self.case(carrier_mode=mode):self.assertEqual(_native(wrapped(base,mode)),base)
        variants=[{'structuredContent':None,'content':[{'type':'text','text':json.dumps(base)}]},
            {'structuredContent':base,'content':[]},{'structuredContent':base,'content':[],'_meta':None},
            {'content':[{'type':'text','text':json.dumps(base),'annotations':None}]}]
        for number,value in enumerate(variants):
            with self.case(optional_empty=number):self.assertEqual(_native(value),base)
    def test_nonidentical_typed_values_or_output_order_rejected(self):
        pairs=[(True,1),(1,1.0),(1,'1'),({'x':None},{'x':''}),([1,2],[2,1]),({'x':[]},{'x':{}}),
            ({'status':'ok'},{'status':'error'}),({'x':'审核'},{'x':'审查'})]
        for number,(left,right) in enumerate(pairs):
            with self.case(type_or_order=number):
                with self.assertRaises(ReceiptParseError):_native({'structuredContent':left,'content':[{'type':'text','text':json.dumps(right)}]})
    def test_top_level_and_block_metadata_cannot_hide_rows(self):
        base={'outputs':[],'status':'ok'}
        mutations={
            'top_extra_row':lambda r:r.__setitem__('row',SECRET),
            'top_error':lambda r:r.__setitem__('error',SECRET),
            'meta_row':lambda r:r.__setitem__('_meta',{'row':SECRET}),
            'block_extra':lambda r:r['content'][0].__setitem__('value',SECRET),
            'block_meta':lambda r:r['content'][0].__setitem__('_meta',{'row':SECRET}),
            'annotation_row':lambda r:r['content'][0].__setitem__('annotations',{'rows':[SECRET]}),
            'content_image':lambda r:r['content'].__setitem__(0,{'type':'image','data':SECRET,'mimeType':'image/png'}),
            'isError_zero':lambda r:r.__setitem__('isError',0),
            'isError_true':lambda r:r.__setitem__('isError',True),
        }
        for label,mutate in mutations.items():
            with self.case(envelope_metadata=label):
                result=wrapped(base);mutate(result)
                with self.assertRaises(ReceiptParseError):_native(result)
    def test_duplicate_json_keys_nonfinite_and_bad_carriers_rejected(self):
        texts=['{"x":1,"x":1}','{"x":1,"x":2}','{"nested":{"x":1,"x":1}}',
            '{"x":NaN}','{"x":Infinity}','{"x":-Infinity}','{"x":']
        for text in texts:
            with self.case(content_text=text):
                with self.assertRaises(ReceiptParseError):_native({'structuredContent':{'x':1},'content':[{'type':'text','text':text}]})
        for label,result in [('none_carriers',{'structuredContent':None,'content':[]}),('dict_content',{'content':{}}),
            ('number_block_text',{'content':[{'type':'text','text':1}]}),('structured_nan',{'structuredContent':{'x':float('nan')}})]:
            with self.case(bad_carrier=label):
                with self.assertRaises(ReceiptParseError):_native(result)
    def test_multiple_text_blocks_are_one_equivalent_list_observation(self):
        with self.case(multiple_blocks='typed_list_mirror'):
            h=self.collection();text=marker(h.wrapper)+'\n'
            env=h.env();env['result']={'structuredContent':[text,'\n'],
                'content':[{'type':'text','text':text},{'type':'text','text':'\n'}]}
            self.assertEqual(h.finish(h.parse(env)).status,'completed');h.assert_no_rows(self)
    def test_collection_complete_chain_all_supported_modes(self):
        for mode in ('direct','structured','content','dual'):
            with self.case(collection_mode=mode):
                h=self.collection();before=deepcopy(h.cloud._data);final=h.finish(h.parse(h.env(mode)))
                self.assertEqual(final.status,'completed');self.assertEqual(h.source.calls,3)
                result=h.bridge.read_result(final);self.assertFalse(result['financial_evidence'])
                self.assertEqual(result['cloud_report']['statistics']['record_count'],10)
                self.assertEqual(result['cloud_report']['evidence']['missing_values'],{'dollar_volume':5})
                self.assertEqual(h.cloud._data,before);h.assert_no_rows(self)
    def test_both_matching_carriers_with_hidden_outputs_still_rejected(self):
        def error():return {'output_type':'error','ename':'RuntimeError','evalue':SECRET,'traceback':[]}
        outputs={'extra_stdout':{'output_type':'stream','name':'stdout','text':SECRET},
            'display':{'output_type':'display_data','data':{'text/plain':SECRET}},
            'error':error(),'stderr':{'output_type':'stream','name':'stderr','text':SECRET}}
        for label,extra in outputs.items():
            with self.case(agreeing_hidden_output=label):
                h=self.collection();native=native_stdout(h.wrapper);native['outputs'].append(extra)
                env=envelope('mcp__quantconnect__jupyter_execute_cell',h.payload,native)
                before=deepcopy(h.local._data)
                with self.assertRaises(ReceiptParseError):h.parse(env)
                self.assertEqual(h.local._data,before);h.assert_no_rows(self)
    def test_conflicts_on_either_side_are_rejected_without_ledger_writes(self):
        for side in ('structured','content'):
            for label in ('extra_stdout','display','error','status','nested_metadata'):
                with self.case(carrier=side,conflict=label):
                    h=self.collection();base=native_stdout(h.wrapper);changed=deepcopy(base)
                    if label=='extra_stdout':changed['outputs'].append({'output_type':'stream','name':'stdout','text':SECRET})
                    elif label=='display':changed['outputs'].append({'output_type':'display_data','data':{'text/plain':SECRET}})
                    elif label=='error':changed['outputs'].append({'output_type':'error','ename':'RuntimeError','evalue':SECRET,'traceback':[]})
                    elif label=='status':changed['success']=False
                    else:changed['metadata']={'rows':[SECRET]}
                    left,right=(changed,base) if side=='structured' else (base,changed)
                    env=h.env();env['result']={'structuredContent':left,'content':[{'type':'text','text':json.dumps(right)}]}
                    before=deepcopy(h.local._data)
                    with self.assertRaises(ReceiptParseError):h.parse(env)
                    self.assertEqual(h.local._data,before);self.assertEqual(h.bridge._record(h.attempt)['status'],'started')
    def test_collection_wrong_json_root_types_are_rejected(self):
        for value in (None,False,True,0,1,1.5,[],{},'not a marker'):
            with self.case(native_type=type(value).__name__,value=value):
                h=self.collection();env=h.env();env['result']=wrapped(value)
                with self.assertRaises(ERRORS):h.parse(env)
                h.assert_no_rows(self)
    def test_duplicate_keys_inside_marker_rejected_in_both_carriers(self):
        for where in ('wrapper','report'):
            with self.case(marker_duplicate=where):
                h=self.collection();text=canonical_json(h.wrapper).decode()
                if where=='wrapper':text=text[:-1]+',"report_ref":'+json.dumps(h.wrapper['report_ref'])+'}'
                else:text=text.replace('"schema_version":1','"schema_version":1,"schema_version":1',1)
                special='AQRP_ENGINEERING_JSON '+base64.b64encode(text.encode()).decode()
                native=native_stdout(h.wrapper);native['outputs'][0]['text']=special
                with self.assertRaises(ReceiptParseError):h.parse(envelope('mcp__quantconnect__jupyter_execute_cell',h.payload,native))
    def test_old_research_complete_chain_equivalent_carriers(self):
        for mode in ('direct','structured','content','dual'):
            with self.case(old_research_mode=mode):
                h=self.old();self.assertEqual(h.complete_research(mode).status,'completed');h.assert_no_rows(self)
    def test_old_lean_submission_read_and_logs_complete_chain(self):
        for mode in ('direct','structured','content','dual'):
            with self.case(old_lean_mode=mode):
                h=self.old();h.lean_context(mode)
                sub=backtest_submission(h.lpayload,h.ldeploy,h.subenv);h.bridge.record_submission(h.lean,sub)
                observed=backtest_observation(h.lpayload,h.ldeploy,h.external,h.readenv,h.logenvs)
                final=h.bridge.consume_completion(h.lean,completion_source=lambda _:observed)
                self.assertEqual(final.status,'completed');h.assert_no_rows(self)
                self.assertFalse(h.bridge.read_result(final)['financial_evidence'])
    def test_old_research_conflicting_carrier_rejected(self):
        for side in ('structured','content'):
            with self.case(old_research_side=side):
                h=self.old();base=native_stdout(h.rwrapper);bad=deepcopy(base);bad['outputs'].append({'output_type':'stream','name':'stdout','text':SECRET})
                left,right=(base,bad) if side=='content' else (bad,base)
                env=envelope('mcp__quantconnect__jupyter_execute_cell',h.rpayload,base)
                env['result']={'structuredContent':left,'content':[{'type':'text','text':json.dumps(right)}]}
                before=deepcopy(h.local._data)
                with self.assertRaises(ReceiptParseError):h.research_parse(env=env)
                self.assertEqual(h.local._data,before)
    def test_old_lean_each_native_stage_conflict_rejected(self):
        for target in ('submission','read','logs'):
            with self.case(old_lean_conflict=target):
                h=self.old();h.lean_context();before=deepcopy(h.local._data)
                targetenv=h.subenv if target=='submission' else h.readenv if target=='read' else h.logenvs[0]
                targetenv['result']['content']=[{'type':'text','text':SECRET}]
                with self.assertRaises(ReceiptParseError):
                    if target=='submission':backtest_submission(h.lpayload,h.ldeploy,h.subenv)
                    else:backtest_observation(h.lpayload,h.ldeploy,h.external,h.readenv,h.logenvs)
                self.assertEqual(h.local._data,before);h.assert_no_rows(self)
    def test_old_lean_matching_runtime_failure_reconciles_without_row_text(self):
        with self.case(old_lean_failure='equal_dual_runtime_error'):
            h=self.old();h.lean_context()
            h.bridge.record_submission(h.lean,backtest_submission(h.lpayload,h.ldeploy,h.subenv))
            native={'success':True,'errors':[],'backtest':{'backtestId':h.external,'projectId':99682,
                'completed':True,'hasInitializeError':False,'progress':0.5,'status':'Runtime Error',
                'error':SECRET,'stacktrace':SECRET,'statistics':{'Total Orders':'0'}}}
            observed=backtest_observation(h.lpayload,h.ldeploy,h.external,
                envelope('mcp__quantconnect__read_backtest',h.lpayload,native,backtest=h.external),[])
            self.assertEqual(h.bridge.consume_completion(h.lean,completion_source=lambda _:observed).status,'failed')
            h.assert_no_rows(self)

class AuditResult(unittest.TextTestResult):
    def __init__(self,*a,**kw):super().__init__(*a,**kw);self.subcases=0;self.first_failure=None
    def addSubTest(self,test,subtest,err):
        self.subcases+=1
        if err and self.first_failure is None:self.first_failure={'method':str(test),'subtest':str(subtest),'traceback':self._exc_info_to_string(err,test)}
        super().addSubTest(test,subtest,err)
    def addError(self,test,err):
        if self.first_failure is None:self.first_failure={'method':str(test),'traceback':self._exc_info_to_string(err,test)}
        super().addError(test,err)
    def addFailure(self,test,err):
        if self.first_failure is None:self.first_failure={'method':str(test),'traceback':self._exc_info_to_string(err,test)}
        super().addFailure(test,err)

stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2,resultclass=AuditResult).run(unittest.defaultTestLoader.loadTestsFromTestCase(IndependentCarrierTests))
raw=stream.getvalue();(OUT/'corrected_run_unittest.txt').write_text(raw,encoding='utf-8')
files=['cloud/qresearch/engineering_receipts.py','cloud/qresearch/engineering_tasks.py','cloud/qresearch/engineering_data.py',
    'cloud/qresearch/collection_execution.py','cloud/qresearch/collection_tasks.py','cloud/qresearch/registry.py']
summary={'commit':'be9442603a31481a9a71e51ca794df77650c7411','source_root':str(ROOT),'command_argv':sys.argv,
    'python':sys.version,'platform':platform.platform(),'pandas':pd.__version__,'numpy':np.__version__,
    'source_raw_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in files},
    'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'methods':result.testsRun,'subcases':result.subcases,
    'failure_records':len(result.failures),'error_records':len(result.errors),'skipped':len(result.skipped),'success':result.wasSuccessful(),
    'first_failure':result.first_failure,'inputs':INPUTS,
    'actions':{'SDK':0,'Research':0,'LEAN':0,'market':0,'models':0,'deploy':0,'actual_budget_change':0,'source_edit':0},
    'scope':'fixed synthetically constructed carrier/receipt/Bridge/Registry paths; not arbitrary SDK envelope certification or real remote execution'}
(OUT/'corrected_run_summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf-8')
print(raw);print(json.dumps({k:v for k,v in summary.items() if k not in {'inputs','first_failure'}},ensure_ascii=False))
sys.exit(0 if result.wasSuccessful() else 1)
