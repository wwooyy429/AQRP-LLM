"""Synthetic diagnostic reproduction; no provider, SDK, cloud or paid task."""
from pathlib import Path
import hashlib
import json
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'cloud'))
import numpy as np
from qresearch.artifacts import ArtifactConflict
from qresearch.collection import HistoricalCollectionPlan, HistoricalSnapshotCollector, CollectionError
from qresearch.historical_source import _scalar
from qresearch.quantconnect import ObjectStoreArtifactStore

OUT=Path(__file__).resolve().parent
OUT.mkdir(parents=True,exist_ok=True)
CATALOG={
    'dollar_volume':{'kind':'number','role':'liquidity','unit':'USD','period_accessor':None},
    'has_fundamental_data':{'kind':'boolean','role':'coverage','unit':'boolean','period_accessor':None},
    'time':{'kind':'text','role':'clock','unit':'timestamp','period_accessor':None},
    'end_time':{'kind':'text','role':'clock','unit':'timestamp','period_accessor':None},
}
PLAN=HistoricalCollectionPlan.from_dict(dict(schema_version=2,plan_id='synthetic-round005',scope='engineering',
    source='quantconnect_fundamental_universe',data_version='synthetic',start='2018-01-02T00:00:00-05:00',
    end_exclusive='2018-01-03T00:00:00-05:00',timezone='America/New_York',fields=list(CATALOG),
    calendar_days_per_request=1,max_batch_records=1000,max_records_per_window=50000,
    source_manifest_hash='a'*64,observation_policy='retain_source_occurrences'),field_catalog=CATALOG)


class NativeObjectStore:
    def __init__(self,mode):
        self.data={};self.mode=mode;self.saves=[]
    def contains_key(self,key):return key in self.data
    def read_bytes(self,key):
        if self.mode=='batch_readback_mismatch' and '/objects/' in key:return b'wrong'
        return self.data[key]
    def save_bytes(self,key,data):
        self.saves.append({'category':key.split('/')[-2],'bytes':len(data)})
        if self.mode=='batch_save_rejected' and '/objects/' in key:return False
        if self.mode=='manifest_save_rejected' and '/windows/' in key:return False
        self.data[key]=bytes(data);return True


class Source:
    def fetch(self,start,end,catalog):
        for i in range(1002):
            values={'dollar_volume':_scalar(np.float64(i+1.25),'number'),
                'has_fundamental_data':_scalar(np.bool_(True),'boolean'),
                'time':'2018-01-01T00:00:00','end_time':'2018-01-02T00:00:00'}
            yield {'sid':'SYNTHETIC'+str(i),'snapshot_at':'2018-01-02T00:00:00-05:00',
                'values':values,'source_record_index':i}


results=[]
for mode in ('normal','batch_save_rejected','batch_readback_mismatch','manifest_save_rejected'):
    native=NativeObjectStore(mode)
    store=ObjectStoreArtifactStore(native,'synthetic-rootcause005',read_only=False,single_producer=True)
    collector=HistoricalSnapshotCollector(store,Source(),PLAN,synthetic=True)
    try:
        result=collector.collect()
        replay=HistoricalSnapshotCollector(store,None,PLAN,synthetic=True).collect()
        assert result['record_count']==replay['record_count']==1002
        assert replay['provider_calls']==0
        outcome={'mode':mode,'success':True,'record_count':result['record_count'],'cache_replay_provider_calls':0}
    except CollectionError as error:
        outcome={'mode':mode,'success':False,'outer_type':type(error).__name__,'outer_message':str(error),
            'hidden_context_type':type(error.__context__).__name__,'context_suppressed':error.__suppress_context__}
        assert outcome['outer_message']=='Historical source collection failed; unfinished intent retained'
    outcome['save_attempts']=native.saves
    outcome['intent_exists']=any('/intents/' in key for key in native.data)
    outcome['completed_manifest_exists']=any('/windows/' in key for key in native.data)
    results.append(outcome)
assert results[0]['success'] and len(results[0]['save_attempts'])==4
assert all(not r['success'] and r['intent_exists'] and not r['completed_manifest_exists'] for r in results[1:])
assert {r['hidden_context_type'] for r in results[1:]}=={'OSError','ArtifactConflict'}
report={'kind':'synthetic_nonidentifiable_collection_failure_MRE','source_commit':'0f6d8c0606d1e3253632b167cab73dd04d03658a',
    'cases':results,'real_market_data_used':False,'cloud_calls':0,'research_executions':0,'LEAN_submissions':0,
    'conclusion':'Normal four-field native-scalar conversion/batching passes; at least two distinct hidden exception types at three storage steps yield identical observed generic error. This does not prove which occurred in actual round005.'}
(OUT/'collection_probe_mre_result.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report))
