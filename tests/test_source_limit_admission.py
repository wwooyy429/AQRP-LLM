"""Synthetic local upload limits reject before grants or input publication."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "cloud"), str(ROOT / "tools"), str(ROOT / "tests")]
import stage2 as cli
from test_deployment_preflight import LocalFixture, SOURCE


class SourceLimitAdmissionTests(unittest.TestCase):
    def configure(self, fixture, maximum, project=17):
        fixture.dump("config/quantconnect.json", {"active_project_id": 17,
            "native_source_file_limit": {"schema_version": 1,
                "project_id": project, "max_file_characters": maximum}})

    def test_source_excess_blocks_freeze_registration_and_claim_without_debit(self):
        for command in ("register", "claim"):
            with self.subTest(command=command), LocalFixture(1) as fixture:
                if command == "claim": fixture.bridge.register()
                self.configure(fixture, len(SOURCE.decode()) - 1)
                before, objects = fixture.registry.snapshot(), dict(fixture.store._data)
                with self.assertRaises(ValueError): fixture.command(command, "research" if command == "claim" else None)
                self.assertEqual(fixture.registry.snapshot(), before)
                self.assertEqual(fixture.store._data, objects)

    def test_task_input_excess_fails_before_input_or_admission_write(self):
        with LocalFixture(1) as fixture:
            self.configure(fixture, len(SOURCE.decode()))
            fixture.bridge.register(); attempt = fixture.bridge.claim("research").attempt_id
            before, objects = fixture.registry.snapshot(), dict(fixture.store._data)
            with self.assertRaises(ValueError): cli.prepare(fixture.bridge, attempt)
            self.assertFalse((fixture.root / "audit/task_inputs" / (attempt + ".py")).exists())
            self.assertEqual(fixture.registry.snapshot(), before)
            self.assertEqual(fixture.store._data, objects)

    def test_wrong_project_or_boolean_limit_fails_closed(self):
        for maximum, project in ((True, 17), (60800, 18)):
            with self.subTest(maximum=maximum, project=project), LocalFixture(1) as fixture:
                self.configure(fixture, maximum, project)
                with self.assertRaises(ValueError): cli.local_deployment_preflight()


if __name__ == "__main__": unittest.main()
