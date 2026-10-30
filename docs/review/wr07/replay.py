"""Replay unmodified archived WR-07 review scripts against an explicit source.

This is a developer execution envelope, never a new independent approval.
The numeric script has a literal historical SHA in its output; the source file
hashes in replay.json identify the actual code executed and take precedence.
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
ARCHIVE = ROOT / "audit/reviews/20261026-fe4374c-windows"
SCRIPTS = {"numeric": ("numeric_agent", "numeric_time_review.py", "test_results.json"),
           "atomic": ("atomic_agent", "atomic_independent.py", "results.json")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--suite", choices=SCRIPTS, required=True)
    args = parser.parse_args()
    source, output = args.source_dir.resolve(), args.output_dir.resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("Output must be empty; preserve all earlier evidence")
    output.mkdir(parents=True, exist_ok=True)
    folder, filename, result_name = SCRIPTS[args.suite]
    original = ARCHIVE / folder / filename
    script_bytes = original.read_bytes()
    expected = json.loads((ARCHIVE / "archive_manifest.json").read_text(encoding="utf-8-sig"))
    script_hash = hashlib.sha256(script_bytes).hexdigest()
    if script_hash != expected["files"][folder + "/" + filename]:
        raise ValueError("Archived script hash mismatch")
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8",
                       OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")
    with tempfile.TemporaryDirectory(prefix="aqrp-wr07-replay-") as directory:
        work = Path(directory)
        hashes = {}
        for name in ("cloud", "config", "tools"):
            for path in sorted((source / name).rglob("*")):
                if not path.is_file() or path.suffix not in {".py", ".json"} or "__pycache__" in path.parts:
                    continue
                relative = path.relative_to(source)
                raw = path.read_bytes()
                target = work / "source" / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw)
                hashes[relative.as_posix()] = hashlib.sha256(raw).hexdigest()
        job = work / folder
        job.mkdir()
        script = job / filename
        script.write_bytes(script_bytes)
        # Atomic supports a source identity override. Numeric's literal old SHA
        # is retained verbatim and explicitly qualified by the replay envelope.
        environment.update(AQRP_AUDIT_SOURCE=str(work / "source"),
                           AQRP_ATOMIC_OUTPUT=str(job), AQRP_AUDIT_SHA="see_replay_source_hashes")
        completed = subprocess.run([sys.executable, "-B", str(script)], cwd=work,
            env=environment, capture_output=True, text=True, encoding="utf-8", errors="replace")
        for path in job.iterdir():
            if path.name != filename and path.is_file():
                shutil.copyfile(path, output / path.name)
        (output / "process_output.txt").write_text(completed.stdout + completed.stderr, encoding="utf-8")
        result = json.loads((output / result_name).read_text(encoding="utf-8")) if (output / result_name).exists() else None
        envelope = {"schema_version": 1, "role": "developer_replay", "suite": args.suite,
            "archived_script_sha256": script_hash, "script_changed": False,
            "source_files": hashes, "process_exit_code": completed.returncode, "result": result,
            "historical_literal_SHA_is_not_executed_source_identity": True,
            "independent_acceptance": False, "financial_evidence": False,
            "market_calls": 0, "model_calls": 0, "lean_submissions": 0}
        (output / "replay.json").write_text(json.dumps(envelope, ensure_ascii=False, indent=2,
            allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"suite": args.suite, "exit_code": completed.returncode,
        "methods": result.get("methods") if result else None,
        "passed": result.get("passed_methods") if result else None}))
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
