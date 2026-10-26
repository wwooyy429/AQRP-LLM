from pathlib import Path
from hashlib import sha256
import json

OUT=Path(__file__).resolve().parent
read=lambda name:json.loads((OUT/name).read_text(encoding="utf-8"))
first=read("source_review_results_first.json")
second=read("secondary_source_results_final.json")
initial_second=read("secondary_source_results_first.json")
pin=read("official_sdk_static_manifest.json")["sha"]
cmd_prefix="& 'C:\\Users\\11638\\.codex\\tmp\\aqrp-review-20261026\\venv\\Scripts\\python.exe' -B "
commands=[{"command":cmd_prefix+"'"+str(OUT/name)+"'","exit_code":code} for name,code in
    [("independent_source_review.py",1),("secondary_source_review.py",1),("minimal_native_endpoint.py",1),("capture_official_sources.py",0)]]
summary={"candidate_sha":"fbe2454e6ea10aa59211c01f236c54bb251527be",
    "review_scope":"historical_source.py, frozen source catalog, source-to-collector-to-ingestor/PIT bridge",
    "decision":"new source module not accepted: WR-09 and WR-10 reproducible",
    "findings":[{"id":"WR-09","severity":"P2","file":"cloud/qresearch/historical_source.py",
        "lines":[84,85,86,195,196,197],"title":"Missing SDK date sentinel is persisted as an observed financial date",
        "trigger":"Both financial date fields return datetime.min and has_value=False, with no available periods",
        "actual":{"financial_statements.file_date.value":"0001-01-01","financial_statements.period_ending_date.value":"0001-01-01",
            "both_missing_counts":0},"expected":{"both_values":None,"both_missing_counts":1},
        "impact":"Corrupts observed metadata semantics and undercounts source gaps; no proven bypass of PIT or financial gate",
        "evidence_kind":"immutable official LEAN NoValue contract plus independent native-shape synthetic projection through public collector",
        "repair_constraint":"Normalize SDK NoValue/all-period-missing; do not drop valid fallback merely because default-period HasValue is false"},
      {"id":"WR-10","severity":"P2","file":"cloud/qresearch/historical_source.py","lines":[160,161,162,180,181,182],
        "title":"Native end-time request convention conflicts with the declared half-open snapshot window",
        "trigger":"Native history legally returns an EndTime index equal to requested end, while source passes start/end unchanged",
        "actual":"HistoricalSourceError: Duplicate or out-of-window native universe snapshot; public collector aborts and retains unfinished intent",
        "expected":"Translate the declared selection-clock interval to the native request convention and complete the exact bounded window",
        "impact":"A normal native endpoint can prevent completion of one-day or multi-day collection; simply accepting the endpoint would violate collector half-open contract",
        "evidence_kind":"immutable official QuantBook->History->reader/filter->Pandas contract plus independent native-shape replay, not real platform execution"}],
    "test_results":{"final_primary":{"methods":8,"passed":7,"failed_methods":1,"failure_records":2,"subtests":73,"errors":0,"skips":0},
        "final_additional":{"methods":3,"passed":1,"failed_methods":2,"failure_records":4,"subtests":3,"errors":0,"skips":0},
        "combined_final":{"methods":11,"passed":8,"failed_methods":3,"failure_records":6,"subtests":76,"errors":0,"skips":0},
        "initial_additional_preserved":{"methods":3,"passed":1,"failed_methods":1,"failure_records":3,"error_methods":1,"errors":1,"subtests":3,"skips":0,
            "error_reason":"Reviewer caught HistoricalSourceError subclass while collector intentionally wraps it as CollectionError; catch widened only, production assertions/inputs unchanged",
            "diff":"secondary_harness_correction.diff"}},
    "positive_scope":["all 15 default fields projected without HasFundamentalData screening",
        "permanent Symbol.id identity, same ticker with distinct SIDs remains distinct, missing/duplicate SIDs rejected",
        "declared numeric/boolean/date/text type controls; NaN/None/pd.NA missing and numeric zero retained",
        "UTC-aware endpoints normalize to NY, spring/fall seven-wall-day bounds pass, naive/final/frontier/oversized requests rejected",
        "Series MultiIndex symbol/time shape, wrong universe, duplicate/out-of-range clocks rejected",
        "official A/I actively trading source semantics respected; D/O delisted; conservative unknown classification",
        "observed liquidity uses supplied dollar_volume, no inferred date/receipt, ingestor archives but PIT read rejects incomplete evidence",
        "fake availability/certification flags in values are not promoted; provenance certification flags remain false",
        "valid non-default-period fallback dates survive with has_value=False; zero remains zero"],
    "official_contract":{"lean_sha":pin,"static_files":19,"manifest":"official_sdk_static_manifest.json",
        "raw_line_number_warning":"Use saved raw-byte one-based line numbers; browser extraction removes blank lines and differs",
        "wr09_chain":{"Common/Data/Fundamental/MultiPeriodField.cs":[31,56],
            "Common/Data/UniverseSelection/BaseFundamentalDataProvider.cs":[70,80,107,109],
            "Common/Data/Fundamental/Generated/FinancialStatementsFileDate.cs":[75,85,89,100,102]},
        "wr10_chain":{"Research/QuantBook.cs":[765,774,776,939,942,959,961,1132,1136],
            "Algorithm/QCAlgorithm.History.cs":[337,342,344,1021,1029],
            "Common/Data/Fundamental/FundamentalUniverse.cs":[60,77],
            "Common/Data/Fundamental/FineFundamental.cs":[33],
            "Engine/DataFeeds/SubscriptionDataSourceReader.cs":[64,65],
            "Engine/DataFeeds/BaseDataCollectionAggregatorReader.cs":[68,80],
            "Engine/HistoricalData/SubscriptionDataReaderHistoryProvider.cs":[220,222],
            "Common/Python/PandasData.cs":[175,180,190]},
        "documentation":[{"url":"https://www.quantconnect.com/docs/v2/research-environment/universes",
            "supports":"universe_history(universe,start,end); flatten=False Series with symbol/time MultiIndex and list of Fundamental objects; selection clock meaning"},
            {"url":"https://www.lean.io/docs/v2/lean-engine/class-reference/classQuantConnect_1_1Data_1_1Fundamental_1_1SecurityReference.html",
             "supports":"A/I currently trading; D/O previously trading then delisted; security type codes, receipt/subtype fields"},
            {"url":"https://www.quantconnect.com/docs/v2/writing-algorithms/securities/asset-classes/us-equity/corporate-fundamentals",
             "supports":"Python financial_statements.file_date.value field path"}]},
    "environment":first["environment"],"source_unchanged":first["source_unchanged"],
    "commands":commands,"scope_limits":["No actual QuantBook/AlgorithmImports runtime loaded; no live SDK object conversions dynamically certified",
        "No actual historical market/universe/fundamental rows obtained",
        "No US200 coverage, point-in-time receipt/vintage/classification/calendar certification",
        "No factor evaluation, final-period data, Research/LEAN/model/deployment/PR actions"],
    "real_sdk_executed":False,"research_calls":0,"lean_submissions":0,"model_calls":0,"financial_evidence":False}
(OUT/"review_summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf-8")
manifest={str(p.relative_to(OUT)):sha256(p.read_bytes()).hexdigest() for p in OUT.rglob("*") if p.is_file() and p.name!="artifact_hashes.json"}
(OUT/"artifact_hashes.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
print(json.dumps({"summary":"review_summary.json","final_methods":11,"passed":8,"failed_methods":3,"failure_records":6,"errors":0,"subtests":76}))
