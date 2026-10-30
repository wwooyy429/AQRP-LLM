"""Synthetic legacy callback bypass reproducer; never opens the real Registry."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT / name) for name in ("cloud", "tests", "tools")]
from test_certification_tasks import CertificationTasksTests
from qresearch.certification_tasks import CertificationTaskBridge

CertificationTasksTests.setUpClass()
case = CertificationTasksTests()
case.setUp()
wrapper = case.wrapper()
external = "qc-research:17:" + case.attempt.attempt_id
receipt = {"identity": case.payload["identity"], "identity_kind": "logical_research_execution_receipt",
    "accepted": True, "external_id": external, "status": "submitted", "deployment": case.deployment,
    "raw_receipt": {"accepted": True}}
completion = {"platform": {"identity": dict(case.payload["identity"], external_id=external),
    "terminal": True, "status": "completed", "deployment": case.deployment, "raw_receipt": {"completed": True}}, **wrapper}
blocked = False
try:
    case.bridge.record_submission(case.attempt, receipt)
    outcome = case.bridge.consume_completion(case.attempt, completion_source=lambda _: completion)
except ValueError:
    blocked = True
    outcome = None
print(json.dumps({"legacy_callbacks_blocked": blocked, "status": outcome.status if outcome else None,
    "dispatch_binding_exists": case.local.exists("certification/research-dispatch/" + case.attempt.attempt_id + ".json"),
    "real_cloud_calls": 0, "real_budget_mutations": 0}))
assert blocked, "Legacy callback completed a certification task without native dispatch/result proof"
