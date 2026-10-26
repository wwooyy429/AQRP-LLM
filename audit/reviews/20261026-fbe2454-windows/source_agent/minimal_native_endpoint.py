"""WR-10 offline MRE: official end-time contract, no actual QuantBook/API."""
from datetime import datetime
import json
from pathlib import Path
import sys
from types import SimpleNamespace as NS
import pandas as pd

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/"source/cloud"))
from qresearch.historical_source import QuantConnectSnapshotSource

class Symbol:
    id="SYNTHETIC-UNIVERSE-SID"
    def __str__(self): return "SYNTHETIC-UNIVERSE"

class QB:
    time=datetime(2017,5,30)
    universe_settings=NS(resolution=None)
    calls=[]
    def set_time_zone(self,zone): self.zone=zone
    def add_universe(self,selector): return NS(symbol=Symbol())
    def universe_history(self,universe,start,end,*,flatten):
        self.calls.append([start.isoformat(),end.isoformat(),flatten])
        # Source date 2017-05-23 has EndTime=2017-05-24, and the official
        # provider accepts it because start < EndTime <= end.
        stamp=datetime(2017,5,24)
        assert start < stamp <= end
        item=NS(symbol=NS(id="SYNTHETIC-STOCK-SID"),dollar_volume=1)
        index=pd.MultiIndex.from_tuples([("SYNTHETIC-UNIVERSE",stamp)],names=["symbol","time"])
        return pd.Series([[item]],index=index,dtype=object)

fields={"dollar_volume":{"kind":"number","role":"supplied_daily_liquidity","unit":"USD","period_accessor":None}}
qb=QB();src=QuantConnectSnapshotSource(qb,fields,api=NS(Resolution=NS(DAILY="daily")))
error=None;rows=None
try:
    rows=list(src.fetch(pd.Timestamp("2017-05-23",tz="America/New_York"),
        pd.Timestamp("2017-05-24",tz="America/New_York"),fields))
except Exception as exc:error={"type":type(exc).__name__,"message":str(exc)}
result={"candidate":"fbe2454e6ea10aa59211c01f236c54bb251527be","native_contract":"start < EndTime <= end",
    "native_response_index":"2017-05-24T00:00:00","rows":rows,"error":error,"native_request":qb.calls,
    "real_sdk_executed":False,"research_or_market_calls":0}
text=json.dumps(result,indent=2);print(text)
(Path(__file__).resolve().parent/"minimal_native_endpoint_result.json").write_text(text,encoding="utf-8")
sys.exit(error is not None)
