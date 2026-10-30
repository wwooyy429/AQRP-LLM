"""Synthetic engineering grants and authoritative quota boundaries; no cloud IO."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "cloud"), str(ROOT / "tests"), str(ROOT / "tools")]
from qresearch.artifacts import FilesystemArtifactStore, MemoryArtifactStore, canonical_json, content_hash, decode_events
from qresearch.engineering_tasks import EngineeringTaskBridge, EngineeringTaskPlan
from qresearch.engineering_receipts import research_observation
from qresearch.registry import Registry, RegistryError, BudgetExceeded, CorruptRegistry
from test_phase2_joint_boundaries import joint_document, wrapper
from test_engineering_receipts import research_tool
import engineering_round as cli


def context(reserve=4):
    store = MemoryArtifactStore()
    limits = {kind: {"total": 8 + reserve, "normal": 8, "reserve": reserve}
              for kind in ("configurations", "research", "lean")}
    return store, Registry(store, limits)


def package(tag="primary", project=17):
    raw = joint_document()
    raw["plan_id"] = "synthetic-round-" + tag
    raw["project_id"] = project
    raw["max_retries"] = {"research": 2, "lean": 2}
    return {"engineering_task_schema_version": 1,
            "plan": EngineeringTaskPlan.from_dict(raw, discovered_project_ids=[project]).to_dict()}


def documents(registry, round_id="synthetic-round-2", project=17, limits=None):
    base = {"schema_version": 1, "round_id": round_id, "project_id": project, "allocation": "reserve",
            "limits": limits or {"configurations": 2, "research": 2, "lean": 1},
            "final_test_enabled": False, "extra_spend_usd": 0}
    authorization = deepcopy(base) | {"authority_kind": "explicit_human_user_message",
        "scope": "stage2_engineering_round", "global_limits_hash": content_hash(registry.limits),
        "request_text": "Synthetic human instruction fixture; authorize the stated bounds, no total increase."}
    digest = content_hash(authorization)
    return base | {"authorization_ref": {"key": "engineering/rounds/user-authorizations/" + digest + ".json",
                                        "sha256": digest}}, authorization


def authorize(registry, **kwargs):
    grant, authority = documents(registry, **kwargs)
    registry.authorize_engineering_round(grant, [package(project=grant["project_id"])], authority)
    return grant, authority


def bridge(registry, frozen=None):
    frozen = frozen or package()
    return EngineeringTaskBridge(registry, EngineeringTaskPlan.from_dict(
        frozen["plan"], discovered_project_ids=[frozen["plan"]["project_id"]]))


def finish_research(task):
    attempt = task.claim("research", allocation="reserve")
    payload = task.payload(attempt)
    deployment = {"source_manifest_hash": payload["identity"]["source_manifest_hash"],
                  "deployment_hash": payload["identity"]["deployment_hash"], "input_hash": "f" * 64}
    observed = research_observation(payload, deployment, research_tool(payload, wrapper(payload)))
    task.record_submission(attempt, observed["submission"])
    task.consume_completion(attempt, completion_source=lambda _: observed["completion"])
    return attempt


class EngineeringRoundTests(unittest.TestCase):
    def reject_without_write(self, store, registry, action, errors=(RegistryError, ValueError)):
        saved, snapshot = dict(store._data), registry.snapshot()
        with self.assertRaises(errors):
            action()
        self.assertEqual(dict(store._data), saved)
        self.assertEqual(registry.snapshot(), snapshot)

    def test_authorization_reserves_without_charge_and_preserves_prefix_and_baseline(self):
        store, registry = context()
        prefix, before = store.read_bytes(registry.JOURNAL), registry.snapshot()
        grant, authority = authorize(registry)
        self.assertEqual(registry.snapshot(), before)
        self.assertTrue(store.read_bytes(registry.JOURNAL).startswith(prefix))
        state = registry.engineering_rounds_snapshot()[grant["round_id"]]
        self.assertEqual(state["config_ids"], [content_hash(package())])
        self.assertEqual(state["usage"], {"configurations": 0, "research": 0, "lean": 0})
        self.assertEqual(Registry(store, registry.limits).snapshot(), before)
        saved = dict(store._data)
        registry.authorize_engineering_round(grant, [package()], authority)
        self.assertEqual(store._data, saved)

    def test_no_plan_name_project_allocation_or_new_object_can_reset_legacy_stop(self):
        store, registry = context()
        for tag in ("old-1", "old-2"):
            registry.register_config(package(tag))
        authorize(registry)
        registry.register_config(package(), allocation="reserve")
        for tag, project, allocation in (("third", 17, "normal"), ("rename", 18, "reserve")):
            self.reject_without_write(store, registry, lambda: Registry(store, registry.limits).register_config(
                package(tag, project), allocation=allocation), (BudgetExceeded,))
        # No old charged config can be attached to the new grant as a repair.
        self.reject_without_write(store, registry, lambda: registry.bind_engineering_configuration(
            "synthetic-round-2", package("old-1")))

    def test_fixed_round_caps_debit_failures_and_keep_native_research_lean_dependency(self):
        store, registry = context()
        authorize(registry)
        first = bridge(registry); first.register(allocation="reserve")
        self.reject_without_write(store, registry, lambda: first.claim("lean", allocation="reserve"))
        first_attempt = first.claim("research", allocation="reserve")
        registry.fail(first_attempt, "Synthetic observed Research failure")
        repair = package("repair")
        registry.bind_engineering_configuration("synthetic-round-2", repair)
        second = bridge(registry, repair); second.register(allocation="reserve")
        research = finish_research(second)
        lean = second.claim("lean", allocation="reserve")
        registry.fail(lean, "Synthetic observed LEAN failure")
        self.assertEqual(registry.engineering_rounds_snapshot()["synthetic-round-2"]["usage"],
                         {"configurations": 2, "research": 2, "lean": 1})
        self.reject_without_write(store, registry, lambda: registry.begin_attempt(first.config_id,
            "research", allocation="reserve", operation_key=first_attempt.operation_key,
            retry_of=first_attempt.attempt_id, reason="Third Research is not granted"), (BudgetExceeded,))
        self.reject_without_write(store, registry, lambda: registry.begin_attempt(second.config_id,
            "lean", allocation="reserve", operation_key=lean.operation_key,
            retry_of=lean.attempt_id, reason="Second LEAN is not granted"), (BudgetExceeded,))
        self.assertFalse(second.claim("research", allocation="reserve").should_execute)
        self.assertEqual(second.claim("research").attempt_id, research.attempt_id)

    def test_binding_is_explicit_bounded_and_cannot_use_unknown_project_work(self):
        store, registry = context()
        authorize(registry)
        first = bridge(registry); first.register(allocation="reserve")
        attempt = first.claim("research", allocation="reserve")
        registry.ambiguous(attempt, reason="Synthetic dispatch returned no stable receipt")
        self.reject_without_write(store, registry, lambda: registry.bind_engineering_configuration(
            "synthetic-round-2", package("repair")))
        self.reject_without_write(store, registry, lambda: registry.close_engineering_round(
            "synthetic-round-2", "Cannot hide unknown work"))
        registry.fail(attempt, "Synthetic reconciled no-running-task evidence", reconciliation="Synthetic provider reconciliation fixture")
        self.reject_without_write(store, registry, lambda: registry.bind_engineering_configuration(
            "synthetic-round-2", package("wrong-project", 18)))
        repair = package("repair")
        registry.bind_engineering_configuration("synthetic-round-2", repair)
        saved = dict(store._data)
        registry.bind_engineering_configuration("synthetic-round-2", repair)
        self.assertEqual(store._data, saved)
        self.reject_without_write(store, registry, lambda: registry.bind_engineering_configuration(
            "synthetic-round-2", package("third")), (BudgetExceeded,))
        self.reject_without_write(store, registry, lambda: registry.register_config(
            repair, allocation="normal"), (BudgetExceeded,))

    def test_global_reserve_is_reserved_against_every_generic_charge_entry_point(self):
        store, registry = context(reserve=2)
        authorize(registry)
        self.reject_without_write(store, registry, lambda: registry.register_config(
            {"generic": "cannot-steal-config-reserve"}, allocation="reserve"), (BudgetExceeded,))
        generic = registry.register_config({"generic": "normal-config"}, allocation="normal")
        self.reject_without_write(store, registry, lambda: registry.begin_attempt(generic, "research",
            allocation="reserve"), (BudgetExceeded,))
        normal = registry.begin_attempt(generic, "research", allocation="normal")
        registry.fail(normal, "Synthetic normal task ended")
        lean = registry.begin_attempt(generic, "lean", allocation="reserve", operation_key="one-unreserved-slot")
        registry.fail(lean, "Synthetic unreserved LEAN slot ended")
        self.reject_without_write(store, registry, lambda: registry.begin_attempt(generic, "lean",
            allocation="reserve", operation_key="steal-granted-slot"), (BudgetExceeded,))
        authorized = bridge(registry); authorized.register(allocation="reserve")
        self.assertTrue(authorized.claim("research", allocation="reserve").should_execute)

    def test_multiple_rounds_cannot_overbook_reserve_or_overlap_same_project(self):
        store, registry = context(reserve=3)
        authorize(registry)
        grant, authority = documents(registry, round_id="other-round", project=18)
        self.reject_without_write(store, registry, lambda: registry.authorize_engineering_round(
            grant, [package(project=18)], authority), (BudgetExceeded,))
        grant, authority = documents(registry, round_id="same-project-next")
        self.reject_without_write(store, registry, lambda: registry.authorize_engineering_round(
            grant, [package("other")], authority))

    def test_grant_does_not_allow_old_unresolved_task_to_be_reissued_under_new_hash(self):
        store, registry = context()
        old = bridge(registry, package("legacy")); old.register()
        pending = old.claim("research")
        grant, authority = documents(registry)
        self.reject_without_write(store, registry, lambda: registry.authorize_engineering_round(
            grant, [package()], authority))
        # Recovery of the exact old operation remains free, including through a
        # reconstructed Registry; it cannot consume a grant or reset a counter.
        reopened = bridge(Registry(store, registry.limits), package("legacy"))
        self.assertEqual(reopened.claim("research").attempt_id, pending.attempt_id)
        self.assertFalse(reopened.claim("research").should_execute)

    def test_close_releases_only_unused_reservation_and_never_refunds_or_reopens(self):
        store, registry = context(reserve=3)
        grant, authority = authorize(registry)
        task = bridge(registry); task.register(allocation="reserve")
        attempt = task.claim("research", allocation="reserve")
        registry.fail(attempt, "Synthetic terminal failure")
        before = registry.snapshot()["usage"]
        registry.close_engineering_round(grant["round_id"], "Synthetic completed engineering investigation")
        self.assertEqual(registry.snapshot()["usage"], before)
        self.reject_without_write(store, registry, lambda: registry.bind_engineering_configuration(
            grant["round_id"], package("repair")))
        self.reject_without_write(store, registry, lambda: registry.begin_attempt(task.config_id,
            "research", allocation="reserve", operation_key=attempt.operation_key,
            retry_of=attempt.attempt_id, reason="Closed grant cannot be resurrected"), (BudgetExceeded,))
        replayed = registry.authorize_engineering_round(grant, [package()], authority)
        self.assertEqual(replayed["status"], "closed")
        self.assertEqual(registry.engineering_rounds_snapshot()[grant["round_id"]]["status"], "closed")
        new, auth = documents(registry, round_id="after-close")
        registry.authorize_engineering_round(new, [package("new-primary")], auth)
        self.assertEqual(registry.snapshot()["usage"], before)

    def test_exact_schema_and_authority_scope_are_checked_before_any_writes(self):
        mutations = [lambda g, a: g.update(limits={"configurations": 3, "research": 2, "lean": 1}),
            lambda g, a: a.update(request_text=""), lambda g, a: g.update(final_test_enabled=True),
            lambda g, a: g.update(extra_spend_usd=1), lambda g, a: g.update(allocation="normal"),
            lambda g, a: g.update(project_id=True), lambda g, a: a.update(global_limits_hash="0" * 64),
            lambda g, a: g.update(unrestricted_override=True), lambda g, a: g.update(round_id="../bad")]
        for mutate in mutations:
            store, registry = context()
            grant, authority = documents(registry)
            mutate(grant, authority)
            self.reject_without_write(store, registry, lambda: registry.authorize_engineering_round(
                grant, [package()], authority))
        for packages in ([], [package(), package()], [{"economic_factor": "not an engineering task"}]):
            store, registry = context(); grant, authority = documents(registry)
            self.reject_without_write(store, registry, lambda: registry.authorize_engineering_round(
                grant, packages, authority))

    def test_replay_rejects_changed_bound_artifacts_and_quota_violating_events(self):
        store, registry = context()
        grant, _ = authorize(registry)
        reference = registry._round_reference(grant, "authorizations")
        store._data[reference["key"]] = canonical_json(dict(grant, final_test_enabled=True))
        with self.assertRaises(CorruptRegistry):
            Registry(store, registry.limits)
        store, registry = context(); authorize(registry)
        task = bridge(registry); task.register(allocation="reserve")
        # A forged event bypassing the trusted operator/Registry APIs is still
        # rejected on replay when it spends another allocation.
        registry._append({"kind": "attempt_started", "attempt_id": "a" * 32,
            "config_id": task.config_id, "stage": "research", "operation_key": task._operation("research"),
            "allocation": "normal", "retry_of": None, "reason": None,
            "result_key": registry.result_key(task.config_id, "research", task._operation("research"))})
        with self.assertRaises(CorruptRegistry):
            registry.snapshot()

    def test_concurrent_binding_authorization_and_claim_are_once_only(self):
        store, registry = context()
        grant, authority = documents(registry)
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda _: registry.authorize_engineering_round(grant, [package()], authority), range(16)))
        with ThreadPoolExecutor(max_workers=8) as pool:
            identities = list(pool.map(lambda _: registry.bind_engineering_configuration(
                grant["round_id"], package("repair")), range(16)))
        self.assertEqual(len(set(identities)), 1)
        self.assertEqual(len(decode_events(store.read_bytes(registry.JOURNAL))), 3)
        task = bridge(registry); task.register(allocation="reserve")
        with ThreadPoolExecutor(max_workers=8) as pool:
            attempts = list(pool.map(lambda _: task.claim("research", allocation="reserve"), range(16)))
        self.assertEqual(sum(item.should_execute for item in attempts), 1)
        self.assertEqual(registry.snapshot()["usage"]["research"]["reserve"], 1)

    def test_filesystem_replay_and_operator_cli_are_metadata_only(self):
        with tempfile.TemporaryDirectory(prefix="aqrp-engineering-round-") as directory:
            store = FilesystemArtifactStore(Path(directory) / "store", data_classification="synthetic", lock_timeout=0.25)
            limits = {kind: {"normal": 8, "reserve": 4, "total": 12} for kind in ("configurations", "research", "lean")}
            registry = Registry(store, limits)
            grant, authority = documents(registry)
            paths = {}
            for name, document in (("grant", grant), ("authorization", authority), ("package", package())):
                paths[name] = Path(directory) / (name + ".json")
                paths[name].write_bytes(canonical_json(document))
            with patch.object(cli, "open_registry", return_value=registry), patch("sys.stdout", new_callable=io.StringIO):
                cli.main(["authorize", "--grant-file", str(paths["grant"]), "--authorization-file", str(paths["authorization"]),
                    "--package-file", str(paths["package"])])
                cli.main(["status"])
                cli.main(["close", "--round-id", grant["round_id"], "--reason", "Synthetic CLI end"])
            self.assertEqual(Registry(store, limits).snapshot()["usage"]["research"]["total"], 0)
            self.assertEqual(registry.engineering_rounds_snapshot()[grant["round_id"]]["status"], "closed")


if __name__ == "__main__":
    unittest.main()
