"""Round-level stop conditions cannot be reset by renaming an engineering plan."""
from copy import deepcopy
from pathlib import Path
import json
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cloud"))
sys.path.insert(0, str(ROOT / "tools"))
from qresearch.artifacts import MemoryArtifactStore
from qresearch.engineering_tasks import EngineeringTaskPlan, EngineeringTaskBridge
from qresearch.registry import Registry
from stage2 import _limits


class Stage2StopTests(unittest.TestCase):
    def setUp(self):
        limits = {stage: {"total": 10, "normal": 10, "reserve": 0}
                  for stage in ("configurations", "research", "lean")}
        self.registry = Registry(MemoryArtifactStore(), limits)

    def bridge(self, name, project=17):
        raw = json.loads((ROOT / "config" / "engineering.json").read_text())
        raw.update(plan_id=name, project_id=project, source_manifest_hash="a" * 64, deployment_hash="b" * 64)
        raw["request_template"]["universe_hash"] = "c" * 64
        plan = EngineeringTaskPlan.from_dict(raw, discovered_project_ids=[17, 18])
        return EngineeringTaskBridge(self.registry, plan)

    def test_renaming_plan_and_switching_project_cannot_reset_configuration_cap(self):
        for name in ("first", "renamed"):
            bridge = self.bridge(name)
            _limits(bridge, "configurations")
            bridge.register()
        for project in (17, 18):
            with self.subTest(project=project), self.assertRaisesRegex(ValueError, "stop condition"):
                _limits(self.bridge("third-name", project), "configurations")
        self.assertEqual(self.registry.snapshot()["usage"]["configurations"]["total"], 2)

    def test_failed_attempts_across_plans_and_projects_still_count(self):
        for stage in ("research", "lean"):
            # Independent synthetic round for each execution category.
            self.setUp()
            bridges = [self.bridge("one", 17), self.bridge("another-name", 18)]
            for bridge in bridges:
                bridge.register()
                attempt = self.registry.begin_attempt(bridge.config_id, stage,
                    operation_key=bridge._operation(stage))
                self.registry.fail(attempt, "synthetic confirmed failure")
            with self.assertRaisesRegex(ValueError, "stop condition"):
                _limits(bridges[-1], stage)
            self.assertEqual(self.registry.snapshot()["usage"][stage]["total"], 2)

    def test_completed_and_unresolved_reuse_does_not_spend_new_quota(self):
        bridge = self.bridge("stable")
        bridge.register()
        attempt = bridge.claim("research")
        _limits(bridge, "research")
        self.assertFalse(bridge.claim("research").should_execute)
        self.registry.complete(attempt, {"synthetic_checked_result": True})
        _limits(bridge, "research")
        self.assertFalse(bridge.claim("research").should_execute)
        self.assertEqual(self.registry.snapshot()["usage"]["research"]["total"], 1)


if __name__ == "__main__":
    unittest.main()
