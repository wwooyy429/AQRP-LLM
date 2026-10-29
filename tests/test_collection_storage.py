"""Synthetic stable-cache provenance and value-free failure boundaries."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cloud"))
from qresearch.artifacts import ArtifactConflict, MemoryArtifactStore, canonical_json, content_hash
from qresearch.collection import (CollectionError, CollectionIntegrityError, CollectionInterrupted,
    CollectionMiss, HistoricalCollectionPlan, HistoricalSnapshotCollector,
    InternalCollectionDiagnosticError, safe_collection_diagnostic)
from qresearch.collection_storage import (StableCollectionCache, data_identity,
    processing_contract_sha256, stable_collection_plan, validate_storage_policy)
from qresearch.storage_capacity import StorageCapacityError, StorageOperationError, StorageVerificationError


CATALOG = {
    "dollar_volume": {"kind": "number", "role": "liquidity", "unit": "USD", "period_accessor": None},
    "has_fundamental_data": {"kind": "boolean", "role": "coverage", "unit": "boolean", "period_accessor": None},
}


def make_plan(*, catalog=None, **changes):
    raw = dict(schema_version=2, plan_id="synthetic-legacy", scope="engineering",
        source="quantconnect_fundamental_universe", data_version="synthetic-v1",
        start="2018-01-01T00:00:00-05:00", end_exclusive="2018-01-03T00:00:00-05:00",
        timezone="America/New_York", fields=list(CATALOG), calendar_days_per_request=1,
        max_batch_records=1, max_records_per_window=10, source_manifest_hash="a" * 64,
        observation_policy="retain_source_occurrences") | changes
    return HistoricalCollectionPlan.from_dict(raw, field_catalog=catalog or CATALOG)


class Source:
    def __init__(self): self.calls = 0
    def fetch(self, start, end, catalog):
        self.calls += 1
        yield {"sid": "SYNTHETIC", "snapshot_at": start.isoformat(), "source_record_index": 0,
               "values": {"dollar_volume": 1.5, "has_fundamental_data": True}}


class ForbiddenSource:
    def __init__(self): self.calls = 0
    def fetch(self, *_):
        self.calls += 1
        raise AssertionError("A cache-only read must not fetch")


def fixture():
    store = MemoryArtifactStore(); legacy = make_plan(); source = Source()
    first = HistoricalSnapshotCollector(store, source, legacy, synthetic=True).collect()
    second = HistoricalSnapshotCollector(store, None, legacy, synthetic=True).collect()
    identity = {"attempt_id": "a" * 32, "config_id": "b" * 64, "data_request_hash": "c" * 64,
                "deployment_hash": "d" * 64, "plan_hash": "e" * 64, "project_id": 1,
                "source_manifest_hash": "a" * 64, "stage": "research"}
    key = "engineering/synthetic/collection-probes/" + identity["plan_hash"] + "/" + identity["attempt_id"] + ".json"
    receipt = {"identity": identity, "collection_plan_hash": legacy.hash, "first": first, "cache_only_replay": second}
    encoded = canonical_json(receipt); store.write_once(key, encoded)
    processing = processing_contract_sha256()
    requested = make_plan(plan_id="another-label", source_manifest_hash="f" * 64)
    policy = {"schema_version": 1, "mode": "reuse_verified_legacy_only", "processing_contract_sha256": processing,
              "legacy": {"plan_identity": legacy.identity(), "plan_hash": legacy.hash,
                         "source_manifest_hash": "a" * 64, "processing_contract_sha256": processing,
                         "receipt_ref": {"key": key, "sha256": sha256(encoded).hexdigest()},
                         "receipt_identity": deepcopy(identity)}}
    return store, legacy, requested, policy, receipt


def replace_receipt(store, policy, receipt):
    encoded = canonical_json(receipt)
    key = policy["legacy"]["receipt_ref"]["key"]
    store._data[key] = encoded
    policy["legacy"]["receipt_ref"]["sha256"] = sha256(encoded).hexdigest()


class StableCacheTests(unittest.TestCase):
    def test_verified_legacy_reuse_writes_nothing_and_preserves_source_refs(self):
        store, legacy, requested, policy, receipt = fixture()
        before = deepcopy(store._data); source = ForbiddenSource()
        result, evidence = StableCollectionCache(store, requested, policy, synthetic=True).collect(source)
        self.assertEqual(source.calls, 0)
        self.assertEqual(store._data, before)
        self.assertEqual(result["plan_hash"], requested.hash)
        self.assertEqual(result["window_refs"], receipt["first"]["window_refs"])
        self.assertEqual(result["provider_calls"], 0)
        self.assertEqual(result["record_count"], 2)
        self.assertEqual(evidence["storage_plan_hash"], legacy.hash)
        self.assertEqual(evidence["origin_receipt_ref"], policy["legacy"]["receipt_ref"])
        self.assertFalse(evidence["new_row_objects"])
        self.assertFalse(evidence["actual_availability_certified"])
        self.assertNotIn("SYNTHETIC", json.dumps(evidence))

    def test_only_incidental_labels_and_full_deployment_hash_are_excluded(self):
        _, legacy, requested, policy, _ = fixture()
        processing = policy["processing_contract_sha256"]
        self.assertNotEqual(legacy.hash, requested.hash)
        self.assertEqual(data_identity(legacy, processing), data_identity(requested, processing))
        self.assertEqual(stable_collection_plan(legacy, processing).hash,
                         stable_collection_plan(requested, processing).hash)
        for changes in ({"data_version": "other-vintage"}, {"max_batch_records": 2},
                        {"max_records_per_window": 11}, {"calendar_days_per_request": 2},
                        {"end_exclusive": "2018-01-04T00:00:00-05:00"}):
            with self.subTest(changes=changes):
                changed = make_plan(**changes)
                self.assertNotEqual(data_identity(changed, processing), data_identity(legacy, processing))
                with self.assertRaises(CollectionError):
                    validate_storage_policy(policy, changed)

    def test_catalog_definition_or_processing_change_cannot_reuse_legacy(self):
        _, _, requested, policy, _ = fixture()
        catalog = deepcopy(CATALOG); catalog["dollar_volume"]["unit"] = "shares"
        with self.assertRaises(CollectionError):
            validate_storage_policy(policy, make_plan(catalog=catalog))
        policy["processing_contract_sha256"] = "1" * 64
        policy["legacy"]["processing_contract_sha256"] = "1" * 64
        with self.assertRaises(CollectionError):
            validate_storage_policy(policy, requested)

    def test_unknown_or_incomplete_policy_and_foreign_identity_rejected(self):
        _, _, requested, base, _ = fixture()
        for edit in (lambda p: p.update(extra=True), lambda p: p.update(schema_version=True),
                     lambda p: p.update(mode="refresh_missing"), lambda p: p.update(legacy=None),
                     lambda p: p["legacy"].update(plan_hash="0" * 64),
                     lambda p: p["legacy"].update(source_manifest_hash="0" * 64),
                     lambda p: p["legacy"]["receipt_identity"].update(stage="lean"),
                     lambda p: p["legacy"]["receipt_identity"].update(project_id=True),
                     lambda p: p["legacy"]["receipt_ref"].update(key="../receipt.json")):
            value = deepcopy(base); edit(value)
            with self.subTest(value=value), self.assertRaises(CollectionError):
                validate_storage_policy(value, requested)

    def test_pinned_legacy_receipt_hash_is_verified_before_reuse(self):
        store, _, requested, policy, _ = fixture()
        policy["legacy"]["receipt_ref"]["sha256"] = "0" * 64
        with self.assertRaises(CollectionIntegrityError):
            StableCollectionCache(store, requested, policy, synthetic=True).collect()

    def test_receipt_counts_identity_and_cache_replay_must_match_actual_original_rows(self):
        for mutate in (lambda r: r["first"].update(record_count=3),
                       lambda r: r["first"].update(provider_calls=True),
                       lambda r: r["first"]["missing_values"].update(dollar_volume=False),
                       lambda r: r["first"].update(reused_windows=1),
                       lambda r: r["cache_only_replay"].update(provider_calls=1),
                       lambda r: r["cache_only_replay"].update(provider_calls=False),
                       lambda r: r["identity"].update(project_id=True),
                       lambda r: r["identity"].update(config_id="0" * 64),
                       lambda r: r.update(extra="SYNTHETIC")):
            store, _, requested, policy, receipt = fixture(); mutate(receipt)
            replace_receipt(store, policy, receipt)
            with self.subTest(mutate=mutate), self.assertRaises(CollectionIntegrityError):
                StableCollectionCache(store, requested, policy, synthetic=True).collect()

    def test_corrupt_payload_or_missing_manifest_never_falls_through_to_source(self):
        for mode in ("corrupt", "missing"):
            store, _, requested, policy, receipt = fixture(); source = ForbiddenSource()
            reference = receipt["first"]["window_refs"][0]
            if mode == "missing":
                del store._data[reference["key"]]
            else:
                manifest = json.loads(store.read_bytes(reference["key"]))
                store._data[manifest["batches"][0]["key"]] = b"{}"
            before = deepcopy(store._data)
            with self.assertRaises((CollectionIntegrityError, CollectionInterrupted)):
                StableCollectionCache(store, requested, policy, synthetic=True).collect(source)
            self.assertEqual(source.calls, 0)
            self.assertEqual(store._data, before)

    def test_new_canonical_cache_survives_future_plan_renames_without_rewrites(self):
        plan = make_plan(); processing = processing_contract_sha256()
        policy = {"schema_version": 1, "mode": "stable_prefetch", "processing_contract_sha256": processing, "legacy": None}
        store = MemoryArtifactStore(); source = Source(); preflight = []
        first, evidence = StableCollectionCache(store, plan, policy, synthetic=True).collect(
            source, before_fetch=lambda p, s, e: preflight.append((p.hash, s, e)))
        self.assertEqual(source.calls, 2)
        self.assertEqual(len(preflight), 2)
        self.assertTrue(evidence["new_row_objects"])
        before = deepcopy(store._data)
        renamed = make_plan(plan_id="future-plan", source_manifest_hash="f" * 64)
        forbidden = ForbiddenSource()
        second, evidence2 = StableCollectionCache(store, renamed, policy, synthetic=True).collect(forbidden)
        self.assertEqual(forbidden.calls, 0)
        self.assertEqual(store._data, before)
        self.assertEqual(first["window_refs"], second["window_refs"])
        self.assertEqual(second["plan_hash"], renamed.hash)
        self.assertEqual(evidence2["mode"], "stable_cache")
        self.assertEqual(evidence["data_identity_hash"], evidence2["data_identity_hash"])

    def test_missing_cache_requires_explicit_preflight_before_any_fetch_or_write(self):
        store = MemoryArtifactStore(); source = Source(); processing = processing_contract_sha256()
        policy = {"schema_version": 1, "mode": "stable_prefetch", "processing_contract_sha256": processing, "legacy": None}
        cache = StableCollectionCache(store, make_plan(), policy, synthetic=True)
        with self.assertRaises(CollectionMiss): cache.collect()
        with self.assertRaises(CollectionError): cache.collect(source)
        self.assertEqual(source.calls, 0)
        self.assertEqual(store._data, {})
        def insufficient(*_): raise StorageCapacityError("byte_capacity_insufficient")
        with self.assertRaises(InternalCollectionDiagnosticError) as caught:
            cache.collect(source, before_fetch=insufficient)
        self.assertEqual(caught.exception.diagnostic["stage"], "capacity_preflight")
        self.assertEqual(caught.exception.diagnostic["failure_code"], "byte_capacity_insufficient")
        self.assertEqual(source.calls, 0)
        self.assertEqual(store._data, {})

    def test_real_residency_is_required_even_for_legacy_only_mode(self):
        store, _, requested, policy, _ = fixture()
        with self.assertRaises(CollectionError): StableCollectionCache(store, requested, policy)


class ProcessingFingerprintTests(unittest.TestCase):
    def source_map(self):
        folder = Path(__file__).resolve().parents[1] / "cloud/qresearch"
        return {name: (folder / name).read_bytes() for name in
                ("historical_source.py", "collection.py", "artifacts.py", "contracts.py", "financial_fields.py")}

    def test_financial_helper_body_is_an_explicit_runtime_dependency(self):
        sources = self.source_map(); baseline = processing_contract_sha256(sources)
        self.assertEqual(processing_contract_sha256(), baseline)
        changed = dict(sources)
        changed["financial_fields.py"] = changed["financial_fields.py"].replace(
            b'presence("12M")', b'presence("3M")', 1)
        self.assertNotEqual(changed["financial_fields.py"], sources["financial_fields.py"])
        self.assertNotEqual(processing_contract_sha256(changed), baseline)
        missing = {name: raw for name, raw in sources.items() if name != "financial_fields.py"}
        with self.assertRaises(CollectionError):
            processing_contract_sha256(missing)

    def test_legacy_four_map_with_new_helper_import_or_reference_rejects(self):
        sources = self.source_map()
        legacy = {name: raw for name, raw in sources.items() if name != "financial_fields.py"}
        for adapter in (b'from .financial_fields import extract_financial_field\n',
                        b'import qresearch.financial_fields as fixed_financial\n',
                        b'from . import financial_fields\n',
                        b'def project(item):\n    return extract_financial_field(item)\n',
                        b'def project(item):\n    return fixed.financial_fields(item)\n',
                        b'module = __import__("qresearch.financial_fields")\n'):
            changed = dict(legacy); changed["historical_source.py"] = adapter
            with self.subTest(adapter=adapter), self.assertRaises(CollectionError):
                processing_contract_sha256(changed)

    def test_current_five_source_newlines_are_canonical_and_closed(self):
        sources = self.source_map(); baseline = processing_contract_sha256(sources)
        varied = {name: b'\xef\xbb\xbf' + raw.replace(b'\r\n', b'\n').rstrip(b'\n').replace(
            b'\n', b'\r\n') + b'\r\n\r\n' for name, raw in sources.items()}
        self.assertEqual(processing_contract_sha256(varied), baseline)
        with self.assertRaises(CollectionError):
            processing_contract_sha256(sources | {"another_dependency.py": b'pass\n'})
        with patch('qresearch.collection_storage.Path.read_bytes',side_effect=FileNotFoundError('SYNTHETIC_PRIVATE_PATH')):
            with self.assertRaises(CollectionError) as caught:
                processing_contract_sha256()
        self.assertNotIn('PRIVATE',str(caught.exception))

    def test_immutable_legacy_four_source_contract_preserves_known_hash(self):
        root = Path(__file__).resolve().parents[1]
        commit = "5e09e63d87a42a07a448e27da6aedbe4e8210a6f"
        names = ("historical_source.py", "collection.py", "artifacts.py", "contracts.py")
        sources = {name: subprocess.check_output(
            ["git", "cat-file", "blob", commit + ":cloud/qresearch/" + name], cwd=root)
            for name in names}
        legacy = processing_contract_sha256(sources)
        self.assertEqual(legacy,"5ef61ef75f80ee7de0abcfd5461896a427a20d4c621d10759855b4cd11468219")
        self.assertNotEqual(processing_contract_sha256(),legacy)

    def test_old_frozen_cache_contract_does_not_fetch_or_write_under_new_runtime(self):
        store, _, requested, policy, _ = fixture()
        old = "5ef61ef75f80ee7de0abcfd5461896a427a20d4c621d10759855b4cd11468219"
        source = ForbiddenSource(); before = deepcopy(store._data)
        for selected in (policy | {"processing_contract_sha256":old},
                         policy | {"legacy":policy["legacy"] | {"processing_contract_sha256":old}}):
            with self.assertRaises(CollectionError):
                StableCollectionCache(store,requested,selected,synthetic=True).collect(source)
            self.assertEqual(source.calls,0)
            self.assertEqual(store._data,before)

    def test_fingerprint_rejects_missing_sources_and_tracks_semantic_changes(self):
        sources = self.source_map(); baseline = processing_contract_sha256(sources)
        for name, before, after in (("collection.py", b"value = int(value)", b"value = int(value) + 1"),
                                     ("contracts.py", b"datetime(2024, 1, 1", b"datetime(2025, 1, 1"),
                                     ("artifacts.py", b"ensure_ascii=False", b"ensure_ascii=True"),
                                     ("historical_source.py", b"import math", b"import math\n# semantic adapter version")):
            changed = dict(sources); self.assertIn(before, changed[name]); changed[name] = changed[name].replace(before, after, 1)
            with self.subTest(name=name): self.assertNotEqual(processing_contract_sha256(changed), baseline)
        with self.assertRaises(CollectionError): processing_contract_sha256({})

    def test_line_endings_and_unrelated_diagnostics_do_not_invalidate_projection_cache(self):
        sources = self.source_map(); baseline = processing_contract_sha256(sources)
        crlf = {key: value.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n") for key, value in sources.items()}
        self.assertEqual(processing_contract_sha256(crlf), baseline)
        changed = dict(sources)
        changed["collection.py"] = changed["collection.py"] + b"\n# new audit-only diagnostic note\n"
        self.assertEqual(processing_contract_sha256(changed), baseline)

    def test_semantic_import_rebinding_invalidates_and_wrapper_transform_must_be_transparent(self):
        sources = self.source_map(); baseline = processing_contract_sha256(sources)
        changed = dict(sources)
        changed["collection.py"] = changed["collection.py"].replace(b"import math", b"import cmath as math", 1)
        self.assertNotEqual(processing_contract_sha256(changed), baseline)
        changed = dict(sources)
        changed["collection.py"] = changed["collection.py"].replace(b"return operation(*args)", b"return None", 1)
        with self.assertRaises(CollectionError): processing_contract_sha256(changed)


class InternalDiagnosticTests(unittest.TestCase):
    def test_owned_storage_failure_stages_and_codes_never_echo_native_values(self):
        for category, error, stage, code in (
                ("objects", StorageOperationError("save_rejected"), "batch_persist", "save_rejected"),
                ("objects", StorageVerificationError("verification_failed"), "batch_verify", "verification_failed"),
                ("windows", StorageOperationError("save_exception"), "manifest_persist", "save_exception"),
                ("objects", RuntimeError("LICENSED sid=SECRET value=999"), "batch_persist", "unexpected_exception")):
            class FailingStore(MemoryArtifactStore):
                def write_once(self, key, data):
                    if "/" + category + "/" in key: raise error
                    return super().write_once(key, data)
            store = FailingStore()
            with self.subTest(category=category, error=type(error)), self.assertRaises(InternalCollectionDiagnosticError) as caught:
                HistoricalSnapshotCollector(store, Source(), make_plan(), synthetic=True, internal_diagnostics=True).collect()
            diagnostic = caught.exception.diagnostic
            self.assertEqual(diagnostic["stage"], stage)
            self.assertEqual(diagnostic["failure_code"], code)
            self.assertNotIn("SECRET", str(caught.exception)); self.assertNotIn("999", str(caught.exception))
            self.assertEqual(set(diagnostic), {"schema_version", "stage", "failure_code", "exception_kind"})

    def test_default_legacy_error_remains_unchanged(self):
        class FailingStore(MemoryArtifactStore):
            def write_once(self, key, data):
                if "/objects/" in key: raise RuntimeError("SECRET")
                return super().write_once(key, data)
        with self.assertRaises(CollectionError) as caught:
            HistoricalSnapshotCollector(FailingStore(), Source(), make_plan(), synthetic=True).collect()
        self.assertEqual(str(caught.exception), "Historical source collection failed; unfinished intent retained")

    def test_mutated_or_unknown_diagnostic_fields_are_rejected(self):
        valid = {"schema_version": 1, "stage": "batch_persist", "failure_code": "save_rejected", "exception_kind": "io_error"}
        self.assertEqual(safe_collection_diagnostic(valid), valid)
        for raw in (valid | {"extra": "secret"}, valid | {"stage": "secret-key"},
                    valid | {"failure_code": "secret-value"}, valid | {"schema_version": True}):
            self.assertIsNone(safe_collection_diagnostic(raw))


if __name__ == "__main__":
    unittest.main()
