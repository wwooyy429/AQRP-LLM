"""Offline native-shaped missing-date probe; no real SDK/provider execution."""
from pathlib import Path
from datetime import datetime
from types import SimpleNamespace as NS
import json,socket,sys
import pandas as pd
ROOT=Path(__file__).parent
source=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else ROOT/'source'
sys.path.insert(0,str(source/'cloud'))
from qresearch.collection import HistoricalCollectionPlan,HistoricalSnapshotCollector
from qresearch.historical_source import QuantConnectSnapshotSource
from qresearch.artifacts import MemoryArtifactStore
def denied(*args,**kwargs):raise AssertionError('Offline source probe forbids networking')
socket.socket.connect=denied
class Symbol:
    def __init__(self,sid):self.id=sid
class MissingDate:
    value=datetime.min
    has_value=False
    is_none=True
class QB:
    def __init__(self):
        self.time=datetime(2018,1,4);self.universe_settings=NS(resolution=None)
        self.symbol=Symbol('AUDIT-UNIVERSE');self.calls=0
    def set_time_zone(self,zone):pass
    def add_universe(self,selector):return NS(symbol=self.symbol)
    def universe_history(self,universe,start,end,*,flatten):
        self.calls+=1
        item=NS(symbol=Symbol('AUDIT-SID-NO-FUNDAMENTALS'),has_fundamental_data=False,
                financial_statements=NS(file_date=MissingDate(),period_ending_date=MissingDate()))
        index=pd.MultiIndex.from_tuples([(self.symbol,pd.Timestamp('2018-01-03'))],names=['symbol','time'])
        return pd.Series([[item]],index=index,dtype=object)
catalog=json.loads((source/'config/source_catalog.json').read_text(encoding='utf-8'))['fields']
fields=['financial_statements.file_date.value','financial_statements.period_ending_date.value']
plan=HistoricalCollectionPlan.from_dict({'schema_version':1,'plan_id':'independent-missing-date','scope':'engineering',
    'source':'quantconnect_fundamental_universe','data_version':'synthetic-native-date-sentinel','start':'2018-01-03T00:00:00-05:00',
    'end_exclusive':'2018-01-04T00:00:00-05:00','timezone':'America/New_York','fields':fields,
    'calendar_days_per_request':1,'max_batch_records':2,'max_records_per_window':10,
    'source_manifest_hash':'ccdd21bafb51f75c089a9089636b18389613446cf69dfa4ca7f029ded0f012bb'},field_catalog=catalog)
qb=QB();native=QuantConnectSnapshotSource(qb,catalog,api=NS(Resolution=NS(DAILY='audit_daily')))
collector=HistoricalSnapshotCollector(MemoryArtifactStore(),native,plan,synthetic=True)
summary=collector.collect();rows=collector.read_window(summary['window_refs'][0]);second=collector.collect()
result={'source_commit':'fbe2454e6ea10aa59211c01f236c54bb251527be','evidence':'offline synthetic native shape, not actual SDK',
    'rows':rows,'missing_values':summary['missing_values'],'provider_calls_total':qb.calls,
    'second_new_calls':second['provider_calls'],'certification':{k:v for k,v in summary.items() if 'certified' in k},
    'expected_values':{f:None for f in fields},'expected_missing_values':{f:1 for f in fields}}
print(json.dumps(result,indent=2))
assert all(rows[0]['values'][f] is None for f in fields), 'Native missing-date sentinel must remain missing'
assert summary['missing_values']==result['expected_missing_values']
