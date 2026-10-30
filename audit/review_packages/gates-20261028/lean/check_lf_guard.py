from pathlib import Path
import json
import sys
ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'cloud')]
from qresearch.artifacts import content_hash
from qresearch.engineering_data import verify_deployment,DeploymentVerificationError
native=json.loads((OUT/'delivered_failure_result.json').read_bytes())
manifest={'engineering_smoke.py':native['worker_diagnostic']['expected_sha256']}
verify_deployment(manifest,content_hash(manifest),source_root=OUT/'lf-guard-fixture/original',worker_diagnostics=True)
caught=False
try:
    verify_deployment(manifest,content_hash(manifest),source_root=OUT/'lf-guard-fixture/append_one_LF',worker_diagnostics=True)
except DeploymentVerificationError as error:
    caught=True
    observed=error.diagnostics
    assert observed['failure_kind']=='source_hash_mismatch'
    assert observed['observed_sha256']==native['worker_diagnostic']['observed_sha256']
    assert observed['worker_observation']['source_format']==native['worker_diagnostic']['worker_observation']['source_format']
assert caught
result=dict(kind='synthetic_known_answer_actual_shared_guard',original_accepted=True,
    append_one_LF_rejected=True,reported_sha_and_full_source_format_exact_match=True,
    actual_diagnostic=observed,only_one_declared_file=True,real_worker_raw_file_retrieved=False,
    first_helper_correction=dict(first_invocation_exit=1,error_kind='AttributeError',
        wrong_helper_field='diagnostic',actual_owned_exception_field='diagnostics',
        actual_guard_already_raised_expected_rejection_before_helper_error=True,
        original_tool_output_retained_in_chat=True,product_code_changed=False),
    real_ledger_writes=0,QC_calls=0,strict_identity_relaxed=False,financial_evidence=False)
(OUT/'lf_guard_check.json').write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
print(json.dumps({k:result[k] for k in ('original_accepted','append_one_LF_rejected','reported_sha_and_full_source_format_exact_match','real_ledger_writes')}))
