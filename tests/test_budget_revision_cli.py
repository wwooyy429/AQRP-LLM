"""Synthetic operator/projection recovery; never open the user's Registry."""
from copy import deepcopy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "cloud"), str(ROOT / "tools")]
import budget_revision as cli
import research
from qresearch.artifacts import FilesystemArtifactStore, canonical_json, content_hash, decode_events
from qresearch.registry import Registry, RegistryError


def budget_fixture():
    return {"schema_version": 1, "configuration_id": "SYNTHETIC-CLI-ONLY",
        "limits": {"full_configurations": 12, "research_execution_attempts": 20,
                   "lean_submission_attempts": 16, "extra_spend_USD": 0,
                   "extra_resource_purchases": 0, "optimization_jobs": 0},
        "allocations": {"full_configurations": {"normal": 8, "reserve": 4, "total": 12},
                        "research_execution_attempts": {"normal": 12, "reserve": 8, "total": 20},
                        "lean_submission_attempts": {"normal": 8, "reserve": 8, "total": 16}},
        "usage": {"configuration_budget_charges": 12, "configuration_normal_used": 8,
                  "configuration_reserve_used": 4, "research_execution_attempts": 15,
                  "research_normal_used": 8, "research_reserve_used": 7,
                  "lean_submission_attempts": 2, "lean_normal_used": 2, "lean_reserve_used": 0,
                  "complete_strategy_configurations_frozen": 0},
        "final_evaluation_execution_enabled": False,
        "resources": {"agent": "SYNTHETIC-A", "research": "SYNTHETIC-R", "backtest": "SYNTHETIC-L"},
        "preserved_declaration": "Synthetic fixtures do not supply actual human authority."}


def documents(registry, revision_id="synthetic-cli-revision"):
    before = deepcopy(registry.limits)
    limits = deepcopy(before)
    limits["configurations"]["reserve"] += 1
    limits["configurations"]["total"] += 1
    base = {"schema_version": 1, "revision_id": revision_id,
            "previous_limits_hash": content_hash(before), "new_limits": limits,
            "final_test_enabled": False, "extra_spend_usd": 0}
    authorization = dict(base, authority_kind="explicit_human_user_message",
        scope="configuration_reserve_increment_v1",
        request_text="SYNTHETIC TEST ONLY; not a production authorization.",
        approval={"question": "Synthetic fixture increases one configuration reserve unit only.", "answer": "批准"})
    digest = content_hash(authorization)
    revision = dict(base, authorization_ref={"key": "budget-revisions/user-authorizations/" + digest + ".json", "sha256": digest})
    return revision, authorization


class BudgetRevisionCLITests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "config").mkdir()
        self.budget = budget_fixture()
        self.budget_path = self.root / "config/budget.json"
        self.budget_path.write_bytes(canonical_json(self.budget))
        self.store = FilesystemArtifactStore(self.root / "audit/runtime")
        self.store.write_once("registry/baseline.json", canonical_json(self.budget))
        self.registry = Registry(self.store, self.budget)
        self.baseline = self.store.read_bytes("registry/baseline.json")
        self.prefix = self.store.read_bytes(self.registry.JOURNAL)
        for module in (cli, research):
            p = patch.object(module, "ROOT", self.root)
            p.start()
            self.addCleanup(p.stop)

    def state_bytes(self):
        return {path.relative_to(self.root).as_posix(): path.read_bytes()
                for path in self.root.rglob("*") if path.is_file()}

    def invoke(self, args):
        output = io.StringIO()
        with patch("sys.stdout", output):
            result = cli.main(args)
        self.assertEqual(json.loads(output.getvalue()), result)
        return result

    def input_files(self, revision, authorization):
        folder = self.root / "operator-inputs"
        folder.mkdir(exist_ok=True)
        r, a = folder / "revision.json", folder / "authorization.json"
        r.write_bytes(canonical_json(revision)); a.write_bytes(canonical_json(authorization))
        return ["apply", "--revision-file", str(r), "--authorization-file", str(a)]

    def test_apply_uses_original_baseline_appends_once_and_projects_authoritative_policy(self):
        revision, authorization = documents(self.registry)
        before = self.registry.snapshot()
        result = self.invoke(self.input_files(revision, authorization))
        self.assertTrue(result["budget_projection_changed"])
        self.assertEqual(result["limits"], revision["new_limits"])
        self.assertEqual(result["usage"], before["usage"])
        self.assertEqual(self.store.read_bytes("registry/baseline.json"), self.baseline)
        journal = self.store.read_bytes(self.registry.JOURNAL)
        self.assertTrue(journal.startswith(self.prefix))
        self.assertEqual(len(decode_events(journal)), len(decode_events(self.prefix)) + 1)
        projected = json.loads(self.budget_path.read_bytes())
        self.assertEqual(projected["limits"]["full_configurations"], 13)
        self.assertEqual(projected["allocations"]["full_configurations"], {"normal": 8, "reserve": 5, "total": 13})
        self.assertEqual(projected["usage"], self.budget["usage"])
        for key in ("resources", "preserved_declaration", "final_evaluation_execution_enabled"):
            self.assertEqual(projected[key], self.budget[key])
        for name in ("research_execution_attempts", "lean_submission_attempts", "extra_spend_USD",
                     "extra_resource_purchases", "optimization_jobs"):
            self.assertEqual(projected["limits"][name], self.budget["limits"][name])
        reopened = Registry(self.store, json.loads(self.baseline))
        self.assertEqual(reopened.snapshot()["limits"], revision["new_limits"])
        self.assertEqual(reopened.snapshot()["usage"], before["usage"])
        self.assertEqual(result["cloud_calls"], 0)

    def test_identical_apply_is_idempotent_including_projection_mtime(self):
        revision, authorization = documents(self.registry)
        cli.apply_revision(revision, authorization, registry=self.registry)
        before = self.state_bytes()
        mtime = self.budget_path.stat().st_mtime_ns
        result = cli.apply_revision(revision, authorization, registry=self.registry)
        self.assertFalse(result["budget_projection_changed"])
        self.assertEqual(self.state_bytes(), before)
        self.assertEqual(self.budget_path.stat().st_mtime_ns, mtime)

    def test_projection_write_failure_is_repaired_by_same_revision_without_double_event(self):
        revision, authorization = documents(self.registry)
        original_budget = self.budget_path.read_bytes()
        with patch.object(cli, "write_changed", side_effect=OSError("Synthetic disk failure")):
            with self.assertRaises(OSError):
                cli.apply_revision(revision, authorization, registry=self.registry)
        committed_journal = self.store.read_bytes(self.registry.JOURNAL)
        self.assertTrue(committed_journal.startswith(self.prefix))
        self.assertEqual(self.registry.snapshot()["limits"]["configurations"]["total"], 13)
        self.assertEqual(self.budget_path.read_bytes(), original_budget)
        result = cli.apply_revision(revision, authorization, registry=Registry(self.store, json.loads(self.baseline)))
        self.assertTrue(result["budget_projection_changed"])
        self.assertEqual(self.store.read_bytes(self.registry.JOURNAL), committed_journal)
        self.assertEqual(self.store.read_bytes("registry/baseline.json"), self.baseline)
        self.assertEqual(json.loads(self.budget_path.read_bytes())["limits"]["full_configurations"], 13)

    def test_invalid_stale_and_changed_duplicate_documents_cannot_write_projection_or_journal(self):
        revision, authorization = documents(self.registry)
        variants = []
        bad = deepcopy(revision); bad["previous_limits_hash"] = "0" * 64; variants.append((bad, authorization))
        bad = deepcopy(revision); bad["extra_spend_usd"] = True; variants.append((bad, authorization))
        bad = deepcopy(revision); bad["new_limits"]["research"]["total"] = 21; variants.append((bad, authorization))
        bad = deepcopy(authorization); bad["approval"]["answer"] = "not approved"; variants.append((revision, bad))
        for r, a in variants:
            before = self.state_bytes()
            with self.subTest(revision=r, authorization=a), self.assertRaises((ValueError, RegistryError)):
                cli.apply_revision(r, a, registry=self.registry)
            self.assertEqual(self.state_bytes(), before)
        cli.apply_revision(revision, authorization, registry=self.registry)
        before = self.state_bytes()
        bad = deepcopy(authorization); bad["request_text"] += " changed"
        digest = content_hash(bad)
        changed = dict(revision, authorization_ref={"key": "budget-revisions/user-authorizations/" + digest + ".json", "sha256": digest})
        with self.assertRaises((ValueError, RegistryError)):
            cli.apply_revision(changed, bad, registry=self.registry)
        self.assertEqual(self.state_bytes(), before)

    def test_status_is_readonly_and_does_not_repair_a_projection_gap(self):
        revision, authorization = documents(self.registry)
        self.registry.authorize_budget_revision(revision, authorization)
        before = self.state_bytes()
        result = self.invoke(["status"])
        self.assertEqual(result["limits"]["configurations"]["total"], 13)
        self.assertEqual(json.loads(self.budget_path.read_bytes())["limits"]["full_configurations"], 12)
        self.assertEqual(self.state_bytes(), before)

    def test_missing_authority_is_rejected_without_bootstrap_or_files(self):
        with tempfile.TemporaryDirectory() as folder:
            missing = Path(folder)
            with patch.object(cli, "ROOT", missing), patch.object(research, "ROOT", missing):
                with self.assertRaises(RegistryError):
                    cli.main(["status"])
            self.assertEqual(list(missing.iterdir()), [])

    def test_incomplete_or_disabled_scope_projection_is_rejected_before_revision(self):
        revision, authorization = documents(self.registry)
        variants = [dict(self.budget, final_evaluation_execution_enabled=True),
                    dict(self.budget, usage=[])]
        bad = deepcopy(self.budget); bad["limits"]["extra_spend_USD"] = 1; variants.append(bad)
        bad = deepcopy(self.budget); bad["allocations"]["full_configurations"]["reserve"] = True; variants.append(bad)
        for budget in variants:
            self.budget_path.write_bytes(canonical_json(budget))
            before = self.state_bytes()
            with self.subTest(budget=budget), self.assertRaises(ValueError):
                cli.apply_revision(revision, authorization, registry=self.registry)
            self.assertEqual(self.state_bytes(), before)


if __name__ == "__main__":
    unittest.main()
