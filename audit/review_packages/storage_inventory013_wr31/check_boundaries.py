"""Collaborative synthetic known answers for WR-31; not independent acceptance.

Accepts an analyzer path so the unchanged assertions can be run first against
the old version and then the repaired version. No cloud access or file writes.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import sys
import unittest


ANALYZER = None
SUBTESTS_EXECUTED = 0


def rows(*names):
    return [{"name": name + ".json", "type": "JSON", "display_size": "1 KB",
             "last_modified": "synthetic", "exact_bytes": None} for name in names]


def observation(paging, names=("a",)):
    return {"path": "synthetic", "paging": paging, "rows": rows(*names)}


def assess(observations):
    return ANALYZER.analyze({"scope_root": "synthetic", "observations": observations}, {}, {})


class PagingBoundaryKnownAnswers(unittest.TestCase):
    def check(self, label, observations, expected_complete, *, lexical_invalid=None):
        global SUBTESTS_EXECUTED
        SUBTESTS_EXECUTED += 1
        with self.subTest(label=label):
            value = assess(observations)
            directory = value["directories"][0]
            self.assertIs(directory["all_entries_observed_at_UI_metadata_level"], expected_complete)
            self.assertIs(value["UI_tree_listing_complete_within_declared_scope"], expected_complete)
            if lexical_invalid is not None:
                self.assertIs(bool(directory["invalid_paging"]), lexical_invalid)
            self.assertEqual(value["confirmed_reclaimable_objects"], [])
            self.assertEqual(value["confirmed_reclaimable_bytes"], 0)
            self.assertIsNone(value["potential_reclaimable_total_bytes"])
            self.assertFalse(value["global_reference_closure_complete"])
            self.assertEqual(value["cloud_calls"], 0)
            self.assertEqual(value["Registry_or_budget_changes"], 0)
            self.assertFalse(value["final_test_enabled"])
            for item in value["objects"]:
                self.assertFalse(item["deletion_authorized"])
                self.assertFalse(item["raw_content_hash_verified"])
                self.assertFalse(item["reference_closure_verified"])

    def test_01_original_WR31_ranges(self):
        for text, expected in [
            ("1 to 1 of 1", True),
            ("-1 to 1 of 1", False),
            ("1 to 1 of 1; 2 to 2 of 2", False),
        ]:
            self.check(text, [observation([text, "Page 1 of 1"])], expected,
                       lexical_invalid=not expected)

    def test_02_signed_or_noninteger_range_tokens(self):
        for text in [
            "+1 to 1 of 1", "1 to -1 of 1", "1 to +1 of 1",
            "1 to 1 of -1", "1 to 1 of +1", "1.0 to 1 of 1",
            "1 to 1.0 of 1", "1 to 1 of 1.0", "1e0 to 1 of 1",
            "--1 to 1 of 1", "−1 to 1 of 1", "1 to 1 of 1e0",
        ]:
            self.check(text, [observation([text, "Page 1 of 1"])], False, lexical_invalid=True)

    def test_03_range_junk_and_multiple_claims(self):
        for text in [
            "garbage 1 to 1 of 1", "1 to 1 of 1 garbage", "x1 to 1 of 1",
            "1 to 1 of 1x", "(1 to 1 of 1)",
            "1 to 1 of 1; 1 to 1 of 1", "1 to 1 of 1; 2 to 2 of 2",
            "1 to 1 of 1 Page 1 of 1", "Range: 1 to 1 of 1",
        ]:
            self.check(text, [observation([text, "Page 1 of 1"])], False, lexical_invalid=True)

    def test_04_page_junk_signs_and_multiple_claims(self):
        for text in [
            "Page -1 of 1", "Page +1 of 1", "Page 1 of -1", "Page 1 of +1",
            "garbage Page 1 of 1", "Page 1 of 1 garbage", "Page 1 of 1x",
            "Page 1 of 1; Page 1 of 1", "Page 1 of 1; Page 2 of 2",
            "Page 1.0 of 1", "Page 1 of 1.0", "(Page 1 of 1)",
        ]:
            self.check(text, [observation(["1 to 1 of 1", text])], False, lexical_invalid=True)

    def test_05_extra_unknown_or_nonstring_labels(self):
        for extra in ["unknown", "", "-bad range", 42, None, True, {}, []]:
            self.check(repr(extra), [observation(["1 to 1 of 1", "Page 1 of 1", extra])],
                       False, lexical_invalid=True)

    def test_06_container_and_claim_cardinality(self):
        for paging in [
            None, "1 to 1 of 1", ("1 to 1 of 1", "Page 1 of 1"),
            {"1 to 1 of 1": None, "Page 1 of 1": None}, [],
            ["1 to 1 of 1"], ["Page 1 of 1"],
            ["1 to 1 of 1", "Page 1 of 1", "Page 1 of 1"],
            ["1 to 1 of 1", "Page 1 of 1", "Page 2 of 2"],
            ["1 to 1 of 1", "1 to 1 of 1", "Page 1 of 1"],
            ["1 to 1 of 1", "2 to 2 of 2", "Page 1 of 1"],
        ]:
            self.check(repr(paging), [observation(paging)], False, lexical_invalid=True)

    def test_07_unicode_and_line_breaks(self):
        for range_text, page_text in [
            ("١ to ١ of ١", "Page 1 of 1"),
            ("１ to １ of １", "Page 1 of 1"),
            ("1 to 1 of 1", "Page ١ of ١"),
            ("1 to 1 of 1", "Page １ of １"),
            ("1\nto 1 of 1", "Page 1 of 1"),
            ("1 to 1 of 1\n", "Page 1 of 1"),
            ("1 to 1 of 1", "Page\n1 of 1"),
            ("1 to 1 of 1", "Page 1 of 1\n"),
            ("1\rto 1 of 1", "Page 1 of 1"),
            ("1\u00a0to 1 of 1", "Page 1 of 1"),
            ("1 to 1 of 1", "Page\u00a01 of 1"),
            ("1\x00 to 1 of 1", "Page 1 of 1"),
        ]:
            self.check(repr((range_text, page_text)), [observation([range_text, page_text])],
                       False, lexical_invalid=True)

    def test_08_supported_ascii_controls(self):
        for range_text, page_text in [
            ("1 to 1 of 1", "Page 1 of 1"),
            ("1to1of1", "Page1of1"),
            ("1 TO 1 OF 1", "pAgE 1 oF 1"),
            (" 1 to 1 of 1 ", " Page 1 of 1 "),
            ("\t1\tto\t1\tof\t1\t", "\tPage\t1\tof\t1\t"),
            ("0000001 to 0000001 of 0000001", "Page 000001 of 000001"),
        ]:
            self.check(repr((range_text, page_text)), [observation([range_text, page_text])],
                       True, lexical_invalid=False)

    def test_09_numeric_width_and_bounds(self):
        for range_text, page_text in [
            ("00000001 to 1 of 1", "Page 1 of 1"),
            ("1 to 00000001 of 1", "Page 1 of 1"),
            ("1 to 1 of 00000001", "Page 1 of 1"),
            ("1 to 1 of 1", "Page 0000001 of 1"),
            ("1 to 1 of 1", "Page 1 of 0000001"),
            ("1 to 1 of 1000001", "Page 1 of 1"),
            ("1 to 1 of 1", "Page 1 of 100001"),
            ("1 to 1 of 1", "Page 100001 of 100001"),
            ("0 to 1 of 1", "Page 1 of 1"),
            ("2 to 1 of 1", "Page 1 of 1"),
            ("1 to 2 of 1", "Page 1 of 1"),
            ("1 to 1 of 1", "Page 2 of 1"),
        ]:
            self.check(repr((range_text, page_text)), [observation([range_text, page_text])],
                       False, lexical_invalid=True)

    def test_10_empty_and_compact_page_controls(self):
        self.check("empty zero page", [observation(["0 to 0 of 0", "Page 0 of 0"], ())],
                   True, lexical_invalid=False)
        self.check("historical empty one page", [observation(["0 to 0 of 0", "Page 1 of 1"], ())],
                   True, lexical_invalid=False)
        self.check("nonempty range zero page", [observation(["1 to 1 of 1", "Page 0 of 0"])], False)
        self.check("empty range with a row", [observation(["0 to 0 of 0", "Page 0 of 0"])], False)
        self.check("compact two pages", [
            observation(["1 to 1 of 2", "Page1of2"], ("a",)),
            observation(["2 to 2 of 2", "Page2of2"], ("b",)),
        ], True, lexical_invalid=False)

    def test_11_mixed_viewport_layout_43(self):
        observations = []
        for start, end, page in [(1, 21, "Page 1 of 3"), (1, 21, "Page 1 of 3"),
                                 (13, 24, "Page 2 of 4"), (25, 36, "Page 3 of 4"),
                                 (37, 43, "Page 4 of 4")]:
            observations.append(observation([f"{start} to {end} of 43", page],
                                            tuple(f"a{n:02}" for n in range(start, end + 1))))
        self.check("43 ordered positions with overlapping page layouts", observations, True,
                   lexical_invalid=False)
        value = assess(observations)
        self.assertEqual(value["unique_UI_leaf_objects"], 43)
        self.assertTrue(value["directories"][0]["page_count_layouts_varied"])
        self.assertEqual(value["directories"][0]["repeated_row_observations_are_not_extra_copies"], 30)

    def test_12_position_count_duplicate_and_total_conflicts(self):
        cases = [
            ("position conflicts", [
                observation(["1 to 2 of 2", "Page 1 of 1"], ("a", "b")),
                observation(["1 to 2 of 2", "Page 1 of 1"], ("b", "a")),
            ]),
            ("key moves position", [
                observation(["1 to 1 of 2", "Page 1 of 2"], ("a",)),
                observation(["2 to 2 of 2", "Page 2 of 2"], ("a",)),
            ]),
            ("one row missing", [observation(["1 to 2 of 2", "Page 1 of 1"], ("a",))]),
            ("duplicate key in range", [observation(["1 to 2 of 2", "Page 1 of 1"], ("a", "a"))]),
            ("total changes", [
                observation(["1 to 1 of 1", "Page 1 of 1"], ("a",)),
                observation(["1 to 1 of 2", "Page 1 of 2"], ("a",)),
            ]),
        ]
        for name, observations in cases:
            self.check(name, observations, False)


def main():
    global ANALYZER
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("analyzer", nargs="?", default=str(Path(__file__).with_name("analyze_inventory.py")))
    args = parser.parse_args()
    path = Path(args.analyzer).resolve()
    spec = importlib.util.spec_from_file_location("WR31_known_answer_target", path)
    ANALYZER = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ANALYZER)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(PagingBoundaryKnownAnswers)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(json.dumps({"kind": "collaborative_synthetic_known_answers_not_independent_acceptance",
                      "methods_run": result.testsRun, "failed_method_or_subtest_records": len(result.failures),
                      "error_records": len(result.errors), "subtests_executed": SUBTESTS_EXECUTED,
                      "cloud_calls": 0, "financial_evidence": False, "independent_acceptance": False,
                      "final_test_enabled": False}))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
