"""Bounded observations of one rejected declared worker source.

These functions do not read files, execute source, strip imports, approve a
deployment or attest an earlier worker. The caller supplies the same source
bytes that caused its strict frozen-hash rejection. Only hashes, counts and
fixed classifications may leave the worker.
"""
import ast
from hashlib import sha256
import html
import json
import re

from .artifacts import canonical_json, validate_key


MAX_AST_SOURCE_BYTES = 262144
MAX_WORKER_DIAGNOSTIC_BYTES = 2048
_HASH = re.compile(r"[0-9a-f]{64}")
_FORMAT_KEYS = {"raw_sha256", "byte_count", "utf8_bom", "crlf_count",
    "standalone_cr_count", "lf_count", "normalized_trailing_lf_count",
    "syntax_status", "algorithm_import_count", "algorithm_from_import_count",
    "algorithm_star_import_count", "future_import_count"}
_AST_KEYS = {"algorithm_import_count", "algorithm_from_import_count",
             "algorithm_star_import_count", "future_import_count"}
_CONTEXT_KEYS = {"root_selection", "source_root_sha256", "verifier_path_sha256",
    "source_path_sha256", "verifier_within_source_root", "inspected_source_is_verifier"}
_SOURCE_FAILURE_MESSAGES = {
    "source_hash_mismatch": "Cloud implementation differs from the frozen deployment",
    "source_unreadable": "Implementation source is unavailable",
    "source_decode_error": "Implementation source is not UTF-8",
}
_MESSAGE_MARKER = re.compile("(" + "|".join(re.escape(value) for value in _SOURCE_FAILURE_MESSAGES.values())
                             + r"); diagnostics=")


def path_fingerprint(value):
    if not isinstance(value, str) or not value:
        raise ValueError("Worker path fingerprint requires a nonempty path token") from None
    return sha256(value.encode("utf-8", errors="surrogatepass")).hexdigest()


def source_format_observation(raw):
    """Describe raw bytes without returning their source or changing identity."""
    if type(raw) is not bytes:
        raise ValueError("Worker source observation requires bytes") from None
    result = {"raw_sha256": sha256(raw).hexdigest(), "byte_count": len(raw),
        "utf8_bom": raw.startswith(b"\xef\xbb\xbf"), "crlf_count": raw.count(b"\r\n"),
        "standalone_cr_count": raw.count(b"\r") - raw.count(b"\r\n"),
        "lf_count": raw.count(b"\n"), "normalized_trailing_lf_count": None,
        "syntax_status": "invalid_utf8", **{name: None for name in _AST_KEYS}}
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeError:
        return result
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    result["normalized_trailing_lf_count"] = len(normalized) - len(normalized.rstrip("\n"))
    if len(raw) > MAX_AST_SOURCE_BYTES:
        result["syntax_status"] = "not_inspected_size_limit"
        return result
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError, RecursionError):
        result["syntax_status"] = "invalid_syntax"
        return result
    counts = {name: 0 for name in _AST_KEYS}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            counts["algorithm_import_count"] += sum(alias.name == "AlgorithmImports" for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            counts["algorithm_from_import_count"] += node.module == "AlgorithmImports"
            counts["algorithm_star_import_count"] += node.module == "AlgorithmImports" and any(
                alias.name == "*" for alias in node.names)
            counts["future_import_count"] += node.module == "__future__"
    result.update(counts, syntax_status="parsed")
    return result


def controlled_source_observation(*, root_context, read_status, raw=None):
    """Build a whitelist-only observation; never an approval or root-cause claim."""
    document = {"schema_version": 1, "kind": "controlled_worker_source_observation",
        "coverage_scope": "first_rejected_declared_source", "root_context": root_context,
        "read_status": read_status, "source_format": None if raw is None else source_format_observation(raw),
        "unlisted_worker_paths_scanned": False, "strict_identity_relaxed": False,
        "old_worker_root_cause_proven": False}
    validate_source_observation(document)
    return document


def validate_source_observation(document):
    """Validate safe diagnostic data, not its provenance or deployment validity."""
    keys = {"schema_version", "kind", "coverage_scope", "root_context", "read_status", "source_format",
            "unlisted_worker_paths_scanned", "strict_identity_relaxed", "old_worker_root_cause_proven"}
    if (not isinstance(document, dict) or set(document) != keys
            or type(document["schema_version"]) is not int or document["schema_version"] != 1
            or document["kind"] != "controlled_worker_source_observation"
            or document["coverage_scope"] != "first_rejected_declared_source"
            or not isinstance(document["read_status"], str)
            or document["read_status"] not in {"read", "missing", "permission_denied", "unreadable"}
            or any(document[name] is not False for name in
                   ("unlisted_worker_paths_scanned", "strict_identity_relaxed", "old_worker_root_cause_proven"))):
        raise ValueError("Invalid bounded worker observation") from None
    context = document["root_context"]
    if (not isinstance(context, dict) or set(context) != _CONTEXT_KEYS
            or not isinstance(context["root_selection"], str)
            or context["root_selection"] not in {"explicit", "verifier_module_parent"}):
        raise ValueError("Invalid worker root observation") from None
    for name in ("source_root_sha256", "source_path_sha256"):
        if not isinstance(context[name], str) or _HASH.fullmatch(context[name]) is None:
            raise ValueError("Invalid worker path fingerprint") from None
    verifier = context["verifier_path_sha256"]
    if verifier is None:
        if any(context[name] is not None for name in ("verifier_within_source_root", "inspected_source_is_verifier")):
            raise ValueError("Unavailable verifier path has no known relation") from None
    elif (not isinstance(verifier, str) or _HASH.fullmatch(verifier) is None
            or any(type(context[name]) is not bool for name in
                   ("verifier_within_source_root", "inspected_source_is_verifier"))):
        raise ValueError("Invalid verifier path observation") from None
    details = document["source_format"]
    if document["read_status"] != "read":
        if details is not None:
            raise ValueError("Unread source cannot carry format observations") from None
        return
    if (not isinstance(details, dict) or set(details) != _FORMAT_KEYS
            or not isinstance(details["raw_sha256"], str) or _HASH.fullmatch(details["raw_sha256"]) is None
            or type(details["utf8_bom"]) is not bool or not isinstance(details["syntax_status"], str)
            or details["syntax_status"] not in {"parsed", "invalid_utf8", "invalid_syntax", "not_inspected_size_limit"}):
        raise ValueError("Invalid source format observation") from None
    for name in ("byte_count", "crlf_count", "standalone_cr_count", "lf_count"):
        if type(details[name]) is not int or not 0 <= details[name] <= 2**63 - 1:
            raise ValueError("Source format counts must be bounded integers") from None
    trailing = details["normalized_trailing_lf_count"]
    if details["syntax_status"] == "invalid_utf8":
        if trailing is not None:
            raise ValueError("Invalid UTF-8 has no decoded EOF count") from None
    elif type(trailing) is not int or not 0 <= trailing <= details["byte_count"]:
        raise ValueError("Invalid source EOF observation") from None
    for name in _AST_KEYS:
        count = details[name]
        if details["syntax_status"] == "parsed":
            if type(count) is not int or not 0 <= count <= details["byte_count"]:
                raise ValueError("Invalid source import count") from None
        elif count is not None:
            raise ValueError("Unparsed source has no AST observations") from None


def _diagnostic_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate worker diagnostic JSON field") from None
        result[key] = value
    return result


def _invalid_constant(_):
    raise ValueError("Non-finite worker diagnostic JSON value") from None


def _validate_controlled_diagnostic(document, prefix):
    common = {"schema_version", "failure_kind", "expected_sha256", "worker_observation"}
    if (not isinstance(document, dict) or type(document.get("schema_version")) is not int
            or document["schema_version"] != 2 or not isinstance(document.get("failure_kind"), str)
            or document["failure_kind"] not in _SOURCE_FAILURE_MESSAGES):
        raise ValueError("Missing supported controlled worker diagnostic") from None
    kind = document["failure_kind"]
    if prefix != _SOURCE_FAILURE_MESSAGES[kind]:
        raise ValueError("Worker diagnostic prefix disagrees with its classification") from None
    path_keys = set(document) & {"path", "path_sha256"}
    expected_keys = common | path_keys | ({"observed_sha256"} if kind == "source_hash_mismatch" else set())
    if len(path_keys) != 1 or set(document) != expected_keys:
        raise ValueError("Unknown or missing controlled worker diagnostic fields") from None
    if "path" in document:
        name = document["path"]
        if (not isinstance(name, str) or len(name) > 160 or not name.endswith(".py")
                or name == "_engineering_task_input.py" or re.fullmatch(r"[A-Za-z0-9_./-]+", name) is None):
            raise ValueError("Unsafe controlled worker diagnostic path") from None
        try:
            validate_key(name)
        except ValueError:
            raise ValueError("Unsafe controlled worker diagnostic path") from None
    for name in ("expected_sha256", "path_sha256", "observed_sha256"):
        if name in document and (not isinstance(document[name], str) or _HASH.fullmatch(document[name]) is None):
            raise ValueError("Invalid controlled worker source digest") from None
    if kind == "source_hash_mismatch" and document["expected_sha256"] == document["observed_sha256"]:
        raise ValueError("Equal source digests cannot prove a mismatch") from None
    worker = document["worker_observation"]
    validate_source_observation(worker)
    read = worker["read_status"] == "read"
    if ((kind == "source_unreadable" and read) or (kind != "source_unreadable" and not read)
            or (kind == "source_decode_error" and worker["source_format"]["syntax_status"] != "invalid_utf8")
            or (kind == "source_hash_mismatch" and worker["source_format"]["syntax_status"] == "invalid_utf8")):
        raise ValueError("Worker read observation disagrees with its failure") from None
    encoded = canonical_json(document)
    if len(prefix.encode("ascii")) + len(b"; diagnostics=") + len(encoded) > MAX_WORKER_DIAGNOSTIC_BYTES:
        raise ValueError("Controlled worker diagnostic exceeds its bound") from None
    return encoded


def extract_worker_diagnostics(messages):
    """Extract exact schema2 diagnostics after native identity validation.

    This parser itself does not authenticate a platform, project or attempt.
    The caller must first validate the native receipt and original binding.
    Direct text and one HTML-entity encoding pass are supported; arbitrary
    escaping, malformed/legacy diagnostics and conflicting observations fail
    closed. No matching marker returns None. Source/traceback text is never
    included in the returned report and no earlier worker is certified.
    """
    if (not isinstance(messages, list) or len(messages) > 16
            or any(not isinstance(value, str) for value in messages)):
        raise ValueError("Worker diagnostic input must be bounded native error strings") from None
    sizes = [len(value.encode("utf-8", errors="surrogatepass")) for value in messages]
    if any(size > 32768 for size in sizes) or sum(sizes) > 131072:
        raise ValueError("Worker diagnostic input exceeds its observation bound") from None
    decoder = json.JSONDecoder(object_pairs_hook=_diagnostic_pairs, parse_constant=_invalid_constant)
    observed, occurrences = None, 0
    for raw in messages:
        text = html.unescape(raw)
        for marker in _MESSAGE_MARKER.finditer(text):
            offset = marker.end()
            while offset < len(text) and text[offset] in " \t\r\n":
                offset += 1
            try:
                document, _ = decoder.raw_decode(text, offset)
                encoded = _validate_controlled_diagnostic(document, marker.group(1))
            except (ValueError, TypeError, RecursionError, UnicodeError):
                raise ValueError("Invalid controlled worker diagnostic representation") from None
            if observed is not None and observed != encoded:
                raise ValueError("Conflicting controlled worker diagnostics") from None
            observed, occurrences = encoded, occurrences + 1
            if occurrences > 64:
                raise ValueError("Too many repeated worker diagnostic observations") from None
    if observed is None:
        return None
    input_hash = sha256(json.dumps(messages, ensure_ascii=True, separators=(",", ":")).encode("ascii")).hexdigest()
    return {"schema_version": 1, "kind": "parsed_controlled_worker_diagnostics",
        "diagnostic": json.loads(observed), "matching_occurrence_count": occurrences,
        "input_messages_sha256": input_hash, "upstream_identity_validation_required": True,
        "remote_provenance_verified": False, "old_worker_root_cause_proven": False,
        "financial_evidence": False}
