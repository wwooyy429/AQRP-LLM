"""Development cross-checks for reclaim_pool016; not GPT acceptance.

Only synthetic alterations of existing permitted audit metadata are evaluated.
The tests do not query Object Store, fetch market data, execute Research/LEAN,
write registry events, or authorize deletion. No original payloads are loaded.
Run with python -B audit/review_packages/reclaim_pool016/test_assessment.py.
"""
from copy import deepcopy
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import socket
import unittest
from unittest.mock import patch


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def load_json(path):
    return json.loads(path.read_bytes())


def file_hash(path):
    return sha256(path.read_bytes()).hexdigest()


class PoolAssessmentCrossChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("reclaim_pool016_subject", HERE / "analyze_pool.py")
        cls.subject = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.subject)
        prior = HERE.parent / "storage_inventory015"
        cls.original_report = load_json(prior / "settled_result.json")["report"]
        cls.original_pool = load_json(prior / "actual_analysis.stdout.txt")[
            "payload_review_pool_without_observed_typed_incoming_edges"]
        cls.original_sources = load_json(HERE / "cloud_source_checks.json")

    def setUp(self):
        self.report = deepcopy(self.original_report)
        self.pool = deepcopy(self.original_pool)
        self.sources = deepcopy(self.original_sources)

    def assess(self):
        # An attempted hidden network fallback is a failure, never a test fixture.
        with patch.object(socket, "socket", side_effect=AssertionError("Network forbidden in offline check")):
            return self.subject.assess(self.report, self.pool, self.sources)

    def candidate(self, key=None):
        key = key or self.pool[0]["key"]
        return next(item for item in self.report["objects"] if item["key"] == key)

    def assert_all_retained(self, result):
        self.assertEqual(len(result["objects"]), 16)
        self.assertEqual(result["confirmed_reclaimable_objects"], [])
        self.assertEqual(result["confirmed_reclaimable_bytes"], 0)
        self.assertIsNone(result["potential_reclaimable_total_bytes"])
        self.assertIs(result["global_reference_closure_complete"], False)
        self.assertIs(result["deletion_authorized"], False)
        self.assertIs(result["final_test_enabled"], False)
        self.assertEqual(result["budget_changes"], 0)
        for item in result["objects"]:
            with self.subTest(key=item["key"]):
                self.assertEqual(item["classification"], "retain_insufficient_evidence")
                self.assertIs(item["deletion_authorized"], False)
                self.assertIs(item["retained"], True)
                self.assertIs(item["actual_content_hash_verified"], False)
                self.assertIsNone(item["content_sha256"])
                self.assertTrue(item["blocked_reasons"])

    def test_01_actual_metadata_fixture_retains_all_sixteen(self):
        self.assert_all_retained(self.assess())

    def test_02_absence_of_bounded_graph_incoming_edges_is_not_deletion_proof(self):
        targets = {edge["target_key"] for edge in self.report["references"]}
        self.assertTrue(all(item["key"] not in targets for item in self.pool))
        self.assert_all_retained(self.assess())

    def test_03_basename_digest_and_two_bytes_do_not_reveal_content(self):
        key = "generic-research/v1/feature-cache/v1/objects/4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945.json"
        source = self.candidate(key)
        self.assertEqual(source["size_bytes"], 2)
        self.assertIsNone(source["content_sha256"])
        row = next(item for item in self.assess()["objects"] if item["key"] == key)
        self.assertIsNone(row["content_sha256"])
        self.assertIs(row["actual_content_hash_verified"], False)
        self.assertIs(row["deletion_authorized"], False)

    def test_04_equal_sizes_are_not_verified_duplicates(self):
        pairs = {}
        for item in self.pool:
            pairs.setdefault(item["exact_size_bytes"], []).append(item["key"])
        equal_size_keys = [keys for keys in pairs.values() if len(keys) > 1]
        self.assertGreaterEqual(len(equal_size_keys), 1)
        result = self.assess()
        by_key = {item["key"]: item for item in result["objects"]}
        for keys in equal_size_keys:
            for key in keys:
                self.assertIs(by_key[key]["actual_content_hash_verified"], False)
                self.assertIs(by_key[key]["deletion_authorized"], False)
        self.assertEqual(result["confirmed_reclaimable_bytes"], 0)

    def test_05_four_a1_errors_keep_consumers_unknown(self):
        errors = [obs for obs in self.sources["observations"] if obs["result"].get("isError") is True]
        self.assertEqual(len(errors), 4)
        self.assertEqual(len({obs["args"]["projectId"] for obs in errors}), 4)
        self.assert_all_retained(self.assess())

    def test_06_report_candidate_size_tamper_rejected(self):
        self.candidate()["size_bytes"] += 1
        with self.assertRaises(ValueError):
            self.assess()

    def test_07_pool_candidate_size_tamper_rejected(self):
        self.pool[0]["exact_size_bytes"] += 1
        with self.assertRaises(ValueError):
            self.assess()

    def test_08_consistent_report_and_pool_size_tamper_still_rejected(self):
        self.candidate()["size_bytes"] += 1
        self.pool[0]["exact_size_bytes"] += 1
        with self.assertRaises(ValueError):
            self.assess()

    def test_09_forged_actual_hash_from_basename_rejected(self):
        row = self.candidate()
        row["content_sha256"] = Path(row["key"]).stem
        with self.assertRaises(ValueError):
            self.assess()

    def test_10_forged_pool_content_hash_rejected(self):
        self.pool[0]["content_sha256"] = Path(self.pool[0]["key"]).stem
        with self.assertRaises(ValueError):
            self.assess()

    def test_11_unverified_payload_cannot_be_relabelled_verified(self):
        self.candidate()["content_status"] = "payload_hash_verified"
        with self.assertRaises(ValueError):
            self.assess()

    def test_12_candidate_role_tamper_rejected(self):
        self.candidate()["role"] = "engineering_receipt"
        with self.assertRaises(ValueError):
            self.assess()

    def test_13_report_deletion_flag_tamper_rejected(self):
        self.candidate()["deletion_authorized"] = True
        with self.assertRaises(ValueError):
            self.assess()

    def test_14_pool_deletion_flag_tamper_rejected(self):
        self.pool[0]["deletion_authorized"] = True
        with self.assertRaises(ValueError):
            self.assess()

    def test_15_duplicate_candidate_key_rejected(self):
        self.pool[1] = deepcopy(self.pool[0])
        with self.assertRaises(ValueError):
            self.assess()

    def test_16_missing_candidate_rejected(self):
        self.pool.pop()
        with self.assertRaises(ValueError):
            self.assess()

    def test_17_unknown_candidate_key_rejected(self):
        self.pool[0]["key"] = "aqrp/engineering/v2/historical-snapshots/v1/objects/" + "0" * 64 + ".json"
        with self.assertRaises(ValueError):
            self.assess()

    def test_18_changed_incoming_edge_claim_rejected(self):
        self.pool[0]["incoming_edges_in_bounded_graph"] = 1
        with self.assertRaises(ValueError):
            self.assess()

    def test_19_final_window_gate_cannot_be_enabled_in_report(self):
        self.report["retention"]["final_test_enabled"] = True
        with self.assertRaises(ValueError):
            self.assess()

    def test_20_safe_deletion_gate_cannot_be_enabled_in_report(self):
        self.report["retention"]["safe_deletion_authorized"] = True
        with self.assertRaises(ValueError):
            self.assess()

    def test_21_bounded_graph_cannot_be_promoted_to_global_closure(self):
        self.report["retention"]["global_reference_closure"] = True
        with self.assertRaises(ValueError):
            self.assess()

    def test_22_missing_cross_project_error_is_not_no_consumers(self):
        index = next(i for i, obs in enumerate(self.sources["observations"]) if obs["result"].get("isError") is True)
        del self.sources["observations"][index]
        with self.assertRaises(ValueError):
            self.assess()

    def test_23_error_cannot_be_relabelled_success_without_native_matches(self):
        row = next(obs for obs in self.sources["observations"] if obs["result"].get("isError") is True)
        row["result"]["isError"] = False
        with self.assertRaises(ValueError):
            self.assess()

    def test_24_missing_main_project_source_page_rejected(self):
        index = next(i for i, obs in enumerate(self.sources["observations"])
                     if obs["args"] == {"projectId": 38436695, "query": "object_store", "page": 5})
        del self.sources["observations"][index]
        with self.assertRaises(ValueError):
            self.assess()

    def test_25_assessment_is_pure_and_budget_and_execution_gates_unchanged(self):
        guard_paths = [ROOT / "config/budget.json", ROOT / "config/development.json",
                       ROOT / "audit/runtime/registry/events.jsonl"]
        self.assertTrue(all(path.is_file() for path in guard_paths))
        before = {str(path): file_hash(path) for path in guard_paths}
        report_before, pool_before, sources_before = deepcopy(self.report), deepcopy(self.pool), deepcopy(self.sources)
        result = self.assess()
        self.assertEqual(before, {str(path): file_hash(path) for path in guard_paths})
        self.assertEqual(self.report, report_before)
        self.assertEqual(self.pool, pool_before)
        self.assertEqual(self.sources, sources_before)
        budget, development = load_json(guard_paths[0]), load_json(guard_paths[1])
        self.assertEqual(budget["usage"]["research_execution_attempts"], 19)
        self.assertEqual(budget["usage"]["lean_submission_attempts"], 4)
        self.assertEqual(budget["configuration_cycle"]["usage"]["total"], 5)
        self.assertIs(budget["final_evaluation_execution_enabled"], False)
        for name in ("market_research_enabled", "llm_runtime_enabled", "final_test_enabled", "live_trading_enabled"):
            self.assertIs(development["execution"][name], False)
        self.assert_all_retained(result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
