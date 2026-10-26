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
from qresearch.engineering_receipts import (_native,_research_stdout,ReceiptParseError,
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

