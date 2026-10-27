"""Auxiliary synthetic review. No real registry, QC, or financial data access."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT / "cloud"), str(ROOT / "tests")]
from qresearch.artifacts import MemoryArtifactStore, canonical_json, content_hash
from qresearch.engineering_rounds import validate_grant
from qresearch.registry import Registry, RegistryError, BudgetExceeded, CorruptRegistry
from test_engineering_rounds import package


LIMITS = {
    "configurations": {"normal": 8, "reserve": 4, "total": 12},
    "research": {"normal": 12, "reserve": 8, "total": 20},
    "lean": {"normal": 8, "reserve": 8, "total": 16},
}
USAGE = {
    "configurations": {"normal": 6, "reserve": 4, "total": 10},
    "research": {"normal": 6, "reserve": 7, "total": 13},
    "lean": {"normal": 1, "reserve": 0, "total": 1},
}


def context(usage=None):
    store = MemoryArtifactStore()
    return store, Registry(store, deepcopy(LIMITS), usage=deepcopy(usage or USAGE))


def receipt(registry, *, round_id="independent-normal", caps=None):
    grant = {"schema_version": 1, "round_id": round_id, "project_id": 17,
        "allocation": "normal", "limits": caps or {"configurations": 2, "research": 4, "lean": 2},
        "extra_spend_usd": 0, "final_test_enabled": False}
    auth = deepcopy(grant) | {"authority_kind": "explicit_human_user_message",
        "scope": "stage2_normal_allocation_exception", "global_limits_hash": content_hash(registry.limits),
        "request_text": "Synthetic only: record the exact bounded normal exception.",
        "normal_allocation_approval": {
            "question": "Synthetic only: allow at most 2 configs, 4 Research, 2 LEAN within existing buckets?",
            "answer": "允许"}}
    return rebind(grant, auth)


def rebind(grant, auth):
    digest = content_hash(auth)
    grant["authorization_ref"] = {"key": "engineering/rounds/user-authorizations/"+digest+".json", "sha256": digest}
    return grant, auth


class IndependentNormalGateTests(unittest.TestCase):
    def rejects_unchanged(self, store, registry, operation, error=(ValueError, RegistryError)):
        saved = dict(store._data)
        with self.assertRaises(error):
            operation()
        self.assertEqual(saved, store._data)

    def test_separate_resource_normal_limits_cannot_borrow_reserve_or_total(self):
        for key, excess in (("configurations", 3), ("research", 7), ("lean", 8)):
            with self.subTest(resource=key):
                store, registry = context()
                caps = {"configurations": 2, "research": 4, "lean": 2}
                caps[key] = excess
                grant, auth = receipt(registry, caps=caps)
                self.rejects_unchanged(store, registry,
                    lambda: registry.authorize_engineering_round(grant, [package()], auth), BudgetExceeded)

    def test_bound_hash_not_prose_reconstruction_controls_same_authorization(self):
        store, registry = context()
        grant, auth = receipt(registry)
        registry.authorize_engineering_round(grant, [package()], auth)
        for key, amount in (("configurations", 1), ("research", 5), ("lean", 3)):
            changed_grant, changed_auth = deepcopy(grant), deepcopy(auth)
            changed_grant["limits"][key] = changed_auth["limits"][key] = amount
            rebind(changed_grant, changed_auth)
            self.rejects_unchanged(store, registry,
                lambda: registry.authorize_engineering_round(changed_grant, [package()], changed_auth))

    def test_other_allocation_generic_scope_or_limits_hash_cannot_reuse_approval(self):
        for mutation in ("allocation", "scope", "global_hash", "authority"):
            with self.subTest(mutation=mutation):
                store, registry = context(); grant, auth = receipt(registry)
                if mutation == "allocation":
                    grant["allocation"] = auth["allocation"] = "reserve"
                elif mutation == "scope":
                    auth["scope"] = "stage2_engineering_round"
                elif mutation == "global_hash":
                    auth["global_limits_hash"] = "f"*64
                else:
                    auth["authority_kind"] = "LLM_proposal"
                rebind(grant, auth)
                self.rejects_unchanged(store, registry,
                    lambda: registry.authorize_engineering_round(grant, [package()], auth))

    def test_mutating_question_answer_or_request_after_hash_is_rejected(self):
        for key in ("question", "answer", "request"):
            with self.subTest(key=key):
                store, registry = context(); grant, auth = receipt(registry)
                if key == "request":
                    auth["request_text"] += " changed"
                else:
                    auth["normal_allocation_approval"][key] += " changed"
                self.rejects_unchanged(store, registry,
                    lambda: registry.authorize_engineering_round(grant, [package()], auth))

    def test_legacy_stop_not_reset_by_new_normal_round_or_changed_project(self):
        prior = deepcopy(USAGE)
        prior["configurations"] = {"normal": 4, "reserve": 4, "total": 8}
        store, registry = context(prior)
        first_id = registry.register_config(package("legacy-one"))
        registry.register_config(package("legacy-two"))
        grant, auth = receipt(registry)
        registry.authorize_engineering_round(grant, [package()], auth)
        self.assertEqual(registry.ENGINEERING_STOP_LIMIT, 2)
        self.rejects_unchanged(store, registry,
            lambda: registry.register_config(package("legacy-third", project=81)), BudgetExceeded)
        self.rejects_unchanged(store, registry,
            lambda: registry.bind_engineering_configuration(grant["round_id"], package("legacy-one")))
        current = registry.register_config(package(), allocation="normal")
        self.assertNotEqual(current, first_id)
        self.assertEqual(registry.snapshot()["limits"], LIMITS)

    def test_failed_config_retains_normal_charge_and_is_not_rebindable(self):
        store, registry = context(); grant, auth = receipt(registry)
        registry.authorize_engineering_round(grant, [package()], auth)
        config_id = registry.register_config(package(), allocation="normal")
        from test_engineering_rounds import bridge
        attempt = bridge(registry).claim("research", allocation="normal")
        registry.fail(attempt, "Synthetic permanent failure")
        charged = deepcopy(registry.snapshot()["usage"])
        registry.close_engineering_round(grant["round_id"], "Synthetic complete stop")
        self.assertEqual(registry.snapshot()["usage"], charged)
        self.assertEqual(charged["research"], {"normal": 7, "reserve": 7, "total": 14})
        new_grant, new_auth = receipt(registry, round_id="other-normal",
            caps={"configurations": 1, "research": 1, "lean": 0})
        registry.authorize_engineering_round(new_grant, [package("new")], new_auth)
        self.rejects_unchanged(store, registry,
            lambda: registry.bind_engineering_configuration(new_grant["round_id"], package()))
        self.assertIn(config_id, registry.snapshot()["config_ids"])

    def test_reserve_authorization_format_and_type_guards_unchanged(self):
        _, registry = context(); grant, auth = receipt(registry)
        grant["allocation"] = auth["allocation"] = "reserve"
        auth["scope"] = "stage2_engineering_round"
        auth.pop("normal_allocation_approval")
        rebind(grant, auth)
        self.assertIs(validate_grant(grant, auth, registry.limits), grant)
        for field, value in (("final_test_enabled", True), ("extra_spend_usd", True), ("schema_version", True), ("project_id", True)):
            candidate, candidate_auth = deepcopy(grant), deepcopy(auth)
            candidate[field] = candidate_auth[field] = value
            rebind(candidate, candidate_auth)
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_grant(candidate, candidate_auth, registry.limits)

    def test_bad_normal_charge_cannot_be_hidden_by_event_chain_rehash(self):
        store, registry = context(); grant, auth = receipt(registry)
        registry.authorize_engineering_round(grant, [package()], auth)
        identity = registry.register_config(package(), allocation="normal")
        # append_event computes a valid chain. Quota and binding validation must
        # still reject a second charge masquerading as a reserve registration.
        registry._append({"kind": "config_registered", "config_id": identity,
            "allocation": "reserve"})
        with self.assertRaises(CorruptRegistry):
            registry.snapshot()


if __name__ == "__main__":
    unittest.main(verbosity=2)
