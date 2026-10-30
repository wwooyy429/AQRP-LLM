"""Build a source-only review manifest and run local synthetic stage checks."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cloud"))
from qresearch.artifacts import content_hash
from research import read_json, write_changed


def source_manifest(root=None):
    root = ROOT if root is None else Path(root).resolve()
    files = {}
    for folder in ("cloud", "config", "templates", "tests", "tools", "docs", ".github"):
        for path in sorted((root / folder).rglob("*")):
            if path.is_file() and path.suffix in {".py", ".json", ".md", ".yml", ".yaml"} and "__pycache__" not in path.parts:
                files[path.relative_to(root).as_posix()] = hashlib.sha256(
                    path.read_text(encoding="utf-8-sig").encode("utf-8")).hexdigest()
    for name in ("requirements-test.txt", ".gitattributes", ".gitignore", "AGENTS.md"):
        path = root / name
        if path.exists():
            files[name] = hashlib.sha256(path.read_text(encoding="utf-8-sig").encode("utf-8")).hexdigest()
    return {"source_files": files, "source_hash": content_hash(files), "market_data_included": False}


def verify():
    plan = read_json(ROOT / "config" / "development.json")
    if [stage["id"] for stage in plan["stages"]] != list(range(8)):
        raise ValueError("Stage plan must contain ordered stages 0 through 7")
    if any(plan["execution"][key] for key in ("market_research_enabled", "llm_runtime_enabled", "final_test_enabled", "live_trading_enabled")):
        raise ValueError("This engineering verifier cannot approve market execution")
    for stage in plan["stages"]:
        if any(previous >= stage["id"] for previous in stage["depends_on"]):
            raise ValueError("Stage dependency must precede the stage")
    for path in list((ROOT / "config").glob("*.json")) + list((ROOT / "templates").glob("*.json")):
        read_json(path)
    environment = dict(os.environ, PYTHONPATH=str(ROOT / "cloud"), PYTHONDONTWRITEBYTECODE="1")
    completed = subprocess.run([sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-q"],
                               cwd=ROOT, env=environment, text=True, capture_output=True)
    report = {"schema_version": 1, "purpose": "engineering_only", **source_manifest(),
              "local_tests_passed": completed.returncode == 0,
              "test_output": completed.stdout + completed.stderr,
              "external_review_status": "pending_GPT_Work", "financial_evidence": False,
              "research_calls_added": 0, "lean_calls_added": 0,
              "stages": [{"id": stage["id"], "status": ("awaiting_external_review" if completed.returncode == 0 else "local_tests_failed") if stage["id"] <= 1 else "not_accepted",
                          "acceptance": stage["acceptance"]} for stage in plan["stages"]]}
    write_changed(ROOT / "audit" / "stage_verification.json", json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"local_tests_passed": report["local_tests_passed"], "source_hash": report["source_hash"],
                     "external_review_status": report["external_review_status"], "test_output": report["test_output"]}))
    return completed.returncode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("verify", "manifest"))
    args = parser.parse_args()
    if args.command == "verify":
        raise SystemExit(verify())
    print(json.dumps(source_manifest(), indent=2))


if __name__ == "__main__":
    main()
