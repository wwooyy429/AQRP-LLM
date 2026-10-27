"""Known-answer metadata checks; no Git mutation, provider or cloud calls."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from review_metadata import COUNTERS, PLATFORM_SCOPE, SOURCE_SCOPE, validate_current

BASELINE = "e" * 40
PATHS = ["cloud/research_config.py", "tests/test_example.py", "tools/example.py"]
OLD = {"source_changed_this_round": ["tools/previous.py"],
       "source_configuration_budget_changed_scope": "One new engineering configuration and one Research precharge",
       "read_or_polled_this_turn_scope": "Prior source read and old terminal observation"}


def document():
    return {**{key: 0 for key in COUNTERS}, "source_configuration_budget_changed": False,
        "read_or_polled_this_turn": False, "candidate_cloud_deployed": False,
        "source_configuration_budget_changed_scope": SOURCE_SCOPE,
        "read_or_polled_this_turn_scope": PLATFORM_SCOPE, "source_changed_this_round": PATHS,
        "current_activity": {"kind": "offline_repair", "baseline_commit": BASELINE,
            "source_roots": ["cloud", "tests", "tools"], "source_suffix": ".py",
            "quantconnect_reads": 0, "quantconnect_writes": 0, "new_deployments": 0},
        "historical_activity_descriptions": [{"recorded_at_commit": BASELINE,
            "actual_cloud_source_commit": "7fc5ef2e9d2379d29f48d05a1f3cc760000884d6", "prior_current_fields": deepcopy(OLD)}]}


class ReviewMetadataTests(unittest.TestCase):
    def check(self, value, **changes):
        return validate_current(value, PATHS, OLD, baseline_commit=BASELINE,
            **({"budget_unchanged": True, "journal_unchanged": True} | changes))

    def test_exact_current_scope_and_preserved_old_descriptions(self):
        result = self.check(document())
        self.assertEqual(result["status"], "metadata_consistent")
        self.assertEqual(result["changed_source_files"], 3)
        self.assertIs(result["external_activity_authenticated"], False)

    def test_zero_counts_cannot_coexist_with_unscoped_old_activity_text(self):
        for key in ("source_configuration_budget_changed_scope", "read_or_polled_this_turn_scope"):
            with self.subTest(key=key):
                value = document(); value[key] = OLD[key]
                with self.assertRaises(ValueError): self.check(value)

    def test_exact_changed_source_set_rejects_missing_extra_duplicate_or_wrong_baseline(self):
        for wrong in (PATHS[:-1], PATHS + ["tools/extra.py"], PATHS + [PATHS[-1]], list(reversed(PATHS))):
            with self.subTest(paths=wrong):
                value = document(); value["source_changed_this_round"] = wrong
                with self.assertRaises(ValueError): self.check(value)
        value = document(); value["current_activity"]["baseline_commit"] = "f" * 40
        with self.assertRaises(ValueError): self.check(value)

    def test_old_descriptions_must_survive_with_pinned_baseline(self):
        for key in ("recorded_at_commit", "actual_cloud_source_commit", "prior_current_fields"):
            with self.subTest(key=key):
                value = document(); del value["historical_activity_descriptions"][0][key]
                with self.assertRaises(ValueError): self.check(value)

    def test_integer_counters_and_actual_budget_journal_bytes_are_required(self):
        for counter in COUNTERS:
            for wrong in (False, True, None, 1):
                with self.subTest(counter=counter, wrong=wrong):
                    value = document(); value[counter] = wrong
                    with self.assertRaises(ValueError): self.check(value)
        for key in ("budget_unchanged", "journal_unchanged"):
            with self.subTest(key=key), self.assertRaises(ValueError): self.check(document(), **{key: False})

    def test_current_platform_and_source_scope_cannot_silently_expand(self):
        for key in ("quantconnect_reads", "quantconnect_writes", "new_deployments"):
            for wrong in (1, True, False):
                with self.subTest(key=key, wrong=wrong):
                    value = document(); value["current_activity"][key] = wrong
                    with self.assertRaises(ValueError): self.check(value)
        for key in ("source_configuration_budget_changed", "read_or_polled_this_turn", "candidate_cloud_deployed"):
            value = document(); value[key] = True
            with self.subTest(key=key), self.assertRaises(ValueError): self.check(value)


if __name__ == "__main__":
    unittest.main()
