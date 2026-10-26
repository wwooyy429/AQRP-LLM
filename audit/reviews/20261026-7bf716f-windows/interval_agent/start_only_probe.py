"""Public-API zero-at-start counterexample; independent synthetic QB only."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import socket
import sys
from types import SimpleNamespace as NS
from zoneinfo import ZoneInfo

cli=argparse.ArgumentParser()
cli.add_argument('--source',required=True)
cli.add_argument('--label',required=True)
cli.add_argument('--out',required=True)
arg=cli.parse_args()
root=Path(arg.source).resolve()
sys.path.insert(0,str(root/'cloud'))
import pandas as pd
from qresearch.artifacts import MemoryArtifactStore
from qresearch.collection import HistoricalCollectionPlan, HistoricalSnapshotCollector
from qresearch.historical_source import QuantConnectSnapshotSource
def no_network(*args,**kwargs): raise AssertionError('network prohibited')
socket.socket=no_network
ny=ZoneInfo('America/New_York')
left=pd.Timestamp('2018-01-03',tz=ny); right=pd.Timestamp('2018-01-04',tz=ny)
catalog={'dollar_volume':{'kind':'number','role':'independent_synthetic','unit':'USD','period_accessor':None}}
api=NS(Resolution=NS(DAILY='independent_daily'))
class QB:
    def __init__(self):
        self.time=datetime(2018,1,4); self.universe_settings=NS(); self.calls=[]
    def set_time_zone(self,zone): assert zone=='America/New_York'
    def add_universe(self,selector): return 'INDEPENDENT-START-UNIVERSE'
    def universe_history(self,universe,start,end,*,flatten):
        self.calls.append((start.isoformat(),end.isoformat()))
        assert flatten is False
        # Single daily point, exactly at frozen start; no end point exists.
        clock=datetime(2018,1,3)
        stamps=[clock] if start<clock<=end else []
        index=pd.MultiIndex.from_tuples([(universe,x) for x in stamps],names=['symbol','time'])
        return pd.Series([[NS(symbol=NS(id='INDEPENDENT-START-SID'),dollar_volume=0)] for _ in stamps],index=index,dtype=object)
qb=QB(); source=QuantConnectSnapshotSource(qb,catalog,api=api)
rows=list(source.fetch(left,right,catalog))
direct={'expected_records':1,'actual_records':len(rows),'passes':len(rows)==1,'native_endpoints':qb.calls}
qb2=QB(); source2=QuantConnectSnapshotSource(qb2,catalog,api=api)
frozen=HistoricalCollectionPlan.from_dict({'schema_version':1,'plan_id':'INDEPENDENT-START','scope':'engineering',
    'source':'quantconnect_fundamental_universe','data_version':'independent-start-v1',
    'start':left.isoformat(),'end_exclusive':right.isoformat(),'timezone':'America/New_York',
    'fields':list(catalog),'calendar_days_per_request':1,'max_batch_records':1,'max_records_per_window':2,
    'source_manifest_hash':hashlib.sha256((root/'cloud/qresearch/historical_source.py').read_bytes()).hexdigest()},field_catalog=catalog)
collector=HistoricalSnapshotCollector(MemoryArtifactStore(),source2,frozen,synthetic=True)
receipt=collector.collect()
chain={'expected_records':1,'actual_records':receipt['record_count'],'passes':receipt['record_count']==1,
    'empty_windows':receipt['empty_windows'],'provider_calls':receipt['provider_calls'],
    'native_endpoints':qb2.calls,'actual_availability_certified':receipt['actual_availability_certified']}
result={'label':arg.label,'argv':sys.argv,'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'source_sha256':hashlib.sha256((root/'cloud/qresearch/historical_source.py').read_bytes()).hexdigest(),
    'synthetic_input':{'start':left.isoformat(),'end':right.isoformat(),'only_EndTime':left.isoformat(),'sid':'INDEPENDENT-START-SID','dollar_volume':0},
    'direct':direct,'collector':chain,'passes':direct['passes'] and chain['passes'],
    'real_SDK_executed':False,'market_calls':0}
Path(arg.out).write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps(result,indent=2,ensure_ascii=False))
sys.exit(0 if result['passes'] else 1)
