"""Developer replay of the archived independent suite, with explicit provenance.

The archived reviewer file is never edited. Adapted mode only handles the
expected BudgetExceeded loser in six race tests and asserts exactly one winner.
It does not change production code, inputs, thresholds or other assertions.
"""
from pathlib import Path
import argparse
import difflib
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[3]
ORIGINAL = ROOT / "audit/reviews/20261026-75f24629-windows/independent_review.py"


def adapted_script(text):
    old = '''                    if kind=='configurations': return {'ok':True,'registered':b.register()}
                    a=b.claim(kind,retry_of=retry,reason='synthetic repair' if retry else None,
                              allocation='reserve' if retry else 'normal')
                    return {'ok':True,'should_execute':a.should_execute}'''
    new = '''                    try:
                        if kind=='configurations': return {'ok':True,'registered':b.register()}
                        a=b.claim(kind,retry_of=retry,reason='synthetic repair' if retry else None,
                                  allocation='reserve' if retry else 'normal')
                        return {'ok':True,'should_execute':a.should_execute}
                    except BudgetExceeded as exc:
                        return {'ok':False,'type':type(exc).__name__,'message':str(exc)}'''
    assertion = "            self.assertTrue(all(a['ok'] for a in answers),answers)"
    replacement = '''            winners=[a for a in answers if a['ok']]
            rejected=[a for a in answers if not a['ok']]
            self.assertEqual(len(winners),1,answers)
            self.assertEqual(len(rejected),1,answers)
            self.assertEqual(rejected[0]['type'],'BudgetExceeded',answers)
            if kind!='configurations': self.assertTrue(winners[0]['should_execute'])
            self.assertEqual(count,2,answers)'''
    if text.count(old) != 1 or text.count(assertion) != 1:
        raise ValueError("Archived reviewer harness differs from the expected original")
    return text.replace(old, new).replace(assertion, replacement)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--mode", choices=("original", "adapted"), required=True)
    args = parser.parse_args()
    source, output = args.source_dir.resolve(), args.output_dir.resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("Use an empty output directory; prior execution evidence is immutable")
    output.mkdir(parents=True, exist_ok=True)
    original_bytes = ORIGINAL.read_bytes()
    text = original_bytes.decode("utf-8-sig").replace("\r\n", "\n")
    changed = adapted_script(text) if args.mode == "adapted" else text
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8",
                       OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")
    # TemporaryDirectory removes only this runner's own directory on completion.
    # No caller source, platform state or archived reviewer evidence is mutated.
    with tempfile.TemporaryDirectory(prefix="aqrp-review-replay-") as directory:
        work = Path(directory)
        copied = {}
        for folder in ("cloud", "config", "tools"):
            for path in sorted((source / folder).rglob("*")):
                if not path.is_file() or "__pycache__" in path.parts or path.suffix not in {".py", ".json"}:
                    continue
                relative = path.relative_to(source)
                payload = path.read_bytes()
                destination = work / "source" / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(payload)
                copied[relative.as_posix()] = hashlib.sha256(payload).hexdigest()
        script = work / "independent_review.py"
        if args.mode == "original":
            script.write_bytes(original_bytes)
        else:
            script.write_text(changed, encoding="utf-8", newline="\n")
        completed = subprocess.run([sys.executable, "-B", str(script)], cwd=work,
            env=environment, capture_output=True, text=True, encoding="utf-8", errors="replace")
        for name in ("independent_test_output.txt", "independent_test_results.json"):
            if (work / name).exists():
                shutil.copyfile(work / name, output / name)
        (output / "process_output.txt").write_text(completed.stdout + completed.stderr, encoding="utf-8")
        if args.mode == "adapted":
            (output / "adapted_independent_review.py").write_text(changed, encoding="utf-8", newline="\n")
            diff = "".join(difflib.unified_diff(text.splitlines(True), changed.splitlines(True),
                fromfile="archived/independent_review.py", tofile="developer/adapted_independent_review.py"))
            (output / "harness.diff").write_text(diff, encoding="utf-8")
        result_path = output / "independent_test_results.json"
        result = json.loads(result_path.read_text(encoding="utf-8")) if result_path.exists() else None
        summary = {"schema_version": 1, "execution_role": "developer_replay",
            "independent_acceptance": False, "financial_evidence": False,
            "harness_mode": args.mode, "original_script_sha256": hashlib.sha256(original_bytes).hexdigest(),
            "executed_script_sha256": hashlib.sha256(script.read_bytes()).hexdigest(),
            "source_files": copied, "process_exit_code": completed.returncode,
            "result": result, "market_calls": 0, "lean_submissions": 0, "model_calls": 0}
        (output / "replay.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2,
            allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"mode": args.mode, "exit_code": completed.returncode,
        "methods": result.get("test_methods") if result else None,
        "passed": result.get("passed_methods") if result else None,
        "failures": result.get("failures") if result else None,
        "errors": result.get("errors") if result else None}))
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
