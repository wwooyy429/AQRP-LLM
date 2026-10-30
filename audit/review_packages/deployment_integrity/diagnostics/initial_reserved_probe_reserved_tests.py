"""Synthetic source-integrity known answers; no provider or real registry."""
from hashlib import sha256
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cloud"))
from qresearch.artifacts import content_hash
import qresearch.engineering_data as data


SOURCE = b"# synthetic source\nVALUE = 1\n"
SECRET = "SENSITIVE_SOURCE_VALUE_123.45"
_DEFAULT = object()


class DeploymentIntegrityDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "receiver.py"
        self.path.write_bytes(SOURCE)
        self.manifest = {"receiver.py": sha256(SOURCE).hexdigest()}

    def error(self, manifest=_DEFAULT, expected=None):
        manifest = self.manifest if manifest is _DEFAULT else manifest
        expected = content_hash(manifest) if expected is None else expected
        try:
            data.verify_deployment(manifest, expected, source_root=self.root)
        except ValueError as error:
            kind = getattr(data, "DeploymentVerificationError", None)
            self.assertTrue(isinstance(kind, type), "Missing typed deployment diagnostics")
            self.assertIsInstance(error, kind)
            self.assertIsInstance(error.diagnostics, dict)
            self.assertEqual(type(error.diagnostics["schema_version"]), int)
            self.assertEqual(error.diagnostics["schema_version"], 1)
            self.assertLess(len(str(error)), 800)
            self.assertNotIn(SECRET, str(error))
            return error
        self.fail("A deployment mismatch was accepted")

    def test_shared_source_digest_matches_existing_text_policy(self):
        function = getattr(data, "source_bytes_sha256", None)
        self.assertTrue(callable(function), "Missing shared deployment source hash")
        for raw in (SOURCE, b"\xef\xbb\xbf" + SOURCE,
                    SOURCE.replace(b"\n", b"\r\n"), SOURCE.replace(b"\n", b"\r")):
            with self.subTest(raw=raw):
                self.assertEqual(function(raw), sha256(SOURCE).hexdigest())
        for raw in (SOURCE[:-1], SOURCE + b"\n", SOURCE + b"CHANGED = True\n"):
            self.assertNotEqual(function(raw), sha256(SOURCE).hexdigest())

    def test_shared_source_digest_invalid_bytes_never_echo_source(self):
        function = getattr(data, "source_bytes_sha256", None)
        self.assertTrue(callable(function))
        for raw in (None, False, SOURCE.decode(), bytearray(SOURCE), b"\xff" + SECRET.encode()):
            with self.subTest(kind=type(raw).__name__), self.assertRaises(ValueError) as caught:
                function(raw)
            self.assertNotIn(SECRET, str(caught.exception))

    def test_success_keeps_hash_and_existing_BOM_newline_contract(self):
        for raw in (SOURCE, b"\xef\xbb\xbf" + SOURCE,
                    SOURCE.replace(b"\n", b"\r\n"), SOURCE.replace(b"\n", b"\r")):
            self.path.write_bytes(raw)
            self.assertEqual(data.verify_deployment(self.manifest, content_hash(self.manifest), source_root=self.root),
                             content_hash(self.manifest))

    def test_mismatch_identifies_exact_path_expected_and_observed(self):
        changed = b"VALUE = 2\n# " + SECRET.encode() + b"\n"
        self.path.write_bytes(changed)
        error = self.error()
        self.assertEqual(error.diagnostics, {"schema_version": 1, "failure_kind": "source_hash_mismatch",
            "path": "receiver.py", "expected_sha256": sha256(SOURCE).hexdigest(),
            "observed_sha256": sha256(changed).hexdigest()})
        self.assertIn("Cloud implementation differs from the frozen deployment", str(error))

    def test_hash_diagnostics_come_from_one_source_read(self):
        changed = b"VALUE = 2\n"
        with patch.object(Path, "read_bytes", side_effect=[changed, SECRET.encode()]) as reader:
            error = self.error()
        self.assertEqual(reader.call_count, 1)
        self.assertEqual(error.diagnostics["observed_sha256"], sha256(changed).hexdigest())

    def test_manifest_shape_and_hash_values_are_checked_before_any_read(self):
        cases = [None, {}, [], {"receiver.py": False}, {"receiver.py": "Z" * 64},
                 {"receiver.py": "0" * 63}, {1: "a" * 64}, {"receiver.py": [SECRET]}]
        for manifest in cases:
            with self.subTest(manifest=manifest), patch.object(Path, "read_bytes") as reader:
                error = self.error(manifest=manifest, expected="a" * 64)
            self.assertIn(error.diagnostics["failure_kind"], {"invalid_manifest", "invalid_path"})
            self.assertEqual(reader.call_count, 0)

    def test_entire_manifest_is_prescanned_before_reading_earlier_valid_file(self):
        for name, value in (("z/../receiver.py", "a" * 64), ("z.py", False)):
            manifest = {"receiver.py": sha256(SOURCE).hexdigest(), name: value}
            with self.subTest(name=name), patch.object(Path, "read_bytes") as reader:
                self.error(manifest=manifest, expected="a" * 64)
            self.assertEqual(reader.call_count, 0)

    def test_manifest_hash_mismatch_is_distinct_and_never_reads_source(self):
        with patch.object(Path, "read_bytes") as reader:
            error = self.error(expected="0" * 64)
        self.assertEqual(reader.call_count, 0)
        self.assertEqual(error.diagnostics["failure_kind"], "manifest_hash_mismatch")
        self.assertEqual(error.diagnostics["expected_sha256"], "0" * 64)
        self.assertEqual(error.diagnostics["observed_sha256"], content_hash(self.manifest))

    def test_invalid_paths_do_not_echo_paths_or_touch_sources(self):
        paths = ["../" + SECRET + ".py", "/" + SECRET + ".py", "q\\receiver.py",
            "q/../receiver.py", "q//receiver.py", "./receiver.py", "C:receiver.py",
            "bad\nreceiver.py", "bad\x00receiver.py", "\ud800.py", "_engineering_task_input.py"]
        for name in paths:
            with self.subTest(name=ascii(name)), patch.object(Path, "read_bytes") as reader:
                error = self.error({name: "a" * 64}, expected="a" * 64)
            self.assertEqual(reader.call_count, 0)
            self.assertEqual(error.diagnostics["failure_kind"], "invalid_path")
            self.assertNotIn("path", error.diagnostics)

    def test_resolved_path_escape_is_rejected_before_source_read(self):
        original = Path.resolve
        outside = self.root.parent / "outside.py"
        def resolved(path, *args, **kwargs):
            return outside if path.name == "receiver.py" else original(path, *args, **kwargs)
        with patch.object(Path, "resolve", resolved), patch.object(Path, "read_bytes") as reader:
            error = self.error()
        self.assertEqual(reader.call_count, 0)
        self.assertEqual(error.diagnostics["failure_kind"], "invalid_path")

    def test_shared_path_contract_rejects_devices_and_forbidden_characters_before_IO(self):
        paths = ["CON.py", "COM1.py", "aux.py", "nested/NUL.py", "LPT9.py", "PRN/x.py",
            "nested./receiver.py", "trailing /receiver.py", 'quote"file.py', "star*.py",
            "pipe|file.py", "q?u.py", "<a>.py", "control\x01.py"]
        for name in paths:
            # Pure lexical resolve plus a forbidden reader ensure even the
            # pre-fix probe never touches a real Windows device or path.
            with self.subTest(name=ascii(name)), patch.object(Path, "resolve", lambda path, *a, **k: path), \
                    patch.object(Path, "read_bytes", side_effect=AssertionError("Unsafe source read")) as reader:
                error = self.error({name: "a" * 64})
            self.assertEqual(error.diagnostics["failure_kind"], "invalid_path")
            self.assertNotIn("path", error.diagnostics)
            self.assertEqual(reader.call_count, 0)

    def test_unreadable_and_non_UTF8_source_have_fixed_safe_diagnostics(self):
        with patch.object(Path, "read_bytes", side_effect=PermissionError("C:\\PRIVATE\\" + SECRET)):
            error = self.error()
        self.assertEqual(error.diagnostics["failure_kind"], "source_unreadable")
        self.assertIsNone(error.__cause__)
        self.assertTrue(error.__suppress_context__)
        self.path.write_bytes(b"\xff" + SECRET.encode())
        error = self.error()
        self.assertEqual(error.diagnostics["failure_kind"], "source_decode_error")
        self.assertNotIn("observed_sha256", error.diagnostics)

    def test_final_line_breaks_remain_part_of_the_frozen_source(self):
        for raw in (SOURCE[:-1], SOURCE + b"\n"):
            self.path.write_bytes(raw)
            self.assertEqual(self.error().diagnostics["failure_kind"], "source_hash_mismatch")

    def test_valid_unicode_path_uses_digest_and_input_stays_outside_manifest(self):
        name = "模块.py"
        (self.root / name).write_bytes(SOURCE + b"CHANGED = True\n")
        error = self.error({name: sha256(SOURCE).hexdigest()})
        self.assertEqual(error.diagnostics["path_sha256"], sha256(name.encode()).hexdigest())
        self.assertNotIn(name, str(error))
        (self.root / "_engineering_task_input.py").write_bytes(SECRET.encode())
        self.assertEqual(data.verify_deployment(self.manifest, content_hash(self.manifest), source_root=self.root), content_hash(self.manifest))

    def test_diagnostic_fields_are_whitelisted_bounded_and_defensive(self):
        self.path.write_bytes(SOURCE + b"CHANGED = True\n")
        error = self.error()
        self.assertLessEqual(set(error.diagnostics), {"schema_version", "failure_kind", "path", "path_sha256", "expected_sha256", "observed_sha256"})
        copy = error.diagnostics
        copy["source"] = SECRET
        self.assertNotIn("source", error.diagnostics)


if __name__ == "__main__":
    unittest.main()
