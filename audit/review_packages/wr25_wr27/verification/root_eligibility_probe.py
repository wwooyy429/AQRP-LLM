"""Developer known-answer matrix using an archived independent synthetic fixture."""
from pathlib import Path
import hashlib
import importlib.util
import json
import sys

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "cloud"))
fixture = ROOT / "audit/reviews/20261027-ea6053e-windows/cert_agent/cert_fixture.py"
spec = importlib.util.spec_from_file_location("root_independent_fixture", fixture)
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)
h.SOURCE = ROOT


def change(raw, mode):
    old = raw["tables"]["security_master"][0]
    old["effective_to"] = "2018-01-25T00:00:00-05:00"
    new = h.deepcopy(old)
    new.update(ticker="RENAMED000", effective_from=old["effective_to"],
               effective_to=None, available_at=old["effective_to"])
    if mode == "unmapped":
        new["instrument_type"] = "UNMAPPED_VENDOR_CODE"
    if mode == "null":
        new["instrument_type"] = None
    if mode in ("etf", "future_etf", "exact_formation_etf", "microsecond_late_etf", "etf_unknown_listed", "only_future"):
        new["instrument_type"] = "etf"
    if mode in ("unlisted", "future_unlisted", "unlisted_unknown_type"):
        new["listed"] = False
    if mode == "unlisted_unknown_type":
        new["instrument_type"] = None
    if mode == "etf_unknown_listed":
        new["listed"] = None
    if mode in ("future_etf", "future_unlisted", "only_future"):
        new["available_at"] = "2018-02-02T09:00:00.000001-05:00"
    if mode == "exact_formation_etf":
        new["available_at"] = "2018-02-01T09:00:00-05:00"
    if mode == "microsecond_late_etf":
        new["available_at"] = "2018-02-01T09:00:00.000001-05:00"
    if mode == "missing_past_etf":
        old["instrument_type"] = "etf"
    if mode == "missing_past_unlisted":
        old["listed"] = False
    if not mode.startswith("missing"):
        raw["tables"]["security_master"].append(new)
    if mode == "only_future":
        raw["tables"]["security_master"] = [row for row in raw["tables"]["security_master"]
                                              if row is not old]
        raw["financial"] = [row for row in raw["financial"] if row["sid"] != "SID000"]
        raw["tables"]["prices"] = [row for row in raw["tables"]["prices"] if row["sid"] != "SID000"]
    raw["liquid"] = [row for row in raw["liquid"] if row["sid"] != "SID000"]
    for row in raw["tables"]["membership"]:
        row["sids"] = raw["sids"][1:201]


passing = {"etf", "unlisted", "exact_formation_etf", "etf_unknown_listed", "unlisted_unknown_type", "only_future"}
modes = ("stock", "null", "unmapped", "etf", "unlisted", "future_etf", "future_unlisted",
         "missing", "missing_past_etf", "missing_past_unlisted", "only_future",
         "exact_formation_etf", "microsecond_late_etf", "etf_unknown_listed", "unlisted_unknown_type")
results, failures = [], []
for mode in modes:
    expected = "observations_passed" if mode in passing else "insufficient_evidence"
    try:
        result = h.run(h.make(lambda raw: change(raw, mode)))
        actual = result["status"]
        assert all(result[key] is False for key in ("vendor_provenance_authenticated", "full_historical_US200_certified",
            "actual_availability_certified", "financial_vintage_certified", "research_certified", "row_values_exported", "financial_evidence"))
        record = {"case": mode, "expected": expected, "actual": actual, "checks": result["checks"],
                  "counts": result["counts"], "passed": actual == expected}
    except h.DataCertificationError as error:
        record = {"case": mode, "expected": expected, "actual": "rejected", "error_class": type(error).__name__,
                  "passed": mode not in passing}
    results.append(record)
    if not record["passed"]:
        failures.append(mode)
    print(json.dumps({key: record[key] for key in ("case", "expected", "actual", "passed")}), flush=True)
report = {"kind": "developer_independent_fixture_eligibility_matrix_not_independent_acceptance",
    "product_raw_sha256": hashlib.sha256((ROOT / "cloud/qresearch/data_certification.py").read_bytes()).hexdigest(),
    "fixture_raw_sha256": hashlib.sha256(fixture.read_bytes()).hexdigest(), "cases": results,
    "failed_cases": failures, "new_platform_calls": 0, "real_ledger_writes": 0,
    "independent_acceptance": False, "financial_evidence": False}
(OUT / "root_eligibility_probe.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
assert not failures, failures
