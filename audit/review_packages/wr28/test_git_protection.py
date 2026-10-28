"""Developer WR28 raw-Git audit-boundary checks; no cloud or Registry writes."""
from copy import deepcopy
from hashlib import sha1, sha256
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = next(path for path in Path(__file__).resolve().parents
            if (path / 'cloud/qresearch').is_dir() and (path / 'config').is_dir())
PACKAGE = ROOT / "audit/review_packages/deployment-eof-v2"
sys.path.insert(0, str(PACKAGE))
import git_protection as protection


class RawGitProtectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.before = (PACKAGE / "protected_before.json").read_bytes()
        cls.manifest = protection.build_manifest(ROOT, cls.before)
        archive = subprocess.run(["git", "archive", "1cf26578da59eebd37e138ca5d6d076991386470"],
            cwd=ROOT, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout
        cls.archive = archive
        cls.raw_files = {}
        with tarfile.open(fileobj=io.BytesIO(archive)) as stream:
            for entry in stream.getmembers():
                if entry.name in cls.manifest["files"]:
                    cls.raw_files[entry.name] = stream.extractfile(entry).read()
        cls.frozen = subprocess.run(["git", "show",
            "662ccd876b67ca0949f921a53c4c33df37cfbbf1:cloud/engineering_smoke.py"], cwd=ROOT,
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="aqrp-wr28-unit-")
        self.addCleanup(self.temporary.cleanup)
        self.export = Path(self.temporary.name)
        for name, raw in self.raw_files.items():
            path = self.export / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)

    def reject(self, action):
        with self.assertRaises(protection.ProtectionError) as caught:
            action()
        self.assertEqual(str(caught.exception), "Git raw-byte protection check failed")
        self.assertNotIn("SECRET", str(caught.exception))

    def test_exact_fixed_git_archive_passes_without_git_or_normalization(self):
        with patch.object(protection, "_git", side_effect=AssertionError("No Git during export verification")):
            result = protection.verify_export(self.export, self.manifest, self.before)
        self.assertEqual(result["protected_git_blobs_verified"], 122)
        self.assertEqual(result["legacy_declared_vs_git_blob_mismatch_count"], 3)
        self.assertFalse(result["legacy_declarations_rewritten"])
        self.assertFalse((self.export / ".git").exists())

    def test_all_122_blob_records_match_independent_git_archive_known_answers(self):
        self.assertEqual(len(self.raw_files), 122)
        declared = json.loads(self.before)
        for name, raw in self.raw_files.items():
            item = self.manifest["files"][name]
            oid = sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
            self.assertEqual(item, {"sha256": sha256(raw).hexdigest(), "git_blob_oid": oid,
                "byte_count": len(raw), "legacy_declared_sha256": declared[name]})

    def test_any_one_byte_mutation_in_every_protected_file_is_rejected(self):
        for name, raw in self.raw_files.items():
            with self.subTest(path=name):
                path = self.export / name
                path.write_bytes(raw + b"\0")
                self.reject(lambda: protection.verify_export(self.export, self.manifest, self.before))
                path.write_bytes(raw)

    def test_crlf_change_bom_and_same_length_byte_flip_are_rejected(self):
        name = "config/research.json"
        raw = self.raw_files[name]
        changed = [raw.replace(b"\n", b"\r\n"), b"\xef\xbb\xbf" + raw,
                   bytes([raw[0] ^ 1]) + raw[1:]]
        for variant in changed:
            self.assertNotEqual(variant, raw)
            (self.export / name).write_bytes(variant)
            self.reject(lambda: protection.verify_export(self.export, self.manifest, self.before))

    def test_every_record_digest_oid_and_length_are_enforced(self):
        name = "config/research.json"
        for field, bad in (("sha256", "0" * 64), ("git_blob_oid", "0" * 40),
                           ("byte_count", len(self.raw_files[name]) + 1)):
            value = deepcopy(self.manifest)
            value["files"][name][field] = bad
            self.reject(lambda: protection.verify_export(self.export, value, self.before))

    def test_closed_manifest_schema_native_counts_constants_and_paths(self):
        values = []
        for field, bad in (("schema_version", True), ("protected_file_count", True),
                ("identity_policy", "SECRET"), ("kind", "SECRET"), ("extra", "SECRET")):
            value = deepcopy(self.manifest)
            value[field] = bad
            values.append(value)
        for field, bad in (("byte_count", True), ("byte_count", -1), ("byte_count", 1.0),
                ("sha256", "A" * 64), ("git_blob_oid", "a" * 39), ("extra", "SECRET")):
            value = deepcopy(self.manifest)
            value["files"]["config/research.json"][field] = bad
            values.append(value)
        for name in ("../SECRET", "/SECRET", "C:/SECRET", "config/../SECRET", "config\\SECRET"):
            value = deepcopy(self.manifest)
            value["files"][name] = value["files"].pop("config/research.json")
            values.append(value)
        for field in ("baseline", "candidate", "materials"):
            value = deepcopy(self.manifest)
            value["git_snapshots"][field]["tree"] = "0" * 40
            values.append(value)
        for value in values:
            self.reject(lambda: protection.validate_manifest(value, self.before))

    def test_path_list_raw_bytes_and_legacy_declarations_remain_bound(self):
        for bad in (self.before + b"\n", self.before.replace(b"\r\n", b"\n"), b"{}", b"SECRET"):
            if bad != self.before:
                self.reject(lambda: protection.validate_manifest(self.manifest, bad))
        changed = deepcopy(self.manifest)
        changed["files"]["config/research.json"]["legacy_declared_sha256"] = "0" * 64
        self.reject(lambda: protection.validate_manifest(changed, self.before))
        raw = json.dumps(self.manifest).encode()
        self.assertEqual(protection.load_manifest(raw, self.before), self.manifest)
        self.reject(lambda: protection.load_manifest(b'{"schema_version":1,"schema_version":1}', self.before))

    def test_missing_and_relocated_protected_file_cannot_pass(self):
        name = "config/research.json"
        (self.export / name).unlink()
        (self.export / "SECRET").write_bytes(self.raw_files[name])
        self.reject(lambda: protection.verify_export(self.export, self.manifest, self.before))

    def test_fixture_is_pinned_source_only_and_does_not_need_git(self):
        path = self.export / protection.FIXTURE_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.frozen)
        self.assertEqual(protection.read_replay_fixture(self.export), self.frozen)
        self.assertEqual(sha256(self.frozen).hexdigest(), protection.FIXTURE_SHA256)
        path.write_bytes(self.frozen + b"\n")
        self.reject(lambda: protection.read_replay_fixture(self.export))

    def test_builder_rejects_missing_git_objects_or_changed_snapshot_evidence(self):
        self.reject(lambda: protection.build_manifest(self.export, self.before))
        with patch.object(protection, "_git", return_value=b"0" * 40 + b"\n"):
            self.reject(lambda: protection.build_manifest(ROOT, self.before))

    def test_full_checker_in_clean_export_uses_pinned_fixture_and_keeps_protected_bytes(self):
        with tarfile.open(fileobj=io.BytesIO(self.archive)) as stream:
            for entry in stream.getmembers():
                if not entry.isfile():
                    continue
                target = self.export / entry.name
                self.assertTrue(target.resolve().is_relative_to(self.export.resolve()))
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(stream.extractfile(entry).read())
        package = self.export / "audit/review_packages/deployment-eof-v2"
        for name in ("verify_candidate.py", "git_protection.py"):
            (package / name).write_bytes((PACKAGE / name).read_bytes())
        (package / "protected_git_baseline.json").write_bytes(json.dumps(self.manifest).encode())
        fixture = self.export / protection.FIXTURE_PATH
        fixture.parent.mkdir(parents=True, exist_ok=True)
        fixture.write_bytes(self.frozen)
        # Every direct subprocess invocation from the checker, including git,
        # is forbidden. This tests .git-free replay even under a parent repo.
        command = ('import runpy,subprocess; '
                   'subprocess.check_output=lambda *a,**k: (_ for _ in ()).throw(AssertionError("No subprocess")); '
                   'subprocess.run=lambda *a,**k: (_ for _ in ()).throw(AssertionError("No subprocess")); '
                   'runpy.run_path("verify_candidate.py",run_name="__main__")')
        completed = subprocess.run([sys.executable, "-X", "utf8", "-B", "-c", command],
            cwd=package, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        result = json.loads(completed.stdout)
        self.assertEqual(result["protected_files_unchanged"], 122)
        self.assertEqual(result["protected_git_baseline"]["legacy_declared_vs_git_blob_mismatch_count"], 3)
        self.assertEqual(result["registry_events"], 48)
        self.assertEqual(result["actual_original_LEAN_status"], "runtime_error")
        self.assertFalse(result["replay_is_worker_file_observation"])
        self.assertEqual(result["cloud_calls"], 0)
        self.assertFalse(result["stage2_accepted"])
        protection.verify_export(self.export, self.manifest, self.before)


if __name__ == "__main__":
    unittest.main()
