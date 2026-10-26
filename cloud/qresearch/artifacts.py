"""Immutable metadata artifacts and corruption-detecting event streams.

FilesystemArtifactStore is deliberately restricted to configuration, metadata,
and synthetic engineering fixtures. Do not put QuantConnect market or financial
data in this local store. A cloud data adapter must use its approved cloud store.

Keys are relative POSIX paths. Writes use deterministic destinations, exclusive
cross-process locks, and atomic publication. Interrupted locks fail closed; they
are never guessed to be abandoned. Event hashes detect corruption, but are not
an externally anchored or tamper-proof audit trail.
"""

from contextlib import contextmanager
import errno
from hashlib import sha256
import json
import math
import os
import stat
from pathlib import Path, PurePosixPath, PureWindowsPath
import threading
import time
from typing import Any, Iterator, Mapping
from uuid import uuid4


_WINDOWS_LOCK_ACCESS_RETRY = os.name == "nt"


class ArtifactError(RuntimeError):
    """Base error for artifact persistence."""


class ArtifactConflict(ArtifactError):
    """An immutable key already contains different bytes."""


class CorruptEventStream(ArtifactError):
    """An event stream is truncated, malformed, or has an invalid hash chain."""


class StoreBusy(ArtifactError):
    """An exclusive lock could not be acquired without guessing its owner state."""


def _validate_json(value: Any) -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        # json.dumps with allow_nan=False rejects non-finite floats below.
        return
    if isinstance(value, list):
        for item in value:
            _validate_json(item)
        return
    if isinstance(value, dict) and all(isinstance(key, str) for key in value):
        for item in value.values():
            _validate_json(item)
        return
    raise TypeError("Canonical JSON permits only JSON values and string object keys")


def canonical_json(value: Any) -> bytes:
    """Stable UTF-8 JSON; non-finite values and implicit object conversions fail."""
    _validate_json(value)
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                      separators=(",", ":")).encode("utf-8")


def content_hash(value: Any) -> str:
    """Hash the full canonical configuration, including all semantic settings."""
    return sha256(canonical_json(value)).hexdigest()


def validate_key(key: str) -> str:
    """Reject traversal, absolute paths, drive names, and ambiguous separators."""
    if (not isinstance(key, str) or not key or "\\" in key or
            any(character in key for character in ':<>"|?*') or
            any(ord(character) < 32 for character in key)):
        raise ValueError("Artifact keys must be nonempty relative POSIX paths")
    if PurePosixPath(key).is_absolute() or PureWindowsPath(key).is_absolute():
        raise ValueError("Absolute artifact keys are prohibited")
    if any(part in ("", ".", "..") for part in key.split("/")):
        raise ValueError("Artifact keys may not contain empty, dot, or parent components")
    # NTFS trims these characters and has reserved device aliases.
    for part in key.split("/"):
        base = part.split(".", 1)[0].upper()
        if part.endswith((".", " ")) or base in {"CON", "PRN", "AUX", "NUL"} or (
                len(base) == 4 and base[:3] in {"COM", "LPT"} and base[3] in "123456789"):
            raise ValueError("Artifact key contains a Windows-reserved component")
    return key


def decode_events(data: bytes) -> list[dict]:
    """Verify every complete record. A torn tail is an error, never discarded."""
    if not data:
        return []
    if not data.endswith(b"\n"):
        raise CorruptEventStream("Event stream has an incomplete final record")
    previous = None
    verified = []
    for sequence, line in enumerate(data.splitlines(), 1):
        try:
            envelope = json.loads(line.decode("utf-8"))
            if set(envelope) != {"sequence", "previous_hash", "event", "hash"}:
                raise ValueError("Unexpected envelope fields")
            if type(envelope["sequence"]) is not int or envelope["sequence"] != sequence:
                raise ValueError("Invalid sequence")
            if envelope["previous_hash"] != previous or not isinstance(envelope["event"], dict):
                raise ValueError("Invalid predecessor or event")
            unsigned = {key: value for key, value in envelope.items() if key != "hash"}
            expected = sha256(canonical_json(unsigned)).hexdigest()
            if envelope["hash"] != expected:
                raise ValueError("Invalid record hash")
        except (ValueError, TypeError, UnicodeDecodeError) as exc:
            raise CorruptEventStream("Invalid event record {}: {}".format(sequence, exc)) from exc
        verified.append(envelope)
        previous = expected
    return verified


def _envelope(previous: list[dict], event: Mapping[str, Any]) -> dict:
    unsigned = {"sequence": len(previous) + 1,
                "previous_hash": previous[-1]["hash"] if previous else None,
                "event": dict(event)}
    return dict(unsigned, hash=sha256(canonical_json(unsigned)).hexdigest())


class MemoryArtifactStore:
    """Thread-safe in-memory metadata store with the same immutable interface."""

    def __init__(self) -> None:
        self._data: dict[str, bytes] = {}
        self._mutex = threading.RLock()
        self._locks: dict[str, threading.RLock] = {}

    def read_bytes(self, key: str) -> bytes:
        with self._mutex:
            try:
                return self._data[validate_key(key)]
            except KeyError as exc:
                raise FileNotFoundError(key) from exc

    def exists(self, key: str) -> bool:
        with self._mutex:
            return validate_key(key) in self._data

    def write_once(self, key: str, data: bytes) -> bool:
        key = validate_key(key)
        if not isinstance(data, bytes):
            raise TypeError("Artifact payload must be bytes")
        with self._mutex:
            if key in self._data:
                if self._data[key] != data:
                    raise ArtifactConflict("Immutable artifact differs: " + key)
                return False
            self._data[key] = data
            return True

    @contextmanager
    def locked(self, key: str) -> Iterator[None]:
        key = validate_key(key)
        with self._mutex:
            lock = self._locks.setdefault(key, threading.RLock())
        with lock:
            yield

    def append_event(self, stream: str, event: Mapping[str, Any]) -> dict:
        stream = validate_key(stream)
        with self.locked("event-locks/" + sha256(stream.encode()).hexdigest()):
            previous = decode_events(self.read_bytes(stream)) if self.exists(stream) else []
            envelope = _envelope(previous, event)
            with self._mutex:
                self._data[stream] = self._data.get(stream, b"") + canonical_json(envelope) + b"\n"
            return envelope


class FilesystemArtifactStore:
    """Local metadata store; cooperating threads and processes share O_EXCL locks.

    There is one immutable destination per key, and one append-only file per
    event stream. Staging names are deterministic and removed after normal
    completion. A process crash can leave a lock/staging file requiring explicit
    owner reconciliation. Automatically removing such a lock could duplicate an
    external submission, so this implementation never does that.
    """

    def __init__(self, root: str | Path, *, data_classification: str = "metadata",
                 lock_timeout: float = 10.0) -> None:
        if data_classification not in {"metadata", "config", "synthetic"}:
            raise ValueError("Local stores permit only metadata, config, or synthetic fixtures")
        if not math.isfinite(lock_timeout) or lock_timeout < 0:
            raise ValueError("lock_timeout must be finite and nonnegative")
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock_timeout = lock_timeout
        self.data_classification = data_classification

    def _path(self, key: str) -> Path:
        validate_key(key)
        target = self.root.joinpath(*key.split("/"))

        def comparable(path: Path) -> str:
            value = str(path)
            if os.name == "nt":
                if value.startswith("\\\\?\\UNC\\"):
                    value = "\\\\" + value[8:]
                elif value.startswith("\\\\?\\"):
                    value = value[4:]
            return os.path.normcase(value)

        # self.root was resolved once at construction. Keep that boundary
        # pinned; resolving it again could follow a subsequently replaced root.
        root_path = comparable(self.root)

        def require_inside(path: Path) -> None:
            try:
                inside = os.path.commonpath((root_path, comparable(path))) == root_path
            except ValueError as exc:
                raise ValueError("Artifact path escapes store root") from exc
            if not inside:
                raise ValueError("Artifact path escapes store root")

        # Resolve stable directories, not an ordinary leaf being deleted by
        # another cooperating writer. On NTFS that leaf can temporarily resolve
        # to $Extend/$Deleted despite having no link or escaping ancestor.
        # Existing symlink/reparse leaves must still resolve inside the root.
        require_inside(target.parent.resolve())
        try:
            metadata = target.lstat()
        except FileNotFoundError:
            metadata = None
        if metadata is not None and (
                stat.S_ISLNK(metadata.st_mode)
                or getattr(metadata, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)):
            require_inside(target.resolve())
        return target

    def read_bytes(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    @contextmanager
    def locked(self, key: str) -> Iterator[None]:
        validate_key(key)
        lock_key = ".locks/" + sha256(key.encode("utf-8")).hexdigest() + ".lock"
        lock_path = self._path(lock_key)
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        token = uuid4().hex
        payload = canonical_json({"owner_token": token, "process_id": os.getpid(), "key": key})
        deadline = time.monotonic() + self.lock_timeout
        while True:
            try:
                descriptor = os.open(str(lock_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                break
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise StoreBusy("Lock remains occupied; reconcile its owner before retry: " + key)
                time.sleep(min(0.01, max(0.0, deadline - time.monotonic())))
            except PermissionError as exc:
                # Windows' CRT can map a briefly delete-pending lock to EACCES
                # without retaining winerror. Retry only this Windows case;
                # persistent access denial keeps its original error and cause.
                if (not _WINDOWS_LOCK_ACCESS_RETRY or exc.errno != errno.EACCES
                        or time.monotonic() >= deadline):
                    raise
                time.sleep(min(0.01, max(0.0, deadline - time.monotonic())))
        try:
            with os.fdopen(descriptor, "wb") as output:
                output.write(payload)
                output.flush()
                os.fsync(output.fileno())
            yield
        finally:
            # Never unlink a lock whose ownership changed unexpectedly.
            if lock_path.exists():
                if lock_path.read_bytes() != payload:
                    raise ArtifactConflict("Lock ownership changed: " + key)
                lock_path.unlink()

    def write_once(self, key: str, data: bytes) -> bool:
        key = validate_key(key)
        if not isinstance(data, bytes):
            raise TypeError("Artifact payload must be bytes")
        with self.locked("artifact-writes/" + sha256(key.encode()).hexdigest()):
            destination = self._path(key)
            if destination.exists():
                if destination.read_bytes() != data:
                    raise ArtifactConflict("Immutable artifact differs: " + key)
                return False
            destination.parent.mkdir(parents=True, exist_ok=True)
            staging = self._path(".staging/" + sha256(key.encode()).hexdigest() + ".tmp")
            staging.parent.mkdir(parents=True, exist_ok=True)
            created = False
            try:
                with staging.open("xb") as output:
                    created = True
                    output.write(data)
                    output.flush()
                    os.fsync(output.fileno())
                os.replace(str(staging), str(destination))
                self._sync_directory(destination.parent)
            finally:
                if created and staging.exists():
                    staging.unlink()
            return True

    @staticmethod
    def _sync_directory(directory: Path) -> None:
        # Windows does not expose POSIX directory fsync through os.open.
        if os.name == "nt":
            return
        descriptor = os.open(str(directory), os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def append_event(self, stream: str, event: Mapping[str, Any]) -> dict:
        stream = validate_key(stream)
        with self.locked("event-locks/" + sha256(stream.encode()).hexdigest()):
            path = self._path(stream)
            previous = decode_events(path.read_bytes()) if path.exists() else []
            envelope = _envelope(previous, event)
            encoded = canonical_json(envelope) + b"\n"
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("ab") as output:
                output.write(encoded)
                output.flush()
                os.fsync(output.fileno())
            self._sync_directory(path.parent)
            return envelope
