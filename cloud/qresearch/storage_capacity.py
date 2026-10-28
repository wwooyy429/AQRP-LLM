"""Value-free Object Store capacity checks and owned storage errors.

The SDK documents max_size, max_files, keys and get_file_path. Only existing
keys are passed to get_file_path: that method can register a missing key. We
inspect file metadata with stat, never enumerate the store's payload iterator
or read any object bytes to measure usage. The SDK's get_file_path may flush
its existing dirty cache; its documented error event is observed without
reading event fields. An unavailable/inconsistent snapshot
fails closed. This is a point-in-time check under the caller's explicit single
producer assertion, not a distributed space reservation.
"""
import os
import stat

from .artifacts import ArtifactConflict


_CAPACITY_CODES = frozenset({"capacity_unavailable", "byte_capacity_insufficient",
                           "file_capacity_insufficient", "invalid_capacity_request"})
_OPERATION_CODES = frozenset({"save_rejected", "save_exception"})
_VERIFICATION_CODES = frozenset({"verification_failed", "verification_exception"})


class _SafeStorageError:
    _allowed_codes = frozenset()

    def __init__(self, failure_code):
        if type(failure_code) is not str or failure_code not in _codes(self):
            raise ValueError("Invalid owned storage failure code")
        self.failure_code = failure_code
        super().__init__("AQRP_STORAGE " + failure_code)

    def safe_diagnostic(self):
        # Revalidate the mutable exception attribute before it may leave cloud.
        code = self.failure_code
        if type(code) is not str or code not in _codes(self):
            return None
        return {"schema_version": 1, "failure_code": code}


class StorageCapacityError(_SafeStorageError, IOError):
    """The requested write envelope cannot be safely admitted."""
    _allowed_codes = _CAPACITY_CODES


class StorageOperationError(_SafeStorageError, IOError):
    """A native save failed; native messages and types are never echoed."""
    _allowed_codes = _OPERATION_CODES


class StorageVerificationError(_SafeStorageError, ArtifactConflict):
    """A save could not be verified through the existing immutable interface."""
    _allowed_codes = _VERIFICATION_CODES


def _codes(error):
    # Instance attributes and attacker subclasses cannot widen the export set.
    if type(error) is StorageCapacityError:
        return _CAPACITY_CODES
    if type(error) is StorageOperationError:
        return _OPERATION_CODES
    if type(error) is StorageVerificationError:
        return _VERIFICATION_CODES
    return frozenset()


def _nonnegative_int(value):
    return type(value) is int and value >= 0


def capacity_request(required_bytes, required_files, *, reserve_bytes=0,
                     reserve_files=0):
    """Validate an explicit, finite envelope without consulting the SDK."""
    values = {"required_bytes": required_bytes, "required_files": required_files,
              "reserve_bytes": reserve_bytes, "reserve_files": reserve_files}
    if any(not _nonnegative_int(value) for value in values.values()):
        raise StorageCapacityError("invalid_capacity_request")
    return values


def check_capacity(snapshot, required_bytes, required_files, *, reserve_bytes=0,
                   reserve_files=0):
    """Pure decision from an exact metadata snapshot and an explicit envelope."""
    request = capacity_request(required_bytes, required_files,
                               reserve_bytes=reserve_bytes, reserve_files=reserve_files)
    fields = {"max_size_bytes", "max_files", "used_size_bytes", "used_files"}
    if (type(snapshot) is not dict or set(snapshot) != fields
            or any(not _nonnegative_int(snapshot[name]) for name in fields)):
        raise StorageCapacityError("capacity_unavailable")
    remaining_bytes = (snapshot["max_size_bytes"] - snapshot["used_size_bytes"]
                       - required_bytes - reserve_bytes)
    remaining_files = snapshot["max_files"] - snapshot["used_files"] - required_files - reserve_files
    if remaining_bytes < 0:
        raise StorageCapacityError("byte_capacity_insufficient")
    if remaining_files < 0:
        raise StorageCapacityError("file_capacity_insufficient")
    return {"schema_version": 1, "status": "sufficient", **snapshot, **request,
            "remaining_bytes_after_reservation": remaining_bytes,
            "remaining_files_after_reservation": remaining_files,
            "usage_method": "keys_file_stat"}


def _keys(object_store, max_files):
    # Do not use iter(object_store): its entries contain object byte arrays.
    keys = set()
    for key in object_store.keys:
        if type(key) is not str or not key or "\x00" in key or key in keys:
            raise StorageCapacityError("capacity_unavailable")
        keys.add(key)
        if len(keys) > max_files:
            raise StorageCapacityError("file_capacity_insufficient")
    return keys


def _sizes(object_store, keys):
    sizes = {}
    for key in keys:
        # get_file_path can create a nonexistent key, hence these two checks.
        if object_store.contains_key(key) is not True:
            raise StorageCapacityError("capacity_unavailable")
        path = object_store.get_file_path(key)
        if type(path) is not str or not path or "\x00" in path:
            raise StorageCapacityError("capacity_unavailable")
        metadata = os.stat(path, follow_symlinks=False)
        if (not stat.S_ISREG(metadata.st_mode)
                or not _nonnegative_int(metadata.st_size)
                or object_store.contains_key(key) is not True):
            raise StorageCapacityError("capacity_unavailable")
        sizes[key] = metadata.st_size
    return sizes


def _metadata_snapshot(object_store):
    maximum = object_store.max_size
    max_files = object_store.max_files
    if not _nonnegative_int(maximum) or not _nonnegative_int(max_files):
        raise StorageCapacityError("capacity_unavailable")
    keys = _keys(object_store, max_files)
    sizes = _sizes(object_store, keys)
    if _keys(object_store, max_files) != keys or _sizes(object_store, keys) != sizes:
        raise StorageCapacityError("capacity_unavailable")
    current_maximum, current_max_files = object_store.max_size, object_store.max_files
    if (not _nonnegative_int(current_maximum) or not _nonnegative_int(current_max_files)
            or current_maximum != maximum or current_max_files != max_files):
        raise StorageCapacityError("capacity_unavailable")
    return {"max_size_bytes": maximum, "max_files": max_files,
            "used_size_bytes": sum(sizes.values()), "used_files": len(keys)}


def inspect_object_store_capacity(object_store):
    """Obtain complete stable usage from documented SDK metadata only.

    Two key/size passes reject observable concurrent changes and unmaterialized
    objects. SDK implementations without safe complete metadata are unsupported
    for writing; callers can continue to consume a completed cache read-only.
    get_file_path may flush existing dirty cache internally. The documented
    error_raised event must be available: a failed silent SDK persist cannot
    turn stale disk sizes into an accepted usage snapshot. This function makes
    no explicit save/delete/clear call and reads no error-event fields. No
    paths, keys, payloads, native exception text or native type names leave it.
    """
    try:
        observed_error = [False]
        def on_error(sender, arguments):
            observed_error[0] = True
        object_store.error_raised += on_error
        try:
            snapshot = _metadata_snapshot(object_store)
        finally:
            object_store.error_raised -= on_error
        if observed_error[0]:
            raise StorageCapacityError("capacity_unavailable")
        return snapshot
    except StorageCapacityError:
        raise
    except Exception:
        raise StorageCapacityError("capacity_unavailable") from None


def preflight_object_store(object_store, required_bytes, required_files, *,
                           reserve_bytes=0, reserve_files=0):
    """Fail before source fetch or writes if the explicit envelope cannot fit."""
    capacity_request(required_bytes, required_files,
                     reserve_bytes=reserve_bytes, reserve_files=reserve_files)
    snapshot = inspect_object_store_capacity(object_store)
    return check_capacity(snapshot, required_bytes, required_files,
                          reserve_bytes=reserve_bytes, reserve_files=reserve_files)
