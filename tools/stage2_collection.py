"""Validate metadata for a proposed collection. Never dispatches QC jobs."""
from pathlib import Path
import argparse
import json
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cloud"))
from qresearch.collection import HistoricalCollectionPlan
from research import read_json
from stages import source_manifest


def catalog():
    raw = read_json(ROOT / "config" / "source_catalog.json")
    expected = {"schema_version", "source", "purpose", "factor_fields_enabled",
                "vendor_revision_certified", "actual_availability_certified", "fields"}
    if (set(raw) != expected or type(raw["schema_version"]) is not int or raw["schema_version"] != 1
            or raw["source"] != "quantconnect_fundamental_universe"
            or raw["purpose"] != "engineering_source_observation_only"
            or any(raw[key] is not False for key in ("factor_fields_enabled", "vendor_revision_certified", "actual_availability_certified"))):
        raise ValueError("Unreviewed source catalog or certification override")
    return raw["fields"]


def preview(raw, *, implementation_hash):
    plan = HistoricalCollectionPlan.from_dict(raw, field_catalog=catalog())
    if plan.to_dict()["source_manifest_hash"] != implementation_hash:
        raise ValueError("Plan does not pin the current source manifest; freeze a new plan")
    windows = plan.windows()
    return {"plan_hash": plan.hash, "source_manifest_hash": implementation_hash,
            "field_count": len(plan.field_catalog), "calendar_window_count": len(windows),
            "first_window": [value.isoformat() for value in windows[0]],
            "last_window": [value.isoformat() for value in windows[-1]],
            "dispatch_supported": False, "budget_admission_performed": False,
            "full_historical_US200_certified": False, "actual_availability_certified": False,
            "financial_evidence": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("template", "validate"))
    parser.add_argument("--plan", type=Path)
    args = parser.parse_args()
    if args.command == "template":
        template = read_json(ROOT / "templates" / "historical_collection.json")
        fields = catalog()
        if not set(template["fields"]) <= set(fields):
            raise ValueError("Template contains fields outside the trusted source catalog")
        print(json.dumps({"template_only": True, "ready_to_dispatch": False,
                          "required_explicit_values": [key for key, value in template.items() if value is None],
                          "source_field_count": len(fields), "market_calls": 0}))
        return
    if args.plan is None:
        parser.error("validate requires --plan; this does not authorize a cloud execution")
    print(json.dumps(preview(read_json(args.plan), implementation_hash=source_manifest()["source_hash"])))


if __name__ == "__main__":
    main()
