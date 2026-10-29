"""Synthetic-only owner-safe lock release; no production registry or cloud I/O."""
import errno
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cloud"))
from qresearch.artifacts import ArtifactConflict, FilesystemArtifactStore, canonical_json


def sharing_error(code=32):
    error = PermissionError(errno.EACCES, "synthetic lock sharing error")
    error.winerror = code
    return error


class Clock:
    def __init__(self, advances=True):
        self.now = 0.0
        self.advances = advances
        self.sleeps = []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        if self.advances:
            self.now += seconds


class LockReleaseRetryTests(unittest.TestCase):
    KEY = "synthetic/transaction"

    def fixture(self, directory, timeout=1):
        store = FilesystemArtifactStore(directory, data_classification="synthetic", lock_timeout=timeout)
        lock = store.root / ".locks" / (sha256(self.KEY.encode()).hexdigest() + ".lock")
        return store, lock

    def test_windows_share_violation_retries_release_without_repeating_body(self):
        with tempfile.TemporaryDirectory() as directory:
            store, lock = self.fixture(directory)
            original = Path.unlink
            clock, owners, entered = Clock(), [], []

            def release(path, *args, **kwargs):
                if path != lock:
                    return original(path, *args, **kwargs)
                owners.append(path.read_bytes())
                if len(owners) < 3:
                    raise sharing_error()
                return original(path, *args, **kwargs)

            with patch("qresearch.artifacts._WINDOWS_LOCK_ACCESS_RETRY", True), patch.object(
                    Path, "unlink", release), patch("qresearch.artifacts.time.monotonic", clock.monotonic), patch(
                    "qresearch.artifacts.time.sleep", clock.sleep):
                with store.locked(self.KEY):
                    entered.append(True)
            self.assertEqual(entered, [True])
            self.assertEqual(len(owners), 3)
            self.assertTrue(all(owner == owners[0] for owner in owners))
            owner = json.loads(owners[0])
            self.assertEqual(owner["key"], self.KEY)
            self.assertEqual(owner["process_id"], os.getpid())
            self.assertRegex(owner["owner_token"], "^[0-9a-f]{32}$")
            self.assertEqual(canonical_json(owner), owners[0])
            self.assertEqual(len(clock.sleeps), 2)
            self.assertFalse(lock.exists())

    def test_replaced_owner_during_backoff_is_preserved_without_second_delete(self):
        with tempfile.TemporaryDirectory() as directory:
            store, lock = self.fixture(directory)
            original = Path.unlink
            clock, calls, replacement = Clock(), [], []

            def release(path, *args, **kwargs):
                if path != lock:
                    return original(path, *args, **kwargs)
                calls.append(path)
                owner = json.loads(path.read_bytes())
                owner["owner_token"] = "0" * 32 if owner["owner_token"] != "0" * 32 else "1" * 32
                replacement.append(canonical_json(owner))
                path.write_bytes(replacement[-1])
                raise sharing_error()

            with patch("qresearch.artifacts._WINDOWS_LOCK_ACCESS_RETRY", True), patch.object(
                    Path, "unlink", release), patch("qresearch.artifacts.time.monotonic", clock.monotonic), patch(
                    "qresearch.artifacts.time.sleep", clock.sleep), self.assertRaises(ArtifactConflict):
                with store.locked(self.KEY):
                    pass
            self.assertEqual(len(calls), 1)
            self.assertEqual(lock.read_bytes(), replacement[0])

    def test_initial_foreign_or_noncanonical_owner_never_deleted(self):
        for change in (lambda o: o.update(process_id=o["process_id"] + 1),
                       lambda o: o.update(key="synthetic/other"),
                       lambda o: o.update(owner_token="foreign"),
                       lambda o: o.update(extra=True),
                       lambda o: None):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                store, lock = self.fixture(directory)
                with patch.object(Path, "unlink") as deleting, self.assertRaises(ArtifactConflict):
                    with store.locked(self.KEY):
                        owner = json.loads(lock.read_bytes())
                        change(owner)
                        changed = json.dumps(owner, indent=2).encode("utf-8")
                        lock.write_bytes(changed)
                deleting.assert_not_called()
                self.assertEqual(lock.read_bytes(), changed)

    def test_context_inherited_by_a_different_process_cannot_release_parent_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            store, lock = self.fixture(directory)
            context = store.locked(self.KEY)
            context.__enter__()
            captured = lock.read_bytes()
            another_process = os.getpid() + 1000
            with patch("qresearch.artifacts.os.getpid", return_value=another_process), patch.object(
                    Path, "unlink") as deleting, self.assertRaises(ArtifactConflict):
                context.__exit__(None, None, None)
            deleting.assert_not_called()
            self.assertEqual(lock.read_bytes(), captured)

    def test_invalid_captured_owner_or_wrong_key_cannot_authorize_release(self):
        variants = ({"owner_token": "a" * 32, "process_id": os.getpid(), "key": self.KEY, "extra": False},
                    {"owner_token": "not-a-token", "process_id": os.getpid(), "key": self.KEY},
                    {"owner_token": "a" * 32, "process_id": True, "key": self.KEY},
                    {"owner_token": "a" * 32, "process_id": os.getpid(), "key": "../outside"},
                    {"owner_token": "a" * 32, "process_id": os.getpid(), "key": "synthetic/other"})
        for owner in variants:
            with self.subTest(owner=owner), tempfile.TemporaryDirectory() as directory:
                store, lock = self.fixture(directory)
                lock.parent.mkdir(parents=True)
                captured = canonical_json(owner)
                lock.write_bytes(captured)
                with patch.object(Path, "unlink") as deleting, self.assertRaises(ArtifactConflict):
                    store._release_lock(lock, captured)
                deleting.assert_not_called()
                self.assertEqual(lock.read_bytes(), captured)

    def test_owner_disappearing_after_denied_release_is_not_reported_as_success(self):
        with tempfile.TemporaryDirectory() as directory:
            store, lock = self.fixture(directory)
            original = Path.unlink
            clock, calls = Clock(), []

            def release(path, *args, **kwargs):
                if path != lock:
                    return original(path, *args, **kwargs)
                calls.append(path)
                original(path, *args, **kwargs)
                raise sharing_error()

            with patch("qresearch.artifacts._WINDOWS_LOCK_ACCESS_RETRY", True), patch.object(
                    Path, "unlink", release), patch("qresearch.artifacts.time.monotonic", clock.monotonic), patch(
                    "qresearch.artifacts.time.sleep", clock.sleep), self.assertRaises(ArtifactConflict):
                with store.locked(self.KEY):
                    pass
            self.assertEqual(len(calls), 1)
            self.assertFalse(lock.exists())

    def test_initially_missing_lock_keeps_legacy_no_delete_behavior(self):
        with tempfile.TemporaryDirectory() as directory:
            store, lock = self.fixture(directory)
            with patch.object(Path, "unlink") as deleting:
                with store.locked(self.KEY):
                    os.unlink(lock)
            deleting.assert_not_called()
            self.assertFalse(lock.exists())

    def test_owner_read_failure_during_backoff_is_not_retried_or_hidden(self):
        with tempfile.TemporaryDirectory() as directory:
            store, lock = self.fixture(directory)
            original_read, original_unlink = Path.read_bytes, Path.unlink
            clock, attempts = Clock(), []
            denied = sharing_error()

            def read(path):
                if path == lock and attempts:
                    raise denied
                return original_read(path)

            def release(path, *args, **kwargs):
                if path != lock:
                    return original_unlink(path, *args, **kwargs)
                attempts.append(path)
                raise sharing_error()

            with patch("qresearch.artifacts._WINDOWS_LOCK_ACCESS_RETRY", True), patch.object(
                    Path, "unlink", release), patch.object(Path, "read_bytes", read), patch(
                    "qresearch.artifacts.time.monotonic", clock.monotonic), patch(
                    "qresearch.artifacts.time.sleep", clock.sleep), self.assertRaises(PermissionError) as caught:
                with store.locked(self.KEY):
                    pass
            self.assertIs(caught.exception, denied)
            self.assertEqual(len(attempts), 1)
            self.assertTrue(lock.exists())

    def test_initial_owner_read_failure_preserves_error_without_delete(self):
        with tempfile.TemporaryDirectory() as directory:
            store, lock = self.fixture(directory)
            original_read = Path.read_bytes
            denied = sharing_error()

            def read(path):
                if path == lock:
                    raise denied
                return original_read(path)

            with patch.object(Path, "read_bytes", read), patch.object(Path, "unlink") as deleting, patch(
                    "qresearch.artifacts.time.sleep") as sleeping, self.assertRaises(PermissionError) as caught:
                with store.locked(self.KEY):
                    pass
            self.assertIs(caught.exception, denied)
            deleting.assert_not_called()
            sleeping.assert_not_called()
            self.assertTrue(lock.exists())

    def test_only_windows_winerror32_is_retryable(self):
        for windows, code in ((False, 32), (True, 5), (True, 33), (True, None)):
            with self.subTest(windows=windows, code=code), tempfile.TemporaryDirectory() as directory:
                store, lock = self.fixture(directory)
                denied = sharing_error(code)
                original = Path.unlink
                attempts = []

                def release(path, *args, **kwargs):
                    if path != lock:
                        return original(path, *args, **kwargs)
                    attempts.append(path)
                    raise denied

                with patch("qresearch.artifacts._WINDOWS_LOCK_ACCESS_RETRY", windows), patch.object(
                        Path, "unlink", release), patch("qresearch.artifacts.time.sleep") as sleeping, self.assertRaises(
                        PermissionError) as caught:
                    with store.locked(self.KEY):
                        pass
                self.assertIs(caught.exception, denied)
                self.assertEqual(len(attempts), 1)
                sleeping.assert_not_called()
                self.assertTrue(lock.exists())

    def test_release_window_honors_lock_timeout_and_preserves_lock_on_exhaustion(self):
        with tempfile.TemporaryDirectory() as directory:
            store, lock = self.fixture(directory, timeout=0.12)
            original = Path.unlink
            clock, attempts = Clock(), []
            denied = sharing_error()

            def release(path, *args, **kwargs):
                if path != lock:
                    return original(path, *args, **kwargs)
                attempts.append(path)
                raise denied

            with patch("qresearch.artifacts._WINDOWS_LOCK_ACCESS_RETRY", True), patch.object(
                    Path, "unlink", release), patch("qresearch.artifacts.time.monotonic", clock.monotonic), patch(
                    "qresearch.artifacts.time.sleep", clock.sleep), self.assertRaises(PermissionError) as caught:
                with store.locked(self.KEY):
                    pass
            self.assertIs(caught.exception, denied)
            self.assertEqual(len(attempts), 3)
            self.assertAlmostEqual(sum(clock.sleeps), 0.12)
            self.assertTrue(lock.exists())

    def test_release_still_bounded_when_clock_does_not_advance(self):
        with tempfile.TemporaryDirectory() as directory:
            store, lock = self.fixture(directory, timeout=1000)
            original = Path.unlink
            clock, attempts = Clock(advances=False), []

            def release(path, *args, **kwargs):
                if path != lock:
                    return original(path, *args, **kwargs)
                attempts.append(path)
                raise sharing_error()

            with patch("qresearch.artifacts._WINDOWS_LOCK_ACCESS_RETRY", True), patch.object(
                    Path, "unlink", release), patch("qresearch.artifacts.time.monotonic", clock.monotonic), patch(
                    "qresearch.artifacts.time.sleep", clock.sleep), self.assertRaises(PermissionError):
                with store.locked(self.KEY):
                    pass
            self.assertEqual(len(attempts), 121)
            self.assertEqual(len(clock.sleeps), 120)
            self.assertTrue(lock.exists())

    def test_release_time_cap_does_not_expand_with_large_acquisition_timeout(self):
        with tempfile.TemporaryDirectory() as directory:
            store, lock = self.fixture(directory, timeout=1000)
            original = Path.unlink
            clock, attempts = Clock(), []

            def release(path, *args, **kwargs):
                if path != lock:
                    return original(path, *args, **kwargs)
                attempts.append(path)
                raise sharing_error()

            with patch("qresearch.artifacts._WINDOWS_LOCK_ACCESS_RETRY", True), patch.object(
                    Path, "unlink", release), patch("qresearch.artifacts.time.monotonic", clock.monotonic), patch(
                    "qresearch.artifacts.time.sleep", clock.sleep), self.assertRaises(PermissionError):
                with store.locked(self.KEY):
                    pass
            self.assertLessEqual(len(attempts), 121)
            self.assertLessEqual(sum(clock.sleeps), 6.0 + 1e-9)
            self.assertTrue(lock.exists())

    def test_zero_timeout_means_one_attempt_without_backoff(self):
        with tempfile.TemporaryDirectory() as directory:
            store, lock = self.fixture(directory, timeout=0)
            denied = sharing_error()
            original = Path.unlink
            attempts = []

            def release(path, *args, **kwargs):
                if path != lock:
                    return original(path, *args, **kwargs)
                attempts.append(path)
                raise denied

            with patch("qresearch.artifacts._WINDOWS_LOCK_ACCESS_RETRY", True), patch.object(
                    Path, "unlink", release), patch("qresearch.artifacts.time.sleep") as sleeping, self.assertRaises(
                    PermissionError) as caught:
                with store.locked(self.KEY):
                    pass
            self.assertIs(caught.exception, denied)
            self.assertEqual(len(attempts), 1)
            sleeping.assert_not_called()
            self.assertTrue(lock.exists())

    def test_release_window_starts_after_long_critical_section(self):
        with tempfile.TemporaryDirectory() as directory:
            store, lock = self.fixture(directory, timeout=1)
            original = Path.unlink
            clock, attempts = Clock(), []

            def release(path, *args, **kwargs):
                if path != lock:
                    return original(path, *args, **kwargs)
                attempts.append(path)
                if len(attempts) == 1:
                    raise sharing_error()
                return original(path, *args, **kwargs)

            with patch("qresearch.artifacts._WINDOWS_LOCK_ACCESS_RETRY", True), patch.object(
                    Path, "unlink", release), patch("qresearch.artifacts.time.monotonic", clock.monotonic), patch(
                    "qresearch.artifacts.time.sleep", clock.sleep):
                with store.locked(self.KEY):
                    clock.now = 99.0
            self.assertEqual(len(attempts), 2)
            self.assertFalse(lock.exists())

    def test_body_exception_survives_successful_release_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            store, lock = self.fixture(directory)
            original = Path.unlink
            clock, attempts = Clock(), []
            body_error = ValueError("synthetic body failure")

            def release(path, *args, **kwargs):
                if path != lock:
                    return original(path, *args, **kwargs)
                attempts.append(path)
                if len(attempts) == 1:
                    raise sharing_error()
                return original(path, *args, **kwargs)

            with patch("qresearch.artifacts._WINDOWS_LOCK_ACCESS_RETRY", True), patch.object(
                    Path, "unlink", release), patch("qresearch.artifacts.time.monotonic", clock.monotonic), patch(
                    "qresearch.artifacts.time.sleep", clock.sleep), self.assertRaises(ValueError) as caught:
                with store.locked(self.KEY):
                    raise body_error
            self.assertIs(caught.exception, body_error)
            self.assertFalse(lock.exists())

    def test_nonretryable_release_failure_keeps_body_error_as_context(self):
        with tempfile.TemporaryDirectory() as directory:
            store, lock = self.fixture(directory)
            original = Path.unlink
            denied, body_error = sharing_error(5), ValueError("synthetic body failure")

            def release(path, *args, **kwargs):
                if path == lock:
                    raise denied
                return original(path, *args, **kwargs)

            with patch("qresearch.artifacts._WINDOWS_LOCK_ACCESS_RETRY", True), patch.object(
                    Path, "unlink", release), self.assertRaises(PermissionError) as caught:
                with store.locked(self.KEY):
                    raise body_error
            self.assertIs(caught.exception, denied)
            self.assertIs(caught.exception.__context__, body_error)
            self.assertTrue(lock.exists())

    def test_retry_exhaustion_keeps_body_error_as_context(self):
        with tempfile.TemporaryDirectory() as directory:
            store, lock = self.fixture(directory, timeout=0.02)
            original = Path.unlink
            clock = Clock()
            denied, body_error = sharing_error(), ValueError("synthetic committed-body failure")

            def release(path, *args, **kwargs):
                if path == lock:
                    raise denied
                return original(path, *args, **kwargs)

            with patch("qresearch.artifacts._WINDOWS_LOCK_ACCESS_RETRY", True), patch.object(
                    Path, "unlink", release), patch("qresearch.artifacts.time.monotonic", clock.monotonic), patch(
                    "qresearch.artifacts.time.sleep", clock.sleep), self.assertRaises(PermissionError) as caught:
                with store.locked(self.KEY):
                    raise body_error
            self.assertIs(caught.exception, denied)
            self.assertIs(caught.exception.__context__, body_error)
            self.assertTrue(lock.exists())

    def test_unrelated_os_error_is_not_retried_or_reclassified(self):
        with tempfile.TemporaryDirectory() as directory:
            store, lock = self.fixture(directory)
            original = Path.unlink
            io_error, attempts = OSError(errno.EIO, "synthetic filesystem error"), []

            def release(path, *args, **kwargs):
                if path == lock:
                    attempts.append(path)
                    raise io_error
                return original(path, *args, **kwargs)

            with patch("qresearch.artifacts._WINDOWS_LOCK_ACCESS_RETRY", True), patch.object(
                    Path, "unlink", release), patch("qresearch.artifacts.time.sleep") as sleeping, self.assertRaises(
                    OSError) as caught:
                with store.locked(self.KEY):
                    pass
            self.assertIs(caught.exception, io_error)
            self.assertEqual(len(attempts), 1)
            sleeping.assert_not_called()
            self.assertTrue(lock.exists())


if __name__ == "__main__":
    unittest.main()
