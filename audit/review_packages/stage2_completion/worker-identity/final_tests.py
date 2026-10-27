"""Synthetic controlled-worker diagnostics, without provider or budget calls."""
from copy import deepcopy
from hashlib import sha256
import html
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "cloud"), str(ROOT / "tests")]
from qresearch.artifacts import content_hash
from qresearch import engineering_data as data
from qresearch.worker_identity import (controlled_source_observation, source_format_observation,
    validate_source_observation, path_fingerprint, extract_worker_diagnostics,
    MAX_AST_SOURCE_BYTES, MAX_WORKER_DIAGNOSTIC_BYTES)
import test_engineering_data as legacy_fixture
import test_native_runtime_failure as native_fixture
import test_engineering_receipts as receipt_fixture
from qresearch import engineering_receipts


SOURCE = b"VALUE = 1\n"
SECRET = "PRIVATE_SOURCE_OR_OS_VALUE_431.25"


def context():
    return {"root_selection": "explicit", "source_root_sha256": "a" * 64,
        "source_path_sha256": "b" * 64, "verifier_path_sha256": "c" * 64,
        "verifier_within_source_root": False, "inspected_source_is_verifier": False}


class WorkerIdentityTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.path = self.root / "receiver.py"
        self.path.write_bytes(SOURCE)
        self.manifest = {"receiver.py": sha256(SOURCE).hexdigest()}

    def reject(self, *, enhanced=True):
        with self.assertRaises(data.DeploymentVerificationError) as caught:
            data.verify_deployment(self.manifest, content_hash(self.manifest),
                source_root=self.root, worker_diagnostics=enhanced)
        return caught.exception

    def test_format_counts_have_exact_known_answers_and_no_hash_normalization(self):
        raw = b"\xef\xbb\xbfVALUE = 1\r\n\r\n# comment\r\n\r"
        observed = source_format_observation(raw)
        self.assertEqual(observed["raw_sha256"], sha256(raw).hexdigest())
        self.assertEqual(observed["byte_count"], len(raw))
        self.assertIs(observed["utf8_bom"], True)
        self.assertEqual(observed["crlf_count"], 3)
        self.assertEqual(observed["standalone_cr_count"], 1)
        self.assertEqual(observed["lf_count"], 3)
        self.assertEqual(observed["normalized_trailing_lf_count"], 2)
        self.assertEqual(observed["syntax_status"], "parsed")
        self.assertNotEqual(observed["raw_sha256"], data.source_bytes_sha256(raw))

    def test_AST_counts_include_both_import_forms_and_future_without_source(self):
        raw = (b'"""docstring"""\nfrom __future__ import annotations\n'
               b'from AlgorithmImports import *\n'
               b'def function():\n    import AlgorithmImports as api\n'
               b'    from AlgorithmImports import QCAlgorithm\n'
               b'    from .AlgorithmImports import private\n')
        result = source_format_observation(raw)
        self.assertEqual((result["algorithm_import_count"], result["algorithm_from_import_count"],
            result["algorithm_star_import_count"], result["future_import_count"]), (1, 2, 1, 1))
        self.assertNotIn("QCAlgorithm", json.dumps(result))

    def test_source_is_never_executed(self):
        marker = self.root / "must-not-exist"
        raw = ("from pathlib import Path\nPath(" + repr(str(marker)) + ").write_text('executed')\n").encode()
        self.assertEqual(source_format_observation(raw)["syntax_status"], "parsed")
        self.assertFalse(marker.exists())

    def test_unparsed_and_oversize_source_return_no_AST_inferences(self):
        for raw, status in ((b"\xff" + SECRET.encode(), "invalid_utf8"),
                            (b"def " + SECRET.encode(), "invalid_syntax"),
                            (b"#" * (MAX_AST_SOURCE_BYTES + 1), "not_inspected_size_limit")):
            with self.subTest(status=status):
                result = source_format_observation(raw)
                self.assertEqual(result["syntax_status"], status)
                for key in ("algorithm_import_count", "algorithm_from_import_count",
                            "algorithm_star_import_count", "future_import_count"):
                    self.assertIsNone(result[key])
                self.assertNotIn(SECRET, json.dumps(result))
        for value in (None, SOURCE.decode(), bytearray(SOURCE), True):
            with self.subTest(type=type(value).__name__), self.assertRaises(ValueError):
                source_format_observation(value)

    def test_path_fingerprints_preserve_no_path_or_private_content(self):
        token = "C:/" + SECRET + "/模块\ud800.py"
        self.assertEqual(path_fingerprint(token), sha256(token.encode("utf-8", errors="surrogatepass")).hexdigest())
        self.assertNotIn(SECRET, path_fingerprint(token))
        for value in (None, "", 1, False):
            with self.subTest(value=value), self.assertRaises(ValueError):
                path_fingerprint(value)

    def test_default_error_schema_is_unchanged(self):
        self.path.write_bytes(b"VALUE = 2\n")
        error = self.reject(enhanced=False)
        self.assertEqual(error.diagnostics, {"schema_version": 1, "failure_kind": "source_hash_mismatch",
            "path": "receiver.py", "expected_sha256": sha256(SOURCE).hexdigest(),
            "observed_sha256": sha256(b"VALUE = 2\n").hexdigest()})

    def test_enhanced_diagnostics_use_same_single_source_read_and_do_not_scan(self):
        raw = b"from AlgorithmImports import *\nVALUE = 2\n# " + SECRET.encode() + b"\n\n"
        with patch.object(Path, "read_bytes", side_effect=[raw, b"DIFFERENT_SECOND_READ"]) as read, \
                patch.object(Path, "rglob", side_effect=AssertionError("Unlisted worker scan")):
            error = self.reject()
        self.assertEqual(read.call_count, 1)
        observed = error.diagnostics
        self.assertEqual(observed["schema_version"], 2)
        self.assertEqual(observed["observed_sha256"], data.source_bytes_sha256(raw))
        worker = observed["worker_observation"]
        self.assertEqual(worker["source_format"]["raw_sha256"], sha256(raw).hexdigest())
        self.assertEqual(worker["source_format"]["algorithm_star_import_count"], 1)
        self.assertEqual(worker["source_format"]["normalized_trailing_lf_count"], 2)
        self.assertIs(worker["strict_identity_relaxed"], False)
        self.assertIs(worker["old_worker_root_cause_proven"], False)
        self.assertIs(worker["unlisted_worker_paths_scanned"], False)
        self.assertEqual(worker["coverage_scope"], "first_rejected_declared_source")
        self.assertLessEqual(len(json.dumps(observed, separators=(",", ":"))), MAX_WORKER_DIAGNOSTIC_BYTES)
        self.assertLessEqual(len(str(error).encode("ascii")), MAX_WORKER_DIAGNOSTIC_BYTES)
        self.assertNotIn(SECRET, str(error))
        self.assertNotIn(str(self.root), str(error))
        self.assertNotIn(str(Path(data.__file__).resolve()), str(error))

    def test_enhanced_nested_diagnostics_are_defensive_copies(self):
        self.path.write_bytes(b"VALUE = 2\n")
        error = self.reject()
        copy = error.diagnostics
        copy["worker_observation"]["source_format"]["raw_sha256"] = SECRET
        self.assertNotIn(SECRET, str(error))
        self.assertNotIn(SECRET, json.dumps(error.diagnostics))

    def test_default_module_root_is_reported_without_revealing_its_path(self):
        fake_module = self.root / "qresearch" / "engineering_data.py"
        self.path.write_bytes(b"VALUE = 2\n")
        with patch.object(data, "__file__", str(fake_module)), self.assertRaises(data.DeploymentVerificationError) as caught:
            data.verify_deployment(self.manifest, content_hash(self.manifest), worker_diagnostics=True)
        root = caught.exception.diagnostics["worker_observation"]["root_context"]
        self.assertEqual(root["root_selection"], "verifier_module_parent")
        self.assertEqual(root["source_root_sha256"], path_fingerprint(str(self.root.resolve())))
        self.assertIs(root["verifier_within_source_root"], True)
        self.assertIs(root["inspected_source_is_verifier"], False)
        self.assertNotIn(str(fake_module), str(caught.exception))

    def test_unavailable_verifier_metadata_does_not_replace_frozen_hash_failure(self):
        self.path.write_bytes(b"VALUE = 2\n")
        with patch.object(data, "__file__", None):
            error = self.reject()
        self.assertEqual(error.diagnostics["failure_kind"], "source_hash_mismatch")
        root = error.diagnostics["worker_observation"]["root_context"]
        self.assertIsNone(root["verifier_path_sha256"])
        self.assertIsNone(root["verifier_within_source_root"])
        self.assertIsNone(root["inspected_source_is_verifier"])

    def test_loaded_verifier_source_relation_is_only_a_token_observation(self):
        self.path.write_bytes(b"VALUE = 2\n")
        with patch.object(data, "__file__", str(self.path)):
            error = self.reject()
        context = error.diagnostics["worker_observation"]["root_context"]
        self.assertIs(context["inspected_source_is_verifier"], True)
        self.assertIs(error.diagnostics["worker_observation"]["old_worker_root_cause_proven"], False)

    def test_new_diagnostic_text_remains_compatible_with_native_failure_metadata_only(self):
        self.path.write_bytes(b"from AlgorithmImports import *\nVALUE = 2\n")
        error = self.reject()
        tool = native_fixture.native_failure([native_fixture.MARKER, str(error)])
        payload, deployment = receipt_fixture.context("lean")
        result = engineering_receipts.backtest_runtime_failure(payload, deployment,
            native_fixture.EXTERNAL, tool)
        self.assertEqual(result["platform"]["status"], "runtime_error")
        self.assertEqual(result["platform"]["raw_receipt"]["response_sha256"], content_hash(tool["result"]))
        self.assertNotIn("worker_observation", json.dumps(result))
        self.assertNotIn("source_format", json.dumps(result))
        self.assertNotIn("orders_count", result["platform"]["raw_receipt"])

    def test_missing_permission_and_decode_errors_have_only_safe_classification(self):
        for failure, status in ((FileNotFoundError(SECRET), "missing"),
                                (PermissionError(SECRET), "permission_denied"),
                                (OSError(SECRET), "unreadable")):
            with self.subTest(status=status), patch.object(Path, "read_bytes", side_effect=failure):
                error = self.reject()
            self.assertEqual(error.diagnostics["worker_observation"]["read_status"], status)
            self.assertIsNone(error.diagnostics["worker_observation"]["source_format"])
            self.assertNotIn(SECRET, str(error))
        self.path.write_bytes(b"\xff" + SECRET.encode())
        error = self.reject()
        self.assertEqual(error.diagnostics["failure_kind"], "source_decode_error")
        self.assertEqual(error.diagnostics["worker_observation"]["source_format"]["syntax_status"], "invalid_utf8")
        self.assertNotIn("observed_sha256", error.diagnostics)

    def test_runtime_context_opts_in_for_both_stages_before_data_access(self):
        fixture = legacy_fixture.EngineeringDataTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        (fixture.root / "receiver.py").write_bytes(b"VALUE = 2\n")
        for stage in ("research", "lean"):
            payload = fixture.payload(stage)
            with self.subTest(stage=stage), self.assertRaises(data.DeploymentVerificationError) as caught:
                data._context(payload, stage, source_root=fixture.root)
            self.assertEqual(caught.exception.diagnostics["schema_version"], 2)
            self.assertIn("worker_observation", caught.exception.diagnostics)

    def test_invalid_manifest_paths_fail_before_enhanced_source_read(self):
        for name in ("../receiver.py", "CON.py", "bad\x7f.py", "_engineering_task_input.py"):
            manifest = {name: "a" * 64}
            with self.subTest(name=name), patch.object(Path, "read_bytes") as read, \
                    self.assertRaises(data.DeploymentVerificationError) as caught:
                data.verify_deployment(manifest, content_hash(manifest), source_root=self.root, worker_diagnostics=True)
            self.assertEqual(read.call_count, 0)
            self.assertEqual(caught.exception.diagnostics["schema_version"], 1)

    def test_strict_hash_and_original_BOM_newline_contract_remain_in_both_modes(self):
        for flag in (False, True):
            for raw in (SOURCE, b"\xef\xbb\xbf" + SOURCE, SOURCE.replace(b"\n", b"\r\n"), SOURCE.replace(b"\n", b"\r")):
                self.path.write_bytes(raw)
                self.assertEqual(data.verify_deployment(self.manifest, content_hash(self.manifest),
                    source_root=self.root, worker_diagnostics=flag), content_hash(self.manifest))
            for raw in (SOURCE[:-1], SOURCE + b"\n", b"from AlgorithmImports import *\n" + SOURCE):
                with self.subTest(flag=flag, raw=raw):
                    self.path.write_bytes(raw)
                    self.reject(enhanced=flag)
        with patch.object(Path, "read_bytes") as read, self.assertRaises(ValueError):
            data.verify_deployment(self.manifest, content_hash(self.manifest), source_root=self.root, worker_diagnostics=1)
        self.assertEqual(read.call_count, 0)

    def test_arbitrary_metadata_or_approval_fields_cannot_enter_diagnostic(self):
        original = controlled_source_observation(root_context=context(), read_status="read", raw=SOURCE)
        mutations = []
        for key in ("source", "absolute_path", "market_rows", "worker_source_verified"):
            changed = deepcopy(original); changed[key] = SECRET; mutations.append(changed)
        for key in ("strict_identity_relaxed", "old_worker_root_cause_proven", "unlisted_worker_paths_scanned"):
            changed = deepcopy(original); changed[key] = True; mutations.append(changed)
        changed = deepcopy(original); changed["root_context"]["source_root_sha256"] = SECRET; mutations.append(changed)
        changed = deepcopy(original); changed["source_format"]["byte_count"] = True; mutations.append(changed)
        for changed in mutations:
            with self.subTest(changed=list(changed)), self.assertRaises(ValueError) as caught:
                data.DeploymentVerificationError("source_hash_mismatch", worker_observation=changed)
            self.assertNotIn(SECRET, str(caught.exception))
        unavailable = context()
        unavailable.update(verifier_path_sha256=None, verifier_within_source_root=None, inspected_source_is_verifier=None)
        validate_source_observation(controlled_source_observation(root_context=unavailable, read_status="missing"))

    def diagnostic_message(self):
        self.path.write_bytes(b"from AlgorithmImports import *\nVALUE = 2\n")
        return str(self.reject())

    def test_extractor_supports_direct_one_HTML_layer_and_identical_repetition(self):
        message = self.diagnostic_message()
        raw = [native_fixture.MARKER, "During initialize: " + message + "\nTraceback: " + SECRET,
            html.escape(message, quote=True) + "\n" + message]
        result = extract_worker_diagnostics(raw)
        self.assertEqual(result["matching_occurrence_count"], 3)
        self.assertEqual(result["diagnostic"]["failure_kind"], "source_hash_mismatch")
        self.assertIs(result["upstream_identity_validation_required"], True)
        for name in ("remote_provenance_verified", "old_worker_root_cause_proven", "financial_evidence"):
            self.assertIs(result[name], False)
        self.assertEqual(result["input_messages_sha256"], sha256(json.dumps(raw,
            ensure_ascii=True, separators=(",", ":")).encode("ascii")).hexdigest())
        self.assertNotIn(SECRET, json.dumps(result))
        self.assertNotIn("Traceback", json.dumps(result))
        self.assertNotIn(str(self.root), json.dumps(result))

    def test_extractor_missing_marker_is_not_a_worker_observation(self):
        for raw in ([], [native_fixture.MARKER], ["Cloud implementation differs from the frozen deployment"],
                    ['unknown source failure; diagnostics={"schema_version":2}']):
            self.assertIsNone(extract_worker_diagnostics(raw))
        self.path.write_bytes(b"VALUE = 2\n")
        with self.assertRaises(ValueError):
            extract_worker_diagnostics([str(self.reject(enhanced=False))])

    def test_extractor_rejects_unknown_keys_invalid_paths_and_missing_worker(self):
        message = self.diagnostic_message()
        prefix, encoded = message.split("; diagnostics=", 1)
        value = json.loads(encoded)
        variants = []
        extra = deepcopy(value); extra["source"] = SECRET; variants.append(extra)
        missing = deepcopy(value); del missing["worker_observation"]; variants.append(missing)
        for name in ("../receiver.py", "CON.py", "_engineering_task_input.py", SECRET + "?.py"):
            changed = deepcopy(value); changed["path"] = name; variants.append(changed)
        flag = deepcopy(value); flag["worker_observation"]["old_worker_root_cause_proven"] = True; variants.append(flag)
        equal = deepcopy(value); equal["observed_sha256"] = equal["expected_sha256"]; variants.append(equal)
        bool_schema = deepcopy(value); bool_schema["schema_version"] = True; variants.append(bool_schema)
        for changed in variants:
            with self.subTest(keys=list(changed)), self.assertRaises(ValueError) as caught:
                extract_worker_diagnostics([prefix + "; diagnostics=" + json.dumps(changed)])
            self.assertNotIn(SECRET, str(caught.exception))

    def test_extractor_rejects_duplicate_JSON_fields_at_all_object_levels(self):
        message = self.diagnostic_message()
        prefix, encoded = message.split("; diagnostics=", 1)
        variants = ('{"schema_version":2,' + encoded[1:],
            encoded.replace('"byte_count":', '"byte_count":1,"byte_count":', 1),
            encoded.replace('"root_selection":', '"root_selection":"explicit","root_selection":', 1))
        for duplicate in variants:
            with self.subTest(first=duplicate[:50]), self.assertRaises(ValueError):
                extract_worker_diagnostics([prefix + "; diagnostics=" + duplicate])

    def test_extractor_rejects_conflicts_noncanonical_escaping_and_mismatched_prefix(self):
        message = self.diagnostic_message()
        prefix, encoded = message.split("; diagnostics=", 1)
        conflict = json.loads(encoded)
        conflict["observed_sha256"] = "0" * 64
        variants = ([message, prefix + "; diagnostics=" + json.dumps(conflict)],
            [html.escape(html.escape(message, quote=True), quote=True)],
            [prefix + "; diagnostics=" + repr(json.loads(encoded))],
            ["Implementation source is unavailable; diagnostics=" + encoded],
            [prefix + "; diagnostics=" + encoded.replace('"byte_count":', '"byte_count":NaN,"unused":', 1)])
        for raw in variants:
            with self.subTest(raw_type=type(raw).__name__), self.assertRaises(ValueError):
                extract_worker_diagnostics(raw)

    def test_extractor_bounds_message_count_bytes_and_repeated_occurrences(self):
        message = self.diagnostic_message()
        for raw in (None, message, [None], [True], [message] * 17, [SECRET * 4000],
                    [message * 5] * 16):
            with self.subTest(type=type(raw).__name__), self.assertRaises(ValueError) as caught:
                extract_worker_diagnostics(raw)
            self.assertNotIn(SECRET, str(caught.exception))

    def test_extractor_supports_only_consistent_source_read_failure_classifications(self):
        for failure in (FileNotFoundError(SECRET), PermissionError(SECRET)):
            with patch.object(Path, "read_bytes", side_effect=failure):
                message = str(self.reject())
            result = extract_worker_diagnostics([message])
            self.assertEqual(result["diagnostic"]["failure_kind"], "source_unreadable")
        self.path.write_bytes(b"\xff" + SECRET.encode())
        error = self.reject()
        result = extract_worker_diagnostics([str(error)])
        self.assertEqual(result["diagnostic"]["failure_kind"], "source_decode_error")
        self.assertNotIn("observed_sha256", result["diagnostic"])
        self.assertNotIn(SECRET, json.dumps(result))
        name = "模块.py"
        (self.root / name).write_bytes(b"VALUE = 2\n")
        manifest = {name: sha256(SOURCE).hexdigest()}
        with self.assertRaises(data.DeploymentVerificationError) as caught:
            data.verify_deployment(manifest, content_hash(manifest), source_root=self.root, worker_diagnostics=True)
        result = extract_worker_diagnostics([str(caught.exception)])
        self.assertEqual(result["diagnostic"]["path_sha256"], sha256(name.encode()).hexdigest())
        self.assertNotIn(name, json.dumps(result))

    def test_extractor_result_cannot_mutate_original_error_or_claim_full_worker(self):
        message = self.diagnostic_message()
        result = extract_worker_diagnostics([message])
        result["diagnostic"]["worker_observation"]["source_format"]["raw_sha256"] = SECRET
        again = extract_worker_diagnostics([message])
        self.assertNotIn(SECRET, json.dumps(again))
        self.assertEqual(again["diagnostic"]["worker_observation"]["coverage_scope"],
                         "first_rejected_declared_source")


if __name__ == "__main__":
    unittest.main()
