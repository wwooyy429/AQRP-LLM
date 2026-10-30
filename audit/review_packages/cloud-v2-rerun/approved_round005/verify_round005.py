"""Read-only offline consistency check of the fixed round005 delivery.

Run with python -B audit/review_packages/cloud-v2-rerun/approved_round005/verify_round005.py.
No QC, provider, Research, LEAN, LLM call or budget event is performed. Pin the
delivery Git commit independently: self-consistent local hashes are not a remote
signature or proof of supplier provenance. This is not an acceptance authority.
"""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "cloud")]
from research import open_registry
from qresearch.deployment_sources import source_sha256

PACKAGE = Path(__file__).resolve().parent
ATTEMPT = "020326aa00434b639e5a73a405168a97"
ROUND = "stage2-source-policy-v2-rerun-005"
RUNTIME = "0f6d8c0606d1e3253632b167cab73dd04d03658a"


def read(path):
    return json.loads(path.read_bytes())


def main():
    report = read(ROOT / "audit/stage2_round005_report.json")
    assert report["runtime_source_commit"] == RUNTIME
    assert report["software_test_count"] == 844 and report["software_tests_passed"]
    assert report["new_configuration_registrations"] == 1
    assert report["new_Research_executions"] == 1 and report["new_LEAN_submissions"] == 0
    assert not any(report["acceptance"].values())
    registry = open_registry()
    state = registry.snapshot()
    current = {k: v["total"] for k, v in state["usage"].items()}
    assert current == report["current_usage"] == {"configurations": 13, "research": 16, "lean": 2}
    round_state = registry.engineering_rounds_snapshot()[ROUND]
    assert round_state["status"] == "closed"
    assert round_state["usage"] == {"configurations": 1, "research": 1, "lean": 0}
    record = next(a for a in state["attempts"] if a["attempt_id"] == ATTEMPT)
    assert record["status"] == "failed"
    assert record["external_id"] == "qc-research:38436695:" + ATTEMPT
    assert not any(a["stage"] == "lean" and a["config_id"] == record["config_id"] for a in state["attempts"])
    journal = (ROOT / "audit/runtime/registry/events.jsonl").read_bytes()
    lines = journal.splitlines(keepends=True)
    assert len(lines) == 55
    assert hashlib.sha256(journal).hexdigest() == report["current_raw_journal_sha256"]
    assert hashlib.sha256(b"".join(lines[:48])).hexdigest() == report["original48_journal_sha256"]
    assert json.loads(lines[48])["event"]["kind"] == "budget_revision_authorized"
    assert json.loads(lines[-1])["event"]["kind"] == "engineering_round_closed"
    deployment = read(ROOT / "audit/deployment.json")
    for name, expected in deployment["source_files"].items():
        assert source_sha256((ROOT / "cloud" / name).read_bytes()) == expected, name
    source = read(PACKAGE / "source_post_upload_metadata.json")
    assert source["declared_source_count"] == len(source["files"]) == 35
    assert source["source_write_count"] == len(source["writes"]) == 10
    assert all(f["actual_source_sha256"] == deployment["source_files"][f["path"]] for f in source["files"])
    entry = read(PACKAGE / "research_read_cell_observation_code1.json")
    cell = entry["result"]["structuredContent"]
    assert entry["arguments"] == {"projectId": 38436695, "index": 1}
    assert cell["cellType"] == "code"
    expected_entry = (PACKAGE / "research_cell_source.txt").read_text(encoding="utf-8")
    assert "".join(cell["source"]) == expected_entry
    observation = read(PACKAGE / "research_execute_cell_observation.json")
    assert observation["tool_name"] == "mcp__quantconnect__jupyter_execute_cell"
    assert observation["arguments"] == entry["arguments"]
    errors = [json.loads(c["text"]) for c in observation["result"]["content"] if c["type"] == "text"]
    assert len(errors) == 2 and errors[0] == errors[1]
    assert errors[0]["output_type"] == "error" and errors[0]["ename"] == "CollectionError"
    assert errors[0]["evalue"] == "Historical source collection failed; unfinished intent retained"
    budget = read(ROOT / "config/budget.json")
    assert budget["limits"]["full_configurations"] == 13
    assert budget["limits"]["research_execution_attempts"] == 20
    assert budget["limits"]["lean_submission_attempts"] == 16
    assert not budget["final_evaluation_execution_enabled"]
    manifest = read(PACKAGE / "artifact_manifest.json")
    for name, expected in manifest["files"].items():
        assert hashlib.sha256((PACKAGE / name).read_bytes()).hexdigest() == expected, name
    result = {"passed": True, "runtime_source_commit": RUNTIME, "journal_events": 55,
              "usage": current, "actual_Research_executions": 1, "actual_LEAN_submissions": 0,
              "round_closed": True, "new_remote_calls": 0, "new_budget_events": 0,
              "independent_GPT_Work_acceptance": False, "stage2_accepted": False,
              "financial_evidence": False, "final_test_enabled": False}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return result


if __name__ == "__main__":
    main()
