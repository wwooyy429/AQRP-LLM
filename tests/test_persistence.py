"""Synthetic-only persistence, corruption, concurrency, and budget tests."""

from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import errno
import json
import multiprocessing
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

import os

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cloud"))

from qresearch.artifacts import (ArtifactConflict, CorruptEventStream,
                                FilesystemArtifactStore, MemoryArtifactStore,
                                StoreBusy, canonical_json, content_hash,
                                decode_events)
from qresearch.registry import BudgetExceeded, CorruptRegistry, Registry, RegistryError


def budget_fixture():
    return {"limits": {"full_configurations": 12,
                       "research_execution_attempts": 20,
                       "lean_submission_attempts": 16},
            "allocations": {"full_configurations": {"normal": 8, "reserve": 4, "total": 12},
                            "research_execution_attempts": {"normal": 12, "reserve": 8, "total": 20},
                            "lean_submission_attempts": {"normal": 8, "reserve": 8, "total": 16}},
            "usage": {"configuration_budget_charges": 5,
                      "configuration_normal_used": 5, "configuration_reserve_used": 0,
                      "research_execution_attempts": 6,
                      "research_normal_used": 4, "research_reserve_used": 2,
                      "lean_submission_attempts": 0}}


def _process_claim(root, config_id, queue):
    try:
        registry = Registry(FilesystemArtifactStore(root), budget_fixture())
        attempt = registry.begin_attempt(config_id, "research", operation_key="fixed-six-fold-run")
        queue.put((attempt.should_execute, attempt.attempt_id))
    except Exception as error:
        chain, cause = [], error
        while cause is not None:
            chain.append({"type": type(cause).__name__, "message": str(cause),
                          "errno": getattr(cause, "errno", None), "winerror": getattr(cause, "winerror", None)})
            cause = cause.__cause__
        queue.put(("error", repr(error), chain))


class _CompletionInterruptedStore(MemoryArtifactStore):
    interrupt_completion = True

    def append_event(self, stream, event):
        if event.get("kind") == "completed" and self.interrupt_completion:
            self.interrupt_completion = False
            raise OSError("Synthetic crash between result publication and journal append")
        return super().append_event(stream, event)


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.store = MemoryArtifactStore()
        self.registry = Registry(self.store, budget_fixture())
        self.config = {"fixture": "synthetic", "rules_version": 1,
                       "universe_count": 200, "timezone": "America/New_York"}

    def register(self):
        return self.registry.register_config(self.config)

    def test_config_identity_is_canonical_and_duplicate_is_free(self):
        identity = self.register()
        after_first = self.store.read_bytes(Registry.JOURNAL)
        reordered = dict(reversed(list(self.config.items())))
        self.assertEqual(identity, self.registry.register_config(reordered))
        self.assertEqual(identity, content_hash(reordered))
        self.assertEqual(after_first, self.store.read_bytes(Registry.JOURNAL))
        usage = self.registry.snapshot()["usage"]
        self.assertEqual(usage["configurations"], {"total": 6, "normal": 6, "reserve": 0})
        self.assertEqual(usage["research"], {"total": 6, "normal": 4, "reserve": 2})
        with self.assertRaises(ValueError):
            self.registry.register_config({"bad": float("nan")})
        self.assertEqual(after_first, self.store.read_bytes(Registry.JOURNAL))

    def test_thread_claims_share_one_execution_and_one_charge(self):
        identity = self.register()
        with ThreadPoolExecutor(max_workers=16) as pool:
            attempts = list(pool.map(lambda _: self.registry.begin_attempt(identity, "research"), range(48)))
        self.assertEqual(sum(item.should_execute for item in attempts), 1)
        self.assertEqual(len({item.attempt_id for item in attempts}), 1)
        self.assertEqual(self.registry.snapshot()["usage"]["research"]["total"], 7)

    def test_existing_approved_config_import_preserves_charge_and_binds_identity(self):
        full_config = dict(self.config, configuration_id="GENERIC-WF-001")
        source = canonical_json({"configuration_id": "GENERIC-WF-001", "charge": 1,
                                 "allocation": "normal", "prior_configuration_charges_preserved": 4}) + b"\n"
        key = "migration/authorized-configurations.jsonl"
        self.store.write_once(key, source)
        reference = {"key": key, "sha256": sha256(source).hexdigest(), "configuration_id": "GENERIC-WF-001"}
        identity = self.registry.import_existing_config(full_config, reference)
        after = self.store.read_bytes(Registry.JOURNAL)
        self.assertEqual(self.registry.snapshot()["usage"]["configurations"]["total"], 5)
        self.assertEqual(self.registry.import_existing_config(full_config, reference), identity)
        self.assertEqual(self.registry.register_config(full_config), identity)
        self.assertEqual(after, self.store.read_bytes(Registry.JOURNAL))
        with self.assertRaises(RegistryError):
            self.registry.import_existing_config(dict(full_config, rules_version=2), reference)
        attempt = self.registry.begin_attempt(identity, "research", allocation="reserve")
        self.assertTrue(attempt.should_execute)
        self.assertEqual(self.registry.snapshot()["usage"]["research"]["reserve"], 3)
        with self.assertRaises(RegistryError):
            self.registry.import_existing_config(full_config, dict(reference, sha256="0" * 64))

    def test_process_claims_share_one_execution_and_one_charge(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = Registry(FilesystemArtifactStore(directory), budget_fixture())
            identity = registry.register_config(self.config)
            context = multiprocessing.get_context("spawn")
            queue = context.Queue()
            processes = [context.Process(target=_process_claim, args=(directory, identity, queue)) for _ in range(4)]
            for process in processes:
                process.start()
            replies = [queue.get(timeout=20) for _ in processes]
            for process in processes:
                process.join(timeout=20)
                self.assertEqual(process.exitcode, 0)
            queue.close()
            self.assertFalse(any(item[0] == "error" for item in replies), replies)
            self.assertEqual(sum(item[0] is True for item in replies), 1)
            self.assertEqual(len({item[1] for item in replies}), 1)
            self.assertEqual(registry.snapshot()["usage"]["research"]["total"], 7)

    def test_cache_hit_has_one_result_path_and_does_not_charge(self):
        identity = self.register()
        first = self.registry.begin_attempt(identity, "research")
        self.assertEqual(self.registry.snapshot()["usage"]["research"]["total"], 7)
        accepted = self.registry.pending(first, external_id="synthetic-job-1", details={"phase": "submitted"})
        self.assertEqual(accepted.status, "pending")
        with self.assertRaises(RegistryError):
            self.registry.read_result(first)
        result = {"fixture": "synthetic", "finished": True, "rows_checked": 4}
        self.registry.complete(first, result)
        journal = self.store.read_bytes(Registry.JOURNAL)
        cached = self.registry.begin_attempt(identity, "research")
        self.assertFalse(cached.should_execute)
        self.assertEqual(cached.status, "completed")
        self.assertEqual(cached.result_key, first.result_key)
        self.assertEqual(self.registry.read_result(cached), result)
        self.registry.complete(cached, result)
        self.assertEqual(journal, self.store.read_bytes(Registry.JOURNAL))
        self.assertEqual(self.registry.snapshot()["usage"]["research"]["total"], 7)
        with self.assertRaises(ArtifactConflict):
            self.registry.complete(cached, {"fixture": "different synthetic output"})

    def test_failures_are_retained_and_retry_is_explicit_and_charged(self):
        identity = self.register()
        failed = self.registry.begin_attempt(identity, "research")
        self.registry.fail(failed, {"type": "synthetic_error", "message": "fixture failure"})
        repeated = self.registry.begin_attempt(identity, "research")
        self.assertFalse(repeated.should_execute)
        self.assertEqual(repeated.status, "failed")
        self.assertEqual(self.registry.snapshot()["usage"]["research"]["total"], 7)
        with self.assertRaises(RegistryError):
            self.registry.begin_attempt(identity, "research", retry_of=failed.attempt_id)
        retry = self.registry.begin_attempt(identity, "research", allocation="reserve",
                                            retry_of=failed.attempt_id, reason="Repair synthetic transport fixture")
        self.assertTrue(retry.should_execute)
        self.assertNotEqual(retry.attempt_id, failed.attempt_id)
        self.assertEqual(retry.result_key, failed.result_key)
        self.registry.fail(retry, "Second synthetic failure")
        snapshot = self.registry.snapshot()
        self.assertEqual(snapshot["usage"]["research"], {"total": 8, "normal": 5, "reserve": 3})
        self.assertEqual([item["status"] for item in snapshot["attempts"]], ["failed", "failed"])
        events = [item["event"] for item in decode_events(self.store.read_bytes(Registry.JOURNAL))]
        self.assertEqual(sum(item["kind"] == "failed" for item in events), 2)
        self.assertEqual(events[-2]["retry_of"], failed.attempt_id)

    def test_unknown_submission_blocks_changed_tokens_without_charge(self):
        identity = self.register()
        initial = self.registry.begin_attempt(identity, "lean")
        self.registry.ambiguous(initial, reason="Synthetic timeout after request transmission")
        before = self.store.read_bytes(Registry.JOURNAL)
        blocked = self.registry.begin_attempt(identity, "lean", operation_key="different-token")
        self.assertFalse(blocked.should_execute)
        self.assertEqual(blocked.attempt_id, initial.attempt_id)
        self.assertEqual(blocked.status, "ambiguous")
        self.assertEqual(before, self.store.read_bytes(Registry.JOURNAL))
        with self.assertRaises(RegistryError):
            self.registry.fail(initial, "Unknown is not confirmed failed")
        with self.assertRaises(RegistryError):
            self.registry.pending(initial, external_id="unverified-new-task")
        self.registry.fail(initial, "Confirmed rejected", reconciliation="Synthetic external task lookup receipt")
        retry = self.registry.begin_attempt(identity, "lean", retry_of=initial.attempt_id,
                                            reason="Retry after observed rejection", allocation="reserve")
        self.assertTrue(retry.should_execute)
        self.assertEqual(self.registry.snapshot()["usage"]["lean"], {"total": 2, "normal": 1, "reserve": 1})

    def test_budget_is_debited_before_claim_and_exhaustion_writes_nothing(self):
        small = {stage: {"total": 2, "normal": 1, "reserve": 1}
                 for stage in ("configurations", "research", "lean")}
        store = MemoryArtifactStore()
        registry = Registry(store, small)
        identity = registry.register_config(self.config)
        first = registry.begin_attempt(identity, "research")
        self.assertEqual(registry.snapshot()["usage"]["research"]["normal"], 1)
        registry.fail(first, "Synthetic failure")
        before = store.read_bytes(Registry.JOURNAL)
        with self.assertRaises(BudgetExceeded):
            registry.begin_attempt(identity, "research", retry_of=first.attempt_id, reason="Repair")
        self.assertEqual(before, store.read_bytes(Registry.JOURNAL))
        second = registry.begin_attempt(identity, "research", "reserve", retry_of=first.attempt_id, reason="Repair")
        registry.fail(second, "Synthetic failure")
        with self.assertRaises(BudgetExceeded):
            registry.begin_attempt(identity, "research", "reserve", retry_of=second.attempt_id, reason="Repair again")
        self.assertEqual(registry.snapshot()["usage"]["research"]["total"], 2)
        with self.assertRaises(BudgetExceeded):
            registry.register_config(dict(self.config, rules_version=2))
        self.assertNotEqual(identity, registry.register_config(dict(self.config, rules_version=2), "reserve"))

    def test_atomic_result_gap_is_reconciled_without_resubmission(self):
        store = _CompletionInterruptedStore()
        registry = Registry(store, budget_fixture())
        identity = registry.register_config(self.config)
        first = registry.begin_attempt(identity, "research")
        result = {"fixture": "synthetic", "finished": True}
        with self.assertRaises(OSError):
            registry.complete(first, result)
        reopened = Registry(store, budget_fixture())
        blocked = reopened.begin_attempt(identity, "research")
        self.assertFalse(blocked.should_execute)
        self.assertEqual(blocked.status, "started")
        with self.assertRaises(RegistryError):
            reopened.read_result(first)
        reopened.complete(first, result)
        self.assertEqual(reopened.read_result(first), result)
        self.assertEqual(reopened.snapshot()["usage"]["research"]["total"], 7)

    def test_torn_or_corrupted_journal_is_rejected_without_repair(self):
        with tempfile.TemporaryDirectory() as directory:
            store = FilesystemArtifactStore(directory)
            registry = Registry(store, budget_fixture())
            registry.register_config(self.config)
            journal = Path(directory) / Registry.JOURNAL
            original = journal.read_bytes()
            torn = original + b'{"sequence":'
            journal.write_bytes(torn)
            with self.assertRaises(CorruptEventStream):
                Registry(store, budget_fixture())
            self.assertEqual(journal.read_bytes(), torn)
            # The journal stores config hashes, not config arrays, so mutate a known event.
            changed = original.replace(b'"kind":"config_registered"', b'"kind":"config_registereD"')
            journal.write_bytes(changed)
            with self.assertRaises(CorruptEventStream):
                Registry(store, budget_fixture())

    def test_referenced_artifact_corruption_and_changed_baseline_are_rejected(self):
        identity = self.register()
        changed = budget_fixture()
        changed["usage"]["configuration_budget_charges"] = 4
        changed["usage"]["configuration_normal_used"] = 4
        with self.assertRaises(CorruptRegistry):
            Registry(self.store, changed)
        self.store._data["configurations/" + identity + ".json"] = canonical_json({"corrupt": True})
        with self.assertRaises(CorruptRegistry):
            self.registry.snapshot()

    def test_filesystem_immutable_single_path_and_path_safety(self):
        with tempfile.TemporaryDirectory() as directory:
            store = FilesystemArtifactStore(directory, data_classification="synthetic")
            with ThreadPoolExecutor(max_workers=8) as pool:
                written = list(pool.map(lambda _: store.write_once("synthetic/fixture.json", b"{}"), range(32)))
            self.assertEqual(sum(written), 1)
            self.assertEqual(store.read_bytes("synthetic/fixture.json"), b"{}")
            with self.assertRaises(ArtifactConflict):
                store.write_once("synthetic/fixture.json", b"[]")
            self.assertEqual([path.relative_to(directory).as_posix() for path in Path(directory).rglob("*") if path.is_file()],
                             ["synthetic/fixture.json"])
            for key in ("../escape", "/absolute", "C:/absolute", "C:\\absolute", "a/../b", "a//b", "./a",
                        "a\\b", "a\nfile", "CON", "a/.", "a/", "a.", "file:stream"):
                with self.subTest(key=key):
                    for operation in (lambda: store.exists(key), lambda: store.read_bytes(key),
                                      lambda: store.write_once(key, b"fixture"),
                                      lambda: store.append_event(key, {"fixture": True})):
                        with self.assertRaises(ValueError):
                            operation()
            with self.assertRaises(ValueError):
                FilesystemArtifactStore(directory, data_classification="quantconnect_market_data")

    def test_deleted_ordinary_leaf_is_not_resolved_into_ntfs_deleted_namespace(self):
        with tempfile.TemporaryDirectory() as directory:
            store = FilesystemArtifactStore(directory)
            leaf = store.root / ".locks" / "synthetic.lock"
            leaf.parent.mkdir()
            leaf.write_bytes(b"synthetic owner")
            original = Path.resolve
            leaf_resolves = []

            def resolve(path, *args, **kwargs):
                if path == leaf:
                    leaf_resolves.append(path)
                    # Deterministic stand-in for the observed Windows result;
                    # ordinary leaves must never call this resolution branch.
                    return Path("C:/$Extend/$Deleted/synthetic-deleted-inode")
                return original(path, *args, **kwargs)

            with patch.object(Path, "resolve", resolve):
                self.assertEqual(store._path(".locks/synthetic.lock"), leaf)
                leaf.unlink()
                self.assertEqual(store._path(".locks/synthetic.lock"), leaf)
            self.assertEqual(leaf_resolves, [])

    def test_parent_and_existing_link_or_reparse_leaf_cannot_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "inside"
            outside = base / "outside"
            outside.mkdir()
            store = FilesystemArtifactStore(root)
            original_resolve, original_lstat = Path.resolve, Path.lstat
            parent, leaf = root / "redirect", root / "leaf"

            def parent_redirect(path, *args, **kwargs):
                return outside if path == parent else original_resolve(path, *args, **kwargs)

            with patch.object(Path, "resolve", parent_redirect), self.assertRaises(ValueError):
                store._path("redirect/item.json")

            for mode, attributes in ((stat.S_IFLNK, 0),
                                     (stat.S_IFREG, getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))):
                metadata = SimpleNamespace(st_mode=mode, st_file_attributes=attributes)

                def lstat(path, *args, **kwargs):
                    return metadata if path == leaf else original_lstat(path, *args, **kwargs)

                def leaf_redirect(path, *args, **kwargs):
                    return outside / "escaped.json" if path == leaf else original_resolve(path, *args, **kwargs)

                with self.subTest(mode=mode, attributes=attributes), patch.object(Path, "lstat", lstat), patch.object(
                        Path, "resolve", leaf_redirect), self.assertRaises(ValueError):
                    store._path("leaf")
            self.assertEqual(list(outside.iterdir()), [])

    def test_path_resolution_preserves_real_parent_and_leaf_io_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            store = FilesystemArtifactStore(directory)
            original_resolve, original_lstat = Path.resolve, Path.lstat
            leaf, parent = store.root / "item", store.root
            for phase in ("parent", "leaf"):
                denied = PermissionError(errno.EACCES, "synthetic actual permission failure")

                def resolve(path, *args, **kwargs):
                    if phase == "parent" and path == parent:
                        raise denied
                    return original_resolve(path, *args, **kwargs)

                def lstat(path, *args, **kwargs):
                    if phase == "leaf" and path == leaf:
                        raise denied
                    return original_lstat(path, *args, **kwargs)

                with self.subTest(phase=phase), patch.object(Path, "resolve", resolve), patch.object(
                        Path, "lstat", lstat), self.assertRaises(PermissionError) as raised:
                    store._path("item")
                self.assertIs(raised.exception, denied)

    def test_occupied_lock_is_preserved_and_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            store = FilesystemArtifactStore(directory, lock_timeout=0)
            key = "synthetic/claim"
            lock = Path(directory) / ".locks" / (sha256(key.encode()).hexdigest() + ".lock")
            lock.parent.mkdir()
            lock.write_bytes(b"synthetic interrupted owner")
            with self.assertRaises(StoreBusy):
                with store.locked(key):
                    self.fail("An unresolved lock must not be acquired")
            self.assertEqual(lock.read_bytes(), b"synthetic interrupted owner")

    def test_windows_transient_lock_access_denial_recovers_once(self):
        with tempfile.TemporaryDirectory() as directory:
            store = FilesystemArtifactStore(directory, lock_timeout=1)
            original_open = os.open
            denied = PermissionError(errno.EACCES, "synthetic delete-pending lock")
            calls = []

            def deny_first_then_open(*args, **kwargs):
                calls.append(args[0])
                if len(calls) == 1:
                    raise denied
                return original_open(*args, **kwargs)

            entered = 0
            with patch("qresearch.artifacts._WINDOWS_LOCK_ACCESS_RETRY", True), patch(
                    "qresearch.artifacts.os.open", side_effect=deny_first_then_open):
                with store.locked("synthetic/transient"):
                    entered += 1
            self.assertEqual(entered, 1)
            self.assertEqual(len(calls), 2)
            self.assertEqual(list((Path(directory) / ".locks").iterdir()), [])

    def test_lock_timeout_must_be_finite_and_nonnegative(self):
        with tempfile.TemporaryDirectory() as directory:
            for timeout in (float("nan"), float("inf"), float("-inf"), -1):
                with self.subTest(timeout=timeout), self.assertRaisesRegex(ValueError, "finite and nonnegative"):
                    FilesystemArtifactStore(directory, lock_timeout=timeout)
            self.assertEqual(FilesystemArtifactStore(directory, lock_timeout=0).lock_timeout, 0)

    def test_windows_persistent_access_denial_preserves_error_and_owner(self):
        with tempfile.TemporaryDirectory() as directory:
            store = FilesystemArtifactStore(directory, lock_timeout=1)
            key = "synthetic/denied"
            lock = Path(directory) / ".locks" / (sha256(key.encode()).hexdigest() + ".lock")
            lock.parent.mkdir()
            owner = b"synthetic unresolved owner"
            lock.write_bytes(owner)
            denied = PermissionError(errno.EACCES, "synthetic persistent access denial")
            with patch("qresearch.artifacts._WINDOWS_LOCK_ACCESS_RETRY", True), patch(
                    "qresearch.artifacts.os.open", side_effect=denied) as opening, patch(
                    "qresearch.artifacts.time.monotonic", side_effect=[0., .5, .5, 1.]), patch(
                    "qresearch.artifacts.time.sleep") as sleeping:
                with self.assertRaises(PermissionError) as raised:
                    with store.locked(key):
                        self.fail("A denied lock cannot enter the critical section")
            self.assertIs(raised.exception, denied)
            self.assertEqual(opening.call_count, 2)
            sleeping.assert_called_once()
            self.assertEqual(lock.read_bytes(), owner)

    def test_nonwindows_or_other_permission_errors_are_not_retried(self):
        with tempfile.TemporaryDirectory() as directory:
            store = FilesystemArtifactStore(directory, lock_timeout=1)
            for windows, code in ((False, errno.EACCES), (True, errno.EPERM)):
                denied = PermissionError(code, "synthetic real permission fault")
                with self.subTest(windows=windows, errno=code), patch(
                        "qresearch.artifacts._WINDOWS_LOCK_ACCESS_RETRY", windows), patch(
                        "qresearch.artifacts.os.open", side_effect=denied) as opening, patch(
                        "qresearch.artifacts.time.sleep") as sleeping:
                    with self.assertRaises(PermissionError) as raised:
                        with store.locked("synthetic/denied"):
                            self.fail("A permission fault cannot enter the critical section")
                self.assertIs(raised.exception, denied)
                opening.assert_called_once()
                sleeping.assert_not_called()

    def test_event_chain_sequence_and_hashes_are_verified(self):
        first = self.store.append_event("synthetic/events.jsonl", {"fixture": 1})
        second = self.store.append_event("synthetic/events.jsonl", {"fixture": 2})
        self.assertEqual(first["sequence"], 1)
        self.assertEqual(second["previous_hash"], first["hash"])
        records = decode_events(self.store.read_bytes("synthetic/events.jsonl"))
        self.assertEqual(len(records), 2)
        corrupted = dict(second, sequence=4)
        with self.assertRaises(CorruptEventStream):
            decode_events(canonical_json(first) + b"\n" + canonical_json(corrupted) + b"\n")


if __name__ == "__main__":
    unittest.main()
