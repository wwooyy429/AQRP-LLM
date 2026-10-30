"""Developer-assistance review only; synthetic stores and read-only old journal."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "cloud"), str(ROOT / "tests")]
from qresearch.artifacts import MemoryArtifactStore, canonical_json, content_hash, decode_events
from qresearch.registry import Registry, RegistryError, BudgetExceeded
from qresearch.engineering_tasks import EngineeringTaskPlan, EngineeringTaskBridge
from qresearch.engineering_rounds import validate_grant
from qresearch.collection import _safe_source_diagnostic, _source_failure_message, SourceDiagnosticError
from test_phase2_joint_boundaries import joint_document
from test_engineering_rounds import finish_research


def fixture(tag="a", project=17):
    raw = joint_document()
    raw.update(plan_id="independent-" + tag, project_id=project,
               max_retries={"research": 2, "lean": 2})
    return {"engineering_task_schema_version": 1,
            "plan": EngineeringTaskPlan.from_dict(raw, discovered_project_ids=[project]).to_dict()}


def setup(reserve=3, limits=None, tag="round-independent"):
    store = MemoryArtifactStore()
    limits = limits or {key: {"normal": 8, "reserve": reserve, "total": 8 + reserve}
                        for key in ("configurations", "research", "lean")}
    registry = Registry(store, limits)
    grant = {"schema_version": 1, "round_id": tag, "project_id": 17, "allocation": "reserve",
             "limits": {"configurations": 2, "research": 2, "lean": 1},
             "final_test_enabled": False, "extra_spend_usd": 0}
    auth = copy.deepcopy(grant) | {"authority_kind": "explicit_human_user_message",
        "scope": "stage2_engineering_round", "global_limits_hash": content_hash(registry.limits),
        "request_text": "Independent synthetic user authorization; no real quota."}
    digest = content_hash(auth)
    grant["authorization_ref"] = {"key": "engineering/rounds/user-authorizations/" + digest + ".json", "sha256": digest}
    return store, registry, grant, auth


class IndependentBoundaries(unittest.TestCase):
    def test_actual_legacy_journal_prefix_and_limits_are_preserved_read_only(self):
        rel = "audit/runtime/registry/events.jsonl"
        previous = subprocess.check_output(["git", "show", "65b8025b8618021eddd50520fe87c764b60af377:" + rel], cwd=ROOT)
        current = (ROOT / rel).read_bytes()
        self.assertEqual(len(decode_events(previous)), 17)
        self.assertTrue(current.startswith(previous))
        budget_previous = json.loads(subprocess.check_output(["git", "show", "65b8025b8618021eddd50520fe87c764b60af377:config/budget.json"], cwd=ROOT))
        budget_now = json.loads((ROOT / "config/budget.json").read_text(encoding="utf-8-sig"))
        for key in ("limits", "allocations"):
            self.assertEqual(budget_now[key], budget_previous[key])
        settings = json.loads((ROOT / "config/development.json").read_text(encoding="utf-8-sig"))
        self.assertIs(settings["execution"]["final_test_enabled"], False)

    def test_grant_boolean_counts_rejected_even_with_matching_authority(self):
        for resource in ("configurations", "research", "lean"):
            store, reg, grant, auth = setup()
            grant["limits"][resource] = True
            auth["limits"][resource] = True
            digest = content_hash(auth)
            grant["authorization_ref"] = {"key": "engineering/rounds/user-authorizations/" + digest + ".json", "sha256": digest}
            before = dict(store._data)
            with self.assertRaises(ValueError):
                reg.authorize_engineering_round(grant, [fixture()], auth)
            self.assertEqual(store._data, before)

    def test_zero_lean_limit_rejects_direct_charge_without_changing_registry(self):
        store, reg, grant, auth = setup()
        grant["limits"]["lean"] = auth["limits"]["lean"] = 0
        digest = content_hash(auth)
        grant["authorization_ref"] = {"key": "engineering/rounds/user-authorizations/" + digest + ".json", "sha256": digest}
        reg.authorize_engineering_round(grant, [fixture()], auth)
        task = EngineeringTaskBridge(reg, EngineeringTaskPlan.from_dict(fixture()["plan"], discovered_project_ids=[17]))
        task.register(allocation="reserve")
        finish_research(task)
        before = dict(store._data)
        with self.assertRaises(BudgetExceeded):
            task.claim("lean", allocation="reserve")
        self.assertEqual(store._data, before)

    def test_closed_round_cannot_charge_never_registered_bound_repair(self):
        store, reg, grant, auth = setup()
        reg.authorize_engineering_round(grant, [fixture()], auth)
        repair = fixture("repair")
        reg.bind_engineering_configuration(grant["round_id"], repair)
        reg.close_engineering_round(grant["round_id"], "Synthetic closure before dispatch")
        before = dict(store._data)
        reopened = Registry(store, reg.limits)
        with self.assertRaises(BudgetExceeded):
            reopened.register_config(repair, allocation="reserve")
        self.assertEqual(store._data, before)

    def test_authorization_does_not_restore_old_failure_or_create_hidden_charge(self):
        store, reg, grant, auth = setup()
        old = fixture("old")
        task = EngineeringTaskBridge(reg, EngineeringTaskPlan.from_dict(old["plan"], discovered_project_ids=[17]))
        task.register()
        attempt = task.claim("research")
        reg.fail(attempt, "Synthetic observed failure")
        before = reg.snapshot()["usage"]
        reg.authorize_engineering_round(grant, [fixture()], auth)
        self.assertEqual(reg.snapshot()["usage"], before)
        recovered = task.claim("research")
        self.assertEqual(recovered.attempt_id, attempt.attempt_id)
        self.assertFalse(recovered.should_execute)
        self.assertEqual(recovered.status, "failed")

    def test_native_error_object_is_never_formatted(self):
        class SecretError(RuntimeError):
            def __str__(self):
                raise AssertionError("secret formatting attempted")
        self.assertEqual(_source_failure_message("fixed prefix", SecretError("market row secret")), "fixed prefix")

    def test_diagnostics_reject_arbitrary_strings_non_native_numbers_and_extra_values(self):
        from test_source_diagnostics import SourceDiagnosticsTests
        from test_historical_source import FakeQB
        diagnostic, _, _ = SourceDiagnosticsTests().fail(FakeQB(RuntimeError("raw financial value")))
        for key, value in (("stage", "secret row"), ("response_rows", True),
                           ("rows_emitted", -1), ("native_calls", 10**10), ("unknown", "financial value")):
            candidate = dict(diagnostic)
            candidate[key] = value
            self.assertIsNone(_safe_source_diagnostic(candidate))
            error = SourceDiagnosticError("ignored original message", diagnostic=candidate)
            self.assertEqual(_source_failure_message("fixed prefix", error), "fixed prefix")


if __name__ == "__main__":
    unittest.main(verbosity=2)
