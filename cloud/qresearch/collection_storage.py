"""Explicit stable cache identity and verified legacy snapshot reuse.

This preparation layer never certifies point-in-time availability. It preserves
the source plan and receipt of reused records and never copies row payloads to
relabel them under a new research-plan identity. Default v1/v2 collection is not
changed by importing this opt-in module.
"""
import ast
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import re

from .artifacts import canonical_json, content_hash, validate_key
from .collection import (CollectionError, CollectionIntegrityError, CollectionInterrupted,
                         CollectionMiss, HistoricalCollectionPlan, HistoricalSnapshotCollector,
                         internal_collection_failure)


_HASH = re.compile(r"[0-9a-f]{64}")
_IDENTITY_FIELDS = {"attempt_id", "config_id", "data_request_hash", "deployment_hash", "plan_hash",
                    "project_id", "source_manifest_hash", "stage"}
_SOURCES = {"historical_source.py", "collection.py", "artifacts.py", "contracts.py"}
_SELECTORS = {
    "collection.py": {"_HASH", "_PATH", "_FIELDS", "_ROOT", "_OCCURRENCE_ROOT",
                      "_OBSERVATION_POLICY", "_OCCURRENCE_COUNTS", "_FLAGS",
                      "_text", "_time", "_catalog", "HistoricalCollectionPlan",
                      "HistoricalSnapshotCollector._identity", "HistoricalSnapshotCollector._window",
                      "HistoricalSnapshotCollector._key",
                      "HistoricalSnapshotCollector._row", "HistoricalSnapshotCollector._observe",
                      "HistoricalSnapshotCollector._projection_state", "HistoricalSnapshotCollector._counts",
                      "HistoricalSnapshotCollector._occurrence_metadata", "HistoricalSnapshotCollector._write_batch",
                      "HistoricalSnapshotCollector._document", "HistoricalSnapshotCollector._load_window",
                      "HistoricalSnapshotCollector.read_window", "HistoricalSnapshotCollector._source_rows"},
    "artifacts.py": {"_validate_json", "canonical_json", "content_hash"},
    "contracts.py": {"NY", "DEVELOPMENT_END", "aware"},
}
_SEMANTIC_IMPORTS = {
    "collection.py": {"Mapping", "dataclass", "date", "sha256", "json", "math", "Integral", "Real", "re",
                      "pd", "canonical_json", "content_hash", "DEVELOPMENT_END", "aware"},
    "artifacts.py": {"sha256", "json", "Any"},
    "contracts.py": {"datetime", "ZoneInfo", "pd"},
}
_WRAPPER = ast.parse('''def _internal_call(self, stage, operation, *args):
    try:
        return operation(*args)
    except CollectionError:
        raise
    except Exception as error:
        if self.internal_diagnostics:
            raise internal_collection_failure(stage, error) from None
        raise
''').body[0]


def _fail():
    raise CollectionError("Invalid explicit stable collection storage policy") from None


def _is_hash(value):
    return type(value) is str and _HASH.fullmatch(value) is not None


class _UnwrapDiagnostics(ast.NodeTransformer):
    """Only the owned diagnostic call wrapper is semantically transparent."""
    def visit_Call(self, node):
        node = self.generic_visit(node)
        if (isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "self" and node.func.attr == "_internal_call"
                and len(node.args) >= 2 and isinstance(node.args[0], ast.Constant)
                and type(node.args[0].value) is str and not node.keywords):
            return ast.Call(func=node.args[1], args=node.args[2:], keywords=[])
        return node


def _semantic_import_bindings(tree, names):
    """Bind actual imported dependencies and detect any top-level rebinding."""
    bindings = {name: [] for name in names}
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                label = alias.asname or (alias.name.split(".")[0] if isinstance(node, ast.Import) else alias.name)
                if label in names:
                    selected = deepcopy(node)
                    selected.names = [deepcopy(alias)]
                    bindings[label].append(ast.dump(selected, include_attributes=False))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name in names:
                bindings[node.name].append(ast.dump(node, include_attributes=False))
        else:
            assigned = {n.id for n in ast.walk(node) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
            for label in assigned & names:
                bindings[label].append(ast.dump(node, include_attributes=False))
    if any(not value for value in bindings.values()):
        _fail()
    return bindings


def processing_contract_sha256(sources=None):
    """Bind projection/time/serialization semantics independently of deployment.

The closed rule uses the complete historical adapter source and selected AST
definitions in its dependency closure. Incidental file/plan labels and logging
are excluded. The optional exact four-source map supports offline comparison
with an immutable older Git version; runtime always calls without overrides.
    """
    if sources is None:
        sources = {name: Path(__file__).with_name(name).read_bytes() for name in _SOURCES}
    if type(sources) is not dict or set(sources) != _SOURCES:
        _fail()
    normalized = {}
    for name, raw in sources.items():
        if not isinstance(raw, (str, bytes)):
            _fail()
        try:
            text = raw.decode("utf-8-sig") if isinstance(raw, bytes) else raw.removeprefix("\ufeff")
            normalized[name] = text.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n") + "\n"
        except (UnicodeError, ValueError):
            _fail()
    selected = {"historical_source.py": normalized["historical_source.py"]}
    for name, wanted in _SELECTORS.items():
        try:
            tree = ast.parse(normalized[name])
        except (SyntaxError, ValueError):
            _fail()
        found = {}
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in wanted:
                found[node.name] = node
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in wanted:
                        found[target.id] = node
            elif isinstance(node, ast.ClassDef):
                if node.name in wanted:
                    found[node.name] = node
                for method in node.body:
                    if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if node.name == "HistoricalSnapshotCollector" and method.name == "_internal_call":
                            if ast.dump(method, include_attributes=False) != ast.dump(_WRAPPER, include_attributes=False):
                                _fail()
                        label = node.name + "." + method.name
                        if label in wanted:
                            found[label] = method
        if set(found) != wanted:
            _fail()
        selected[name] = {
            "definitions": {label: ast.dump(_UnwrapDiagnostics().visit(deepcopy(node)), include_attributes=False)
                            for label, node in sorted(found.items())},
            "dependency_bindings": _semantic_import_bindings(tree, _SEMANTIC_IMPORTS[name])}
    return content_hash({"closed_processing_rule": "snapshot-projection-dependency-v1", "sources": selected})


def data_identity(plan, processing_hash):
    if not isinstance(plan, HistoricalCollectionPlan) or not _is_hash(processing_hash):
        _fail()
    raw = plan.to_dict()
    if raw["schema_version"] != 2:
        _fail()
    semantics = {key: value for key, value in raw.items() if key not in {"plan_id", "source_manifest_hash"}}
    return {"schema_version": 1, "processing_contract_sha256": processing_hash,
            "collection": semantics, "field_catalog": plan.field_catalog}


def stable_collection_plan(plan, processing_hash):
    semantic_hash = content_hash(data_identity(plan, processing_hash))
    raw = plan.to_dict() | {"plan_id": "data-cache-" + semantic_hash,
                          "source_manifest_hash": processing_hash}
    return HistoricalCollectionPlan.from_dict(raw, field_catalog=plan.field_catalog)


def _reference(raw):
    if type(raw) is not dict or set(raw) != {"key", "sha256"} or not _is_hash(raw["sha256"]):
        _fail()
    try:
        validate_key(raw["key"])
    except (TypeError, ValueError):
        _fail()
    if not raw["key"].endswith(".json"):
        _fail()
    return raw


def _receipt_identity(raw, legacy):
    if type(raw) is not dict or set(raw) != _IDENTITY_FIELDS:
        _fail()
    if (type(raw["attempt_id"]) is not str or re.fullmatch(r"[0-9a-f]{32}", raw["attempt_id"]) is None
            or type(raw["project_id"]) is not int or raw["project_id"] <= 0 or raw["stage"] != "research"
            or any(not _is_hash(raw[key]) for key in _IDENTITY_FIELDS - {"attempt_id", "project_id", "stage"})
            or raw["source_manifest_hash"] != legacy.to_dict()["source_manifest_hash"]):
        _fail()
    return raw


def validate_storage_policy(policy, requested_plan):
    """Pure validation; callers cannot approve arbitrary processing fingerprints."""
    if (type(policy) is not dict or set(policy) != {"schema_version", "mode", "processing_contract_sha256", "legacy"}
            or type(policy["schema_version"]) is not int or policy["schema_version"] != 1
            or type(policy["mode"]) is not str
            or policy["mode"] not in {"reuse_verified_legacy_only", "stable_prefetch"}
            or not _is_hash(policy["processing_contract_sha256"])):
        _fail()
    actual = processing_contract_sha256()
    if not _is_hash(actual) or actual != policy["processing_contract_sha256"]:
        _fail()
    data_identity(requested_plan, actual)
    old = policy["legacy"]
    if old is None:
        if policy["mode"] == "reuse_verified_legacy_only":
            _fail()
    else:
        if (type(old) is not dict or set(old) != {"plan_identity", "plan_hash", "source_manifest_hash",
                "processing_contract_sha256", "receipt_ref", "receipt_identity"}
                or type(old["plan_identity"]) is not dict
                or set(old["plan_identity"]) != {"plan", "field_catalog"}
                or not _is_hash(old["plan_hash"]) or not _is_hash(old["source_manifest_hash"])
                or old["processing_contract_sha256"] != actual):
            _fail()
        legacy = HistoricalCollectionPlan.from_dict(old["plan_identity"]["plan"],
                                                    field_catalog=old["plan_identity"]["field_catalog"])
        if (legacy.identity() != old["plan_identity"] or legacy.hash != old["plan_hash"]
                or legacy.to_dict()["source_manifest_hash"] != old["source_manifest_hash"]
                or data_identity(legacy, actual) != data_identity(requested_plan, actual)):
            _fail()
        reference = _reference(old["receipt_ref"])
        identity = _receipt_identity(old["receipt_identity"], legacy)
        suffix = "/collection-probes/" + identity["plan_hash"] + "/" + identity["attempt_id"] + ".json"
        if not reference["key"].endswith(suffix):
            _fail()
    try:
        return json.loads(canonical_json(policy))
    except (TypeError, ValueError):
        _fail()


class StableCollectionCache:
    """Verify and reuse completed rows without changing their provenance."""
    def __init__(self, store, requested_plan, policy, *, synthetic=False):
        if type(synthetic) is not bool:
            _fail()
        self.store, self.plan, self.synthetic = store, requested_plan, synthetic
        self.policy = validate_storage_policy(policy, requested_plan)
        self.processing_hash = self.policy["processing_contract_sha256"]
        self.data_hash = content_hash(data_identity(requested_plan, self.processing_hash))
        self.storage_plan = stable_collection_plan(requested_plan, self.processing_hash)
        # Enforce residency even when the request will be served from legacy.
        HistoricalSnapshotCollector(store, None, self.storage_plan, synthetic=synthetic)

    def _summary(self, observed, mode, storage_plan_hash, reference=None, *, new_row_objects=False):
        summary = deepcopy(observed)
        summary["plan_hash"] = self.plan.hash
        evidence = {"schema_version": 1, "mode": mode, "data_identity_hash": self.data_hash,
                    "requested_plan_hash": self.plan.hash, "storage_plan_hash": storage_plan_hash,
                    "origin_receipt_ref": deepcopy(reference),
                    "verified_window_count": observed["window_count"], "provider_calls": observed["provider_calls"],
                    "reused_windows": observed["reused_windows"], "new_row_objects": new_row_objects,
                    "full_historical_US200_certified": False, "actual_availability_certified": False}
        return summary, evidence

    def _legacy(self):
        old = self.policy["legacy"]
        if old is None:
            raise CollectionMiss("No verified completed stable collection cache is available")
        reference = old["receipt_ref"]
        try:
            encoded = self.store.read_bytes(reference["key"])
            if len(encoded) > 1048576:
                raise ValueError
            receipt = json.loads(encoded)
            if sha256(encoded).hexdigest() != reference["sha256"] or canonical_json(receipt) != encoded:
                raise ValueError
        except (FileNotFoundError, ValueError, TypeError, UnicodeError):
            raise CollectionIntegrityError("Pinned legacy collection receipt is missing or invalid") from None
        if (type(receipt) is not dict or set(receipt) != {"identity", "collection_plan_hash", "first", "cache_only_replay"}
                or canonical_json(receipt["identity"]) != canonical_json(old["receipt_identity"])
                or receipt["collection_plan_hash"] != old["plan_hash"]):
            raise CollectionIntegrityError("Pinned legacy receipt identity differs from the frozen policy")
        legacy = HistoricalCollectionPlan.from_dict(old["plan_identity"]["plan"],
                                                    field_catalog=old["plan_identity"]["field_catalog"])
        reader = HistoricalSnapshotCollector(self.store, None, legacy, synthetic=self.synthetic,
                                             internal_diagnostics=True)
        # This validates every completed window, content-addressed batch and row
        # against its ORIGINAL plan. A missing/unfinished window cannot fall
        # through to a source or be silently replaced.
        observed = reader.collect()
        first = receipt["first"]
        if (type(first) is not dict or set(first) != set(observed)
                or canonical_json(receipt["cache_only_replay"]) != canonical_json(observed)
                or canonical_json({name: value for name, value in first.items()
                                   if name not in {"provider_calls", "reused_windows"}})
                    != canonical_json({name: value for name, value in observed.items()
                                       if name not in {"provider_calls", "reused_windows"}})
                or type(first["provider_calls"]) is not int or type(first["reused_windows"]) is not int
                or first["provider_calls"] < 0 or first["reused_windows"] < 0
                or first["provider_calls"] + first["reused_windows"] != observed["window_count"]):
            raise CollectionIntegrityError("Pinned legacy counts or references differ from verified original rows")
        return self._summary(observed, "verified_legacy", legacy.hash, reference)

    def collect(self, source=None, *, before_fetch=None):
        if self.policy["mode"] == "reuse_verified_legacy_only":
            try:
                return self._legacy()
            except CollectionError:
                raise
            except Exception as error:
                raise internal_collection_failure("cache_read", error) from None
        reader = HistoricalSnapshotCollector(self.store, None, self.storage_plan, synthetic=self.synthetic,
                                             internal_diagnostics=True)
        try:
            windows = [reader._key(reader._window(*pair)) for pair in self.storage_plan.windows()]
            if all(self.store.exists(key) for key in windows):
                return self._summary(reader.collect(), "stable_cache", self.storage_plan.hash)
            # Full pinned legacy reuse precedes any new source request. An
            # explicit legacy policy must verify; failure does not refresh it.
            if self.policy["legacy"] is not None:
                return self._legacy()
            if source is None:
                return self._summary(reader.collect(), "stable_cache", self.storage_plan.hash)
            if not callable(before_fetch):
                raise CollectionError("Explicit storage capacity preflight is required before collection fetches")
            producer = HistoricalSnapshotCollector(self.store, source, self.storage_plan, synthetic=self.synthetic,
                                                   internal_diagnostics=True, before_fetch=before_fetch)
            observed = producer.collect()
            return self._summary(observed, "stable_prefetch", self.storage_plan.hash,
                                 new_row_objects=observed["provider_calls"] > 0)
        except CollectionError:
            raise
        except Exception as error:
            raise internal_collection_failure("cache_read", error) from None
