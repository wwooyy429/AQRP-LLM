"""Synthetic operator-authorized normal allocation exception; no cloud IO.

The recorded question/reply is trusted operator input, never a signature or
authentication of its speaker. These fixtures do not authorize real execution.
"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "cloud"), str(ROOT / "tests")]
from qresearch.artifacts import MemoryArtifactStore, canonical_json, content_hash
from qresearch.engineering_receipts import research_observation
from qresearch.engineering_rounds import validate_grant
from qresearch.registry import Registry, RegistryError, BudgetExceeded, CorruptRegistry
from test_engineering_rounds import bridge, documents as reserve_documents, package
from test_engineering_receipts import research_tool
from test_phase2_joint_boundaries import wrapper


def context():
    # Synthetic baseline mirrors fixed bucket capacities and previously charged
    # usage, including exhausted configuration reserve. No real ledger is read.
    limits = {
        "configurations": {"total": 12, "normal": 8, "reserve": 4},
        "research": {"total": 20, "normal": 12, "reserve": 8},
        "lean": {"total": 16, "normal": 8, "reserve": 8},
    }
    usage = {
        "configurations": {"total": 10, "normal": 6, "reserve": 4},
        "research": {"total": 13, "normal": 6, "reserve": 7},
        "lean": {"total": 1, "normal": 1, "reserve": 0},
    }
    store = MemoryArtifactStore()
    return store, Registry(store, limits, usage=usage)


def documents(registry, round_id="synthetic-normal-exception", project=17):
    grant, authorization = reserve_documents(registry, round_id=round_id, project=project,
        limits={"configurations": 2, "research": 4, "lean": 2})
    grant["allocation"] = authorization["allocation"] = "normal"
    authorization["scope"] = "stage2_normal_allocation_exception"
    authorization["normal_allocation_approval"] = {
        "question": ("Synthetic complete operator question: permit this Stage 2 normal allocation exception, "
                     "at most 2 configurations, 4 Research executions and 2 LEAN submissions, "
                     "within unchanged total and bucket limits, no extra spend and final testing disabled?"),
        "answer": "允许",
    }
    return rebind(grant, authorization)


def rebind(grant, authorization):
    digest = content_hash(authorization)
    grant["authorization_ref"] = {"key": "engineering/rounds/user-authorizations/" + digest + ".json",
                                  "sha256": digest}
    return grant, authorization


def authorize(registry):
    grant, authorization = documents(registry)
    registry.authorize_engineering_round(grant, [package()], authorization)
    return grant, authorization


def complete_research(task, *, retry_of=None):
    attempt = task.claim("research", allocation="normal", retry_of=retry_of,
                         reason="Synthetic explicit repair" if retry_of else None)
    payload = task.payload(attempt)
    deployment = {"source_manifest_hash": payload["identity"]["source_manifest_hash"],
                  "deployment_hash": payload["identity"]["deployment_hash"], "input_hash": "f" * 64}
    observed = research_observation(payload, deployment, research_tool(payload, wrapper(payload)))
    task.record_submission(attempt, observed["submission"])
    task.consume_completion(attempt, completion_source=lambda _: observed["completion"])
    return attempt


class NormalEngineeringRoundTests(unittest.TestCase):
    def reject_without_write(self, store, registry, action, errors=(RegistryError, ValueError)):
        saved, snapshot = dict(store._data), registry.snapshot()
        with self.assertRaises(errors):
            action()
        self.assertEqual(store._data, saved)
        self.assertEqual(registry.snapshot(), snapshot)

    def test_explicit_normal_exception_is_metadata_only_idempotent_and_replayable(self):
        store, registry = context()
        before, prefix = registry.snapshot(), store.read_bytes(registry.JOURNAL)
        grant, authorization = authorize(registry)
        self.assertEqual(set(grant), {"schema_version", "round_id", "project_id", "allocation", "limits",
                                     "authorization_ref", "final_test_enabled", "extra_spend_usd"})
        self.assertEqual(grant["schema_version"], 1)
        self.assertEqual(registry.snapshot(), before)
        self.assertTrue(store.read_bytes(registry.JOURNAL).startswith(prefix))
        saved = dict(store._data)
        registry.authorize_engineering_round(grant, [package()], authorization)
        replayed = Registry(store, registry.limits, usage=registry.initial_usage)
        self.assertEqual(replayed.engineering_rounds_snapshot(), registry.engineering_rounds_snapshot())
        self.assertEqual(store._data, saved)

    def test_generic_normal_scope_or_missing_approval_cannot_open_exception(self):
        mutations = [lambda a: a.pop("normal_allocation_approval"),
                     lambda a: a.update(scope="stage2_engineering_round"),
                     lambda a: a.update(scope="unrestricted_normal"),
                     lambda a: a.update(authority_kind="llm_proposal")]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                store, registry = context()
                grant, authorization = documents(registry)
                mutate(authorization)
                rebind(grant, authorization)
                self.reject_without_write(store, registry, lambda: registry.authorize_engineering_round(
                    grant, [package()], authorization))
        store, registry = context()
        grant, authorization = reserve_documents(registry)
        grant["allocation"] = authorization["allocation"] = "normal"
        rebind(grant, authorization)
        self.reject_without_write(store, registry, lambda: registry.authorize_engineering_round(
            grant, [package()], authorization))

    def test_approval_closed_schema_native_strings_bounds_and_literal_reply(self):
        class StringSubclass(str):
            pass

        invalid = [{}, {"question": "Q", "answer": "允许", "extra": True},
                   {"question": "", "answer": "允许"}, {"question": "  ", "answer": "允许"},
                   {"question": "Q" * 8001, "answer": "允许"},
                   {"question": True, "answer": "允许"}, {"question": ["Q"], "answer": "允许"},
                   {"question": StringSubclass("Q"), "answer": "允许"},
                   {"question": "Q", "answer": StringSubclass("允许")},
                   {"question": "Q", "answer": "不允许"}, {"question": "Q", "answer": "允许 "},
                   {"question": "Q", "answer": ""}, {"question": "Q", "answer": True},
                   {"question": "Q", "answer": "A" * 1001}, None, []]
        _, registry = context()
        for approval in invalid:
            with self.subTest(approval=approval):
                grant, authorization = documents(registry)
                authorization["normal_allocation_approval"] = approval
                rebind(grant, authorization)
                with self.assertRaises(ValueError):
                    validate_grant(grant, authorization, registry.limits)
        grant, authorization = documents(registry)
        authorization["normal_allocation_approval"]["question"] = "Q" * 8000
        rebind(grant, authorization)
        self.assertIs(validate_grant(grant, authorization, registry.limits), grant)

    def test_reserve_schema_and_scope_are_unchanged(self):
        # Reserve has no room at the synthetic baseline, but validation still
        # accepts its original schema and reaches the unchanged capacity guard.
        store, registry = context()
        grant, authorization = reserve_documents(registry)
        self.assertIs(validate_grant(grant, authorization, registry.limits), grant)
        self.reject_without_write(store, registry, lambda: registry.authorize_engineering_round(
            grant, [package()], authorization), (BudgetExceeded,))
        authorization["normal_allocation_approval"] = {"question": "Q", "answer": "允许"}
        rebind(grant, authorization)
        with self.assertRaises(ValueError):
            validate_grant(grant, authorization, registry.limits)

    def test_two_config_four_research_two_lean_caps_charge_failures_and_same_parent(self):
        store, registry = context()
        grant, _ = authorize(registry)
        first = bridge(registry); first.register(allocation="normal")
        self.reject_without_write(store, registry, lambda: first.claim("lean", allocation="normal"))
        failed = first.claim("research", allocation="normal")
        registry.fail(failed, "Synthetic Research failure still charged")
        complete_research(first, retry_of=failed.attempt_id)
        lean = first.claim("lean", allocation="normal")
        registry.fail(lean, "Synthetic LEAN failure still charged")
        second_lean = first.claim("lean", allocation="normal", retry_of=lean.attempt_id,
                                  reason="Synthetic explicit LEAN repair")
        registry.fail(second_lean, "Synthetic second LEAN failure still charged")
        self.reject_without_write(store, registry, lambda: first.claim("lean", allocation="normal",
            retry_of=second_lean.attempt_id, reason="Third LEAN exceeds round cap"), (BudgetExceeded,))
        second_package = package("normal-repair")
        registry.bind_engineering_configuration(grant["round_id"], second_package)
        second = bridge(registry, second_package); second.register(allocation="normal")
        self.reject_without_write(store, registry, lambda: second.claim("lean", allocation="normal"))
        research = second.claim("research", allocation="normal")
        registry.fail(research, "Synthetic third Research failure")
        fourth = second.claim("research", allocation="normal", retry_of=research.attempt_id,
                              reason="Synthetic explicit Research repair")
        registry.fail(fourth, "Synthetic fourth Research failure")
        self.reject_without_write(store, registry, lambda: second.claim("research", allocation="normal",
            retry_of=fourth.attempt_id, reason="Fifth Research exceeds round cap"), (BudgetExceeded,))
        self.reject_without_write(store, registry, lambda: registry.bind_engineering_configuration(
            grant["round_id"], package("third-normal")), (BudgetExceeded,))
        self.assertEqual(registry.engineering_rounds_snapshot()[grant["round_id"]]["usage"],
                         {"configurations": 2, "research": 4, "lean": 2})
        for kind, debit in (("configurations", 2), ("research", 4), ("lean", 2)):
            usage = registry.snapshot()["usage"][kind]
            original = registry.initial_usage[kind]
            self.assertEqual(usage["normal"], original["normal"] + debit)
            self.assertEqual(usage["total"], original["total"] + debit)
            self.assertEqual(usage["reserve"], original["reserve"])

    def test_normal_grant_cannot_fall_back_to_reserve_or_steal_other_reserved_capacity(self):
        store, registry = context(); grant, _ = authorize(registry)
        self.reject_without_write(store, registry, lambda: registry.register_config(
            package(), allocation="reserve"), (BudgetExceeded,))
        task = bridge(registry); task.register(allocation="normal")
        self.reject_without_write(store, registry, lambda: task.claim("research", allocation="reserve"),
                                  (BudgetExceeded,))
        self.reject_without_write(store, registry, lambda: registry.register_config(
            {"synthetic": "cannot-spend-reserved-normal-config"}, allocation="normal"), (BudgetExceeded,))
        # One configuration normal slot remains globally but is reserved.
        # A larger grant cannot borrow exhausted reserve or exceed total.
        store2, registry2 = context(); oversized, authority = documents(registry2)
        oversized["limits"]["configurations"] = authority["limits"]["configurations"] = 3
        rebind(oversized, authority)
        self.reject_without_write(store2, registry2, lambda: registry2.authorize_engineering_round(
            oversized, [package()], authority), (BudgetExceeded,))

    def test_pending_project_bind_and_close_guards_and_terminal_close_replay(self):
        store, registry = context(); grant, authority = authorize(registry)
        task = bridge(registry); task.register(allocation="normal")
        attempt = task.claim("research", allocation="normal")
        registry.ambiguous(attempt, reason="Synthetic unknown dispatch outcome")
        self.reject_without_write(store, registry, lambda: registry.bind_engineering_configuration(
            grant["round_id"], package("repair")))
        self.reject_without_write(store, registry, lambda: registry.close_engineering_round(
            grant["round_id"], "Cannot close unknown work"))
        other_grant, other_authority = documents(registry, round_id="other-same-project")
        self.reject_without_write(store, registry, lambda: registry.authorize_engineering_round(
            other_grant, [package("other")], other_authority))
        restored = bridge(Registry(store, registry.limits, usage=registry.initial_usage))
        self.assertFalse(restored.claim("research", allocation="normal").should_execute)
        self.assertEqual(restored.claim("research").attempt_id, attempt.attempt_id)
        registry.fail(attempt, "Synthetic resolved terminal", reconciliation="Synthetic no-running-task evidence")
        before = registry.snapshot()["usage"]
        registry.close_engineering_round(grant["round_id"], "Synthetic final investigation closure")
        self.assertEqual(registry.snapshot()["usage"], before)
        self.reject_without_write(store, registry, lambda: registry.bind_engineering_configuration(
            grant["round_id"], package("repair")))
        self.reject_without_write(store, registry, lambda: task.claim("research", allocation="normal",
            retry_of=attempt.attempt_id, reason="Closed round cannot restart"), (BudgetExceeded,))
        registry.authorize_engineering_round(grant, [package()], authority)
        replayed = Registry(store, registry.limits, usage=registry.initial_usage)
        self.assertEqual(replayed.engineering_rounds_snapshot()[grant["round_id"]]["status"], "closed")
        # Released unused normal reservation is available, but charged failures
        # remain in both normal and total counters after closing and replay.
        replayed.register_config({"synthetic": "released-normal-slot"}, allocation="normal")
        self.assertEqual(replayed.snapshot()["usage"]["configurations"]["total"], 12)

    def test_tampered_authority_or_cross_bucket_event_is_rejected_on_replay(self):
        store, registry = context(); grant, authority = authorize(registry)
        changed = deepcopy(authority); changed["normal_allocation_approval"]["answer"] = "不允许"
        store._data[grant["authorization_ref"]["key"]] = canonical_json(changed)
        with self.assertRaises(CorruptRegistry):
            Registry(store, registry.limits, usage=registry.initial_usage)
        store, registry = context(); authorize(registry)
        task = bridge(registry); task.register(allocation="normal")
        registry._append({"kind": "attempt_started", "attempt_id": "b" * 32,
            "config_id": task.config_id, "stage": "research", "operation_key": task._operation("research"),
            "allocation": "reserve", "retry_of": None, "reason": None,
            "result_key": registry.result_key(task.config_id, "research", task._operation("research"))})
        with self.assertRaises(CorruptRegistry):
            registry.snapshot()


if __name__ == "__main__":
    unittest.main()
