"""Versioned deployment source identity; no source execution or provider I/O.

Legacy identities preserve every decoded EOF newline. Version 2 explicitly
binds both that original identity and a narrowly canonical terminal-LF identity.
Project preflight remains exact; only an admitted v2 worker may differ in the
bounded number of terminal LF characters. Body bytes are never normalized away.
"""
import ast
import codecs
from hashlib import sha256
from io import BytesIO
import re
import tokenize
import warnings

from .artifacts import validate_key


SOURCE_IDENTITY_POLICY = "utf8_sig_universal_newlines_terminal_lf_v1"
MAX_TERMINAL_LFS = 64
MAX_SOURCE_BYTES = 2 * 1024 * 1024
MAX_SOURCE_FILES = 512
MAX_SOURCE_PATH_BYTES = 1024
_HASH = re.compile(r"[0-9a-f]{64}")
_RECORD_FIELDS = {"source_sha256", "canonical_sha256", "terminal_lf_count"}
_MANIFEST_FIELDS = {"schema_version", "source_identity_policy", "files"}
_GENERATED = {"_engineering_task_input.py", "_collection_task_input.py"}
_ERRORS = {
    "invalid_source_type": "Deployment source must be bytes",
    "invalid_utf8": "Deployment source must contain valid UTF-8",
    "source_too_large": "Deployment source exceeds the declared byte bound",
    "terminal_lf_bound": "Deployment source exceeds the terminal LF bound",
    "invalid_python": "Deployment source is not valid supported Python",
    "unsafe_normalization": "Terminal LF normalization changes source syntax",
    "invalid_manifest": "Deployment source manifest has an invalid closed schema",
    "invalid_path": "Deployment source path is not a permitted managed Python path",
    "invalid_record": "Deployment source record has an invalid closed schema",
    "canonical_mismatch": "Canonical deployment source differs from its frozen record",
    "source_record_mismatch": "Frozen source record cannot be reconstructed from observed source",
    "source_mismatch": "Project source differs from its frozen original identity",
    "invalid_selection": "Source identity selection must be boolean",
}


class SourceIdentityError(ValueError):
    """A closed reason and static message; never expose source/error contents."""

    def __init__(self, reason):
        if type(reason) is not str or reason not in _ERRORS:
            raise ValueError("Unknown deployment source identity reason") from None
        self.reason = reason
        super().__init__(_ERRORS[reason])


def _fail(reason):
    raise SourceIdentityError(reason) from None


def normalize_source_bytes(raw):
    """Existing UTF8-sig/universal-newline bytes; preserve EOF exactly.

    This legacy helper deliberately adds no syntax, size or terminal-LF limits.
    Version-2 constraints are enforced only by canonical_source_bytes.
    """
    if type(raw) is not bytes:
        _fail("invalid_source_type")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeError:
        _fail("invalid_utf8")
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def source_sha256(raw):
    return sha256(normalize_source_bytes(raw)).hexdigest()


def _syntax_signature(source):
    try:
        # Compilation validates syntax (including future-import placement), but
        # never executes the produced code object. Suppress warnings whose
        # native text could interpolate a source literal.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            compile(source, "<deployment-source>", "exec", dont_inherit=True)
            tree = ast.parse(source, filename="<deployment-source>", mode="exec")
            return ast.dump(tree, annotate_fields=True, include_attributes=False)
    except (SyntaxError, ValueError, TypeError, RecursionError, MemoryError, OverflowError):
        _fail("invalid_python")


def _require_utf8_encoding(raw):
    # Source is explicitly UTF-8. A different coding cookie can change the AST
    # of the same UTF-8 bytes, even though compiling already-decoded str would
    # ignore that cookie. Also retain raw-byte compilation below so removing a
    # BOM cannot repair an inconsistent original cookie silently.
    try:
        encoding, _ = tokenize.detect_encoding(BytesIO(raw).readline)
        supported = codecs.lookup(encoding).name in {"utf-8", "utf-8-sig"}
    except (SyntaxError, LookupError, UnicodeError):
        _fail("invalid_python")
    if not supported:
        _fail("invalid_python")


def canonical_source_bytes(raw):
    """Explicit v2 identity: normalize only a bounded terminal LF run.

    Interior bytes, spaces, tabs, comments, imports and string contents remain
    in the digest. Both forms must be valid Python with the same AST. In
    particular, a terminal explicit line continuation cannot be made valid or
    change meaning merely by dropping its extra physical newline.
    """
    if type(raw) is not bytes:
        _fail("invalid_source_type")
    if len(raw) > MAX_SOURCE_BYTES:
        _fail("source_too_large")
    normalized = normalize_source_bytes(raw)
    count = len(normalized) - len(normalized.rstrip(b"\n"))
    if count > MAX_TERMINAL_LFS:
        _fail("terminal_lf_bound")
    canonical = normalized.rstrip(b"\n") + b"\n"
    _require_utf8_encoding(raw)
    original_signature = _syntax_signature(raw)
    if _syntax_signature(normalized) != original_signature:
        _fail("unsafe_normalization")
    try:
        canonical_signature = _syntax_signature(canonical)
    except SourceIdentityError:
        _fail("unsafe_normalization")
    if canonical_signature != original_signature:
        _fail("unsafe_normalization")
    return canonical


def source_record(raw):
    """Pin original bytes and the explicit v2 canonical identity together."""
    canonical = canonical_source_bytes(raw)
    normalized = normalize_source_bytes(raw)
    return {"source_sha256": sha256(normalized).hexdigest(),
            "canonical_sha256": sha256(canonical).hexdigest(),
            "terminal_lf_count": len(normalized) - len(normalized.rstrip(b"\n"))}


def _path(name, *, version):
    # Preserve legacy's generated-input exclusion. The new protocol additionally
    # excludes the collection input rather than changing historical contracts.
    generated = {"_engineering_task_input.py"} if version == 1 else _GENERATED
    if (type(name) is not str or not name.endswith(".py") or name in generated
            or any(ord(character) == 127 for character in name)):
        _fail("invalid_path")
    try:
        validate_key(name)
        encoded = name.encode("utf-8")
    except (TypeError, ValueError, UnicodeError):
        _fail("invalid_path")
    if version == 2 and (len(encoded) > MAX_SOURCE_PATH_BYTES
            or name.rsplit("/", 1)[-1].casefold() in _GENERATED):
        _fail("invalid_path")
    return name


def _validate_v2_file_set(files):
    if len(files) > MAX_SOURCE_FILES:
        _fail("invalid_manifest")
    aliases = {name.casefold() for name in files}
    if len(aliases) != len(files):
        _fail("invalid_path")
    # An ancestor cannot itself be a source file, including after casefold.
    for name in aliases:
        parts = name.split("/")
        if any("/".join(parts[:index]) in aliases for index in range(1, len(parts))):
            _fail("invalid_path")


def _record(value):
    if type(value) is not dict or set(value) != _RECORD_FIELDS:
        _fail("invalid_record")
    for key in ("source_sha256", "canonical_sha256"):
        if type(value[key]) is not str or _HASH.fullmatch(value[key]) is None:
            _fail("invalid_record")
    if (type(value["terminal_lf_count"]) is not int
            or not 0 <= value["terminal_lf_count"] <= MAX_TERMINAL_LFS):
        _fail("invalid_record")
    return {name: value[name] for name in ("source_sha256", "canonical_sha256", "terminal_lf_count")}


def parse_manifest(manifest):
    """Return ``(version, copied records)`` without source reads or downgrade.

    Legacy: ``{path: digest}``; v2: the exact schema-version/policy/files envelope.
    A malformed claimed v2 envelope is never reinterpreted as legacy.
    """
    if type(manifest) is not dict or not manifest:
        _fail("invalid_manifest")
    if "schema_version" in manifest or "source_identity_policy" in manifest or "files" in manifest:
        if (set(manifest) != _MANIFEST_FIELDS
                or type(manifest["schema_version"]) is not int or manifest["schema_version"] != 2
                or type(manifest["source_identity_policy"]) is not str
                or manifest["source_identity_policy"] != SOURCE_IDENTITY_POLICY
                or type(manifest["files"]) is not dict or not manifest["files"]):
            _fail("invalid_manifest")
        if len(manifest["files"]) > MAX_SOURCE_FILES:
            _fail("invalid_manifest")
        files = {}
        for name, value in manifest["files"].items():
            files[_path(name, version=2)] = _record(value)
        _validate_v2_file_set(files)
        return 2, files
    files = {}
    for name, digest in manifest.items():
        _path(name, version=1)
        if type(digest) is not str or _HASH.fullmatch(digest) is None:
            _fail("invalid_manifest")
        files[name] = {"source_sha256": digest}
    return 1, files


def build_manifest(sources):
    """Build v2 solely from explicitly named managed source bytes."""
    if type(sources) is not dict or not sources or len(sources) > MAX_SOURCE_FILES:
        _fail("invalid_manifest")
    for name in sources:
        _path(name, version=2)
    _validate_v2_file_set(sources)
    files = {}
    for name, raw in sources.items():
        files[_path(name, version=2)] = source_record(raw)
    result = {"schema_version": 2, "source_identity_policy": SOURCE_IDENTITY_POLICY,
              "files": {name: files[name] for name in sorted(files)}}
    parse_manifest(result)
    return result


def validate_record_against_source(raw, record, require_source_bytes=False):
    """Verify observed bytes against an admitted v2 record.

    Canonical equality is insufficient alone: rebuild the originally pinned
    source digest using the observed body and *declared* LF count. A strict
    project preflight also compares the actually observed original identity.
    Return the reconstructed record, suitable for a complete observed manifest
    hash; do not falsely call its LF count the worker's actual LF count.
    """
    if type(require_source_bytes) is not bool:
        _fail("invalid_selection")
    frozen = _record(record)
    observed = source_record(raw)
    if observed["canonical_sha256"] != frozen["canonical_sha256"]:
        _fail("canonical_mismatch")
    canonical = canonical_source_bytes(raw)
    reconstructed = canonical[:-1] + b"\n" * frozen["terminal_lf_count"]
    reconstructed_digest = sha256(reconstructed).hexdigest()
    if reconstructed_digest != frozen["source_sha256"]:
        _fail("source_record_mismatch")
    # Validate the pinned zero-LF form as well. An admitted original may not
    # require a terminal continuation that its stated EOF count cannot support.
    if canonical_source_bytes(reconstructed) != canonical:
        _fail("source_record_mismatch")
    if require_source_bytes and (observed["source_sha256"] != frozen["source_sha256"]
            or observed["terminal_lf_count"] != frozen["terminal_lf_count"]):
        _fail("source_mismatch")
    return {"source_sha256": reconstructed_digest,
            "canonical_sha256": observed["canonical_sha256"],
            "terminal_lf_count": frozen["terminal_lf_count"]}
