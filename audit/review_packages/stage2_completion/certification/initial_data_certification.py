"""Metadata-only certification-plan validation. Never reads market row files."""
from pathlib import Path
import argparse
import json
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cloud"))
from qresearch.data_certification import DataCertificationPlan, certification_capabilities
from qresearch.engineering_receipts import _json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("capabilities", "validate-plan"))
    parser.add_argument("--plan-file", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "capabilities":
            if args.plan_file is not None:
                raise ValueError
            catalog = _json((ROOT / "config/source_catalog.json").read_text(encoding="utf-8-sig"))["fields"]
            result = certification_capabilities(catalog)
        else:
            if args.plan_file is None:
                raise ValueError
            plan = DataCertificationPlan.from_dict(_json(args.plan_file.read_text(encoding="utf-8-sig")))
            value = plan.to_dict()
            result = {"plan_valid": True, "plan_hash": plan.hash, "scope_start": value["start"],
                "scope_end_exclusive": value["end_exclusive"], "warmup_start": value["warmup_start"],
                "financial_field_count": len(value["financial_catalog"]), "ready_to_dispatch": False,
                "budget_admission_performed": False, "research_certified": False, "financial_evidence": False}
    except (OSError, ValueError, TypeError, KeyError):
        print(json.dumps({"plan_valid": False, "ready_to_dispatch": False, "error": "Invalid certification metadata"}))
        raise SystemExit(2)
    print(json.dumps(result, ensure_ascii=True))


if __name__ == "__main__":
    main()
