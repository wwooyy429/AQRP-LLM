"""Developer replay of permitted failure metadata in isolated stores only."""
from pathlib import Path
from unittest.mock import patch
import hashlib
import json
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "cloud"), str(ROOT / "tools")]
import research
import stage2

ATTEMPT = "f5d05f5b964b4a1d924e4b70cd207386"
PACKET = ROOT / "audit/tool_observations" / (ATTEMPT + "-research.json")
TOOL = json.loads(PACKET.read_bytes())
assert hashlib.sha256(PACKET.read_bytes()).hexdigest() == "14ae4a18636496737862a1ce314d90ae7fcf1abaf35f8a0f27145e0e839af8f3"


def fingerprints(folder):
    return {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in folder.rglob("*") if p.is_file() and not p.name.endswith(".lock")}


real_before = fingerprints(ROOT / "audit/runtime")
budget = (ROOT / "config/budget.json").read_bytes()
cases = []
for label in ("original_17_replay", "15_17_17_recovery", "missing_dispatch", "wrong_cell"):
    with tempfile.TemporaryDirectory(prefix="aqrp-wr21-metadata-") as temp:
        work = Path(temp)
        shutil.copytree(ROOT / "audit/runtime", work / "audit/runtime")
        (work / "config").mkdir()
        (work / "config/budget.json").write_bytes(budget)
        (work / "audit/task_inputs").mkdir()
        shutil.copyfile(ROOT / "audit/task_inputs" / (ATTEMPT + ".py"),
                        work / "audit/task_inputs" / (ATTEMPT + ".py"))
        runtime = work / "audit/runtime"
        journal = runtime / "registry/events.jsonl"
        if label == "15_17_17_recovery":
            journal.write_bytes(b"".join(journal.read_bytes().splitlines(keepends=True)[:15]))
            shutil.rmtree(runtime / "engineering/evidence" / ATTEMPT)
            (runtime / "engineering/submissions" / (ATTEMPT + ".json")).unlink()
        if label == "missing_dispatch":
            (runtime / "engineering/research-dispatch" / (ATTEMPT + ".json")).unlink()
        observed = json.loads(json.dumps(TOOL))
        if label == "wrong_cell":
            observed["arguments"]["index"] += 1
        with patch.object(research, "ROOT", work), patch.object(stage2, "ROOT", work):
            registry = research.open_registry()
            bridge = stage2.bridge_for_attempt(ATTEMPT, registry=registry)
            before = fingerprints(runtime)
            usage = registry.snapshot()["usage"]
            if label in ("missing_dispatch", "wrong_cell"):
                try:
                    stage2.settle_research_result(bridge, ATTEMPT, observed)
                except ValueError:
                    pass
                else:
                    raise AssertionError(label + " was accepted")
                assert before == fingerprints(runtime), label + " wrote artifacts"
                events = [len(journal.read_bytes().splitlines())]
            else:
                events = [len(journal.read_bytes().splitlines())]
                for repeat in range(2):
                    result = stage2.settle_research_result(bridge, ATTEMPT, observed)
                    assert result.status == "failed"
                    events.append(len(journal.read_bytes().splitlines()))
                assert events == ([15, 17, 17] if label == "15_17_17_recovery" else [17, 17, 17])
                if label == "original_17_replay":
                    assert before == fingerprints(runtime)
            assert registry.snapshot()["usage"] == usage
            assert not bridge.store.exists(bridge._record(ATTEMPT)["result_key"])
            cases.append({"case": label, "passed": True, "events": events,
                          "usage_unchanged": True, "success_result_absent": True})
assert fingerprints(ROOT / "audit/runtime") == real_before
assert (ROOT / "config/budget.json").read_bytes() == budget
report = {"kind": "developer_isolated_original_packet_replay", "cases": cases,
          "original_packet_sha256": hashlib.sha256(PACKET.read_bytes()).hexdigest(),
          "real_runtime_unchanged": True, "real_budget_unchanged": True,
          "new_cloud_calls": 0, "independent_acceptance": False, "financial_evidence": False}
out = ROOT / ".git/repair-work/wr22_wr24/root_native_replay.json"
out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report))
