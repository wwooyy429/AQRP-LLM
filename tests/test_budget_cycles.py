"""Configuration-cycle isolation with synthetic stores only; no cloud calls."""
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
sys.path[:0] = [str(ROOT / "cloud"), str(ROOT / "tools"), str(ROOT / "tests")]
from qresearch.artifacts import MemoryArtifactStore, FilesystemArtifactStore, canonical_json, content_hash, decode_events
from qresearch.budget_cycles import (BudgetCycleError, authorization_reference, cycle_reference, validate_cycle)
from qresearch.registry import Registry, RegistryError, BudgetExceeded, CorruptRegistry
import budget_cycle as cli
import budget_revision
import research
import test_engineering_rounds as rounds
import test_budget_revisions as revisions


LIMITS = {"configurations": {"normal": 2, "reserve": 1, "total": 3},
          "research": {"normal": 3, "reserve": 3, "total": 6},
          "lean": {"normal": 3, "reserve": 3, "total": 6}}


def documents(registry, cycle_id="SYNTHETIC-config-cycle-1"):
    cycle = {"schema_version": 1, "cycle_id": cycle_id,
             "previous_state_hash": registry.configuration_cycle_snapshot()["state_hash"],
             "capacity": deepcopy(registry.limits["configurations"]),
             "final_test_enabled": False, "extra_spend_usd": 0}
    authorization = deepcopy(cycle) | {"authority_kind": "explicit_human_user_message",
        "scope": "configuration_cycle_reset_v1", "request_text": "SYNTHETIC direct human reset instruction; not actual authority."}
    cycle["authorization_ref"] = authorization_reference(authorization)
    return cycle, authorization


def bind(cycle, authorization):
    for name, value in cycle.items():
        if name != "authorization_ref":
            authorization[name] = deepcopy(value)
    cycle["authorization_ref"] = authorization_reference(authorization)


def round_documents(registry, round_id="SYNTHETIC-cycle-round"):
    grant, authority = rounds.documents(registry, round_id=round_id,
        limits={"configurations": 1, "research": 1, "lean": 1})
    grant["schema_version"] = authority["schema_version"] = 2
    grant["configuration_cycle_id"] = authority["configuration_cycle_id"] = registry.configuration_cycle_snapshot()["cycle_id"]
    digest = content_hash(authority)
    grant["authorization_ref"] = {"key": "engineering/rounds/user-authorizations/" + digest + ".json", "sha256": digest}
    return grant, authority


def normal_round_documents(registry, round_id="SYNTHETIC-normal-direct"):
    grant, authority = round_documents(registry, round_id)
    grant["allocation"] = authority["allocation"] = "normal"
    authority["scope"] = "stage2_normal_allocation_exception"
    authority["normal_allocation_approval"] = {"direct_request": authority["request_text"]}
    digest = content_hash(authority)
    grant["authorization_ref"] = {"key": "engineering/rounds/user-authorizations/" + digest + ".json", "sha256": digest}
    return grant, authority


class BudgetCycleTests(unittest.TestCase):
    def setUp(self):
        self.store = MemoryArtifactStore()
        self.usage = {kind: {"normal": 0, "reserve": 0, "total": 0} for kind in LIMITS}
        self.usage["configurations"] = deepcopy(LIMITS["configurations"])
        self.registry = Registry(self.store, LIMITS, self.usage)

    def rejected_without_writes(self, action, exceptions=(ValueError, RegistryError)):
        before = dict(self.store._data)
        with self.assertRaises(exceptions):
            action()
        self.assertEqual(self.store._data, before)

    def reset(self, name="SYNTHETIC-config-cycle-1"):
        cycle, authority = documents(self.registry, name)
        result = self.registry.authorize_configuration_cycle(cycle, authority)
        return cycle, authority, result

    def test_renew_only_configuration_allowance_preserves_lifetime_prefix_and_baseline(self):
        before = self.registry.snapshot()
        prefix = self.store.read_bytes(self.registry.JOURNAL)
        cycle, authority, current = self.reset()
        self.assertEqual(current["usage"], {"normal": 0, "reserve": 0, "total": 0})
        self.assertEqual(current["capacity"], LIMITS["configurations"])
        self.assertEqual(current["lifetime_usage"], self.usage["configurations"])
        self.assertEqual(current["starting_lifetime_usage"], self.usage["configurations"])
        self.assertEqual(current["sequence"], 1)
        self.assertEqual(self.registry.snapshot()["usage"], before["usage"])
        self.assertEqual(self.registry.limits, LIMITS)
        self.assertTrue(self.store.read_bytes(self.registry.JOURNAL).startswith(prefix))
        self.assertEqual(len(decode_events(self.store.read_bytes(self.registry.JOURNAL))), 2)
        self.assertEqual(self.store.read_bytes(cycle_reference(cycle)["key"]), canonical_json(cycle))
        self.assertEqual(Registry(self.store, LIMITS, self.usage).snapshot(), self.registry.snapshot())
        history = self.registry.configuration_cycles_snapshot()
        self.assertEqual(history["initial"]["usage"], LIMITS["configurations"])
        self.assertEqual(history[cycle["cycle_id"]], current)

    def test_allocation_caps_apply_to_cycle_cumulative_counters_keep_increasing(self):
        self.reset()
        first = self.registry.register_config({"synthetic": 1}, "normal")
        self.registry.register_config({"synthetic": 2}, "normal")
        self.registry.register_config({"synthetic": 3}, "reserve")
        self.assertEqual(self.registry.snapshot()["usage"]["configurations"]["total"], 6)
        self.assertEqual(self.registry.configuration_cycle_snapshot()["usage"], LIMITS["configurations"])
        for allocation in ("normal", "reserve"):
            self.rejected_without_writes(lambda: self.registry.register_config({"synthetic": 4}, allocation), (BudgetExceeded,))
        # A cumulative config count greater than its per-cycle cap must not
        # prevent ordinary R/L charging or refill either execution resource.
        for stage in ("research", "lean"):
            for i in range(3):
                attempt = self.registry.begin_attempt(first, stage, operation_key=stage + str(i))
                self.registry.fail(attempt, "Synthetic terminal failure")
            self.rejected_without_writes(lambda: self.registry.begin_attempt(first, stage, operation_key="over-cap"), (BudgetExceeded,))
        self.assertEqual(Registry(self.store, LIMITS, self.usage).snapshot(), self.registry.snapshot())

    def test_same_hash_is_still_idempotent_and_original_cycle_origin_is_retained(self):
        store = MemoryArtifactStore(); registry = Registry(store, LIMITS)
        old = registry.register_config({"synthetic": "same"})
        cycle, authority = documents(registry)
        registry.authorize_configuration_cycle(cycle, authority)
        before = dict(store._data)
        self.assertEqual(registry.register_config({"synthetic": "same"}), old)
        self.assertEqual(store._data, before)
        self.assertEqual(registry.configuration_cycle_snapshot()["usage"]["total"], 0)
        new = registry.register_config({"synthetic": "new"})
        origins = registry.snapshot()["configuration_origins"]
        self.assertEqual(origins[old]["cycle_id"], "initial")
        self.assertEqual(origins[new]["cycle_id"], cycle["cycle_id"])
        saved = decode_events(store.read_bytes(registry.JOURNAL))[-1]["event"]
        self.assertEqual(saved["configuration_cycle_id"], cycle["cycle_id"])

    def test_same_authorization_is_idempotent_after_activity_but_changed_duplicate_rejected(self):
        cycle, authority, _ = self.reset()
        config = self.registry.register_config({"synthetic": "later"})
        attempt = self.registry.begin_attempt(config, "research")
        before = dict(self.store._data)
        current = self.registry.authorize_configuration_cycle(cycle, authority)
        self.assertEqual(self.store._data, before)
        self.assertEqual(current["usage"]["total"], 1)
        changed = deepcopy(authority); changed["request_text"] += " changed"
        rebound = deepcopy(cycle); rebound["authorization_ref"] = authorization_reference(changed)
        self.rejected_without_writes(lambda: self.registry.authorize_configuration_cycle(rebound, changed))
        self.registry.fail(attempt, "Synthetic stopped")
        second, second_auth = documents(self.registry, "SYNTHETIC-cycle-2")
        self.registry.authorize_configuration_cycle(second, second_auth)
        prefix = self.store.read_bytes(self.registry.JOURNAL)
        self.assertEqual(self.registry.authorize_configuration_cycle(cycle, authority)["cycle_id"], second["cycle_id"])
        self.assertEqual(self.store.read_bytes(self.registry.JOURNAL), prefix)

    def test_new_reset_requires_all_rounds_closed_and_tasks_resolved(self):
        store = MemoryArtifactStore(); registry = Registry(store, LIMITS)
        grant, authority = rounds.documents(registry, limits={"configurations": 1, "research": 1, "lean": 1})
        registry.authorize_engineering_round(grant, [rounds.package()], authority)
        cycle, authorization = documents(registry)
        with self.assertRaises(RegistryError):
            registry.authorize_configuration_cycle(cycle, authorization)
        registry.close_engineering_round(grant["round_id"], "Synthetic unused round stopped")
        config = registry.register_config({"synthetic": "plain"})
        attempt = registry.begin_attempt(config, "research")
        cycle, authorization = documents(registry)
        for status in ("started", "pending", "ambiguous"):
            if status == "pending": registry.pending(attempt, external_id="SYNTHETIC")
            if status == "ambiguous": registry.ambiguous(attempt, reason="SYNTHETIC unknown")
            with self.assertRaises(RegistryError):
                registry.authorize_configuration_cycle(cycle, authorization)
        registry.fail(attempt, "Synthetic terminal confirmed", reconciliation="SYNTHETIC actual evidence")
        registry.authorize_configuration_cycle(cycle, authorization)

    def test_stale_usage_policy_and_cycle_identity_reject_without_writes(self):
        self.reset()
        stale, authority = documents(self.registry, "SYNTHETIC-stale")
        self.registry.register_config({"synthetic": "state changed"})
        self.rejected_without_writes(lambda: self.registry.authorize_configuration_cycle(stale, authority))
        cycle, auth = documents(self.registry, "SYNTHETIC-wrong-capacity")
        cycle["capacity"]["reserve"] += 1; cycle["capacity"]["total"] += 1; bind(cycle, auth)
        self.rejected_without_writes(lambda: self.registry.authorize_configuration_cycle(cycle, auth))
        revision, rev_auth = revisions.documents(self.registry)
        self.rejected_without_writes(lambda: self.registry.authorize_budget_revision(revision, rev_auth))

    def test_unknown_fields_types_final_spend_and_wrong_reference_are_closed(self):
        base, auth = documents(self.registry)
        mutations = [lambda c,a:c.update(schema_version=True), lambda c,a:c.update(cycle_id="initial"),
            lambda c,a:c.update(cycle_id="../SECRET"), lambda c,a:c.update(extra=True),
            lambda c,a:c.update(final_test_enabled=True), lambda c,a:c.update(extra_spend_usd=0.0),
            lambda c,a:c.update(previous_state_hash="A"*64), lambda c,a:c["capacity"].update(normal=True),
            lambda c,a:c["capacity"].update(research=20), lambda c,a:a.update(request_text=" "),
            lambda c,a:a.update(request_text="\ud800"), lambda c,a:a.update(scope="budget_reset_everything"),
            lambda c,a:a.update(authority_kind="llm_proposal"), lambda c,a:a.update(extra=True)]
        for mutation in mutations:
            cycle, authority = deepcopy(base), deepcopy(auth)
            mutation(cycle, authority)
            try: bind(cycle, authority)
            except BudgetCycleError: pass
            self.rejected_without_writes(lambda: self.registry.authorize_configuration_cycle(cycle, authority))
        for reference in ({"key":"../SECRET","sha256":"a"*64}, {"key":base["authorization_ref"]["key"],"sha256":"b"*64}):
            cycle=deepcopy(base);cycle["authorization_ref"]=reference
            self.rejected_without_writes(lambda: self.registry.authorize_configuration_cycle(cycle, auth))

    def test_after_reset_new_round_requires_version2_cycle_binding_and_reservations_use_cycle(self):
        cycle, _, _ = self.reset()
        package = rounds.package("cycle-new")
        old_grant, old_auth = rounds.documents(self.registry, limits={"configurations": 1,"research": 1,"lean": 1})
        self.rejected_without_writes(lambda: self.registry.authorize_engineering_round(old_grant, [package], old_auth))
        grant, authority = round_documents(self.registry)
        self.registry.authorize_engineering_round(grant, [package], authority)
        self.rejected_without_writes(lambda: self.registry.register_config({"synthetic": "reserved-other"}, "reserve"), (BudgetExceeded,))
        task=rounds.bridge(self.registry,package);task.register(allocation="reserve")
        attempt=task.claim("research",allocation="reserve");self.registry.fail(attempt,"Synthetic native failure")
        self.registry.close_engineering_round(grant["round_id"],"Synthetic no retry")
        self.assertEqual(self.registry.snapshot()["usage"]["configurations"]["total"], 4)
        self.assertEqual(self.registry.configuration_cycle_snapshot()["usage"]["reserve"],1)
        self.assertEqual(Registry(self.store,LIMITS,self.usage).engineering_rounds_snapshot(),self.registry.engineering_rounds_snapshot())
        newer, newer_auth = documents(self.registry,"SYNTHETIC-next")
        self.registry.authorize_configuration_cycle(newer,newer_auth)
        stale, stale_auth = round_documents(self.registry,"SYNTHETIC-stale-new-round")
        stale["configuration_cycle_id"] = stale_auth["configuration_cycle_id"] = cycle["cycle_id"]
        digest=content_hash(stale_auth);stale["authorization_ref"]={"key":"engineering/rounds/user-authorizations/"+digest+".json","sha256":digest}
        self.rejected_without_writes(lambda:self.registry.authorize_engineering_round(stale,[rounds.package("stale")],stale_auth))

    def test_legacy_round_and_reserve_revision_replay_at_original_cycle(self):
        store=MemoryArtifactStore(); registry=Registry(store,LIMITS)
        package=rounds.package("legacy-before-reset")
        grant, authority=rounds.documents(registry,limits={"configurations":1,"research":1,"lean":1})
        registry.authorize_engineering_round(grant,[package],authority)
        task=rounds.bridge(registry,package);task.register(allocation="reserve")
        attempt=task.claim("research",allocation="reserve");registry.fail(attempt,"Synthetic observed failure")
        registry.close_engineering_round(grant["round_id"],"Synthetic stop")
        revision, rev_auth=revisions.documents(registry);registry.authorize_budget_revision(revision,rev_auth)
        old=registry.engineering_rounds_snapshot()[grant["round_id"]]
        cycle, auth=documents(registry);registry.authorize_configuration_cycle(cycle,auth)
        restarted=Registry(store,LIMITS)
        self.assertEqual(restarted.engineering_rounds_snapshot()[grant["round_id"]],old)
        self.assertEqual(restarted.authorize_engineering_round(grant,[package],authority),old)
        self.assertEqual(restarted.authorize_budget_revision(revision,rev_auth)["effective_limits"],revision["new_limits"])

    def test_v2_normal_grant_binds_direct_request_without_fabricated_reply(self):
        self.reset()
        grant, authority = normal_round_documents(self.registry)
        package = rounds.package('normal-direct')
        self.registry.authorize_engineering_round(grant,[package],authority)
        task=rounds.bridge(self.registry,package);task.register(allocation='normal')
        attempt=task.claim('research',allocation='normal')
        self.assertTrue(attempt.should_execute)
        self.assertEqual(self.registry.configuration_cycle_snapshot()['usage']['normal'],1)
        self.assertEqual(self.registry.snapshot()['usage']['research']['normal'],1)
        self.registry.fail(attempt,'Synthetic actual failure')
        self.registry.close_engineering_round(grant['round_id'],'Synthetic stop without retry')
        self.assertEqual(Registry(self.store,LIMITS,self.usage).engineering_rounds_snapshot(),self.registry.engineering_rounds_snapshot())

    def test_direct_normal_request_schema_must_match_exactly_and_v1_stays_closed(self):
        self.reset()
        grant, authority = normal_round_documents(self.registry)
        package = rounds.package('normal-direct-closed')
        for approval in ({'direct_request':'changed'}, {'direct_request':True},
                         {'direct_request':authority['request_text'],'answer':'允许'}, {},
                         {'direct_request':authority['request_text']+' '},
                         {'question':'SYNTHETIC','answer':'yes'}):
            changed=deepcopy(authority); changed['normal_allocation_approval']=approval
            rebound=deepcopy(grant); digest=content_hash(changed)
            rebound['authorization_ref']={'key':'engineering/rounds/user-authorizations/'+digest+'.json','sha256':digest}
            self.rejected_without_writes(lambda:self.registry.authorize_engineering_round(rebound,[package],changed))
        store=MemoryArtifactStore(); registry=Registry(store,LIMITS)
        old_grant, old_auth=rounds.documents(registry,limits={'configurations':1,'research':1,'lean':1})
        old_grant['allocation']=old_auth['allocation']='normal'
        old_auth['scope']='stage2_normal_allocation_exception'
        old_auth['normal_allocation_approval']={'direct_request':old_auth['request_text']}
        digest=content_hash(old_auth);old_grant['authorization_ref']={'key':'engineering/rounds/user-authorizations/'+digest+'.json','sha256':digest}
        before=dict(store._data)
        with self.assertRaises(ValueError): registry.authorize_engineering_round(old_grant,[package],old_auth)
        self.assertEqual(store._data,before)

    def test_tampered_authorization_missing_refs_and_cycle_event_replay_fail_closed(self):
        cycle, authority, _=self.reset()
        saved=dict(self.store._data)
        for key in (cycle["authorization_ref"]["key"],cycle_reference(cycle)["key"]):
            self.store._data=dict(saved);self.store._data[key]=b'{}'
            with self.assertRaises(CorruptRegistry):Registry(self.store,LIMITS,self.usage)
        self.store._data=dict(saved)
        self.store.append_event(self.registry.JOURNAL,{"kind":"configuration_cycle_authorized","cycle_ref":cycle_reference(cycle)})
        with self.assertRaises(CorruptRegistry):Registry(self.store,LIMITS,self.usage)

    def test_concurrent_same_reset_appends_once_and_concurrent_new_ids_are_stale(self):
        with tempfile.TemporaryDirectory() as directory:
            registry=Registry(FilesystemArtifactStore(directory),LIMITS,self.usage)
            cycle, authority=documents(registry)
            with ThreadPoolExecutor(max_workers=4) as pool:
                results=list(pool.map(lambda _:registry.authorize_configuration_cycle(cycle,authority),range(8)))
            self.assertTrue(all(r==results[0] for r in results))
            self.assertEqual(len(decode_events(registry.store.read_bytes(registry.JOURNAL))),2)
            first, first_auth=documents(registry,"SYNTHETIC-race-a")
            second, second_auth=documents(registry,"SYNTHETIC-race-b")
            def apply(pair):
                try:registry.authorize_configuration_cycle(*pair);return True
                except (ValueError,RegistryError):return False
            with ThreadPoolExecutor(max_workers=2) as pool:
                outcomes=list(pool.map(apply,[(first,first_auth),(second,second_auth)]))
            self.assertEqual(sum(outcomes),1)
            self.assertEqual(len(decode_events(registry.store.read_bytes(registry.JOURNAL))),3)


class BudgetCycleCLITests(unittest.TestCase):
    def test_thirteen_configuration_known_answer_does_not_refill_research_or_lean(self):
        from test_budget_revision_cli import budget_fixture
        budget=budget_fixture()
        budget['limits']['full_configurations']=13
        budget['allocations']['full_configurations']={'normal':8,'reserve':5,'total':13}
        budget['usage'].update(configuration_budget_charges=13,configuration_reserve_used=5,
            research_execution_attempts=16,research_reserve_used=8)
        registry=Registry(MemoryArtifactStore(),budget)
        cycle,auth=documents(registry);registry.authorize_configuration_cycle(cycle,auth)
        after=registry.snapshot()
        projected=cli.project_cycle(budget,limits=after['limits'],usage=after['usage'],
            configuration_cycle=after['configuration_cycle'])
        self.assertEqual(projected['usage'],budget['usage'])
        self.assertEqual(projected['configuration_cycle']['usage'],{'normal':0,'reserve':0,'total':0})
        self.assertEqual(projected['configuration_cycle']['remaining'],{'normal':8,'reserve':5,'total':13})
        config=registry.register_config({'synthetic':'new cycle config'},allocation='normal')
        self.assertEqual(registry.snapshot()['usage']['configurations']['total'],14)
        self.assertEqual(registry.configuration_cycle_snapshot()['usage']['total'],1)
        with self.assertRaises(BudgetExceeded):registry.begin_attempt(config,'research',allocation='reserve')
        research=registry.begin_attempt(config,'research',allocation='normal')
        registry.fail(research,'Synthetic confirmed failure')
        self.assertEqual(registry.snapshot()['usage']['research']['total'],17)
        self.assertEqual(registry.snapshot()['usage']['lean']['total'],2)

    def test_projection_crash_recovery_keeps_cumulative_values_and_baseline(self):
        from test_budget_revision_cli import budget_fixture
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'config').mkdir();budget=budget_fixture()
            path=root/'config/budget.json';path.write_bytes(canonical_json(budget))
            store=FilesystemArtifactStore(root/'audit/runtime');store.write_once('registry/baseline.json',canonical_json(budget))
            registry=Registry(store,budget);baseline=store.read_bytes('registry/baseline.json')
            cycle, auth=documents(registry)
            with patch.object(cli,'ROOT',root):
                with patch.object(cli,'write_changed',side_effect=OSError('Synthetic disk failure')):
                    with self.assertRaises(OSError):cli.apply_cycle(cycle,auth,registry=registry)
                journal=store.read_bytes(registry.JOURNAL)
                result=cli.apply_cycle(cycle,auth,registry=Registry(store,budget))
                self.assertTrue(result['budget_projection_changed'])
                projection=json.loads(path.read_bytes())
                self.assertEqual(projection['usage'],budget['usage'])
                self.assertEqual(projection['configuration_cycle']['usage']['total'],0)
                self.assertEqual(projection['configuration_cycle']['capacity']['total'],12)
                self.assertEqual(store.read_bytes(registry.JOURNAL),journal)
                self.assertEqual(store.read_bytes('registry/baseline.json'),baseline)
                before=path.read_bytes();again=cli.apply_cycle(cycle,auth,registry=registry)
                self.assertFalse(again['budget_projection_changed'],
                    {'before':json.loads(before),'after':json.loads(path.read_bytes())})
                self.assertEqual(path.read_bytes(),before)
                registry.register_config({'synthetic':'new lifetime13'},allocation='normal')
                cli.apply_cycle(cycle,auth,registry=registry)
                projection=json.loads(path.read_bytes())
                self.assertEqual(projection['usage']['configuration_budget_charges'],13)
                self.assertEqual(projection['configuration_cycle']['usage']['total'],1)

    def test_no_existing_registry_bootstrap_and_malformed_projection_cannot_append(self):
        from test_budget_revision_cli import budget_fixture
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with patch.object(budget_revision,'ROOT',root):
                with self.assertRaises(RegistryError):cli.main(['status'])
            self.assertEqual(list(root.rglob('*')),[])
            (root/'config').mkdir();budget=budget_fixture();path=root/'config/budget.json'
            bad=deepcopy(budget);bad['final_evaluation_execution_enabled']=True
            path.write_bytes(canonical_json(bad));store=MemoryArtifactStore();registry=Registry(store,budget)
            cycle,auth=documents(registry);before=dict(store._data)
            with patch.object(cli,'ROOT',root):
                with self.assertRaises(ValueError):cli.apply_cycle(cycle,auth,registry=registry)
            self.assertEqual(store._data,before)


if __name__ == '__main__':
    unittest.main()
