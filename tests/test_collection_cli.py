"""Metadata CLI boundaries; all dates and identities below are synthetic."""
from copy import deepcopy
import contextlib
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import stage2_collection as cli


class CollectionCLITests(unittest.TestCase):
    def plan(self):
        raw = json.loads((ROOT / "templates" / "historical_collection.json").read_text(encoding="utf-8"))
        raw.update(plan_id="SYNTHETIC-ONLY", data_version="SYNTHETIC-v1", source_manifest_hash="b" * 64,
                   start="2018-03-10T00:00:00-05:00", end_exclusive="2018-03-13T00:00:00-04:00")
        return raw

    def test_template_is_inactive_and_catalog_does_not_enable_factor_fields(self):
        output = io.StringIO()
        with patch.object(sys, "argv", ["stage2_collection.py", "template"]), contextlib.redirect_stdout(output):
            cli.main()
        report = json.loads(output.getvalue())
        self.assertFalse(report["ready_to_dispatch"])
        self.assertEqual(report["market_calls"], 0)
        self.assertIn("source_manifest_hash", report["required_explicit_values"])
        self.assertIn("dollar_volume", cli.catalog())
        data = json.loads((ROOT / "config" / "data.json").read_text(encoding="utf-8"))
        self.assertEqual(data["factor_field_whitelist"], [])

    def test_manifest_mismatch_rejected_and_preview_exports_only_metadata(self):
        raw = self.plan()
        with self.assertRaises(ValueError):
            cli.preview(raw, implementation_hash="a" * 64)
        report = cli.preview(raw, implementation_hash="b" * 64)
        self.assertEqual(report["calendar_window_count"], 3)
        self.assertFalse(report["dispatch_supported"])
        self.assertFalse(report["budget_admission_performed"])
        self.assertFalse(report["financial_evidence"])
        self.assertNotIn("records", report)

    def test_unreviewed_catalog_flags_cannot_open_certification(self):
        catalog = json.loads((ROOT / "config" / "source_catalog.json").read_text(encoding="utf-8"))
        for key in ("factor_fields_enabled", "vendor_revision_certified", "actual_availability_certified"):
            changed = deepcopy(catalog)
            changed[key] = True
            with self.subTest(key=key), patch.object(cli, "read_json", return_value=changed):
                with self.assertRaises(ValueError):
                    cli.catalog()

    def test_inactive_or_final_plan_does_not_preview(self):
        inactive = json.loads((ROOT / "templates" / "historical_collection.json").read_text(encoding="utf-8"))
        with self.assertRaises(ValueError):
            cli.preview(inactive, implementation_hash="b" * 64)
        final = self.plan()
        final.update(start="2024-01-01T00:00:00-05:00", end_exclusive="2024-01-02T00:00:00-05:00")
        with self.assertRaises(ValueError):
            cli.preview(final, implementation_hash="b" * 64)


if __name__ == "__main__":
    unittest.main()
