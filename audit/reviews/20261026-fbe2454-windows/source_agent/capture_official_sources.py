"""Save public, immutable primary-source SDK code only; no market endpoints."""
from pathlib import Path
from hashlib import sha256
import difflib
import json
from urllib.request import Request,urlopen

OUT=Path(__file__).resolve().parent
SDK=OUT/"official_sdk_static"
SDK.mkdir(exist_ok=True)
PIN="f3d841e60dfd010ee5fc293ea893e56952484108"
PATHS=["Research/QuantBook.cs","Algorithm/QCAlgorithm.History.cs",
    "Engine/HistoricalData/SubscriptionDataReaderHistoryProvider.cs",
    "Common/Python/PandasData.cs","Common/Python/PandasConverter.DataFrameGenerator.cs",
    "Common/Data/Fundamental/FundamentalUniverse.cs","Common/Data/Fundamental/Fundamental.cs",
    "Common/Data/Fundamental/FineFundamental.cs",
    "Engine/DataFeeds/SubscriptionDataSourceReader.cs","Engine/DataFeeds/BaseDataCollectionAggregatorReader.cs",
    "Common/Data/UniverseSelection/BaseDataCollection.cs","Common/Data/Fundamental/MultiPeriodField.cs",
    "Common/Data/UniverseSelection/BaseFundamentalDataProvider.cs",
    "Common/Data/Fundamental/Generated/FinancialStatementsFileDate.cs",
    "Common/Data/Fundamental/Generated/FinancialStatementsPeriodEndingDate.cs",
    "Common/Data/Fundamental/Generated/FinancialStatementsAccessionNumber.cs",
    "Common/Data/Fundamental/Generated/FinancialStatementsFormType.cs",
    "Common/Data/Fundamental/Generated/SecurityReference.cs",
    "Common/Data/Fundamental/Generated/CompanyReference.cs"]
manifest=[]
for path in PATHS:
    url=f"https://raw.githubusercontent.com/QuantConnect/Lean/{PIN}/{path}"
    data=urlopen(Request(url,headers={"User-Agent":"Independent-offline-contract-audit"}),timeout=30).read()
    filename=path.replace("/","__")
    (SDK/filename).write_bytes(data)
    manifest.append({"url":url,"github_url":f"https://github.com/QuantConnect/Lean/blob/{PIN}/{path}",
        "saved_file":"official_sdk_static/"+filename,"sha256":sha256(data).hexdigest(),
        "lines":len(data.splitlines())})
(OUT/"official_sdk_static_manifest.json").write_text(json.dumps({"repository":"QuantConnect/Lean",
    "sha":PIN,"public_static_source_only":True,"files":manifest},indent=2),encoding="utf-8")
old=(OUT/"secondary_source_review_first.py").read_text().splitlines(keepends=True)
new=(OUT/"secondary_source_review.py").read_text().splitlines(keepends=True)
(OUT/"secondary_harness_correction.diff").write_text("".join(difflib.unified_diff(old,new,
    fromfile="secondary_source_review_first.py",tofile="secondary_source_review.py")),encoding="utf-8")
print(json.dumps({"saved_static_files":len(manifest),"immutable_lean_sha":PIN}))
