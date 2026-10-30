"""Check the fixed review snapshot and run its selected offline test modules.

Run against a detached 75f2462 checkout or the bundle's source directory, not
against a moving development checkout. This script makes no network/tool calls.
It never builds config, opens the real Registry, submits QC work or writes source.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import importlib.metadata
import io
import json
import os
import platform
import subprocess
import sys
import time
import unittest

sys.dont_write_bytecode = True


def digest(path):
    return hashlib.sha256(path.read_text(encoding="utf-8-sig").encode("utf-8")).hexdigest()


def integrity(source, manifest):
    errors = []
    for item in manifest["source_files"]:
        path = source / item["path"]
        if not path.resolve().is_relative_to(source) or not path.is_file():
            errors.append({"path": item["path"], "problem": "missing_or_outside_snapshot"})
        elif digest(path) != item["sha256"]:
            errors.append({"path": item["path"], "problem": "sha256_mismatch"})
    return errors


def environment():
    versions = {}
    for name in ("numpy", "pandas", "python-dateutil", "pytz", "tzdata", "six"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    return {"platform": platform.platform(), "python": platform.python_version(), "packages": versions}


def execute_tests(source, manifest):
    sys.path[:0] = [str(source / "cloud"), str(source / "tests")]
    loader = unittest.TestLoader()
    suite, counts = unittest.TestSuite(), {}
    for module in manifest["test_modules"]:
        selected = loader.loadTestsFromName(module)
        counts[module] = selected.countTestCases()
        suite.addTests(selected)
    output = io.StringIO()
    start = time.monotonic()
    result = unittest.TextTestRunner(stream=output, verbosity=1).run(suite)
    def method_id(test):
        return getattr(test, "test_case", test).id()
    failures = {method_id(test) for test, _ in result.failures}
    errors = {method_id(test) for test, _ in result.errors}
    skipped = {method_id(test) for test, _ in result.skipped}
    expected = {method_id(test) for test, _ in result.expectedFailures}
    unexpected = {method_id(test) for test in result.unexpectedSuccesses}
    report = {"actually_executed": True, "run": result.testsRun,
        "failed": len(failures), "errors": len(errors), "skipped": len(skipped),
        "failure_records_including_subtests": len(result.failures), "error_records_including_subtests": len(result.errors),
        "expected_failures": len(expected), "unexpected_successes": len(unexpected),
        "test_methods_by_module": counts, "seconds": time.monotonic() - start,
        "successful": result.wasSuccessful(), "output": output.getvalue()}
    report["passed"] = report["run"] - len(failures | errors | skipped | expected | unexpected)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=Path(__file__).with_name("manifest.json"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    source, manifest_path = args.source_dir.resolve(), args.manifest.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if args.child:
        print(json.dumps(execute_tests(source, manifest), ensure_ascii=True))
        return
    if args.output and args.output.resolve().is_relative_to(source):
        raise ValueError("Write the report outside the frozen source directory")
    before = integrity(source, manifest)
    report = {"schema_version": 1, "purpose": "developer_offline_phase01_recheck",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "reviewed_source_commit": manifest["code_source_commit"],
        "expected_original_source_manifest_hash": manifest["original_source_manifest_hash"],
        "environment": environment(), "source_file_count": len(manifest["source_files"]),
        "source_integrity_errors_before": before, "independent_review": False,
        "financial_evidence": False, "market_execution_requested": False,
        "Research_calls_added": 0, "LEAN_submissions_added": 0,
        "configuration_registrations_added": 0, "tests": None}
    required_versions = {}
    for line in (source / "requirements-test.txt").read_text(encoding="utf-8-sig").splitlines():
        if line.strip() and not line.lstrip().startswith("#"):
            name, version = line.strip().split("==", 1)
            required_versions[name] = version
    report["required_versions"] = required_versions
    report["pinned_dependencies_match"] = all(report["environment"]["packages"].get(name) == version
        for name, version in required_versions.items())
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
        PYTHONPATH=os.pathsep.join((str(source / "cloud"), str(source / "tests"))))
    if not before:
        checked = subprocess.run([sys.executable, "-B", "tools/stages.py", "manifest"],
            cwd=source, env=env, capture_output=True, text=True)
        report["source_manifest_command"] = "python -B tools/stages.py manifest (cwd=fixed source)"
        report["source_manifest_exit_code"] = checked.returncode
        actual = json.loads(checked.stdout)["source_hash"] if checked.returncode == 0 else None
        report["actual_original_source_manifest_hash"] = actual
        if actual == manifest["original_source_manifest_hash"]:
            command = [sys.executable, "-B", str(Path(__file__).resolve()), "--child",
                       "--source-dir", str(source), "--manifest", str(manifest_path)]
            completed = subprocess.run(command, cwd=source, env=env, capture_output=True, text=True)
            report["test_command"] = "python -B review/run_checks.py --child --source-dir source --manifest review/manifest.json (absolute paths resolved at execution)"
            report["test_process_exit_code"] = completed.returncode
            if completed.returncode == 0:
                report["tests"] = json.loads(completed.stdout)
            else:
                report["test_process_error"] = completed.stderr
    report["source_integrity_errors_after"] = integrity(source, manifest)
    tests = report["tests"]
    passed = bool(tests and tests["successful"] and tests["run"] == manifest["expected_test_methods"]
        and tests["passed"] == manifest["expected_test_methods"]
        and all(tests[key] == 0 for key in ("failed", "errors", "skipped", "expected_failures", "unexpected_successes"))
        and report["pinned_dependencies_match"]
        and not before and not report["source_integrity_errors_after"]
        and report.get("actual_original_source_manifest_hash") == manifest["original_source_manifest_hash"])
    report["developer_recheck_passed"] = passed
    report["known_open_findings"] = manifest["known_open_findings"]
    report["acceptance_note"] = "Developer evidence only. Does not resolve WR-04 or grant independent phase/system acceptance."
    encoded = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(json.dumps({"developer_recheck_passed": passed, "test_run": tests["run"] if tests else None,
        "passed": tests["passed"] if tests else None, "failed": tests["failed"] if tests else None,
        "errors": tests["errors"] if tests else None, "known_open_findings": report["known_open_findings"]}))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
