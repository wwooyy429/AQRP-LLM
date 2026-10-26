"""WR-13 independent registered-annotation boundaries and synthetic worker chains."""
import argparse
import base64
from copy import deepcopy
from datetime import datetime,timedelta
import hashlib
import io
import json
from pathlib import Path
import platform
import socket
import sys
import unittest
from types import SimpleNamespace as NS

ap=argparse.ArgumentParser();ap.add_argument('--source',required=True);ap.add_argument('--out',required=True)
arg=ap.parse_args();ROOT=Path(arg.source).resolve();OUT=Path(arg.out).resolve();OUT.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(ROOT/'cloud'))
import pandas as pd
import numpy as np
from qresearch.artifacts import MemoryArtifactStore,canonical_json,content_hash
from qresearch.registry import Registry
from qresearch.collection_tasks import CollectionTaskPlan,CollectionTaskBridge
from qresearch.collection_execution import run_collection_task,stdout_marker,collection_research_observation
from qresearch.engineering_tasks import EngineeringTaskPlan,EngineeringTaskBridge
from qresearch.engineering_data import run_research_task,_finish
from qresearch.engineering_receipts import (_annotations,_text_node,_native,_research_stdout,ReceiptParseError,
    research_observation,backtest_submission,backtest_observation)

def forbidden(*a,**kw):raise AssertionError('network prohibited during synthetic execution')
socket.socket=forbidden
BUDGET=json.loads((ROOT/'config/budget.json').read_text(encoding='utf-8'))
MANIFEST=json.loads((ROOT/'audit/deployment.json').read_text(encoding='utf-8'))['source_files']
SOURCE_HASH=content_hash({'synthetic':'independent-WR13-v2'})
CAT={'dollar_volume':{'kind':'number','role':'independent_synthetic','unit':'USD','period_accessor':None}}
SECRET='INDEPENDENT-DC49-SYNTHETIC-ROW-SECRET'
GOOD={'audience':['assistant','user','assistant'],'priority':0.125,'lastModified':'2016-02-29T12:34:56.123456+05:45'}
INPUTS=[]

def marker(wrapper):return 'AQRP_ENGINEERING_JSON '+base64.b64encode(canonical_json(wrapper)).decode()
def carriers(native,*,outer_annotation=GOOD):
    return {'isError':False,'structuredContent':native,
        'content':[{'type':'text','text':json.dumps(native,indent=2),'annotations':deepcopy(outer_annotation)}]}
def native_shape(text,annotation,shape):
    node={'type':'text','text':text}
    if annotation!='ABSENT':node['annotations']=deepcopy(annotation)
    if shape=='root':return node
    if shape=='content':return {'content':[node],'status':'ok'}
    if shape=='outputs':return {'outputs':[node],'status':'ok'}
    if shape=='wrappers':return {'results':{'cells':[{'output':{'content':[node]}}]},'status':'completed'}
    if shape=='json_text':
        wrapped={'outputs':[node],'status':'ok'}
        for _ in range(4):wrapped={'type':'text','text':json.dumps(wrapped),'annotations':deepcopy(GOOD)}
        return {'content':[wrapped],'status':'ok'}
    raise AssertionError(shape)
def tool(name,payload,native,*,external=None):
    arguments={'projectId':payload['identity']['project_id']}
    if name.endswith('jupyter_execute_cell'):arguments['index']=3
    elif name.endswith('create_backtest'):arguments['backtestName']='independent-offline'
    else:
        arguments['backtestId']=external
        if name.endswith('search_backtest_logs'):arguments.update(query='AQRP_ENGINEERING '+payload['identity']['attempt_id'],page=1)
    return {'tool_name':name,'arguments':arguments,'result':carriers(native)}

class SyntheticObjectStore:
    def __init__(self):self.data={}
    def contains_key(self,key):return key in self.data
    def read_bytes(self,key):return self.data[key]
    def save_bytes(self,key,value):self.data[key]=bytes(value);return True
class SyntheticHours:
    def is_date_open(self,day):return day.weekday()<5
    def get_next_trading_day(self,day):
        day=day+timedelta(days=1)
        while not self.is_date_open(day):day+=timedelta(days=1)
        return day
    def get_previous_trading_day(self,day):
        day=day-timedelta(days=1)
        while not self.is_date_open(day):day-=timedelta(days=1)
        return day
    def get_next_market_close(self,day,extended):
        assert not extended
        return datetime(day.year,day.month,day.day,16)
class SyntheticSymbol:
    def __init__(self,ticker):self.value=ticker;self.id=SECRET+'-'+ticker
    def __str__(self):return self.value
class SyntheticQB:
    """Invented weekday calendar/constant numbers, not exchange/market evidence."""
    def __init__(self):
        self.object_store=SyntheticObjectStore();self.settings=NS();self.securities={};self.history_calls=0
    def set_time_zone(self,zone):assert zone=='America/New_York'
    def set_start_date(self,y,m,d):self.time=datetime(y,m,d)
    def set_end_date(self,*args):pass
    def add_equity(self,ticker,resolution,*,fill_forward,data_normalization_mode):
        assert not fill_forward
        symbol=SyntheticSymbol(ticker);security=NS(symbol=symbol,exchange=NS(hours=SyntheticHours()))
        self.securities[symbol]=security;return security
    def history(self,symbols,start,end,resolution,*,fill_forward,extended_market_hours,data_normalization_mode):
        assert not fill_forward and not extended_market_hours
        self.history_calls+=1
        clocks=pd.date_range(start,end-timedelta(days=1),freq='B')
        index=pd.MultiIndex.from_tuples([(symbol,stamp.to_pydatetime().replace(hour=16)) for symbol in symbols for stamp in clocks],names=['symbol','time'])
        return pd.DataFrame({'close':[42.125]*len(index)},index=index)
API=NS(Resolution=NS(DAILY='SYNTHETIC_DAILY'),DataNormalizationMode=NS(RAW='SYNTHETIC_RAW'),Globals=NS(version='independent-fake-lean'))

class Harness:
    def __init__(self,family):
        self.family=family;self.local=MemoryArtifactStore();self.reg=Registry(self.local,BUDGET)
        if family=='collection':
            cp={'schema_version':1,'plan_id':'independent-cp','scope':'engineering','source':'quantconnect_fundamental_universe',
                'data_version':'independent-v3','start':'2018-03-09T00:00:00-05:00','end_exclusive':'2018-03-14T00:00:00-04:00',
                'timezone':'America/New_York','fields':list(CAT),'calendar_days_per_request':2,'max_batch_records':2,
                'max_records_per_window':30,'source_manifest_hash':SOURCE_HASH}
            plan=CollectionTaskPlan.from_dict({'schema_version':1,'task_kind':'historical_collection','scope':'engineering',
                'plan_id':'independent-WR13-collection','project_id':99851,'source_manifest_hash':SOURCE_HASH,
                'deployment_hash':content_hash(MANIFEST),'collection_plan':cp,'field_catalog':CAT,
                'report_namespace':'independent-wr13-collection','max_retries':1},discovered_project_ids=(99851,),field_catalog=CAT)
            self.bridge=CollectionTaskBridge(self.reg,plan)
        else:
            plan=EngineeringTaskPlan.from_dict({'schema_version':1,'plan_id':'independent-WR13-old','scope':'engineering',
                'project_id':99852,'source_manifest_hash':SOURCE_HASH,'deployment_hash':content_hash(MANIFEST),
                'request_mode':'symbol_resolution','request_template':{'dataset':'US Equities','fields':['close'],
                    'start':'2018-01-01T00:00:00-05:00','end':'2019-01-01T00:00:00-05:00','data_version':'independent-v3',
                    'universe_hash':'8'*64,'normalization':'raw','timezone':'America/New_York'},
                'symbol_resolution':{'tickers':['AAPL','MSFT'],'as_of':'2019-01-01T00:00:00-05:00','method':'QuantBook.add_equity/as-of fixed fixture'},
                'observation_window':{'start':'2018-01-03T00:00:00-05:00','end_exclusive':'2018-01-06T00:00:00-05:00'},
                'required_checks':{'research':['raw_data_received','second_prefetch_no_history','cache_only_consumer','coverage_observed_complete'],
                    'lean':['raw_data_received','no_orders']},'max_retries':{'research':1,'lean':1},
                'report_namespace':'independent-wr13-old','orders_enabled':False,'financial_metrics_enabled':False,
                'economic_factor':None,'economic_model':None},discovered_project_ids=(99852,))
            self.bridge=EngineeringTaskBridge(self.reg,plan)
        self.bridge.register();self.attempt=self.bridge.claim('research')
        self.payload=dict(self.bridge.payload(self.attempt),deployment_manifest=MANIFEST)
        text='TASK_INPUT_JSON = '+repr(canonical_json(self.payload).decode())+'\n'
        self.deploy={'source_manifest_hash':SOURCE_HASH,'deployment_hash':content_hash(MANIFEST),
            'input_hash':hashlib.sha256(text.encode()).hexdigest()}
        if family=='collection':
            class Source:
                calls=0
                def fetch(self,start,end,catalog):
                    self.calls+=1
                    for stamp in pd.date_range(start,end-pd.DateOffset(days=1),freq='D'):
                        yield {'sid':SECRET,'snapshot_at':stamp.isoformat(),'values':{'dollar_volume':1234.75}}
                        yield {'sid':'INDEPENDENT-MISSING','snapshot_at':stamp.isoformat(),'values':{'dollar_volume':None}}
            self.source=Source();self.cloud=MemoryArtifactStore()
            self.wrapper=run_collection_task(self.payload,field_catalog=CAT,source=self.source,store=self.cloud,
                synthetic=True,source_root=ROOT/'cloud')
        else:
            self.qb=SyntheticQB()
            self.wrapper=run_research_task(self.payload,api=API,quantbook_factory=lambda:self.qb)
    def parse(self,native,*,outer_annotation=GOOD):
        env=tool('mcp__quantconnect__jupyter_execute_cell',self.payload,native)
        env['result']=carriers(native,outer_annotation=outer_annotation)
        if self.family=='collection':return collection_research_observation(self.payload,self.deploy,env,field_catalog=CAT)
        return research_observation(self.payload,self.deploy,env)
    def finish(self,parsed):
        self.bridge.record_submission(self.attempt,parsed['submission'])
        return self.bridge.consume_completion(self.attempt,completion_source=lambda _:parsed['completion'])
    def assert_no_rows(self,test):test.assertNotIn(SECRET.encode(),b''.join(self.local._data.values()))

class IndependentAnnotationTests(unittest.TestCase):
    def case(self,**params):INPUTS.append({'method':self._testMethodName,**params});return self.subTest(**params)
    def test_official_schema_registered_field_contract(self):
        schema=json.loads((OUT/'official_mcp_schema_2025-11-25.json').read_text(encoding='utf-8'))['$defs']
        checks={'annotation_fields':set(schema['Annotations']['properties'])=={'audience','priority','lastModified'},
            'role_enum':schema['Role']['enum']==['user','assistant'],
            'priority_interval':schema['Annotations']['properties']['priority']['minimum']==0 and schema['Annotations']['properties']['priority']['maximum']==1,
            'text_string':schema['TextContent']['properties']['text']['type']=='string'}
        for name,value in checks.items():
            with self.case(schema_check=name):self.assertTrue(value)
    def test_annotation_registered_positive_subset(self):
        values=[None,{}, {'audience':[]},{'audience':['user','assistant','user']},{'priority':0},{'priority':1},
            {'priority':-0.0},{'priority':0.9999999999999999},GOOD]
        clocks=['0001-01-01','9999-12-31','2016-02-29','2018-01-03T00:00:00','2018-01-03 00:00:00',
            '2018-01-03t00:00:00z','2018-01-03T23:59:59Z','2018-01-03T00:00:00.123456789+05:45',
            '2018-01-03T00:00:00,5-03:30','2018-01-03T00:00:00+23:59','2018-01-03T00:00:00-00:00']
        values += [{'lastModified':value} for value in clocks]
        for number,value in enumerate(values):
            with self.case(positive_annotation=number,value=str(value)):_annotations(value)
    def test_annotation_unknown_keys_types_priorities_rejected(self):
        values=[{'rows':[SECRET]},{'errors':[SECRET]},{'outputs':[SECRET]},{'_meta':{'rows':[SECRET]}},
            {'audience':['system']},{'audience':'user'},{'audience':[True]},{'audience':None},
            {'priority':True},{'priority':None},{'priority':'0.5'},{'priority':[]},{'priority':-0.01},{'priority':1.01},
            {'priority':float('nan')},{'priority':float('inf')},{'priority':float('-inf')},{'priority':10**500},
            [],'annotation string',False,42]
        for number,value in enumerate(values):
            with self.case(invalid_annotation=number,value=str(value)):
                with self.assertRaises(ReceiptParseError):_annotations(value)
    def test_annotation_invalid_calendar_registered_clock_rejected(self):
        clocks=['0000-01-01','2018-02-29','2018-13-01','2018-01-00','2018-01-03T24:00:00',
            '2018-01-03T00:00:60Z','2018-01-03T12:60:00','2018-01-03T00:00:00+24:00',
            '2018-01-03T00:00:00-24:00','2018-01-03T00:00:00+05:60','2018-01-03T00:00:00+00:00:01',
            '2018-01-03T00:00:00+0500','2018-01-03T00:00','20180103','2018-01-03Z','2018-01-03T00:00:00.','',SECRET]
        for value in clocks:
            with self.case(unsupported_or_invalid_clock=value):
                with self.assertRaises(ReceiptParseError):_annotations({'lastModified':value})
        for value in (None,False,0,[],{}):
            with self.case(non_string_clock=str(value)):
                with self.assertRaises(ReceiptParseError):_annotations({'lastModified':value})
    def test_text_node_nonstring_or_unknown_fields_rejected(self):
        for value in (None,False,True,0,1.5,{},[],{'text':'AQRP_ENGINEERING_JSON abc'}):
            with self.case(nonstring_text=str(value)):
                with self.assertRaises(ReceiptParseError):_text_node({'type':'text','text':value})
        for field in ('rows','error','outputs','_meta'):
            with self.case(text_unknown_field=field):
                with self.assertRaises(ReceiptParseError):_text_node({'type':'text','text':'AQRP_ENGINEERING_JSON abc',field:SECRET})
    def test_outer_nested_and_deep_json_positive_paths(self):
        for shape in ('root','content','outputs','wrappers','json_text'):
            for annotation in ('ABSENT',None,{},GOOD):
                with self.case(shape=shape,annotation=str(annotation)):
                    native=native_shape('AQRP_ENGINEERING_JSON abc',annotation,shape)
                    self.assertEqual(_research_stdout(_native(carriers(native))),'abc')
        with self.case(shape='outer_only_standard_annotations'):
            self.assertEqual(_research_stdout(_native({'content':[{'type':'text','text':'AQRP_ENGINEERING_JSON abc','annotations':GOOD}]})),'abc')
    def test_recursive_unknown_side_loads_rejected(self):
        for shape in ('root','content','outputs','wrappers','json_text'):
            for annotation in ({'rows':[SECRET]},{'errors':[SECRET]},{'priority':True},{'audience':['tool']}):
                with self.case(shape=shape,annotation=str(annotation)):
                    native=native_shape('AQRP_ENGINEERING_JSON abc',annotation,shape)
                    with self.assertRaises(ReceiptParseError):_research_stdout(_native(carriers(native)))
    def test_deep_json_text_malformed_duplicate_annotation_keys_rejected(self):
        inners=['{"type":"text","text":"AQRP_ENGINEERING_JSON abc","annotations":{"priority":0,"priority":1}}',
            '{"type":"text","text":"AQRP_ENGINEERING_JSON abc","annotations":{"priority":NaN}}',
            '{"type":"text","text":"AQRP_ENGINEERING_JSON abc","annotations":{"rows":[]}}',
            '{"type":"text","text": {"content":["AQRP_ENGINEERING_JSON abc"]}}']
        for text in inners:
            with self.case(deep_json=text):
                native={'outputs':[{'type':'text','text':text,'annotations':GOOD}]}
                with self.assertRaises(ReceiptParseError):_research_stdout(_native(carriers(native)))
    def test_new_and_old_actual_synthetic_workers_complete(self):
        for family in ('collection','old_research'):
            for shape in ('root','content','wrappers','json_text'):
                with self.case(family=family,shape=shape):
                    h=Harness(family);usage=h.reg.snapshot()['usage']['research']['total']
                    parsed=h.parse(native_shape(marker(h.wrapper),GOOD,shape));final=h.finish(parsed)
                    self.assertEqual(final.status,'completed');h.assert_no_rows(self)
                    self.assertEqual(h.reg.snapshot()['usage']['research']['total'],usage)
                    self.assertFalse(h.bridge.read_result(final)['financial_evidence'])
                    if family=='collection':self.assertEqual(h.source.calls,3)
                    else:self.assertEqual(h.qb.history_calls,1)
    def test_new_old_full_worker_negative_annotation_gate_no_mutation(self):
        for family in ('collection','old_research'):
            for shape in ('root','content','outputs','json_text'):
                for field in ('rows','errors'):
                    with self.case(family=family,shape=shape,unknown_annotation=field):
                        h=Harness(family);before=deepcopy(h.local._data);usage=deepcopy(h.reg.snapshot()['usage'])
                        with self.assertRaises(ReceiptParseError):h.parse(native_shape(marker(h.wrapper),{field:[SECRET]},shape))
                        self.assertEqual(h.local._data,before);self.assertEqual(h.reg.snapshot()['usage'],usage)
                        self.assertEqual(h.bridge._record(h.attempt)['status'],'started');h.assert_no_rows(self)
    def test_full_workers_nonstring_text_cannot_extract_valid_marker(self):
        for family in ('collection','old_research'):
            for value_kind in ('dict','list','bool'):
                with self.case(family=family,nonstring_text=value_kind):
                    h=Harness(family);actual=marker(h.wrapper)
                    value={'outputs':[actual]} if value_kind=='dict' else [actual] if value_kind=='list' else True
                    node={'type':'text','text':value,'annotations':GOOD}
                    with self.assertRaises(ReceiptParseError):h.parse({'content':[node],'status':'ok'})
                    self.assertEqual(h.bridge._record(h.attempt)['status'],'started');h.assert_no_rows(self)
    def test_lean_receipts_shared_outer_standard_annotations_and_rejections(self):
        h=Harness('old_research');h.finish(h.parse(native_shape(marker(h.wrapper),GOOD,'content')))
        attempt=h.bridge.claim('lean');payload=h.bridge.payload(attempt)
        deploy={'source_manifest_hash':SOURCE_HASH,'deployment_hash':content_hash(MANIFEST),'input_hash':'7'*64}
        cloud=MemoryArtifactStore()
        wrapper=_finish(cloud,payload,{'raw_data_received':True,'no_orders':True},
            {'data_event_count':6,'slice_count':3,'orders_submitted':0,'runtime_error_count':0},h.wrapper['cloud_report']['resolution'])
        external='independent-offline-lean'
        sub=tool('mcp__quantconnect__create_backtest',payload,{'success':True,'errors':[],'backtestId':external})
        read=tool('mcp__quantconnect__read_backtest',payload,{'success':True,'errors':[],
            'backtest':{'backtestId':external,'projectId':99852,'completed':True,'progress':1,'status':'Completed.',
                'hasInitializeError':False,'statistics':{'Total Orders':'0'}}},external=external)
        text=marker(wrapper).split(' ',1)[1];chunks=[text[i:i+500] for i in range(0,len(text),500)]
        lines=['AQRP_ENGINEERING '+payload['identity']['attempt_id']+' '+str(i)+'/'+str(len(chunks))+' '+c for i,c in enumerate(chunks)]
        logs=[tool('mcp__quantconnect__search_backtest_logs',payload,{'success':True,'errors':[],'logs':lines,'totalPages':1},external=external)]
        for target in ('submission','read','logs'):
            with self.case(lean_invalid_outer_annotation=target):
                altered=deepcopy(sub if target=='submission' else read if target=='read' else logs[0])
                altered['result']['content'][0]['annotations']={'rows':[SECRET]}
                with self.assertRaises(ReceiptParseError):
                    if target=='submission':backtest_submission(payload,deploy,altered)
                    else:backtest_observation(payload,deploy,external,altered if target=='read' else read,[altered] if target=='logs' else logs)
        with self.case(lean_positive='standard_annotation_three_stages'):
            ack=backtest_submission(payload,deploy,sub);h.bridge.record_submission(attempt,ack)
            observed=backtest_observation(payload,deploy,external,read,logs)
            self.assertEqual(h.bridge.consume_completion(attempt,completion_source=lambda _:observed).status,'completed');h.assert_no_rows(self)

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

stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2,resultclass=AuditResult).run(unittest.defaultTestLoader.loadTestsFromTestCase(IndependentAnnotationTests))
raw=stream.getvalue();(OUT/'first_run_unittest.txt').write_text(raw,encoding='utf-8')
files=['cloud/qresearch/engineering_receipts.py','cloud/qresearch/engineering_data.py','cloud/qresearch/engineering_tasks.py',
    'cloud/qresearch/collection_execution.py','cloud/qresearch/collection_tasks.py','cloud/qresearch/quantconnect.py','cloud/qresearch/registry.py']
summary={'commit':'dc49f0f3037918f3ce4413665c59b164a8d6e2b7','command_argv':sys.argv,'python':sys.version,
    'platform':platform.platform(),'numpy':np.__version__,'pandas':pd.__version__,
    'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'source_raw_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in files},
    'methods':result.testsRun,'subcases':result.subcases,'failure_records':len(result.failures),'error_records':len(result.errors),
    'skipped':len(result.skipped),'success':result.wasSuccessful(),'first_failure':result.first_failure,'inputs':INPUTS,
    'actions':{'real_SDK':0,'Research':0,'LEAN':0,'market':0,'models':0,'deploy':0,'real_budget_changes':0,'candidate_source_edits':0},
    'scope':'registered annotation/clock subset, invented weekday calendar and constant numbers for actual pure-Python worker execution; not actual SDK/cloud/data evidence'}
(OUT/'first_run_summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf-8')
print(raw);print(json.dumps({k:v for k,v in summary.items() if k not in {'inputs','first_failure'}},ensure_ascii=False))
sys.exit(0 if result.wasSuccessful() else 1)
