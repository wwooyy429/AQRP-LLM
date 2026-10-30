"""Synthetic first-admission write boundaries; no cloud or real budget calls."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "cloud"), str(ROOT / "tools"), str(ROOT / "tests")]
from qresearch.artifacts import canonical_json
from qresearch.engineering_tasks import EngineeringTaskError
from qresearch.registry import RegistryError
import stage2 as cli
from test_native_research_failure import error_tool, read_cell
from test_wr17_engineering_recovery import SyntheticFixture


class InjectedWriteFailure(OSError):
    pass


class WR23PrepareProtocolTests(unittest.TestCase):
    def assert_settlement_blocked(self, fixture):
        before, saved = fixture.registry.snapshot(), dict(fixture.store._data)
        for tool in (fixture.research_observation(), error_tool(index=0)):
            with self.assertRaises((ValueError, EngineeringTaskError)):
                cli.settle_research_result(fixture.bridge, fixture.attempt, tool)
            self.assertEqual(fixture.registry.snapshot(), before)
            self.assertEqual(fixture.store._data, saved)
        with self.assertRaises((EngineeringTaskError, RegistryError)):
            fixture.bridge.claim("lean")
        self.assertEqual(fixture.registry.snapshot(), before)
        self.assertEqual(fixture.store._data, saved)

    def test_first_admission_atomically_pins_protocol_identity(self):
        for version in (1, 2):
            with self.subTest(version=version), SyntheticFixture(version) as fixture:
                value = cli.admitted_input(fixture.bridge, fixture.attempt)
                self.assertEqual(set(value), {"payload", "deployment", "input_path", "cloud_input_path", "research_entry_protocol"})
                sidecar = fixture.store.read_bytes("engineering/research-entry-protocol/" + fixture.attempt + ".json")
                self.assertEqual(canonical_json(value["research_entry_protocol"]), sidecar)
                self.assert_settlement_blocked(fixture)

    def test_actual_entry_write_failure_cannot_recover_as_unbound_legacy(self):
        for version in (1, 2):
            with self.subTest(version=version), SyntheticFixture(version, prepare=False) as fixture:
                original = fixture.store.write_once
                entry = "engineering/research-entry-protocol/" + fixture.attempt + ".json"
                def interrupted(key, data):
                    if key == entry:
                        raise InjectedWriteFailure("Synthetic entry write interrupted")
                    return original(key, data)
                before = fixture.registry.snapshot()
                with patch.object(fixture.store, "write_once", side_effect=interrupted), self.assertRaises(InjectedWriteFailure):
                    cli.prepare(fixture.bridge, fixture.attempt)
                self.assertFalse(fixture.store.exists(entry))
                fixture.admission = cli.prepare(fixture.bridge, fixture.attempt)
                self.assertIn("research_entry_protocol", fixture.admission)
                self.assertFalse(fixture.store.exists(entry))
                self.assert_settlement_blocked(fixture)
                self.assertEqual(fixture.registry.snapshot(), before)
                saved = dict(fixture.store._data)
                with self.assertRaises(EngineeringTaskError):
                    cli.research_dispatch(fixture.bridge, fixture.attempt,
                        read_cell(fixture.admission["payload"], fixture.admission["deployment"], index=0))
                self.assertEqual(fixture.store._data, saved)

    def test_each_input_admission_entry_write_boundary_preserves_new_protocol(self):
        for boundary in ("input", "admission", "entry"):
            for after_write in (False, True):
                with self.subTest(boundary=boundary, after_write=after_write), SyntheticFixture(2, prepare=False) as fixture:
                    original_store = fixture.store.write_once
                    original_input = cli.write_changed
                    admission_key = "engineering/admitted-inputs/" + fixture.attempt + ".json"
                    entry_key = "engineering/research-entry-protocol/" + fixture.attempt + ".json"
                    def write_store(key, data):
                        target = admission_key if boundary == "admission" else entry_key
                        if boundary != "input" and key == target:
                            if after_write:
                                original_store(key, data)
                            raise InjectedWriteFailure("Synthetic store publication interrupted")
                        return original_store(key, data)
                    def write_input(path, text):
                        if boundary == "input":
                            if after_write:
                                original_input(path, text)
                            raise InjectedWriteFailure("Synthetic input publication interrupted")
                        return original_input(path, text)
                    before = fixture.registry.snapshot()
                    with patch.object(fixture.store, "write_once", side_effect=write_store), patch.object(cli, "write_changed", side_effect=write_input):
                        with self.assertRaises(InjectedWriteFailure):
                            cli.prepare(fixture.bridge, fixture.attempt)
                    if fixture.store.exists(admission_key):
                        self.assertIn("research_entry_protocol", json.loads(fixture.store.read_bytes(admission_key)))
                    fixture.admission = cli.prepare(fixture.bridge, fixture.attempt)
                    self.assertIn("research_entry_protocol", fixture.admission)
                    self.assert_settlement_blocked(fixture)
                    self.assertEqual(fixture.registry.snapshot(), before)
                    if fixture.store.exists(entry_key):
                        source = read_cell(fixture.admission["payload"], fixture.admission["deployment"], index=0)
                        self.assertTrue(cli.research_dispatch(fixture.bridge, fixture.attempt, source)["should_execute"])
                        self.assertFalse(cli.research_dispatch(fixture.bridge, fixture.attempt, source)["should_execute"])
                        self.assertEqual(cli.settle_research_result(fixture.bridge, fixture.attempt, fixture.research_observation()).status, "completed")
                    else:
                        saved = dict(fixture.store._data)
                        self.assertEqual(cli.prepare(fixture.bridge, fixture.attempt), fixture.admission)
                        self.assertEqual(fixture.store._data, saved)

    def test_inline_protocol_corruption_is_rejected_before_any_writes(self):
        for mode in ("empty", "wrong-kind", "boolean-alias", "wrong-attempt"):
            with self.subTest(mode=mode), SyntheticFixture(2) as fixture:
                # JSON restores independent identities exactly as persisted;
                # do not let Python aliasing mutate payload and protocol together.
                original = json.loads(canonical_json(fixture.admission))
                protocol = original["research_entry_protocol"]
                if mode == "empty":
                    original["research_entry_protocol"] = {}
                elif mode == "wrong-kind":
                    original["research_entry_protocol"] = None
                elif mode == "boolean-alias":
                    protocol["schema_version"] = True
                else:
                    protocol["identity"]["attempt_id"] = "0" * 32
                key = "engineering/admitted-inputs/" + fixture.attempt + ".json"
                fixture.store._data[key] = canonical_json(original)
                before, saved = fixture.registry.snapshot(), dict(fixture.store._data)
                with self.assertRaises(ValueError):
                    cli.prepare(fixture.bridge, fixture.attempt)
                with self.assertRaises(ValueError):
                    cli.settle_research_result(fixture.bridge, fixture.attempt, fixture.research_observation())
                self.assertEqual(fixture.registry.snapshot(), before)
                self.assertEqual(fixture.store._data, saved)

    def test_inline_identity_survives_missing_or_contradictory_sidecar(self):
        for mode in ("missing", "different"):
            with self.subTest(mode=mode), SyntheticFixture(2) as fixture:
                key = "engineering/research-entry-protocol/" + fixture.attempt + ".json"
                if mode == "missing":
                    del fixture.store._data[key]
                else:
                    fixture.store._data[key] = canonical_json({"synthetic_foreign_protocol": True})
                self.assert_settlement_blocked(fixture)

    def test_historical_four_field_admission_with_original_entry_still_recovers(self):
        with SyntheticFixture(2) as fixture:
            fixture.admission.pop("research_entry_protocol")
            fixture.store._data["engineering/admitted-inputs/" + fixture.attempt + ".json"] = canonical_json(fixture.admission)
            before = fixture.registry.snapshot()["usage"]
            self.assertEqual(cli.prepare(fixture.bridge, fixture.attempt), fixture.admission)
            permit = cli.research_dispatch(fixture.bridge, fixture.attempt,
                read_cell(fixture.admission["payload"], fixture.admission["deployment"], index=0))
            self.assertTrue(permit["should_execute"])
            self.assertEqual(cli.settle_research_result(fixture.bridge, fixture.attempt, error_tool(index=0)).status, "failed")
            self.assertEqual(cli.settle_research_result(fixture.bridge, fixture.attempt, error_tool(index=0)).status, "failed")
            self.assertEqual(fixture.registry.snapshot()["usage"], before)

    def test_concurrent_first_prepare_publishes_one_identical_input(self):
        with SyntheticFixture(2, prepare=False) as fixture:
            original_input = cli.write_changed
            writes = []
            def writing(path, text):
                writes.append(str(path))
                return original_input(path, text)
            with patch.object(cli, "write_changed", side_effect=writing), ThreadPoolExecutor(max_workers=8) as pool:
                values = list(pool.map(lambda _: cli.prepare(fixture.bridge, fixture.attempt), range(24)))
            self.assertTrue(all(value == values[0] for value in values))
            self.assertEqual(len(writes), 1)
            fixture.admission = values[0]
            self.assert_settlement_blocked(fixture)

    def test_new_prepared_dispatch_is_still_single_use_under_concurrency(self):
        with SyntheticFixture(2) as fixture:
            tool = read_cell(fixture.admission["payload"], fixture.admission["deployment"], index=0)
            with ThreadPoolExecutor(max_workers=8) as pool:
                values = list(pool.map(lambda _: cli.research_dispatch(fixture.bridge, fixture.attempt, tool), range(16)))
            self.assertEqual(sum(value["should_execute"] for value in values), 1)
            before, saved = fixture.registry.snapshot(), dict(fixture.store._data)
            self.assertEqual(cli.prepare(fixture.bridge, fixture.attempt), fixture.admission)
            self.assertFalse(cli.research_dispatch(fixture.bridge, fixture.attempt, tool)["should_execute"])
            self.assertEqual(fixture.registry.snapshot(), before)
            self.assertEqual(fixture.store._data, saved)


if __name__ == "__main__":
    unittest.main()
