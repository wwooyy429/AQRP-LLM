"""Known-answer metadata checks; no Git mutation, provider or cloud calls."""
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from review_metadata import COUNTERS, PLATFORM_SCOPE, SOURCE_SCOPE, validate_current
import review_metadata
import stages

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


class RootManifestTests(unittest.TestCase):
    """Independent minimal trees expose a foreign hash despite a legal shape."""
    NAMES = ("AGENTS.md", "cloud/factors.py", "config/budget.json", "tests/fixture.py", "tools/example.py")
    CHANGED = ["cloud/factors.py", "tests/fixture.py", "tools/example.py"]
    BUDGET = b'{"quota":"synthetic-only"}\n'
    JOURNAL = b'{"synthetic_event":1}\n'

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="aqrp-root-manifest-")
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.tool = self.make_root("tool", b"VALUE = 1\n")
        self.target = self.make_root("target", b"VALUE = 2\n")

    def expected(self, root):
        files = {name: hashlib.sha256((root / name).read_bytes().decode("utf-8-sig")
            .replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")).hexdigest() for name in self.NAMES}
        raw = json.dumps(files, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
        return {"source_files": files, "source_hash": hashlib.sha256(raw).hexdigest(), "market_data_included": False}

    def make_root(self, name, factor):
        root = self.home / name
        values = {"AGENTS.md": b"Synthetic known-answer root only.\n", "cloud/factors.py": factor,
            "config/budget.json": self.BUDGET, "tests/fixture.py": b"# synthetic fixture\n",
            "tools/example.py": b"# known metadata source\n", "audit/runtime/registry/events.jsonl": self.JOURNAL}
        for path, raw in values.items():
            target = root / path; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(raw)
        value = document()
        value["source_changed_this_round"] = list(self.CHANGED)
        value["candidate_source_manifest_hash"] = self.expected(root)["source_hash"]
        self.write_metadata(root, value)
        return root

    def write_metadata(self, root, value):
        (root / "audit/stage2_current_readiness.json").write_text(json.dumps(value), encoding="utf-8")

    def check(self, root):
        resolved = Path(root).resolve()
        def git(command, *, cwd):
            self.assertEqual(Path(cwd), resolved)
            self.assertEqual(command[0], "git")
            args = command[1:]
            if args == ["show", BASELINE + ":audit/stage2_current_readiness.json"]:
                return json.dumps(OLD).encode("utf-8")
            if args == ["show", BASELINE + ":config/budget.json"]:
                return self.BUDGET
            if args == ["show", BASELINE + ":audit/runtime/registry/events.jsonl"]:
                return self.JOURNAL
            if args == ["diff", "--name-only", "-z", "--no-renames", BASELINE, "--", "cloud", "tests", "tools"]:
                return ("\0".join(self.CHANGED) + "\0").encode("utf-8")
            if args == ["ls-files", "--others", "--exclude-standard", "-z", "--", "cloud", "tests", "tools"]:
                return b""
            self.fail("Unexpected synthetic Git command: " + repr(args))
        with patch.object(review_metadata.subprocess, "check_output", side_effect=git):
            return review_metadata.check_repository(root)

    def test_explicit_roots_match_independent_known_answers_without_changing_default(self):
        original = stages.ROOT
        with patch.object(stages, "ROOT", self.tool):
            self.assertEqual(stages.source_manifest(), self.expected(self.tool))
            self.assertEqual(stages.source_manifest(root=self.target), self.expected(self.target))
            self.assertEqual(stages.source_manifest(root=str(self.tool)), self.expected(self.tool))
            self.assertEqual(stages.source_manifest(), self.expected(self.tool))
            self.assertEqual(stages.ROOT, self.tool)
        self.assertEqual(stages.ROOT, original)

    def test_target_hash_is_accepted_and_the_valid_foreign_tool_hash_is_rejected(self):
        with patch.object(stages, "ROOT", self.tool):
            self.assertEqual(self.check(self.target)["status"], "metadata_consistent")
            path = self.target / "audit/stage2_current_readiness.json"
            value = json.loads(path.read_bytes())
            value["candidate_source_manifest_hash"] = self.expected(self.tool)["source_hash"]
            self.write_metadata(self.target, value)
            with self.assertRaisesRegex(ValueError, "actual local source manifest"):
                self.check(self.target)
            value["candidate_source_manifest_hash"] = self.expected(self.target)["source_hash"]
            self.write_metadata(self.target, value)
            self.assertEqual(self.check(self.target)["status"], "metadata_consistent")

    def test_relative_root_from_an_unrelated_cwd_and_alternating_trees(self):
        caller = self.home / "caller"; caller.mkdir()
        previous = Path.cwd()
        try:
            os.chdir(caller)
            with patch.object(stages, "ROOT", self.tool):
                self.assertEqual(stages.source_manifest(root="../target"), self.expected(self.target))
                self.assertEqual(self.check("../target")["status"], "metadata_consistent")
                self.assertEqual(self.check("../tool")["status"], "metadata_consistent")
                self.assertEqual(self.check("../target")["status"], "metadata_consistent")
                self.assertEqual(stages.source_manifest(), self.expected(self.tool))
        finally:
            os.chdir(previous)

    def test_target_budget_and_journal_are_checked_instead_of_tool_files(self):
        with patch.object(stages, "ROOT", self.tool):
            for name, raw in (("config/budget.json", self.BUDGET), ("audit/runtime/registry/events.jsonl", self.JOURNAL)):
                with self.subTest(path=name):
                    (self.tool / name).write_bytes(b"Foreign tool bytes must not be consulted\n")
                    self.assertEqual(self.check(self.target)["status"], "metadata_consistent")
                    (self.target / name).write_bytes(b"Target differs from its original baseline\n")
                    with self.assertRaisesRegex(ValueError, "budget or journal"):
                        self.check(self.target)
                    (self.target / name).write_bytes(raw)
                    (self.tool / name).write_bytes(raw)

    def test_historical_descriptions_and_changed_paths_remain_target_bound(self):
        with patch.object(stages, "ROOT", self.tool):
            original = json.loads((self.target / "audit/stage2_current_readiness.json").read_bytes())
            value = deepcopy(original)
            value["historical_activity_descriptions"][0]["prior_current_fields"]["read_or_polled_this_turn_scope"] = "Wrong target history"
            self.write_metadata(self.target, value)
            with self.assertRaisesRegex(ValueError, "Prior activity descriptions"):
                self.check(self.target)
            value = deepcopy(original); value["source_changed_this_round"] = self.CHANGED[:-1]
            self.write_metadata(self.target, value)
            with self.assertRaisesRegex(ValueError, "source list"):
                self.check(self.target)

    def test_explicit_root_keeps_existing_bom_newline_and_scope_policy(self):
        root = self.home / "normalization"; (root / "cloud/__pycache__").mkdir(parents=True)
        (root / "cloud/known.py").write_bytes(b"\xef\xbb\xbfFIRST = 1\r\nSECOND = 2\rTHIRD = 3\n")
        (root / "cloud/__pycache__/ignored.py").write_bytes(b"ignored\n")
        (root / "cloud/ignored.csv").write_bytes(b"ignored\n")
        normalized = b"FIRST = 1\nSECOND = 2\nTHIRD = 3\n"
        expected = {"cloud/known.py": hashlib.sha256(normalized).hexdigest()}
        actual = stages.source_manifest(root=root)
        self.assertEqual(actual["source_files"], expected)
        self.assertIs(actual["market_data_included"], False)


if __name__ == "__main__":
    unittest.main()
