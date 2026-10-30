"""Synthetic input-binding counterexample; no SDK, worker or remote calls.
Usage: python -B minimal_wr18.py SOURCE. Repair must reject without writes and exit 0; original baseline exits 1.
"""
from pathlib import Path
from copy import deepcopy
import json, sys
S = Path(sys.argv[1]).resolve()
sys.dont_write_bytecode = True
sys.path.insert(0, str(S/'cloud'))
from qresearch.artifacts import MemoryArtifactStore, canonical_json, content_hash
from qresearch.registry import Registry, RegistryError
from qresearch.engineering_tasks import EngineeringTaskPlan, EngineeringTaskBridge, EngineeringTaskError
from qresearch.collection import HistoricalCollectionPlan

def fixture():
    raw = json.loads((S/'audit/stage2_joint_preview.json').read_text(encoding='utf-8'))['plan']
    plan = EngineeringTaskPlan.from_dict(raw, discovered_project_ids=[raw['project_id']])
    limits = {k:dict(total=n, normal=n, reserve=0) for k,n in [('configurations',12),('research',20),('lean',16)]}
    r = Registry(MemoryArtifactStore(), limits)
    b = EngineeringTaskBridge(r, plan); b.register(); a = b.claim('research')
    p = b.payload(a); ident = p['identity']; ext = 'qc-research:'+str(raw['project_id'])+':'+a.attempt_id
    dep = dict(source_manifest_hash=raw['source_manifest_hash'], deployment_hash=raw['deployment_hash'], input_hash='d'*64)
    refs = {'resolved_registry_ref':{'key':'synthetic/registry.json','sha256':'1'*64},
            'resolved_request_ref':{'key':'synthetic/request.json','sha256':'2'*64}}
    resolution = dict(resolved_request_hash='2'*64, resolved_registry_hash='1'*64,
        resolution_artifact_hash=content_hash(refs), tickers=['AAPL','MSFT'], ticker_count=2,
        permanent_sid_count=2, method=raw['symbol_resolution']['method'], **refs)
    child = raw['collection_probe']
    cp = HistoricalCollectionPlan.from_dict(child['collection_plan'], field_catalog=child['field_catalog'])
    probe = dict(schema_version=1, plan_hash=cp.hash,
        receipt_ref={'key':raw['report_namespace']+'/collection-probes/'+plan.hash+'/'+a.attempt_id+'.json','sha256':'3'*64},
        window_count=40, record_count=40, source_fetch_calls=40, reused_windows=0,
        empty_windows=0, cache_only_source_fetch_calls=0, missing_values=dict.fromkeys(child['field_catalog'],0))
    probe.update(dict.fromkeys(['full_historical_US200_certified','actual_availability_certified',
        'research_certified','row_values_exported','financial_vintage_certified'],False))
    report = dict(schema_version=1, identity=ident, status='completed', terminal=True,
        checks=dict.fromkeys(raw['required_checks']['research'],True), resolution=resolution,
        statistics=dict(record_count=2, history_calls_first=1, history_calls_second=0, expected_formation_count=1),
        evidence={'collection_probe':probe})
    report.update(dict.fromkeys(['market_values_exported','economic_factor_tested','final_data_accessed',
                                'full_US200_coverage_certified','actual_availability_verified'],False))
    sub = dict(identity=ident, identity_kind=p['external_identity_kind'], external_id=ext,
        accepted=True, status='submitted', deployment=dep, raw_receipt={'synthetic':True})
    obs = dict(platform=dict(identity=dict(ident, external_id=ext), terminal=True, status='completed',
                            deployment=deepcopy(dep), raw_receipt={'synthetic':True}),
               cloud_report=report, report_ref={'key':p['report_key'],'sha256':content_hash(report)})
    b.record_submission(a, sub)
    return r,b,a,p,obs,ext

# Positive control: a matching Bridge completion permits LEAN.
r,b,a,p,obs,ext = fixture()
assert b.consume_completion(a, completion_source=lambda _:obs).status == 'completed'
assert r.begin_attempt(b.config_id,'lean',operation_key=b._operation('lean')).should_execute
print('matching completion: LEAN permitted')

r,b,a,p,obs,ext = fixture()
obs['platform']['deployment']['input_hash'] = 'e'*64
try:
    b.consume_completion(a, completion_source=lambda _:obs)
except EngineeringTaskError as exc:
    print('Bridge refused:', exc)
else:
    raise AssertionError('Bridge unexpectedly accepted conflicting input')
digest = content_hash(obs)
key = 'engineering/evidence/'+a.attempt_id+'/completion/'+digest+'.json'
r.store.write_once(key, canonical_json(obs))
result = dict(scope='engineering', identity=p['identity'], external_id=ext,
    cloud_report=obs['cloud_report'], report_ref=obs['report_ref'],
    platform_evidence_ref={'key':key,'sha256':digest}, financial_evidence=False)
r.complete(a,result,external_id=ext)
before_usage = r.snapshot()['usage']
before_artifacts = deepcopy(r.store._data)
refused = False
try:
    r.begin_attempt(b.config_id, 'lean', operation_key=b._operation('lean'))
except RegistryError as exc:
    refused = True
    print('Registry refused:', exc)
assert refused, 'WR-18: conflicting Research input admitted'
assert r.snapshot()['usage'] == before_usage
assert r.store._data == before_artifacts
print('repaired: matching allowed, conflicting refused, no new artifacts/debit')
