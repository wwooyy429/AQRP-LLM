"""Offline, independent, native-shape source review; never imports author fixtures."""
import copy
from datetime import datetime, date
from hashlib import sha256
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace as NS
import unittest
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "source"
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC / "cloud"))
from qresearch.historical_source import QuantConnectSnapshotSource, HistoricalSourceError, observed_liquidity_record
from qresearch.collection import HistoricalCollectionPlan, HistoricalSnapshotCollector
from qresearch.artifacts import MemoryArtifactStore
from qresearch.ingestion import HistoricalBatchIngestor, MissingPITEvidence

CAT = json.loads((SRC / "config/source_catalog.json").read_text())
FIELDS = CAT["fields"]
NY = ZoneInfo("America/New_York")
OBSERVATIONS = {}
def at(s): return pd.Timestamp(s, tz=NY)

class Symbol:
    def __init__(self, sid, ticker="SYNTHETIC-TICKER"):
        self.id, self.ticker = sid, ticker
    def __str__(self): return self.ticker

def fundamental(sid="SYNTHETIC-SID-A", **kwargs):
    item = NS(symbol=Symbol(sid), dollar_volume=17.5, has_fundamental_data=False,
        time=datetime(2017, 5, 22), end_time=datetime(2017, 5, 23), market_cap=12345,
        security_reference=NS(security_type="ST00000001", common_share_sub_type="",
            is_depositary_receipt=False, share_class_status="I", exchange_id="NAS"),
        company_reference=NS(is_reit=False),
        financial_statements=NS(period_ending_date=NS(value=date(2017, 3, 31)),
            file_date=NS(value=date(2017, 5, 1)), accession_number=NS(value="SYNTHETIC-0001"),
            form_type=NS(value="10-Q")))
    for k,v in kwargs.items(): setattr(item,k,v)
    return item

def series(items=None, times=None, universes=None):
    items = [[fundamental()]] if items is None else items
    times = [datetime(2017,5,23)] * len(items) if times is None else times
    universes = ["SYNTHETIC-UNIVERSE"] * len(items) if universes is None else universes
    return pd.Series(items, index=pd.MultiIndex.from_arrays([universes,times], names=["symbol","time"]),dtype=object)

class QB:
    def __init__(self,response=None):
        self.response = series() if response is None else response
        self.time = datetime(2017,5,30)
        self.universe_settings=NS(resolution=None)
        self.calls=[]
        self.universe=NS(symbol=Symbol("SYNTHETIC-UNIVERSE-SID", "SYNTHETIC-UNIVERSE"))
    def set_time_zone(self,z): self.zone=z
    def add_universe(self,f): self.selector=f; return self.universe
    def universe_history(self,*args,**kwargs):
        self.calls.append((args,kwargs)); return self.response

def source(response=None):
    qb=QB(response)
    return QuantConnectSnapshotSource(qb,FIELDS,api=NS(Resolution=NS(DAILY="daily"))),qb

def fetch(src, fields=None, start=None, end=None):
    return list(src.fetch(at("2017-05-23") if start is None else start,
        at("2017-05-24") if end is None else end,FIELDS if fields is None else fields))

def plan(fields=None):
    return HistoricalCollectionPlan.from_dict({"schema_version":1,"plan_id":"independent-SYNTHETIC-only",
        "scope":"engineering","source":"quantconnect_fundamental_universe","data_version":"SYNTHETIC-v1",
        "start":at("2017-05-23").isoformat(),"end_exclusive":at("2017-05-24").isoformat(),
        "timezone":"America/New_York","fields":list(FIELDS if fields is None else fields),
        "calendar_days_per_request":1,"max_batch_records":2,"max_records_per_window":100,
        "source_manifest_hash":"1"*64},field_catalog=FIELDS)

class IndependentSourceTests(unittest.TestCase):
    def test_complete_projection_and_no_coverage_screen(self):
        a,b=fundamental("SYNTHETIC-1"),fundamental("SYNTHETIC-2")
        b.dollar_volume=0; b.market_cap=float("nan")
        b.financial_statements=None
        src,qb=source(series([[a,b]])); rows=fetch(src)
        self.assertEqual([r["sid"] for r in rows],["SYNTHETIC-1","SYNTHETIC-2"])
        self.assertEqual(src._all_symbols([a,b]),[a.symbol,b.symbol])
        self.assertFalse(rows[0]["values"]["has_fundamental_data"])
        self.assertEqual(rows[1]["values"]["dollar_volume"],0)
        self.assertIsNone(rows[1]["values"]["market_cap"])
        self.assertEqual(set(rows[0]["values"]),set(FIELDS))
        self.assertEqual(rows[0]["values"]["financial_statements.file_date.value"],"2017-05-01")
        self.assertEqual(rows[0]["values"]["time"],"2017-05-22T00:00:00")
        self.assertEqual(rows[0]["snapshot_at"],"2017-05-23T00:00:00-04:00")
        self.assertEqual(len(qb.calls),1)
        self.assertEqual(qb.calls[0][1],{"flatten":False})
        self.assertIsNone(qb.calls[0][0][1].tzinfo)

    def test_subset_frozen_definitions(self):
        src,qb=source(); subset={"dollar_volume":FIELDS["dollar_volume"]}
        self.assertEqual(fetch(src,subset)[0]["values"],{"dollar_volume":17.5})
        for altered in ({"price":FIELDS["dollar_volume"]},
                {"dollar_volume":{**FIELDS["dollar_volume"],"unit":"shares"}}):
            with self.subTest(altered=altered):
                before=len(qb.calls)
                with self.assertRaises(HistoricalSourceError): fetch(src,altered)
                self.assertEqual(len(qb.calls),before)

    def test_scalar_types_missing_and_zero(self):
        cases=[("dollar_volume",True), ("dollar_volume","17"),("dollar_volume",float("inf")),
            ("has_fundamental_data",2),("has_fundamental_data","False"),("market_cap",{}),
            ("security_reference.security_type",17),("financial_statements.file_date.value","2017-5-1"),
            ("financial_statements.file_date.value","2017-05-01T00:00:00"),
            ("financial_statements.form_type.value",lambda: "10-Q")]
        for path,value in cases:
            with self.subTest(path=path,value=repr(value)):
                item=fundamental(); target=item
                parts=path.split(".")
                for name in parts[:-1]: target=getattr(target,name)
                setattr(target,parts[-1],value)
                src,_=source(series([[item]]))
                with self.assertRaises(HistoricalSourceError): fetch(src)
        for value in (None,np.nan,pd.NA):
            with self.subTest(missing=repr(value)):
                src,_=source(series([[fundamental(dollar_volume=value)]]))
                self.assertIsNone(fetch(src)[0]["values"]["dollar_volume"])
        for value,expected in ((np.int64(0),0),(np.float64(17.5),17.5)):
            with self.subTest(numeric=repr(value)):
                src,_=source(series([[fundamental(dollar_volume=value)]]))
                self.assertEqual(fetch(src)[0]["values"]["dollar_volume"],expected)

    def test_clocks_dst_utc_and_window_boundaries(self):
        for start,end in (("2017-03-10","2017-03-17"),("2017-11-01","2017-11-08")):
            with self.subTest(start=start):
                src,qb=source(series(times=[pd.Timestamp(start).to_pydatetime()]))
                qb.time=pd.Timestamp(end).to_pydatetime()
                rows=fetch(src,start=at(start).tz_convert("UTC"),end=at(end).tz_convert("UTC"))
                self.assertEqual(pd.Timestamp(rows[0]["snapshot_at"]),at(start))
        for start,end in (("2017-05-23","2017-05-31"),("2017-05-23 12:00","2017-05-24"),
                ("2024-01-01","2024-01-02"),("2017-05-24","2017-05-23")):
            with self.subTest(start=start,end=end):
                src,qb=source()
                with self.assertRaises(HistoricalSourceError): fetch(src,start=at(start),end=at(end))
                self.assertEqual(len(qb.calls),0)
        for naive in (datetime(2017,5,23),"2017-05-23",pd.NaT):
            with self.subTest(naive=repr(naive)):
                src,qb=source()
                with self.assertRaises(HistoricalSourceError): fetch(src,start=naive)
                self.assertEqual(len(qb.calls),0)
        for frontier in (datetime(2017,5,23),datetime(2024,1,2)):
            with self.subTest(frontier=repr(frontier)):
                src,qb=source();qb.time=frontier
                with self.assertRaises(HistoricalSourceError): fetch(src)
                self.assertEqual(len(qb.calls),0)

    def test_sid_universe_shape_and_duplicate_rejection(self):
        without=NS(dollar_volume=1)
        bad_sid=[None,""," "," SID ","X"*257]
        responses=[pd.DataFrame(),pd.Series([[fundamental()]],index=[datetime(2017,5,23)]),
            series([[fundamental(),fundamental()]]),series([[without]]),
            series([[fundamental()]],universes=["WRONG-UNIVERSE"]),
            series([[fundamental()],[fundamental()]],times=[datetime(2017,5,23)]*2),
            series([[fundamental()]],times=[datetime(2017,5,24)]),
            series([[fundamental()]],times=[datetime(2017,5,22)]),
            series([NS(symbol=Symbol("X"))])]
        for sid in bad_sid: responses.append(series([[fundamental(sid)]]))
        tickeronly=fundamental();tickeronly.symbol="SYNTHETIC-TICKER";responses.append(series([[tickeronly]]))
        renamed=series();renamed.index=renamed.index.set_names(["time","symbol"]);responses.append(renamed)
        for i,response in enumerate(responses):
            with self.subTest(case=i):
                src,_=source(response)
                with self.assertRaises(HistoricalSourceError): fetch(src)

    def test_classification_primary_contract(self):
        src,_=source(); row=fetch(src)[0]
        for code,expected in (("A",True),("I",True),("D",False),("O",False),("?",None),(None,None)):
            with self.subTest(status=code):
                r=copy.deepcopy(row);r["values"]["security_reference.share_class_status"]=code
                self.assertIs(observed_liquidity_record(r,session_close=at("2017-05-22 16:00"))["listed"],expected)
        cases=[({},"common_stock"),({"security_reference.security_type":"ST00000002"},"preferred_stock"),
            ({"security_reference.security_type":"ST000000A1"},"unit"),
            ({"security_reference.common_share_sub_type":"Closed-End Fund"},"closed_end_fund"),
            ({"security_reference.common_share_sub_type":"Foreign Share"},None),
            ({"security_reference.security_type":"unknown"},None),
            ({"security_reference.is_depositary_receipt":True},"adr"),({"company_reference.is_reit":True},"reit_common")]
        for changes,expected in cases:
            with self.subTest(classification=changes):
                r=copy.deepcopy(row);r["values"].update(changes)
                self.assertEqual(observed_liquidity_record(r,session_close=at("2017-05-22 16:00"))["instrument_type"],expected)

    def test_bridge_ingestion_preserves_unknown_and_rejects_pit(self):
        src,_=source();r=fetch(src)[0]
        # Deceptive source "values" are not evidence and do not get promoted.
        r["values"].update(vendor_available_at="2017-05-22T17:00:00-04:00",
            actual_availability_certified=True,availability_basis="actual_historical_receipt")
        bridge=observed_liquidity_record(r,session_close=at("2017-05-22 16:00"))
        for key in ("vendor_available_at","historical_ingested_at","classification_effective_at",
                "classification_available_at","listing_effective_at","listing_available_at"):
            with self.subTest(unknown=key): self.assertIsNone(bridge[key])
        self.assertEqual(bridge["availability_basis"],"unknown")
        self.assertTrue(bridge["source_revision"].startswith("observed_snapshot:"))
        store=MemoryArtifactStore()
        ing=HistoricalBatchIngestor(store,source="SYNTHETIC-source",data_version="SYNTHETIC-v1",
            origin="historical_declared_fixture",synthetic=True)
        receipt=ing.ingest("liquidity",[bridge],partition="independent")
        self.assertFalse(receipt["actual_source_timing_certified"])
        self.assertEqual(receipt["gaps"]["actual_availability_unverified"],1)
        with self.assertRaises(MissingPITEvidence):
            ing.liquidity_rows_asof(receipt["batch_ref"],at("2017-05-23 09:00"),[at("2017-05-22 16:00")])
        for key,value in src.provenance().items():
            if key.endswith("certified"):
                with self.subTest(provenance=key): self.assertIs(value,False)
        for close in (at("2017-05-23"),at("2017-05-24"),"2017-05-22 16:00"):
            with self.subTest(bad_close=str(close)):
                with self.assertRaises(HistoricalSourceError): observed_liquidity_record(r,session_close=close)

    def test_date_no_value_sentinel_remains_missing(self):
        # LEAN MultiPeriodField<DateTime>.NoValue is default(DateTime),
        # represented here as native Python datetime.min. This is not SDK execution.
        item=fundamental()
        item.financial_statements.period_ending_date=NS(value=datetime.min,has_value=False)
        item.financial_statements.file_date=NS(value=datetime.min,has_value=False)
        src,_=source(series([[item]]))
        p=plan();store=MemoryArtifactStore();collector=HistoricalSnapshotCollector(store,src,p,synthetic=True)
        result=collector.collect()
        row=collector.read_window(result["window_refs"][0])[0]
        OBSERVATIONS["missing_date_projection"]={"row":row,"collection":result}
        for path in ("financial_statements.period_ending_date.value","financial_statements.file_date.value"):
            with self.subTest(path=path): self.assertIsNone(row["values"][path])

class Recorder(unittest.TextTestResult):
    def __init__(self,*a,**k):
        super().__init__(*a,**k);self.subtests=0;self.records=[]
    def addSubTest(self,test,subtest,err):
        self.subtests+=1
        if err is not None:self.records.append({"test":str(subtest),"traceback":self._exc_info_to_string(err,test)})
        super().addSubTest(test,subtest,err)
    def addError(self,test,err):
        self.records.append({"test":str(test),"traceback":self._exc_info_to_string(err,test)})
        super().addError(test,err)

if __name__=="__main__":
    files=list((SRC/"cloud").rglob("*.py"))+[SRC/"config/source_catalog.json"]
    before={str(p.relative_to(SRC)):sha256(p.read_bytes()).hexdigest() for p in files}
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(IndependentSourceTests)
    stream=io.StringIO()
    result=unittest.TextTestRunner(stream=stream,verbosity=2,resultclass=Recorder).run(suite)
    output=stream.getvalue();print(output,end="")
    errors=len(result.errors);failures=len(result.failures)
    failed_methods={x["test"].split(" (")[0] for x in result.records}
    report={"candidate_sha":"fbe2454e6ea10aa59211c01f236c54bb251527be","methods":result.testsRun,
        "subtests":result.subtests,"failure_records":failures,"errors":errors,"skips":len(result.skipped),
        "failing_or_error_methods":len(failed_methods),"passed_methods":result.testsRun-len(failed_methods),
        "first_failure":result.records[0] if result.records else None,"all_failures":result.records,
        "observations":OBSERVATIONS,"source_unchanged":before=={str(p.relative_to(SRC)):sha256(p.read_bytes()).hexdigest() for p in files},
        "environment":{"python":sys.version,"numpy":np.__version__,"pandas":pd.__version__},
        "real_sdk_executed":False,"platform_calls":0,"financial_evidence":False}
    (OUT/"source_review_output_first.txt").write_text(output,encoding="utf-8")
    (OUT/"source_review_results_first.json").write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
    sys.exit(not result.wasSuccessful())
