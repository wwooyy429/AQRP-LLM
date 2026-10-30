"""Synthetic SDK metadata and quota boundaries; no QuantConnect connection."""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
import json
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cloud"))
from qresearch.artifacts import ArtifactConflict
from qresearch.quantconnect import ObjectStoreArtifactStore
from qresearch.storage_capacity import (StorageCapacityError, StorageOperationError,
    StorageVerificationError, check_capacity, inspect_object_store_capacity,
    preflight_object_store)


SECRET = "PRIVATE-KEY-OR-PAYLOAD-999"


class ErrorSignal:
    def __init__(self): self.handlers = []
    def __iadd__(self, handler): self.handlers.append(handler); return self
    def __isub__(self, handler): self.handlers.remove(handler); return self
    def emit(self):
        for handler in self.handlers:
            handler(self, object())


class MetadataStore:
    """Existing files expose sizes; reading their payload is forbidden."""
    def __init__(self, root, sizes=(10, 20), max_size=100, max_files=10):
        self.root = root
        self.max_size, self.max_files = max_size, max_files
        self.error_raised = ErrorSignal()
        self.paths = {}
        for index, size in enumerate(sizes):
            key = "unexported-key-" + str(index)
            path = root / str(index)
            path.write_bytes(b"x" * size)
            self.paths[key] = str(path)
        self.path_requests = []
        self.contains_requests = []
        self.save_calls = 0

    @property
    def keys(self):
        return list(self.paths)

    def __iter__(self):
        raise AssertionError("Payload iterator must never be used")

    def contains_key(self, key):
        self.contains_requests.append(key)
        return key in self.paths

    def get_file_path(self, key):
        self.path_requests.append(key)
        if key not in self.paths:
            raise AssertionError("Never ask SDK to register a missing key")
        return self.paths[key]

    def read_bytes(self, key):
        raise AssertionError("Capacity check must never read licensed object bytes")

    def save_bytes(self, key, data):
        self.save_calls += 1
        raise AssertionError("Preflight must not write")


class StorageCapacityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_complete_metadata_counts_entire_store_without_reading_payloads(self):
        native = MetadataStore(self.root)
        result = inspect_object_store_capacity(native)
        self.assertEqual(result, {"max_size_bytes": 100, "max_files": 10,
                                  "used_size_bytes": 30, "used_files": 2})
        self.assertEqual(len(native.path_requests), 4)
        self.assertEqual(native.save_calls, 0)
        self.assertEqual(native.error_raised.handlers, [])
        self.assertNotIn("unexported-key", json.dumps(result))

    def test_exact_boundary_and_explicit_reserve_known_answer(self):
        result = preflight_object_store(MetadataStore(self.root), 60, 7,
                                       reserve_bytes=10, reserve_files=1)
        self.assertEqual(result["remaining_bytes_after_reservation"], 0)
        self.assertEqual(result["remaining_files_after_reservation"], 0)
        self.assertEqual(result["usage_method"], "keys_file_stat")

    def test_bytes_or_file_space_rejected_before_save_or_source_fetch(self):
        for required_bytes, required_files, code in ((71, 0, "byte_capacity_insufficient"),
                                                   (0, 9, "file_capacity_insufficient")):
            with self.subTest(code=code):
                native = MetadataStore(self.root)
                adapter = ObjectStoreArtifactStore(native, "prefix", read_only=False, single_producer=True)
                source_calls = []
                with self.assertRaises(StorageCapacityError) as caught:
                    adapter.preflight_capacity(required_bytes, required_files)
                    source_calls.append("fetch")
                self.assertEqual(caught.exception.failure_code, code)
                self.assertEqual(native.save_calls, 0)
                self.assertEqual(source_calls, [])

    def test_invalid_request_fails_before_accessing_native_metadata(self):
        class Untouchable:
            @property
            def max_size(self):
                raise AssertionError("Invalid request must fail before SDK access")
        for bad in (-1, True, 1.5, "1", None):
            for key in ("required_bytes", "required_files", "reserve_bytes", "reserve_files"):
                values = dict(required_bytes=1, required_files=1, reserve_bytes=0, reserve_files=0)
                values[key] = bad
                with self.subTest(key=key, bad=bad), self.assertRaises(StorageCapacityError) as caught:
                    preflight_object_store(Untouchable(), **values)
                self.assertEqual(caught.exception.failure_code, "invalid_capacity_request")

    def test_missing_usage_metadata_fails_closed(self):
        for native in (object(), SimpleNamespace(max_size=100),
                       SimpleNamespace(max_size=100, max_files=10),
                       SimpleNamespace(max_size=True, max_files=10, keys=[])):
            with self.subTest(native=type(native).__name__), self.assertRaises(StorageCapacityError) as caught:
                inspect_object_store_capacity(native)
            self.assertEqual(caught.exception.failure_code, "capacity_unavailable")

    def test_stale_key_never_calls_get_file_path_to_create_it(self):
        native = MetadataStore(self.root)
        native.contains_key = lambda key: False
        with self.assertRaises(StorageCapacityError):
            inspect_object_store_capacity(native)
        self.assertEqual(native.path_requests, [])

    def test_duplicate_or_unsafe_native_keys_fail_without_echoing_names(self):
        for key_set in ([SECRET, SECRET], [None], [""], ["bad\x00key"]):
            native = SimpleNamespace(max_size=100, max_files=10, keys=key_set, error_raised=ErrorSignal())
            with self.subTest(keys=key_set), self.assertRaises(StorageCapacityError) as caught:
                inspect_object_store_capacity(native)
            self.assertNotIn(SECRET, str(caught.exception))

    def test_unmaterialized_or_nonfile_metadata_fails_closed(self):
        for target in (self.root / "absent", self.root):
            native = MetadataStore(self.root)
            native.paths[next(iter(native.paths))] = str(target)
            with self.subTest(target=target.name), self.assertRaises(StorageCapacityError) as caught:
                inspect_object_store_capacity(native)
            self.assertEqual(caught.exception.failure_code, "capacity_unavailable")

    def test_metadata_exception_never_exports_arbitrary_sdk_message_or_path(self):
        native = MetadataStore(self.root)
        with patch("qresearch.storage_capacity.os.stat", side_effect=RuntimeError(SECRET)):
            with self.assertRaises(StorageCapacityError) as caught:
                inspect_object_store_capacity(native)
        self.assertEqual(str(caught.exception), "AQRP_STORAGE capacity_unavailable")
        self.assertNotIn(SECRET, json.dumps(caught.exception.safe_diagnostic()))
        self.assertTrue(caught.exception.__suppress_context__)

    def test_key_set_change_between_passes_is_not_an_accurate_snapshot(self):
        class ChangingStore(MetadataStore):
            calls = 0
            @property
            def keys(self):
                self.calls += 1
                return list(self.paths) if self.calls == 1 else []
        with self.assertRaises(StorageCapacityError) as caught:
            inspect_object_store_capacity(ChangingStore(self.root))
        self.assertEqual(caught.exception.failure_code, "capacity_unavailable")

    def test_sdk_persist_error_event_rejects_plausible_stale_file_sizes(self):
        class SilentPersistFailure(MetadataStore):
            def get_file_path(self, key):
                self.error_raised.emit()
                return super().get_file_path(key)
        native = SilentPersistFailure(self.root)
        with self.assertRaises(StorageCapacityError) as caught:
            inspect_object_store_capacity(native)
        self.assertEqual(caught.exception.failure_code, "capacity_unavailable")
        self.assertEqual(native.error_raised.handlers, [])

    def test_sdk_without_safe_error_event_fails_closed(self):
        native = MetadataStore(self.root)
        del native.error_raised
        with self.assertRaises(StorageCapacityError) as caught:
            inspect_object_store_capacity(native)
        self.assertEqual(caught.exception.failure_code, "capacity_unavailable")

    def test_size_changes_between_passes_are_rejected(self):
        native = MetadataStore(self.root)
        actual_stat = __import__("os").stat
        count = 0
        def changing_stat(path, **kwargs):
            nonlocal count
            count += 1
            result = actual_stat(path, **kwargs)
            if count > 2:
                return SimpleNamespace(st_mode=result.st_mode, st_size=result.st_size + 1)
            return result
        with patch("qresearch.storage_capacity.os.stat", side_effect=changing_stat):
            with self.assertRaises(StorageCapacityError):
                inspect_object_store_capacity(native)

    def test_read_only_adapter_does_not_measure_or_reserve_another_copy(self):
        native = MetadataStore(self.root)
        adapter = ObjectStoreArtifactStore(native, "prefix")
        with self.assertRaises(PermissionError):
            adapter.preflight_capacity(1, 1)
        self.assertEqual(native.path_requests, [])
        self.assertEqual(native.save_calls, 0)

    def test_safe_error_mutation_cannot_widen_diagnostic_export(self):
        for error in (StorageCapacityError("capacity_unavailable"),
                      StorageOperationError("save_rejected"),
                      StorageVerificationError("verification_failed")):
            error.failure_code = SECRET
            error._allowed_codes = {SECRET}
            self.assertIsNone(error.safe_diagnostic())

    def test_pure_check_rejects_noncanonical_snapshot_without_sdk(self):
        snapshot = {"max_size_bytes": 100, "max_files": 10, "used_size_bytes": 30, "used_files": 2}
        for modified in (snapshot | {"extra": 0}, snapshot | {"used_size_bytes": True},
                         snapshot | {"max_files": -1}):
            with self.assertRaises(StorageCapacityError):
                check_capacity(modified, 1, 1)


class StorageOperationTests(unittest.TestCase):
    def adapter(self, native):
        return ObjectStoreArtifactStore(native, "synthetic", read_only=False, single_producer=True)

    def test_native_save_false_has_owned_backwards_compatible_error(self):
        native = SimpleNamespace(save_bytes=lambda key, value: False)
        with self.assertRaises(IOError) as caught:
            self.adapter(native)._save("a", b"synthetic")
        self.assertIs(type(caught.exception), StorageOperationError)
        self.assertEqual(caught.exception.safe_diagnostic(), {"schema_version": 1, "failure_code": "save_rejected"})

    def test_native_save_exception_text_is_suppressed(self):
        def fail(*args):
            raise RuntimeError(SECRET)
        native = SimpleNamespace(save_bytes=fail)
        with self.assertRaises(StorageOperationError) as caught:
            self.adapter(native)._save("a", b"synthetic")
        self.assertEqual(caught.exception.failure_code, "save_exception")
        self.assertNotIn(SECRET, str(caught.exception))
        self.assertTrue(caught.exception.__suppress_context__)

    def test_verification_conflict_is_owned_and_still_artifact_conflict(self):
        class Native:
            data = None
            def contains_key(self, key): return self.data is not None
            def save_bytes(self, key, data): self.data = b"other-synthetic"; return True
            def read_bytes(self, key): return self.data
        with self.assertRaises(ArtifactConflict) as caught:
            self.adapter(Native()).write_once("a", b"synthetic")
        self.assertIs(type(caught.exception), StorageVerificationError)
        self.assertEqual(caught.exception.failure_code, "verification_failed")

    def test_verification_native_error_is_sanitized(self):
        class Native:
            saved = False
            def contains_key(self, key): return self.saved
            def save_bytes(self, key, data): self.saved = True; return True
            def read_bytes(self, key): raise RuntimeError(SECRET)
        with self.assertRaises(StorageVerificationError) as caught:
            self.adapter(Native()).write_once("a", b"synthetic")
        self.assertEqual(caught.exception.failure_code, "verification_exception")
        self.assertNotIn(SECRET, str(caught.exception))


if __name__ == "__main__":
    unittest.main()
