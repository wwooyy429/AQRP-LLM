"""SDK-contract-shaped offline probe for (start,end] history indexing."""
from pathlib import Path
from datetime import datetime
from types import SimpleNamespace as NS
import json,socket,sys
import pandas as pd
ROOT=Path(__file__).parent;source=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else ROOT/'source'
sys.path.insert(0,str(source/'cloud'))
from qresearch.historical_source import QuantConnectSnapshotSource
class Symbol:
    def __init__(self,sid):self.id=sid
class QB:
    def __init__(self):
        self.time=datetime(2018,1,5);self.universe_settings=NS(resolution=None);self.symbol=Symbol('AUDIT-UNIVERSE')
        self.calls=[];self.returned=[]
    def set_time_zone(self,zone):pass
    def add_universe(self,selector):return NS(symbol=self.symbol)
    def universe_history(self,universe,start,end,*,flatten):
        self.calls.append([start.isoformat(),end.isoformat()])
        stamps=[t for t in [datetime(2018,1,3),datetime(2018,1,4)] if start<t<=end]
        self.returned.extend(t.isoformat() for t in stamps)
        index=pd.MultiIndex.from_tuples([(self.symbol,pd.Timestamp(t)) for t in stamps],names=['symbol','time'])
        return pd.Series([[NS(symbol=Symbol('AUDIT-SID'),dollar_volume=100.)] for t in stamps],index=index,dtype=object)
def denied(*args,**kwargs):raise AssertionError('Offline history-boundary probe forbids networking')
socket.socket.connect=denied
catalog=json.loads((source/'config/source_catalog.json').read_text(encoding='utf-8'))['fields'];selected={'dollar_volume':catalog['dollar_volume']}
qb=QB();native=QuantConnectSnapshotSource(qb,catalog,api=NS(Resolution=NS(DAILY='audit_daily')))
try:
    rows=list(native.fetch(pd.Timestamp('2018-01-03',tz='America/New_York'),pd.Timestamp('2018-01-04',tz='America/New_York'),selected))
    error=None
except Exception as exc:
    rows=None;error={'type':type(exc).__name__,'message':str(exc)}
result={'source_commit':'fbe2454e6ea10aa59211c01f236c54bb251527be','real_SDK_executed':False,
    'upstream_contract':'history accepts EndTime > start and EndTime <= end; pandas index=EndTime',
    'requested_plan_interval':'[2018-01-03T00:00:00-05:00,2018-01-04T00:00:00-05:00)',
    'actual_history_arguments':qb.calls,'SDK_contract_returned':qb.returned,'rows':rows,'error':error,
    'expected_snapshot_times':['2018-01-03T00:00:00-05:00']}
print(json.dumps(result,indent=2))
assert error is None,'Map the SDK history interval to the frozen half-open plan before fetching'
assert [row['snapshot_at'] for row in rows]==result['expected_snapshot_times']
