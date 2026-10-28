"""Read-only reconciliation plus a local replay of one frozen source file.

No QuantConnect calls, market-data reads, registration, debit or settlement.
Run on the fixed review checkout with its original protected audit artifacts.
"""
from hashlib import sha256
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
PACKAGE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
from git_protection import load_manifest, verify_export, read_replay_fixture
sys.path[:0] = [str(ROOT / "cloud"), str(ROOT / "tools")]
from qresearch.artifacts import FilesystemArtifactStore, content_hash
from qresearch.deployment_sources import build_manifest, parse_manifest
from qresearch.engineering_data import (DeploymentVerificationError, verify_deployment,
                                       verify_deployment_observation)
from qresearch.engineering_receipts import backtest_runtime_failure
from qresearch.registry import Registry
import stage2


def verify():
    protected_raw = (PACKAGE / "protected_before.json").read_bytes()
    protected = load_manifest((PACKAGE / "protected_git_baseline.json").read_bytes(), protected_raw)
    protection = verify_export(ROOT, protected, protected_raw)
    store = FilesystemArtifactStore(ROOT / "audit/runtime")
    baseline = json.loads(store.read_bytes("registry/baseline.json"))
    registry = Registry(store, baseline)
    snapshot = registry.snapshot()
    assert {name: value["total"] for name, value in snapshot["usage"].items()} == dict(configurations=12, research=15, lean=2)
    assert len((ROOT / "audit/runtime/registry/events.jsonl").read_bytes().splitlines()) == 48
    attempt = "37dc855045e14ca49c88fd9d75f40cf7"
    bridge = stage2.bridge_for_attempt(attempt, registry=registry)
    admission = stage2.admitted_input(bridge, attempt)
    payload, deployment = admission["payload"], admission["deployment"]
    assert parse_manifest(payload["deployment_manifest"])[0] == 1
    assert bridge._record(attempt)["status"] == "failed"
    assert deployment["input_hash"] == "8c9de804d671e13040a8aa765315937898ed8f9b1f28909606a5eff0a897dc03"
    packet_path = ROOT / ("audit/tool_observations/" + attempt + "-backtest-result.json")
    packet_raw = packet_path.read_bytes()
    assert sha256(packet_raw).hexdigest() == "61d3578b184d8667e73a53b2cdbfabc5c83570b6a652b17c554a9f076b92d497"
    native = backtest_runtime_failure(payload, deployment, "3e68866a46ca88ff16481c31b3c2c822", json.loads(packet_raw))
    assert native["platform"]["status"] == "runtime_error" and native["platform"]["terminal"] is True
    # A fixed, version-controlled source fixture enables .git-free replay. This
    # is the archived 662ccd source, not a fresh or recovered worker-file read.
    frozen = read_replay_fixture(ROOT)
    assert sha256(frozen).hexdigest() == "33ffa365d6b54d0a823574eaba5831c2f53c6aae7f2dff2c885b1d7ac0c9ca90"
    assert sha256(frozen + b"\n").hexdigest() == "5b7111b3806c2f4a8f93b85ffb8a54fa63cebdefb126bcc449c6020b95d3c4e5"
    legacy = {"engineering_smoke.py": sha256(frozen).hexdigest()}
    versioned = build_manifest({"engineering_smoke.py": frozen})
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        (root / "engineering_smoke.py").write_bytes(frozen + b"\n")
        try:
            verify_deployment(legacy, content_hash(legacy), source_root=root, worker_diagnostics=True)
        except DeploymentVerificationError as error:
            assert error.diagnostics["schema_version"] == 2
            assert error.diagnostics["observed_sha256"] == sha256(frozen + b"\n").hexdigest()
        else:
            raise AssertionError("Legacy EOF identity was weakened")
        observed = verify_deployment_observation(versioned, content_hash(versioned), source_root=root)
        assert observed["eof_normalized_file_count"] == 1
        assert observed["original_source_identity_match"] is False
        try:
            verify_deployment(versioned, content_hash(versioned), source_root=root, require_source_bytes=True)
        except DeploymentVerificationError:
            pass
        else:
            raise AssertionError("Local original source identity was weakened")
        (root / "engineering_smoke.py").write_bytes(frozen + b"\nCHANGED = True\n")
        try:
            verify_deployment(versioned, content_hash(versioned), source_root=root)
        except DeploymentVerificationError:
            pass
        else:
            raise AssertionError("Body change was accepted")
    assert verify_export(ROOT, protected, protected_raw) == protection
    return {"kind": "readonly_candidate_reconciliation_and_one_file_local_replay",
        "protected_files_unchanged": protection["protected_git_blobs_verified"], "registry_events": 48,
        "protected_git_baseline": protection,
        "global_usage": {name: value["total"] for name, value in snapshot["usage"].items()},
        "actual_original_LEAN_status": "runtime_error", "original_ledger_status": "failed",
        "legacy_manifest_version": 1, "original_input_retained": True,
        "synthetic_v2_one_LF_replay": "passed", "synthetic_local_strict_rejection": "passed",
        "replay_source": "pinned_662ccd_version_controlled_source_fixture",
        "replay_is_worker_file_observation": False,
        "synthetic_body_rejection": "passed", "actual_new_cloud_run": False,
        "cloud_calls": 0, "new_configurations": 0, "Research_executions": 0, "LEAN_submissions": 0,
        "stage2_accepted": False, "financial_evidence": False, "final_test_enabled": False}


if __name__ == "__main__":
    print(json.dumps(verify(), sort_keys=True))
