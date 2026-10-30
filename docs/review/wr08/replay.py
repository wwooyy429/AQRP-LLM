"""Developer replay of archived WR-08 public test classes, with immutable scripts.

Runs the original PublicContracts (12) or ExactPearsonTests (10) methods. It
does not invoke compatibility main's machine-specific static/history helpers;
those original evidence records remain archived and are not claimed as rerun.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
ARCHIVE = ROOT / "audit/reviews/20261026-7b0dcce-windows"
SUITES = {"compatibility": ("compat_agent", "compatibility_checks.py", "PublicContracts"),
          "pearson": ("numeric_agent", "exact_pearson_review.py", "ExactPearsonTests")}

RUNNER = '''from pathlib import Path
import hashlib, importlib.util, io, json, socket, sys, unittest
script, class_name = Path(sys.argv[1]), sys.argv[2]
def denied(*args, **kwargs): raise AssertionError("Offline developer replay forbids networking")
socket.socket.connect = denied
spec = importlib.util.spec_from_file_location("archived_suite", script)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
class DetailedResult(unittest.TextTestResult):
    def __init__(self, *a, **k): super().__init__(*a, **k); self.subcases = 0
    def addSubTest(self, test, subtest, error):
        self.subcases += 1
        super().addSubTest(test, subtest, error)
stream = io.StringIO()
suite = unittest.defaultTestLoader.loadTestsFromTestCase(getattr(module, class_name))
result = unittest.TextTestRunner(stream=stream, verbosity=2, resultclass=DetailedResult).run(suite)
def identity(test): return getattr(test, "test_case", test).id()
failed = {identity(test) for test, _ in result.failures}
errors = {identity(test) for test, _ in result.errors}
skipped = {identity(test) for test, _ in result.skipped}
report = {"methods": result.testsRun, "passed_methods": result.testsRun-len(failed|errors|skipped),
    "failed_methods": len(failed), "error_methods": len(errors), "skipped": len(skipped),
    "failure_records": len(result.failures), "error_records": len(result.errors),
    "expected_failures": len(result.expectedFailures), "unexpected_successes": len(result.unexpectedSuccesses),
    "subcases": result.subcases, "observations": getattr(module, "OBS", None),
    "failures": [{"test": str(test), "traceback": tb} for test, tb in result.failures],
    "errors": [{"test": str(test), "traceback": tb} for test, tb in result.errors]}
(script.parent/"test_output.txt").write_text(stream.getvalue(), encoding="utf-8")
(script.parent/"test_results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)+"\\n", encoding="utf-8")
print(json.dumps({key: report[key] for key in ("methods", "passed_methods", "failed_methods", "error_methods", "skipped", "subcases")}))
ok = result.wasSuccessful() and result.testsRun > 0 and not (result.skipped or result.expectedFailures or result.unexpectedSuccesses)
raise SystemExit(0 if ok else 1)
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--suite", choices=SUITES, required=True)
    args = parser.parse_args()
    source, output = args.source_dir.resolve(), args.output_dir.resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("Use an empty output directory; earlier evidence must not be overwritten")
    output.mkdir(parents=True, exist_ok=True)
    folder, filename, class_name = SUITES[args.suite]
    raw_script = (ARCHIVE / folder / filename).read_bytes()
    original_hash = hashlib.sha256(raw_script).hexdigest()
    manifest = json.loads((ARCHIVE / "archive_manifest.json").read_text(encoding="utf-8-sig"))
    if manifest["files"][folder + "/" + filename] != original_hash:
        raise ValueError("Archived reviewer script has changed")
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8",
                       OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")
    with tempfile.TemporaryDirectory(prefix="aqrp-wr08-replay-") as directory:
        work = Path(directory)
        hashes = {}
        for name in ("cloud", "config", "tools"):
            for path in sorted((source / name).rglob("*")):
                if not path.is_file() or path.suffix not in {".py", ".json"} or "__pycache__" in path.parts:
                    continue
                relative = path.relative_to(source)
                raw = path.read_bytes()
                destination = work / "source" / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(raw)
                hashes[relative.as_posix()] = hashlib.sha256(raw).hexdigest()
        job = work / folder
        job.mkdir()
        script = job / filename
        script.write_bytes(raw_script)
        runner = work / "run_class.py"
        runner.write_text(RUNNER, encoding="utf-8")
        completed = subprocess.run([sys.executable, "-B", str(runner), str(script), class_name],
            cwd=work, env=environment, text=True, capture_output=True, encoding="utf-8", errors="replace")
        for name in ("test_output.txt", "test_results.json"):
            if (job / name).exists():
                shutil.copyfile(job / name, output / name)
        (output / "process_output.txt").write_text(completed.stdout + completed.stderr, encoding="utf-8")
        result_path = output / "test_results.json"
        result = json.loads(result_path.read_text(encoding="utf-8")) if result_path.exists() else None
        unchanged = all(hashlib.sha256((work / "source" / name).read_bytes()).hexdigest() == digest
                        for name, digest in hashes.items())
        report = {"schema_version": 1, "role": "developer_replay", "suite": args.suite,
            "entrypoint": class_name + " unittest methods only; original main helpers not rerun",
            "archived_script_sha256": original_hash, "script_changed": False,
            "runner_sha256": hashlib.sha256(RUNNER.encode()).hexdigest(),
            "source_files": hashes, "source_unchanged": unchanged,
            "process_exit_code": completed.returncode, "result": result,
            "independent_acceptance": False, "financial_evidence": False,
            "market_calls": 0, "model_API_calls": 0, "lean_submissions": 0}
        (output / "replay.json").write_text(json.dumps(report, ensure_ascii=False, indent=2,
            allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"suite": args.suite, "exit_code": completed.returncode,
        "methods": result.get("methods") if result else None,
        "passed": result.get("passed_methods") if result else None}))
    return completed.returncode if unchanged else 1


if __name__ == "__main__":
    raise SystemExit(main())
