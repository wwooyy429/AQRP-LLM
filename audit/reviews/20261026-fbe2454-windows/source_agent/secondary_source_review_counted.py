"""Extra review cases, added after initial run; primary SDK contract replay only."""
from datetime import datetime
import io
import json
from pathlib import Path
import sys
import unittest
from independent_source_review import (NS,QB,Symbol,series,fundamental,source,fetch,at,FIELDS,
    QuantConnectSnapshotSource,HistoricalSourceError,HistoricalCollectionPlan,
    HistoricalSnapshotCollector,MemoryArtifactStore,plan,Recorder)
from qresearch.collection import CollectionError

OUT=Path(__file__).resolve().parent
OBS={}

class EndTimeReplayQB(QB):
    """Replay LEAN's TimeBasedFilter; this class makes no network calls.

    Official f3d841e provider keeps start < EndTime <= end. PandasData uses
    EndTime as Series index. Input data are independently invented objects.
    """
    def universe_history(self,universe,start,end,*,flatten):
        self.calls.append(((universe,start,end),{"flatten":flatten}))
        days=[datetime(2017,5,d) for d in range(21,31)]
        accepted=[d for d in days if start < d <= end]
        return series([[fundamental("SYNTHETIC-"+str(d.day))] for d in accepted],times=accepted)

class AdditionalSourceTests(unittest.TestCase):
    def test_valid_fallback_dates_and_zero_remain_values(self):
        item=fundamental(dollar_volume=0)
        # HasValue concerns the default period; Value may be valid via fallback.
        item.financial_statements.file_date=NS(has_value=False,value=datetime(2016,12,7))
        item.financial_statements.period_ending_date=NS(has_value=False,value=datetime(2016,9,30))
        src,_=source(series([[item]]));row=fetch(src)[0]
        self.assertEqual(row["values"]["financial_statements.file_date.value"],"2016-12-07")
        self.assertEqual(row["values"]["financial_statements.period_ending_date.value"],"2016-09-30")
        self.assertEqual(row["values"]["dollar_volume"],0)

    def test_native_endtime_contract_maps_exact_selection_window(self):
        for days in (1,2,7):
            with self.subTest(days=days):
                qb=EndTimeReplayQB()
                src=QuantConnectSnapshotSource(qb,FIELDS,api=NS(Resolution=NS(DAILY="daily")))
                start=at("2017-05-22");end=start+__import__("pandas").DateOffset(days=days)
                expected=[at("2017-05-"+str(d)).isoformat() for d in range(22,22+days)]
                got=None;error=None
                try: got=[r["snapshot_at"] for r in fetch(src,start=start,end=end)]
                except HistoricalSourceError as exc: error=str(exc)
                OBS[str(days)]={"expected_snapshot_clocks":expected,"actual_snapshot_clocks":got,
                    "error":error,"native_request":[str(x) for x in qb.calls[0][0][1:]],
                    "native_filter":"start < EndTime <= end","api_calls":len(qb.calls)}
                self.assertIsNone(error,"Adapter rejects an official-contract endpoint before mapping its half-open selection window")
                self.assertEqual(got,expected)

    def test_public_collector_fails_with_legal_native_endpoint(self):
        qb=EndTimeReplayQB();src=QuantConnectSnapshotSource(qb,FIELDS,api=NS(Resolution=NS(DAILY="daily")))
        collector=HistoricalSnapshotCollector(MemoryArtifactStore(),src,plan(),synthetic=True)
        result=None;error=None
        try:result=collector.collect()
        except CollectionError as exc:error=str(exc)
        OBS["collector"]={"error":error,"result":result,"api_calls":len(qb.calls)}
        self.assertIsNone(error,"A legal native endpoint prevents completion of the one-day collection window")

if __name__=="__main__":
    stream=io.StringIO()
    result=unittest.TextTestRunner(stream=stream,verbosity=2,resultclass=Recorder).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(AdditionalSourceTests))
    output=stream.getvalue();print(output,end="")
    def method_id(case):
        return case.test_case.id() if hasattr(case,"test_case") else case.id()
    execution_records=[{"test":str(case),"method_id":method_id(case),"traceback":trace}
        for case,trace in result.failures+result.errors]
    failed_methods={record["method_id"] for record in execution_records}
    report={"methods":result.testsRun,"passed_methods":result.testsRun-len(failed_methods),
        "failed_or_error_methods":len(failed_methods),"failure_records":len(result.failures),
        "error_records":len(result.errors),"subtests":result.subtests,"skips":len(result.skipped),
        "first_failure":execution_records[0] if execution_records else None,"all_failures":execution_records,
        "observations":OBS,"real_sdk_executed":False,"platform_calls":0,
        "evidence_kind":"immutable official LEAN static contract plus synthetic native-shape replay"}
    (OUT/"secondary_source_output_counted.txt").write_text(output,encoding="utf-8")
    (OUT/"secondary_source_results_counted.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    sys.exit(not result.wasSuccessful())
