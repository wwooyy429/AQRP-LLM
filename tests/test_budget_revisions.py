"""Append-only user budget revisions, synthetic stores and instructions only."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "cloud"), str(ROOT / "tests")]
from qresearch.artifacts import (MemoryArtifactStore, FilesystemArtifactStore, canonical_json,
                                content_hash, decode_events)
from qresearch.budget_revisions import (BudgetRevisionError, authorization_reference,
                                       revision_reference, validate_revision)
from qresearch.registry import Registry, RegistryError, BudgetExceeded, CorruptRegistry
import test_engineering_rounds as rounds


LIMITS = {"configurations": {"normal": 2, "reserve": 1, "total": 3},
          "research": {"normal": 3, "reserve": 3, "total": 6},
          "lean": {"normal": 3, "reserve": 3, "total": 6}}


def documents(registry, identity="SYNTHETIC-budget-revision-1"):
    previous = registry.limits
    new = deepcopy(previous)
    new["configurations"]["reserve"] += 1
    new["configurations"]["total"] += 1
    revision = {"schema_version": 1, "revision_id": identity,
        "previous_limits_hash": content_hash(previous), "new_limits": new,
        "final_test_enabled": False, "extra_spend_usd": 0}
    authorization = deepcopy(revision) | {"authority_kind": "explicit_human_user_message",
        "scope": "configuration_reserve_increment_v1", "request_text": "SYNTHETIC approval fixture only.",
        "approval": {"question": "SYNTHETIC: add one configuration reserve slot only?", "answer": "批准"}}
    revision["authorization_ref"] = authorization_reference(authorization)
    return revision, authorization


def bind(revision, authorization):
    for name, value in revision.items():
        if name != "authorization_ref":
            authorization[name] = deepcopy(value)
    revision["authorization_ref"] = authorization_reference(authorization)


class BudgetRevisionsTests(unittest.TestCase):
    def setUp(self):
        self.store = MemoryArtifactStore()
        self.registry = Registry(self.store, deepcopy(LIMITS))

    def reject_without_writes(self, action, errors=(ValueError, RegistryError)):
        before, snapshot = dict(self.store._data), self.registry.snapshot()
        with self.assertRaises(errors):
            action()
        self.assertEqual(self.store._data, before)
        self.assertEqual(self.registry.snapshot(), snapshot)

    def test_extension_changes_only_effective_limits_and_preserves_initialized_prefix(self):
        revision, authorization = documents(self.registry)
        prefix = self.store.read_bytes(self.registry.JOURNAL)
        original = self.registry.snapshot()
        result = self.registry.authorize_budget_revision(revision, authorization)
        self.assertTrue(self.store.read_bytes(self.registry.JOURNAL).startswith(prefix))
        self.assertEqual(len(decode_events(self.store.read_bytes(self.registry.JOURNAL))), 2)
        self.assertEqual(result["revision_id"], revision["revision_id"])
        self.assertEqual(result["revision_hash"], content_hash(revision))
        self.assertEqual(result["revision_ref"], revision_reference(revision))
        self.assertEqual(self.registry.limits, revision["new_limits"])
        self.assertEqual(self.registry._initial_limits, LIMITS)
        after = self.registry.snapshot()
        self.assertEqual({k:v for k,v in after.items() if k != "limits"},
                         {k:v for k,v in original.items() if k != "limits"})
        self.assertEqual(Registry(self.store, deepcopy(LIMITS)).snapshot(), after)
        self.assertEqual(self.registry.budget_revisions_snapshot()[revision["revision_id"]], result)
        with self.assertRaises(CorruptRegistry):
            Registry(self.store, revision["new_limits"])

    def test_repeated_identical_revision_is_idempotent_even_during_later_activity(self):
        revision, authorization = documents(self.registry)
        first = self.registry.authorize_budget_revision(revision, authorization)
        frozen = rounds.package("after-revision")
        grant, authority = rounds.documents(self.registry, limits={"configurations":1,"research":1,"lean":1})
        self.registry.authorize_engineering_round(grant, [frozen], authority)
        task = rounds.bridge(self.registry, frozen)
        task.register(allocation="reserve")
        task.claim("research", allocation="reserve")
        saved = dict(self.store._data)
        self.assertEqual(self.registry.authorize_budget_revision(revision, authorization), first)
        self.assertEqual(self.store._data, saved)
        changed = deepcopy(authorization)
        changed["request_text"] += " changed"
        replacement = deepcopy(revision)
        replacement["authorization_ref"] = authorization_reference(changed)
        self.reject_without_writes(lambda: self.registry.authorize_budget_revision(replacement, changed))

    def test_historical_closed_round_uses_its_old_limits_hash_after_restart(self):
        old_package = rounds.package("old-before-revision")
        old_grant, old_auth = rounds.documents(self.registry, round_id="old-round",
            limits={"configurations":1,"research":1,"lean":1})
        self.registry.authorize_engineering_round(old_grant, [old_package], old_auth)
        old_task = rounds.bridge(self.registry, old_package)
        old_task.register(allocation="reserve")
        attempt = old_task.claim("research", allocation="reserve")
        self.registry.fail(attempt, "SYNTHETIC observed terminal failure")
        self.registry.close_engineering_round("old-round", "SYNTHETIC stop")
        old_snapshot = self.registry.engineering_rounds_snapshot()["old-round"]
        prefix = self.store.read_bytes(self.registry.JOURNAL)
        saved_auth = self.store.read_bytes(old_grant["authorization_ref"]["key"])
        revision, authorization = documents(self.registry)
        self.registry.authorize_budget_revision(revision, authorization)
        restarted = Registry(self.store, deepcopy(LIMITS))
        self.assertEqual(restarted.engineering_rounds_snapshot()["old-round"], old_snapshot)
        self.assertEqual(self.store.read_bytes(old_grant["authorization_ref"]["key"]), saved_auth)
        self.assertEqual(restarted.authorize_engineering_round(old_grant, [old_package], old_auth), old_snapshot)
        tampered = deepcopy(old_auth)
        tampered["request_text"] = "Changed historical instruction"
        with self.assertRaises(RegistryError):
            restarted.authorize_engineering_round(old_grant, [old_package], tampered)
        new_package = rounds.package("new-after-revision")
        grant, authority = rounds.documents(restarted, round_id="new-round",
            limits={"configurations":1,"research":1,"lean":1})
        self.assertNotEqual(authority["global_limits_hash"], old_auth["global_limits_hash"])
        restarted.authorize_engineering_round(grant, [new_package], authority)
        task = rounds.bridge(restarted, new_package)
        task.register(allocation="reserve")
        with self.assertRaises(ValueError):
            task.claim("lean", allocation="reserve")
        rounds.finish_research(task)
        lean = task.claim("lean", allocation="reserve")
        restarted.fail(lean, "SYNTHETIC observed runtime failure")
        restarted.close_engineering_round("new-round", "SYNTHETIC stop without retry")
        self.assertTrue(self.store.read_bytes(self.registry.JOURNAL).startswith(prefix))
        self.assertEqual(restarted.snapshot()["usage"]["configurations"]["reserve"], 2)
        self.assertEqual(restarted.snapshot()["usage"]["research"]["reserve"], 2)
        self.assertEqual(restarted.snapshot()["usage"]["lean"]["reserve"], 1)
        self.assertEqual(Registry(self.store, LIMITS).snapshot(), restarted.snapshot())

    def test_exhausted_configuration_cap_opens_exactly_one_new_reserve_slot(self):
        store = MemoryArtifactStore()
        usage = {name: {"normal":0,"reserve":0,"total":0} for name in LIMITS}
        usage["configurations"] = deepcopy(LIMITS["configurations"])
        registry = Registry(store, LIMITS, usage)
        with self.assertRaises(BudgetExceeded):
            registry.register_config({"synthetic": 1}, allocation="reserve")
        revision, authorization = documents(registry)
        registry.authorize_budget_revision(revision, authorization)
        registry.register_config({"synthetic": 1}, allocation="reserve")
        with self.assertRaises(BudgetExceeded):
            registry.register_config({"synthetic": 2}, allocation="reserve")
        self.assertEqual(registry.snapshot()["usage"]["configurations"]["total"], 4)

    def test_new_revision_requires_no_open_round_and_no_unresolved_attempt(self):
        frozen = rounds.package()
        grant, authority = rounds.documents(self.registry, limits={"configurations":1,"research":1,"lean":1})
        self.registry.authorize_engineering_round(grant, [frozen], authority)
        revision, authorization = documents(self.registry)
        self.reject_without_writes(lambda: self.registry.authorize_budget_revision(revision, authorization))
        self.registry.close_engineering_round(grant["round_id"], "SYNTHETIC unused grant close")
        config = self.registry.register_config({"synthetic": "plain-config"})
        attempt = self.registry.begin_attempt(config, "research")
        for status in ("started", "pending", "ambiguous"):
            if status == "pending":
                self.registry.pending(attempt, external_id="SYNTHETIC-external")
            elif status == "ambiguous":
                self.registry.ambiguous(attempt, reason="SYNTHETIC uncertain outcome")
            self.reject_without_writes(lambda: self.registry.authorize_budget_revision(revision, authorization))
        self.registry.fail(attempt, "SYNTHETIC confirmed terminal", reconciliation="SYNTHETIC evidence")
        self.registry.authorize_budget_revision(revision, authorization)

    def test_changed_duplicate_stale_previous_hash_and_extra_dimensions_reject(self):
        revision, authorization = documents(self.registry)
        stale, stale_auth = documents(self.registry, identity="other-id-with-stale-previous")
        self.registry.authorize_budget_revision(revision, authorization)
        self.reject_without_writes(lambda: self.registry.authorize_budget_revision(stale, stale_auth))
        for resource, field, difference in (("research","reserve",1),("lean","normal",1),
                ("configurations","normal",1),("configurations","reserve",2),
                ("configurations","reserve",0)):
            changed, authority = documents(self.registry, identity="SYNTHETIC-invalid-new-delta")
            changed["new_limits"][resource][field] += difference
            changed["new_limits"][resource]["total"] = (
                changed["new_limits"][resource]["normal"] + changed["new_limits"][resource]["reserve"])
            if difference == 0:
                changed["new_limits"]["configurations"]["reserve"] -= 1
                changed["new_limits"]["configurations"]["total"] -= 1
            bind(changed, authority)
            self.reject_without_writes(lambda: self.registry.authorize_budget_revision(changed, authority))

    def test_closed_schema_native_counters_spend_final_and_user_approval(self):
        base, authority = documents(self.registry)
        changes = [lambda r,a:r.update(schema_version=True), lambda r,a:r.update(extra="SECRET"),
            lambda r,a:r.update(final_test_enabled=True), lambda r,a:r.update(extra_spend_usd=0.0),
            lambda r,a:r.update(extra_spend_usd=True), lambda r,a:r.update(previous_limits_hash="A"*64),
            lambda r,a:r.update(revision_id="../SECRET"),
            lambda r,a:r["new_limits"]["configurations"].update(reserve=True,total=3),
            lambda r,a:r["new_limits"]["configurations"].update(reserve=-1,total=1),
            lambda r,a:r["new_limits"]["research"].update(extra=0),
            lambda r,a:a["approval"].update(answer="允许"), lambda r,a:a["approval"].update(extra="SECRET"),
            lambda r,a:a.update(scope="stage2_engineering_round"), lambda r,a:a.update(request_text=" "),
            lambda r,a:a.update(request_text="\ud800"), lambda r,a:a.update(extra="SECRET")]
        for change in changes:
            revision, authorization = deepcopy(base), deepcopy(authority)
            change(revision, authorization)
            # Even well-bound malformed requests must be denied before writes.
            try:
                bind(revision, authorization)
            except BudgetRevisionError:
                pass
            self.reject_without_writes(lambda: self.registry.authorize_budget_revision(revision, authorization))

    def test_refs_and_changed_authorization_cannot_be_substituted(self):
        base, authority = documents(self.registry)
        for ref in ({"key":"../SECRET","sha256":"a"*64}, {"sha256":"a"*64},
                    dict(base["authorization_ref"], extra=True), dict(base["authorization_ref"], sha256="b"*64)):
            changed = deepcopy(base)
            changed["authorization_ref"] = ref
            self.reject_without_writes(lambda: self.registry.authorize_budget_revision(changed, authority))
        authority["approval"]["question"] += " changed without rebinding"
        self.reject_without_writes(lambda: self.registry.authorize_budget_revision(base, authority))

    def test_round_identifier_validation_stays_closed_before_duplicate_lookup(self):
        frozen = rounds.package("SYNTHETIC-identifier-boundary")
        grant, authority = rounds.documents(self.registry, limits={"configurations":1,"research":1,"lean":1})
        for value in (None, True, False, 1, [], {}, "", "../SECRET"):
            changed = deepcopy(grant)
            if value is None:
                changed.pop("round_id")
            else:
                changed["round_id"] = value
            self.reject_without_writes(lambda: self.registry.authorize_engineering_round(changed, [frozen], authority))
        for invalid in (None, [], "SECRET"):
            self.reject_without_writes(lambda: self.registry.authorize_engineering_round(invalid, [frozen], authority))

    def test_limits_return_copy_and_internal_transactions_do_not_reenter_getter(self):
        revision, authority = documents(self.registry)
        with patch.object(Registry, "limits", property(lambda _: (_ for _ in ()).throw(AssertionError("No nested getter")))):
            self.registry.authorize_budget_revision(revision, authority)
            self.assertEqual(self.registry.snapshot()["limits"], revision["new_limits"])
        observed = self.registry.limits
        observed["configurations"]["total"] = 999
        self.assertEqual(self.registry.limits, revision["new_limits"])
        result = self.registry.budget_revisions_snapshot()
        result[revision["revision_id"]]["revision"]["new_limits"]["lean"]["reserve"] = 999
        self.assertEqual(self.registry.limits, revision["new_limits"])

    def test_concurrent_same_identity_appends_one_revision_and_conflicting_stale_loses(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = Registry(FilesystemArtifactStore(directory), LIMITS)
            revision, authority = documents(registry)
            prefix = registry.store.read_bytes(registry.JOURNAL)
            def apply(_):
                return Registry(FilesystemArtifactStore(directory), LIMITS).authorize_budget_revision(revision, authority)
            with ThreadPoolExecutor(max_workers=6) as executor:
                results = list(executor.map(apply, range(12)))
            self.assertTrue(all(item == results[0] for item in results))
            self.assertTrue(registry.store.read_bytes(registry.JOURNAL).startswith(prefix))
            self.assertEqual(len(decode_events(registry.store.read_bytes(registry.JOURNAL))), 2)
        with tempfile.TemporaryDirectory() as directory:
            registry = Registry(FilesystemArtifactStore(directory), LIMITS)
            one, auth_one = documents(registry, "SYNTHETIC-race-one")
            two, auth_two = documents(registry, "SYNTHETIC-race-two")
            def competing(pair):
                try:
                    Registry(FilesystemArtifactStore(directory), LIMITS).authorize_budget_revision(*pair)
                    return True
                except ValueError:
                    return False
            with ThreadPoolExecutor(max_workers=2) as executor:
                winners = list(executor.map(competing, [(one, auth_one), (two, auth_two)]))
            self.assertEqual(sum(winners), 1)
            self.assertEqual(len(decode_events(registry.store.read_bytes(registry.JOURNAL))), 2)

    def test_modified_persisted_auth_or_revision_fails_replay(self):
        revision, authority = documents(self.registry)
        result = self.registry.authorize_budget_revision(revision, authority)
        for key in (revision["authorization_ref"]["key"], result["revision_ref"]["key"]):
            original = self.store._data[key]
            self.store._data[key] = original + b" "
            with self.assertRaises(CorruptRegistry):
                Registry(self.store, LIMITS)
            self.store._data[key] = original
        self.assertEqual(self.registry.limits, revision["new_limits"])


if __name__ == "__main__":
    unittest.main()
