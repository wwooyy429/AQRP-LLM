"""Independent joint-v2 worker/cache/native-receipt/Registry review, synthetic only."""
from copy import copy,deepcopy
from datetime import datetime,timedelta
import base64
import hashlib
import io
import json
from pathlib import Path
import platform
import sys
from types import SimpleNamespace as NS
import unittest
import independent_market_helper as h
from qresearch.artifacts import ArtifactConflict
from qresearch.collection import HistoricalCollectionPlan
from qresearch.engineering_data import (run_research_task,_run_collection_probe,_cloud_store,
    initialize_receiver,receive_slice,finish_receiver)
from qresearch.engineering_tasks import EngineeringTaskPlan,EngineeringTaskBridge,JOINT_PROBE_CHECKS
from qresearch.engineering_receipts import (ReceiptParseError,research_observation,backtest_submission,backtest_observation)

ROOT=h.ROOT;OUT=h.OUT
SECRET='INDEPENDENT-JOINT-V2-ROW-SENTINEL'
CATALOG=json.loads((ROOT/'config/source_catalog.json').read_text(encoding='utf-8'))['fields']
FIELDS=['dollar_volume','has_fundamental_data','time','end_time']
CAT={key:CATALOG[key] for key in FIELDS}
INPUTS=[];EXECUTIONS={'research_worker_invocations':0,'receiver_initialize_invocations':0,'receiver_finish_invocations':0,'receiver_slices':0,'probe_helper_replays':0}
FILES=['cloud/qresearch/engineering_data.py','cloud/qresearch/engineering_tasks.py','cloud/qresearch/engineering_receipts.py',
    'cloud/qresearch/historical_source.py','cloud/qresearch/collection.py','cloud/qresearch/registry.py','cloud/qresearch/quantconnect.py']
BEFORE={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in FILES}

def encode(wrapper):return base64.b64encode(h.canonical_json(wrapper)).decode()
def marker(wrapper):return 'AQRP_ENGINEERING_JSON '+encode(wrapper)
def native(wrapper):return {'outputs':[{'output_type':'stream','name':'stdout','text':marker(wrapper)}],'status':'ok','success':True}
def wrapped(value,mode='dual'):
    if mode=='direct':return deepcopy(value)
    if mode=='structured':return {'structuredContent':deepcopy(value)}
    if mode=='content':return {'content':[{'type':'text','text':json.dumps(value)}]}
    return {'isError':False,'structuredContent':deepcopy(value),
        'content':[{'type':'text','text':json.dumps(value,indent=2),'annotations':{'audience':['assistant'],'priority':0.5,'lastModified':'2018-01-03T12:34:56.5Z'}}]}
def tool(name,payload,value,*,mode='dual',external=None):
    args={'projectId':payload['identity']['project_id']}
    if name.endswith('jupyter_execute_cell'):args['index']=5
    elif name.endswith('create_backtest'):args['backtestName']='independent-joint-v2-offline'
    else:
        args['backtestId']=external
        if name.endswith('search_backtest_logs'):args.update(query='AQRP_ENGINEERING '+payload['identity']['attempt_id'],page=1)
    return {'tool_name':name,'arguments':args,'result':wrapped(value,mode)}

class JointQB(h.SyntheticQB):
    def __init__(self,mode='good'):
        super().__init__();self.mode=mode;self.universe_settings=NS();self.universe_calls=[];self.selector_counts=[]
        self.points=[datetime(2017,12,31),*list(h.pd.date_range('2018-01-01','2018-02-10',freq='D').to_pydatetime())]
    def history(self,*args,**kwargs):
        result=super().history(*args,**kwargs)
        for field,value in [('open',41.0),('high',43.0),('low',40.0),('volume',1000.0)]:result[field]=value
        return result
    @staticmethod
    def snapshot(stamp):
        return [NS(symbol=NS(id=SECRET+'-NO-FUND'),dollar_volume=0.,has_fundamental_data=False,time=stamp-timedelta(days=1),end_time=stamp),
            NS(symbol=NS(id=SECRET+'-HAS-FUND'),dollar_volume=None,has_fundamental_data=True,time=stamp-timedelta(days=1),end_time=stamp)]
    def add_universe(self,selector):
        self.selector_counts.append(len(selector(self.snapshot(datetime(2018,1,1)))))
        return NS(symbol='INDEPENDENT-JOINT-UNIVERSE')
    def universe_history(self,universe,start,end,*,flatten):
        assert start.tzinfo is None and end.tzinfo is None and flatten is False
        self.universe_calls.append((start,end))
        if self.mode=='raises':raise RuntimeError(SECRET)
        stamps=[] if self.mode=='empty' else [stamp for stamp in self.points if start<stamp<=end]
        pairs=[('INDEPENDENT-JOINT-UNIVERSE',stamp) for stamp in stamps]
        if self.mode=='outside_end':pairs.append(('INDEPENDENT-JOINT-UNIVERSE',end+timedelta(microseconds=1)))
        elif self.mode=='duplicate' and pairs:pairs+=pairs[:1]
        elif self.mode=='mixed' and pairs:pairs.append(('OTHER-UNIVERSE',pairs[0][1]))
        index=h.pd.MultiIndex.from_tuples(pairs,names=['symbol','time'])
        return h.pd.Series([self.snapshot(stamp) for _,stamp in pairs],index=index,dtype=object)

class Receiver(JointQB):
    def __init__(self,object_store,*,wrong_sid=False,orders=False):
        super().__init__();self.object_store=object_store;self.wrong_sid=wrong_sid
        self.transactions=NS(get_orders=lambda:[NS()] if orders else [])
    def set_cash(self,value):assert value==100000
    def set_benchmark(self,value):self.benchmark=value
    def add_equity(self,*args,**kwargs):
        security=super().add_equity(*args,**kwargs)
        if self.wrong_sid:security.symbol.id='OTHER-'+security.symbol.id
        return security

class JointHarness:
    def __init__(self,*,mode='good',auto_claim=True,version_tag='one'):
        self.qb=JointQB(mode);self.local=h.MemoryArtifactStore();self.reg=h.Registry(self.local,h.BUDGET)
        self.manifest=h.MANIFEST;self.sh=h.content_hash({'independent_joint_source':'v2-'+version_tag})
        cp={'schema_version':1,'plan_id':'independent-fixed-40','scope':'engineering','source':'quantconnect_fundamental_universe',
            'data_version':'independent-four-field-'+version_tag,'start':'2018-01-01T00:00:00-05:00',
            'end_exclusive':'2018-02-10T00:00:00-05:00','timezone':'America/New_York','fields':FIELDS,
            'calendar_days_per_request':1,'max_batch_records':1000,'max_records_per_window':50000,'source_manifest_hash':self.sh}
        raw={'schema_version':2,'plan_id':'independent-joint-'+version_tag,'scope':'engineering','project_id':99943,
            'source_manifest_hash':self.sh,'deployment_hash':h.content_hash(self.manifest),'request_mode':'symbol_resolution',
            'request_template':{'dataset':'US Equities','fields':['open','high','low','close','volume'],
                'start':'2018-01-01T00:00:00-05:00','end':'2019-01-01T00:00:00-05:00',
                'data_version':'independent-market-'+version_tag,'universe_hash':'8'*64,'normalization':'raw','timezone':'America/New_York'},
            'symbol_resolution':{'tickers':['AAPL','MSFT'],'as_of':'2019-01-01T00:00:00-05:00','method':'QuantBook.add_equity/as-of fixed fixture'},
            'observation_window':{'start':'2018-01-03T00:00:00-05:00','end_exclusive':'2018-01-06T00:00:00-05:00'},
            'required_checks':{'research':['source_snapshot_matches','raw_data_received','second_prefetch_no_history','same_partition_ids',
                'cache_only_consumer','read_only_write_rejected','final_request_rejected','coverage_observed_complete','development_only',
                'symbol_registry_resolved',*sorted(JOINT_PROBE_CHECKS)],
                'lean':['source_snapshot_matches','raw_data_received','complete_expected_bars','no_orders','development_only','symbol_registry_resolved','corporate_action_received']},
            'max_retries':{'research':0,'lean':0},'report_namespace':'independent-joint-v2','orders_enabled':False,
            'financial_metrics_enabled':False,'economic_factor':None,'economic_model':None,
            'collection_probe':{'collection_plan':cp,'field_catalog':CAT}}
        self.plan=EngineeringTaskPlan.from_dict(raw,discovered_project_ids=(99943,),probe_field_catalog=CATALOG)
        self.bridge=EngineeringTaskBridge(self.reg,self.plan);self.bridge.register();self.attempt=None
        if auto_claim:self.bind(self.bridge.payload(self.bridge.claim('research')))
    def bind(self,payload):
        self.payload=dict(payload,deployment_manifest=self.manifest);self.attempt=self.payload['identity']['attempt_id']
        text='TASK_INPUT_JSON = '+repr(h.canonical_json(self.payload).decode())+'\n'
        self.deploy={'source_manifest_hash':self.sh,'deployment_hash':h.content_hash(self.manifest),'input_hash':hashlib.sha256(text.encode()).hexdigest()}
    def run(self,payload=None):
        if payload is not None:self.bind(payload)
        EXECUTIONS['research_worker_invocations']+=1
        self.wrapper=run_research_task(self.payload,api=h.API,quantbook_factory=lambda:self.qb)
        return self.wrapper
    def parse(self,wrapper=None,mode='dual',env=None):
        return research_observation(self.payload,self.deploy,env or tool('mcp__quantconnect__jupyter_execute_cell',self.payload,native(wrapper or self.wrapper),mode=mode))
    def finish_research(self,parsed=None):
        parsed=parsed or self.parse();self.bridge.record_submission(self.attempt,parsed['submission'])
        return self.bridge.consume_completion(self.attempt,completion_source=lambda _:parsed['completion'])
    def receiver(self,*,wrong_sid=False,orders=False,payload=None):
        claim=self.bridge.claim('lean');self.lean_attempt=claim.attempt_id
        self.lean_payload=dict(self.bridge.payload(claim),deployment_manifest=self.manifest)
        if payload is not None:self.lean_payload=payload
        self.lean_deploy={'source_manifest_hash':self.sh,'deployment_hash':h.content_hash(self.manifest),'input_hash':'6'*64}
        algorithm=Receiver(self.qb.object_store,wrong_sid=wrong_sid,orders=orders)
        EXECUTIONS['receiver_initialize_invocations']+=1
        initialize_receiver(algorithm,self.lean_payload,api=h.API)
        for day in (datetime(2018,1,3),datetime(2018,1,4),datetime(2018,1,5)):
            clock=day.replace(hour=16);algorithm.time=clock
            bars={security.symbol:NS(symbol=security.symbol,end_time=clock,open=41.,high=43.,low=40.,close=42.125,volume=1000.) for security in algorithm.securities.values()}
            dividends={}
            if day.day==3:
                symbol=next(iter(algorithm.securities));dividends[symbol]=NS(symbol=symbol,time=clock,end_time=clock,distribution=0.1)
            data=NS(bars=bars,dividends=dividends,splits={},delistings={},symbol_changed_events={})
            EXECUTIONS['receiver_slices']+=1;receive_slice(algorithm,data)
        EXECUTIONS['receiver_finish_invocations']+=1
        self.lean_wrapper=finish_receiver(algorithm);return self.lean_wrapper
    def finish_lean(self,*,wrapper=None,mode='dual'):
        wrapper=wrapper or self.lean_wrapper;external='independent-joint-backtest-'+self.lean_attempt
        sub=backtest_submission(self.lean_payload,self.lean_deploy,tool('mcp__quantconnect__create_backtest',self.lean_payload,
            {'success':True,'errors':[],'backtestId':external},mode=mode))
        self.bridge.record_submission(self.lean_attempt,sub)
        read=tool('mcp__quantconnect__read_backtest',self.lean_payload,{'success':True,'errors':[],
            'backtest':{'backtestId':external,'projectId':99943,'completed':True,'progress':1,'status':'Completed.',
                'hasInitializeError':False,'statistics':{'Total Orders':'0'}}},mode=mode,external=external)
        text=encode(wrapper);parts=[text[i:i+500] for i in range(0,len(text),500)]
        lines=['AQRP_ENGINEERING '+self.lean_attempt+' '+str(i)+'/'+str(len(parts))+' '+value for i,value in enumerate(parts)]
        logs=[tool('mcp__quantconnect__search_backtest_logs',self.lean_payload,{'success':True,'errors':[],'logs':lines,'totalPages':1},mode=mode,external=external)]
        observed=backtest_observation(self.lean_payload,self.lean_deploy,external,read,logs)
        return self.bridge.consume_completion(self.lean_attempt,completion_source=lambda _:observed)
    def no_rows(self,test):
        data=b''.join(self.local._data.values());test.assertNotIn(SECRET.encode(),data);test.assertNotIn(h.SECRET.encode(),data)

def fork(base):
    result=copy(base);result.local=h.MemoryArtifactStore();result.local._data=deepcopy(base.local._data)
    result.reg=h.Registry(result.local,h.BUDGET);result.bridge=EngineeringTaskBridge(result.reg,base.plan)
    result.payload=deepcopy(base.payload);result.deploy=deepcopy(base.deploy);return result
def changed(wrapper,mutate):
    value=deepcopy(wrapper);mutate(value['cloud_report']);value['report_ref']['sha256']=h.content_hash(value['cloud_report']);return value

class IndependentJointWorkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.base=JointHarness();cls.base.run()
    def case(self,**params):INPUTS.append({'method':self._testMethodName,**params});return self.subTest(**params)
    def test_actual_joint_worker_known_counts_hashes_and_half_open_requests(self):
        b=self.base;report=b.wrapper['cloud_report'];summary=report['evidence']['collection_probe']
        expected={'window_count':40,'record_count':80,'source_fetch_calls':40,'reused_windows':0,'empty_windows':0,'cache_only_source_fetch_calls':0}
        for key,value in expected.items():
            with self.case(summary_count=key):self.assertEqual(summary[key],value)
        with self.case(summary='missing_and_hashes'):
            self.assertEqual(summary['missing_values'],{'dollar_volume':40,'has_fundamental_data':0,'time':0,'end_time':0})
            self.assertEqual(b.qb.selector_counts,[2]);self.assertEqual(b.qb.history_calls,1);self.assertEqual(len(b.qb.universe_calls),40)
            receipt_bytes=b.qb.object_store.data['aqrp/engineering/v2/'+summary['receipt_ref']['key']]
            self.assertEqual(hashlib.sha256(receipt_bytes).hexdigest(),summary['receipt_ref']['sha256'])
            receipt=json.loads(receipt_bytes);self.assertEqual(receipt['identity'],b.payload['identity'])
            self.assertEqual(receipt['first']['window_refs'],receipt['cache_only_replay']['window_refs'])
            self.assertEqual(receipt['cache_only_replay']['provider_calls'],0)
            self.assertEqual(receipt['collection_plan_hash'],summary['plan_hash'])
            self.assertEqual(summary['plan_hash'],HistoricalCollectionPlan.from_dict(b.plan.to_dict()['collection_probe']['collection_plan'],field_catalog=CAT).hash)
            report_bytes=b.qb.object_store.data['aqrp/engineering/v2/'+b.wrapper['report_ref']['key']]
            self.assertEqual(hashlib.sha256(report_bytes).hexdigest(),b.wrapper['report_ref']['sha256'])
        for index,(left,right) in enumerate(b.qb.universe_calls):
            with self.case(window=index):
                day=datetime(2018,1,1)+timedelta(days=index)
                self.assertEqual((left,right),(day-timedelta(microseconds=1),day+timedelta(days=1)-timedelta(microseconds=1)))
                self.assertLess(right,datetime(2018,2,10))
    def test_native_research_and_actual_receiver_full_chain(self):
        for mode in ('direct','content','dual'):
            with self.case(mode=mode):
                b=fork(self.base);charged=b.reg.snapshot()['usage']
                self.assertEqual(b.finish_research(b.parse(mode=mode)).status,'completed');b.no_rows(self)
                b.receiver();self.assertEqual(b.lean_payload['research_resolution'],b.wrapper['cloud_report']['resolution'])
                self.assertEqual(b.lean_wrapper['cloud_report']['statistics']['data_event_count'],6)
                self.assertEqual(b.lean_wrapper['cloud_report']['statistics']['dividend_event_count'],1)
                self.assertEqual(b.finish_lean(mode=mode).status,'completed');b.no_rows(self)
                self.assertEqual(b.reg.snapshot()['usage']['research'],charged['research'])
                self.assertEqual(b.reg.snapshot()['usage']['lean']['total'],charged['lean']['total']+1)
                self.assertFalse(b.bridge.read_result(b.lean_attempt)['financial_evidence'])
    def test_joint_summary_tampering_and_certification_side_loads_rejected(self):
        def summary(report):return report['evidence']['collection_probe']
        cases={
            'foreign_plan':lambda r:summary(r).__setitem__('plan_hash','f'*64),
            'foreign_attempt_path':lambda r:summary(r)['receipt_ref'].__setitem__('key','independent-joint-v2/collection-probes/'+self.base.plan.hash+'/'+'f'*32+'.json'),
            'windows_39':lambda r:summary(r).__setitem__('window_count',39),
            'count_bool':lambda r:summary(r).__setitem__('record_count',True),
            'cache_fetch':lambda r:summary(r).__setitem__('cache_only_source_fetch_calls',1),
            'missing_excess':lambda r:summary(r)['missing_values'].__setitem__('dollar_volume',81),
            'extra_rows':lambda r:summary(r).__setitem__('rows',[SECRET]),
            'financial_cert':lambda r:summary(r).__setitem__('financial_vintage_certified',True),
            'US200_cert':lambda r:summary(r).__setitem__('full_historical_US200_certified',True),
            'availability_cert':lambda r:summary(r).__setitem__('actual_availability_certified',True),
            'row_export_cert':lambda r:summary(r).__setitem__('row_values_exported',True),
            'parent_final_cert':lambda r:r.__setitem__('final_data_accessed',True),
            'missing_summary':lambda r:r['evidence'].pop('collection_probe'),
            'joint_check_disagrees':lambda r:r['checks'].__setitem__('collection_nonempty',False),
        }
        for label,mutate in cases.items():
            with self.case(tamper=label):
                b=fork(self.base);before=deepcopy(b.local._data)
                with self.assertRaises((ValueError,ReceiptParseError)):b.parse(changed(b.wrapper,mutate))
                self.assertEqual(b.local._data,before);self.assertEqual(b.bridge._record(b.attempt)['status'],'started')
    def test_native_carriers_hidden_output_annotations_and_wrong_project(self):
        cases={
            'conflict_text':lambda e:e['result'].__setitem__('content',[{'type':'text','text':SECRET}]),
            'outer_annotation_rows':lambda e:e['result']['content'][0].__setitem__('annotations',{'rows':[SECRET]}),
            'wrong_project':lambda e:e['arguments'].__setitem__('projectId',99944),
            'native_error':lambda e:e['result'].__setitem__('isError',True),
        }
        for label,mutate in cases.items():
            with self.case(native=label):
                b=fork(self.base);env=tool('mcp__quantconnect__jupyter_execute_cell',b.payload,native(b.wrapper));mutate(env)
                with self.assertRaises(ReceiptParseError):b.parse(env=env)
                b.no_rows(self)
        with self.case(native='equal_dual_hidden_display'):
            b=fork(self.base);value=native(b.wrapper);value['outputs'].append({'output_type':'display_data','data':{'text/plain':SECRET}})
            with self.assertRaises(ReceiptParseError):b.parse(env=tool('mcp__quantconnect__jupyter_execute_cell',b.payload,value))
    def test_collection_receipt_replay_zero_fetch_and_corruption_fail_closed(self):
        b=self.base;store=_cloud_store(b.qb.object_store);before=deepcopy(b.qb.object_store.data);calls=len(b.qb.universe_calls)
        with self.case(replay='same-child-same-parent'):
            EXECUTIONS['probe_helper_replays']+=1;observed=_run_collection_probe(b.qb,store,b.plan,b.payload,api=h.API)
            self.assertEqual(observed,b.wrapper['cloud_report']['evidence']['collection_probe'])
            self.assertEqual(b.qb.object_store.data,before);self.assertEqual(len(b.qb.universe_calls),calls)
        for target in ('receipt_identity','payload_bytes'):
            with self.case(corruption=target):
                clone=copy(b.qb);clone.object_store=h.SyntheticObjectStore();clone.object_store.data=deepcopy(before)
                if target=='receipt_identity':
                    ref=b.wrapper['cloud_report']['evidence']['collection_probe']['receipt_ref'];key='aqrp/engineering/v2/'+ref['key']
                    item=json.loads(clone.object_store.data[key]);item['identity']['attempt_id']='f'*32;clone.object_store.data[key]=h.canonical_json(item)
                else:
                    key=next(k for k in clone.object_store.data if '/historical-snapshots/v1/objects/' in k);clone.object_store.data[key]=b'{}'
                with self.assertRaises((ValueError,RuntimeError)):
                    EXECUTIONS['probe_helper_replays']+=1;_run_collection_probe(clone,_cloud_store(clone.object_store),b.plan,b.payload,api=h.API)
                self.assertEqual(len(clone.universe_calls),calls)
    def test_empty_child_observation_is_failed_without_coverage_approval(self):
        with self.case(child='all-empty'):
            b=JointHarness(mode='empty');b.run();summary=b.wrapper['cloud_report']['evidence']['collection_probe']
            self.assertEqual(summary['empty_windows'],40);self.assertEqual(summary['record_count'],0)
            self.assertEqual(b.wrapper['cloud_report']['status'],'failed')
            self.assertEqual(b.finish_research().status,'failed');b.no_rows(self)
            with self.assertRaises(ValueError):b.bridge.claim('lean')
    def test_invalid_native_child_leaves_intent_and_blocks_source_refetch(self):
        for mode in ('raises','outside_end','duplicate','mixed'):
            with self.case(child_response=mode):
                b=JointHarness(mode=mode)
                for repetition in range(2):
                    with self.assertRaises((ValueError,RuntimeError)) as error:b.run()
                    self.assertNotIn(SECRET,str(error.exception))
                self.assertEqual(len(b.qb.universe_calls),1);self.assertEqual(b.qb.history_calls,1)
                self.assertTrue(any('/historical-snapshots/v1/intents/' in k for k in b.qb.object_store.data))
                self.assertNotIn('aqrp/engineering/v2/'+b.payload['report_key'],b.qb.object_store.data)
                self.assertEqual(b.bridge._record(b.attempt)['status'],'started');b.no_rows(self)
    def test_trusted_adapter_worker_error_is_ambiguous_and_not_free_retried(self):
        with self.case(adapter='worker-native-request-error'):
            b=JointHarness(mode='raises',auto_claim=False)
            class Adapter:
                calls=0
                def submit_research(self,payload,*,operation_key):
                    self.calls+=1;self.usage=b.reg.snapshot()['usage']['research']['total'];b.run(payload)
            adapter=Adapter();b.bridge.adapter=adapter;attempt=b.bridge.submit('research')
            self.assertEqual(attempt.status,'ambiguous');self.assertEqual(adapter.usage,10)
            self.assertFalse(b.bridge.submit('research').should_execute);self.assertEqual(adapter.calls,1)
            self.assertEqual(b.reg.snapshot()['usage']['research']['total'],10);b.no_rows(self)
    def test_research_resolution_and_lean_probe_side_loads_bound(self):
        with self.case(binding='receiver-wrong-permanent-SID'):
            b=fork(self.base);b.finish_research()
            with self.assertRaises(ValueError):b.receiver(wrong_sid=True)
        with self.case(binding='lean-cannot-carry-research-probe-summary'):
            b=fork(self.base);b.finish_research();b.receiver()
            bad=changed(b.lean_wrapper,lambda r:r['evidence'].__setitem__('collection_probe',b.wrapper['cloud_report']['evidence']['collection_probe']))
            with self.assertRaises(ReceiptParseError):b.finish_lean(wrapper=bad)
        with self.case(binding='lean-resolution-reference-changed'):
            b=fork(self.base);b.finish_research();b.receiver()
            bad=deepcopy(b.lean_wrapper)
            resolution=bad['cloud_report']['resolution'];resolution['resolved_registry_ref']['key']='other/synthetic-registry.json'
            refs={key:resolution[key] for key in ('resolved_registry_ref','resolved_request_ref')}
            resolution['resolution_artifact_hash']=h.content_hash(refs);bad['report_ref']['sha256']=h.content_hash(bad['cloud_report'])
            with self.assertRaises(ValueError):b.finish_lean(wrapper=bad)

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

stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2,resultclass=AuditResult).run(unittest.defaultTestLoader.loadTestsFromTestCase(IndependentJointWorkerTests))
raw=stream.getvalue();(OUT/'first_run_unittest.txt').write_text(raw,encoding='utf-8')
after={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in FILES}
summary={'commit':'8f7236ecbafcb514f07a6af4150a5afdbc1fd474','command_argv':sys.argv,'python':sys.version,'platform':platform.platform(),
    'numpy':h.np.__version__,'pandas':h.pd.__version__,'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'source_raw_sha256_before':BEFORE,'source_raw_sha256_after':after,'source_unchanged':BEFORE==after,
    'methods':result.testsRun,'subcases':result.subcases,'failure_records':len(result.failures),'error_records':len(result.errors),
    'skipped':len(result.skipped),'success':result.wasSuccessful(),'first_failure':result.first_failure,'inputs':INPUTS,
    'actual_component_invocations':EXECUTIONS,'actual_native_SDK_executed':False,
    'actions':{'network':0,'Research':0,'LEAN':0,'market':0,'models':0,'deployment':0,'authoritative_budget_changes':0,'candidate_source_edits':0},
    'limits':'Invented weekday calendar, constant OHLCV, synthetic universe points and actual pure-Python workers/receiver functions; no real SDK/Research/LEAN/data certification'}
(OUT/'first_run_summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf-8')
print(raw);print(json.dumps({k:v for k,v in summary.items() if k not in {'inputs','first_failure','source_raw_sha256_after'}},ensure_ascii=False))
sys.exit(0 if result.wasSuccessful() and summary['source_unchanged'] else 1)
