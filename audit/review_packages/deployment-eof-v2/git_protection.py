"""Raw Git-blob protection for the WR-28 audit repair, standard library only.

The old worktree-derived declarations are retained verbatim as provenance.
They are not redefined as normalized hashes. This separate manifest is derived
from fixed Git blobs and checks exported bytes without requiring a .git folder.
The manifest itself belongs to the independently pinned review source version;
it is an audit record, not a remote signature or worker-file observation.
"""
from hashlib import sha1, sha256
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import subprocess


POLICY = "sha256_and_git_sha1_blob_on_raw_bytes_v1"
BASELINE_COMMIT = "8d65c290773547c83549c098172f1eb8c3376cd7"
PATH_LIST = "audit/review_packages/deployment-eof-v2/protected_before.json"
PATH_LIST_SHA256 = "26308901ada1f73a1fa9064bc76d4a55ec9ed53b820ab1dc9bcd2f529ad28677"
PATH_LIST_BLOB = "2988aa67d03d862d4544abfad98145f355d2cccb"
FILE_COUNT = 122
SNAPSHOTS = {
    "baseline": {"commit": BASELINE_COMMIT, "tree": "884e1275aa938336624761880b82b13809653353"},
    "candidate": {"commit": "4a42c18f0b78bea2068d589bc12f1615712354c6", "tree": "2ae4560b47f469feacf49cc7171b23a7dc575266"},
    "materials": {"commit": "1cf26578da59eebd37e138ca5d6d076991386470", "tree": "aca57cf7928428ce8da0cd41e5edb47a53fe79fb"},
}
FIXTURE_PATH = "audit/review_packages/deployment-eof-v2/fixtures/engineering_smoke_662ccd.py"
FIXTURE_SHA256 = "33ffa365d6b54d0a823574eaba5831c2f53c6aae7f2dff2c885b1d7ac0c9ca90"
MAX_BYTES = 16 * 1024 * 1024
_HASH256 = re.compile(r"[0-9a-f]{64}")
_OID = re.compile(r"[0-9a-f]{40}")
_FIELDS = {"schema_version", "kind", "identity_policy", "protected_file_count",
           "path_list_source", "git_snapshots", "files"}
_FILE_FIELDS = {"sha256", "git_blob_oid", "byte_count", "legacy_declared_sha256"}


class ProtectionError(ValueError):
    """Static audit error; no source, file paths or native diagnostics escape."""


def _fail():
    raise ProtectionError("Git raw-byte protection check failed") from None


def _path(value):
    if (type(value) is not str or not value or "\\" in value
            or any(ord(c) < 32 or ord(c) == 127 or c in ':<>"|?*' for c in value)
            or PurePosixPath(value).is_absolute() or PureWindowsPath(value).is_absolute()
            or any(part in {"", ".", ".."} for part in value.split("/"))):
        _fail()
    for part in value.split("/"):
        base = part.split(".", 1)[0].upper()
        if (part.endswith((".", " ")) or base in {"CON", "PRN", "AUX", "NUL"}
                or (len(base) == 4 and base[:3] in {"COM", "LPT"} and base[3] in "123456789")):
            _fail()
    try:
        valid = len(value.encode("utf-8")) <= 4096
    except UnicodeError:
        valid = False
    if not valid:
        _fail()
    return value


def _digest(value, pattern):
    if type(value) is not str or pattern.fullmatch(value) is None:
        _fail()


def _pairs(items):
    result = {}
    for name, value in items:
        if name in result:
            _fail()
        result[name] = value
    return result


def _json(raw):
    if type(raw) is not bytes or len(raw) > MAX_BYTES:
        _fail()
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                           parse_constant=lambda value: _fail())
    except (ValueError, TypeError, UnicodeError, RecursionError):
        _fail()
    return value


def blob_oid(raw):
    if type(raw) is not bytes or len(raw) > MAX_BYTES:
        _fail()
    return sha1(b"blob " + str(len(raw)).encode("ascii") + b"\x00" + raw).hexdigest()


def protected_paths(raw):
    if type(raw) is not bytes or sha256(raw).hexdigest() != PATH_LIST_SHA256 or blob_oid(raw) != PATH_LIST_BLOB:
        _fail()
    value = _json(raw)
    if type(value) is not dict or len(value) != FILE_COUNT:
        _fail()
    for name, digest in value.items():
        _path(name)
        _digest(digest, _HASH256)
    if len({name.casefold() for name in value}) != len(value):
        _fail()
    return value


def _source():
    return {"path": PATH_LIST, "sha256": PATH_LIST_SHA256, "git_blob_oid": PATH_LIST_BLOB,
            "git_commit": SNAPSHOTS["materials"]["commit"],
            "legacy_hash_policy": "original_declarations_preserved_without_reinterpretation"}


def validate_manifest(value, protected_before_raw):
    declarations = protected_paths(protected_before_raw)
    if (type(value) is not dict or set(value) != _FIELDS
            or type(value["schema_version"]) is not int or value["schema_version"] != 1
            or value["kind"] != "immutable_git_raw_blob_protection"
            or value["identity_policy"] != POLICY
            or type(value["protected_file_count"]) is not int or value["protected_file_count"] != FILE_COUNT
            or type(value["path_list_source"]) is not dict or value["path_list_source"] != _source()
            or type(value["git_snapshots"]) is not dict or value["git_snapshots"] != SNAPSHOTS
            or type(value["files"]) is not dict or set(value["files"]) != set(declarations)):
        _fail()
    for name, item in value["files"].items():
        _path(name)
        if type(item) is not dict or set(item) != _FILE_FIELDS:
            _fail()
        _digest(item["sha256"], _HASH256)
        _digest(item["git_blob_oid"], _OID)
        if (type(item["byte_count"]) is not int or not 0 <= item["byte_count"] <= MAX_BYTES
                or type(item["legacy_declared_sha256"]) is not str
                or item["legacy_declared_sha256"] != declarations[name]):
            _fail()
    return value


def load_manifest(raw, protected_before_raw):
    return validate_manifest(_json(raw), protected_before_raw)


def verify_export(root, manifest, protected_before_raw):
    """Read actual exported bytes; no decode, newline conversion or Git needed."""
    validate_manifest(manifest, protected_before_raw)
    try:
        root = Path(root).resolve(strict=True)
    except (TypeError, ValueError, OSError, RuntimeError):
        _fail()
    mismatches = 0
    for name, item in sorted(manifest["files"].items()):
        try:
            path = root / name
            # Reject links rather than allowing protected paths to read outside
            # the export or alias another protected source through a link.
            cursor = root
            for component in name.split("/"):
                cursor = cursor / component
                if cursor.is_symlink():
                    _fail()
            if not path.resolve(strict=True).is_relative_to(root) or not path.is_file():
                _fail()
            raw = path.read_bytes()
        except (TypeError, ValueError, OSError, RuntimeError):
            _fail()
        if (len(raw) != item["byte_count"] or sha256(raw).hexdigest() != item["sha256"]
                or blob_oid(raw) != item["git_blob_oid"]):
            _fail()
        mismatches += item["legacy_declared_sha256"] != item["sha256"]
    return {"identity_policy": POLICY, "baseline_commit": BASELINE_COMMIT,
            "protected_git_blobs_verified": FILE_COUNT,
            "legacy_declarations_source_sha256": PATH_LIST_SHA256,
            "legacy_declared_vs_git_blob_mismatch_count": mismatches,
            "legacy_declarations_rewritten": False}


def read_replay_fixture(root):
    """Pinned version-controlled source for synthetic replay, never a worker read."""
    try:
        raw = (Path(root) / FIXTURE_PATH).read_bytes()
    except (TypeError, ValueError, OSError):
        _fail()
    if sha256(raw).hexdigest() != FIXTURE_SHA256:
        _fail()
    return raw


def _git(repository, *args, input_bytes=None):
    try:
        result = subprocess.run(["git", *args], cwd=repository, input=input_bytes,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    except (OSError, subprocess.SubprocessError, TypeError, ValueError):
        _fail()
    return result.stdout


def _tree_files(repository, snapshot):
    tree = _git(repository, "rev-parse", snapshot["commit"] + "^{tree}")
    if tree != snapshot["tree"].encode("ascii") + b"\n":
        _fail()
    raw = _git(repository, "ls-tree", "-r", "-z", "--full-tree", snapshot["commit"])
    files = {}
    try:
        for entry in raw.split(b"\x00"):
            if not entry:
                continue
            metadata, name = entry.split(b"\t", 1)
            mode, kind, oid = metadata.split(b" ")
            if kind != b"blob" or mode not in {b"100644", b"100755"}:
                continue
            name, oid = name.decode("utf-8"), oid.decode("ascii")
            _digest(oid, _OID)
            files[name] = oid
    except (ValueError, UnicodeError):
        _fail()
    return files


def _blobs(repository, oids):
    oids = sorted(set(oids))
    raw = _git(repository, "cat-file", "--batch", input_bytes="".join(oid + "\n" for oid in oids).encode("ascii"))
    cursor, result = 0, {}
    for oid in oids:
        end = raw.find(b"\n", cursor)
        if end == -1:
            _fail()
        try:
            observed, kind, size = raw[cursor:end].split(b" ")
            count = int(size)
        except (ValueError, TypeError):
            _fail()
        if (observed != oid.encode("ascii") or kind != b"blob" or not 0 <= count <= MAX_BYTES
                or str(count).encode("ascii") != size):
            _fail()
        start = end + 1
        body = raw[start:start + count]
        cursor = start + count + 1
        if len(body) != count or raw[cursor - 1:cursor] != b"\n" or blob_oid(body) != oid:
            _fail()
        result[oid] = body
    if cursor != len(raw):
        _fail()
    return result


def build_manifest(repository, protected_before_raw):
    """Build only from three fixed commit trees and their raw cat-file blobs."""
    declarations = protected_paths(protected_before_raw)
    try:
        repository = Path(repository).resolve(strict=True)
        actual_root = _git(repository, "rev-parse", "--show-toplevel").decode("utf-8").rstrip("\n")
        exact_root = Path(actual_root).resolve(strict=True) == repository
    except (TypeError, ValueError, OSError, UnicodeError, RuntimeError):
        _fail()
    if not exact_root:
        _fail()
    trees = {name: _tree_files(repository, snapshot) for name, snapshot in SNAPSHOTS.items()}
    materials_oid = trees["materials"].get(PATH_LIST)
    if materials_oid != PATH_LIST_BLOB:
        _fail()
    for path in declarations:
        oid = trees["baseline"].get(path)
        if oid is None or any(tree.get(path) != oid for tree in trees.values()):
            _fail()
    blobs = _blobs(repository, [trees["baseline"][path] for path in declarations] + [materials_oid])
    if blobs[materials_oid] != protected_before_raw:
        _fail()
    files = {}
    for path, legacy in sorted(declarations.items()):
        oid = trees["baseline"][path]
        raw = blobs[oid]
        files[path] = {"sha256": sha256(raw).hexdigest(), "git_blob_oid": oid,
                       "byte_count": len(raw), "legacy_declared_sha256": legacy}
    value = {"schema_version": 1, "kind": "immutable_git_raw_blob_protection", "identity_policy": POLICY,
             "protected_file_count": FILE_COUNT, "path_list_source": _source(),
             "git_snapshots": {name: dict(item) for name, item in SNAPSHOTS.items()}, "files": files}
    return validate_manifest(value, protected_before_raw)
