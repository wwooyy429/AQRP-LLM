import argparse,json,sys
from copy import deepcopy
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);a=p.parse_args()
sys.dont_write_bytecode=True;sys.path.insert(0,str(a.source.resolve()/'cloud'))
from qresearch.artifacts import MemoryArtifactStore
from qresearch.collection import HistoricalCollectionPlan,HistoricalSnapshotCollector,CollectionError
catalog={'dollar_volume':{'kind':'number','role':'synthetic_liquidity','unit':'USD','period_accessor':None}}
plan=HistoricalCollectionPlan.from_dict(dict(schema_version=2,observation_policy='retain_source_occurrences',
 plan_id='review-known-answer',scope='engineering',source='quantconnect_fundamental_universe',
 data_version='synthetic-v1',start='2018-01-03T00:00:00-05:00',end_exclusive='2018-01-04T00:00:00-05:00',
 timezone='America/New_York',fields=['dollar_volume'],calendar_days_per_request=1,max_batch_records=2,
 max_records_per_window=10,source_manifest_hash='1'*64),field_catalog=catalog)
rows=[dict(sid=sid,snapshot_at='2018-01-03T09:00:00-05:00',source_record_index=i,
 values={'dollar_volume':v})for i,(sid,v)in enumerate([('A',1),('A',1),('B',2),('A',3),('A',1)])]
class Source:
 calls=0
 def __init__(self,data):self.data=data
 def fetch(self,*args):self.calls+=1;return iter(deepcopy(self.data))
store=MemoryArtifactStore();source=Source(rows)
writer=HistoricalSnapshotCollector(store,source,plan,synthetic=True);first=writer.collect()
assert(first['record_count'],first['duplicate_projection_records'],first['conflicting_projection_records'])==(5,3,1)
assert writer.read_window(first['window_refs'][0])==rows
batch_count=len(json.loads(store.read_bytes(first['window_refs'][0]['key']))['batches']);assert batch_count==3
before=dict(store._data);reader=HistoricalSnapshotCollector(store,None,plan,synthetic=True);again=reader.collect()
assert again['provider_calls']==0 and again['record_count']==5 and source.calls==1 and store._data==before
assert reader.read_window(again['window_refs'][0])==rows
bad=deepcopy(rows);bad[-1]['source_record_index']=6
try:HistoricalSnapshotCollector(MemoryArtifactStore(),Source(bad),plan,synthetic=True).collect()
except CollectionError:pass
else:raise AssertionError('A source ordinal gap was accepted')
assert first['full_historical_US200_certified']is False and first['research_certified']is False
print(json.dumps({'retained':5,'duplicate_projections':3,'conflicts_against_first':1,
 'batches':batch_count,'cache_source_calls':0,'index_gap_rejected':True,'financial_evidence':False}))
