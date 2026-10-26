"""WR-14 fractional hint clocks, including both synthetic worker/ledger paths.

These are receipt compatibility checks, not market or financial evidence. The
worker fixtures use invented observations and an in-memory budget registry.
"""
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "cloud"), str(ROOT / "tests")]
from qresearch.engineering_receipts import ReceiptParseError, _annotations, _native, _research_stdout, research_observation
from qresearch.collection_execution import collection_research_observation
import test_wr13_annotations as fixture


def clocks():
    """Zero through six decimal places, comma/dot and registered zone forms."""
    for precision in range(7):
        fractions = ("",) if precision == 0 else tuple(separator + "500000"[:precision] for separator in (".", ","))
        for fraction in fractions:
            for zone in ("Z", "+05:30", ""):
                yield "2026-10-27T12:34:56" + fraction + zone


class WR14FractionalAnnotationTests(unittest.TestCase):
    def test_zero_to_six_places_at_inner_and_outer_carriers(self):
        for stamp in clocks():
            annotations = {"lastModified": stamp, "audience": ["assistant"], "priority": 0.25}
            for entry in ("root", "content", "outputs"):
                with self.subTest(stamp=stamp, entry=entry):
                    native = fixture.shape(fixture.text_node(annotations=annotations), entry)
                    carrier = fixture.envelope(native, outer=annotations)
                    before = deepcopy(carrier)
                    self.assertEqual(_research_stdout(_native(carrier)), "e30=")
                    self.assertEqual(carrier, before, "Validation must not rewrite the original hint string")

    def test_registered_separators_offsets_and_unbounded_fraction_grammar(self):
        # Existing grammar accepts any nonempty decimal fraction. It must not
        # depend on fromisoformat's different precision limits across Python.
        stamps = ("2024-02-29", "2024-02-29t00:00:00.1z", "2024-02-29 23:59:59,12-04:00",
                  "2026-10-27T12:34:56.123456789Z", "2026-10-27T12:34:56,000000000+23:59")
        for stamp in stamps:
            with self.subTest(stamp=stamp):
                annotations = {"lastModified": stamp}
                before = deepcopy(annotations)
                _annotations(annotations)
                self.assertEqual(annotations, before)

    def test_fraction_does_not_relax_calendar_time_or_offset_boundaries(self):
        invalid = ("2023-02-29T12:34:56.5Z", "2024-02-30T12:34:56.12Z", "2026-13-01T12:34:56.1234Z",
                   "0000-01-01T12:34:56.12345Z", "2026-10-27T24:00:00.5Z", "2026-10-27T23:60:00.5Z",
                   "2026-10-27T23:59:60.5Z", "2026-10-27T12:34:56.5+00:60", "2026-10-27T12:34:56.5-01:99",
                   "2026-10-27T12:34:56.5+24:00", "2026-10-27T12:34:56.Z", "2026-10-27T12:34:56,Z",
                   "2026-10-27T12:34:56.5.0Z", "2026-10-27T12:34:56.5+05:30:00", "2026-10-27.5",
                   "2026-10-27T12:34:56.5Z\n", "2026-10-27T12:34:56.٥Z")
        for stamp in invalid:
            with self.subTest(stamp=stamp), self.assertRaises(ReceiptParseError):
                _annotations({"lastModified": stamp})

    def test_valid_fraction_never_permits_unknown_annotation_side_data(self):
        for stamp in clocks():
            for side in ({"rows": [fixture.SECRET]}, {"error": fixture.SECRET}, {"outputs": []}, {"_meta": {}}):
                with self.subTest(stamp=stamp, side=list(side)):
                    annotations = {"lastModified": stamp, **side}
                    for outer in (False, True):
                        carrier = fixture.envelope(fixture.shape(fixture.text_node(
                            annotations={} if outer else annotations), "content"),
                            outer=annotations if outer else {})
                        with self.assertRaises(ReceiptParseError) as caught:
                            _research_stdout(_native(carrier))
                        self.assertNotIn(fixture.SECRET, str(caught.exception))


class WR14FractionalWorkerChainTests(unittest.TestCase):
    def exercise(self, kind):
        helper = fixture.WR13ReceiptChainTests()
        for stamp in clocks():
            with self.subTest(kind=kind, stamp=stamp), tempfile.TemporaryDirectory() as directory:
                local, registry, bridge, attempt, payload, deployment, marker = helper.build(kind, Path(directory))
                annotation = {"lastModified": stamp}
                native = fixture.shape(fixture.text_node(marker, annotation), "content")
                tool = {"tool_name": "mcp__quantconnect__jupyter_execute_cell", "arguments": {"projectId": 17, "index": 2},
                        "result": fixture.envelope(native, outer=annotation)}
                original_tool = deepcopy(tool)
                before = registry.snapshot()
                before_bytes = dict(local._data)
                parse = (lambda value: collection_research_observation(payload, deployment, value, field_catalog=fixture.CATALOG)) \
                    if kind == "collection" else (lambda value: research_observation(payload, deployment, value))
                observed = parse(tool)
                self.assertEqual(tool, original_tool)
                self.assertEqual(registry.snapshot(), before, "Receipt parsing itself must not mutate the registry")
                self.assertEqual(local._data, before_bytes)
                bridge.record_submission(attempt, observed["submission"])
                self.assertEqual(bridge.consume_completion(attempt, completion_source=lambda _: observed["completion"]).status,
                                 "completed")
                self.assertEqual(registry.snapshot()["usage"], before["usage"], "A completed receipt cannot debit a second execution")
                self.assertNotIn(b"WR13-SYNTHETIC-CLOUD-SID", b"".join(local._data.values()))

    def test_new_collection_worker_fractional_hints_complete_without_extra_debit(self):
        self.exercise("collection")

    def test_old_research_worker_fractional_hints_complete_without_extra_debit(self):
        self.exercise("legacy")


if __name__ == "__main__":
    unittest.main()
