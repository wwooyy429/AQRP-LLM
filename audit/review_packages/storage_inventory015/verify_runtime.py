"""Read-only replay of the delivered same-attempt native inventory evidence."""
from contextlib import redirect_stdout
from io import StringIO
from hashlib import sha256
from pathlib import Path
import importlib.util,json,sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path[:0]=[str(ROOT/'cloud'),str(ROOT/'tools')]
def main():
    manifest=json.loads((HERE/'runtime_packet_manifest.json').read_bytes())
    for item in manifest['files']:
        p=(ROOT/item['path']).resolve();assert p.is_relative_to(ROOT)
        assert sha256(p.read_bytes()).hexdigest()==item['sha256'],item['path']
    from storage_inventory import bridge_for_attempt
    from research import open_registry
    from stages import source_manifest
    from collection_task_cli import execution_source_manifest
    from qresearch.artifacts import decode_events
    from qresearch.storage_inventory_tasks import native_observation,admitted_input,_binding
    attempt='d22d36298ece423da53ed13817dd9b2e'
    before=(ROOT/'audit/runtime/registry/events.jsonl').read_bytes()
    registry=open_registry();bridge=bridge_for_attempt(attempt);snapshot=registry.snapshot()
    record=[r for r in snapshot['attempts'] if r['attempt_id']==attempt][0]
    assert record['status']=='completed' and record['stage']=='research'
    expected=json.loads((HERE/'settled_result.json').read_bytes())
    assert bridge.read_result(attempt)==expected
    payload=admitted_input(bridge,attempt)['payload'];binding=_binding(bridge.store,payload)
    envelope=json.loads((HERE/'execute_cell_native.json').read_bytes())
    observed=native_observation(payload,binding,envelope)
    assert observed['observation']['report']==expected['report']
    assert observed['observation']['status']=='completed'
    assert binding['arguments']=={'projectId':38436695,'index':2}
    assert binding['cell_source_sha256']=='321c62f1debd35b4f0d1f015e8b96b4c948341ebbb673659eafa4efd8107933b'
    assert sha256((HERE/'actual_cell_source.py').read_bytes()).hexdigest()==binding['cell_source_sha256']
    worker=(ROOT/'cloud/qresearch/storage_inventory.py').read_bytes()
    assert sha256(worker).hexdigest()==payload['identity']['worker_sha256']=='9f60769abc5430d2501e563750dcf13100662e7e181a450407ba8f0722981763'
    write=json.loads((HERE/'worker_native_exact_arguments.json').read_bytes())
    assert write['worker_write']['arguments']['content'].encode()==worker
    assert write['worker_readback']['result']['structuredContent']['content'].encode()==worker
    timing=json.loads((HERE/'execute_timing.json').read_bytes());assert timing['actual_execute_calls']==1
    cap=expected['report']['capacity_after']
    assert expected['report']['capacity_before']==cap and expected['report']['metadata_observation_stable']
    assert (cap['used_files'],cap['used_size_bytes'],cap['free_size_bytes'])==(488,52374905,53895)
    assert cap['lean_required_bytes']==73728 and cap['lean_byte_envelope_sufficient'] is False
    assert cap['lean_required_bytes']-cap['free_size_bytes']==19833
    spec=importlib.util.spec_from_file_location('fixed_inventory015_analysis',HERE/'analyze_actual.py')
    analyzer=importlib.util.module_from_spec(spec);spec.loader.exec_module(analyzer)
    capture=StringIO()
    with redirect_stdout(capture):analyzer.main()
    analysis=json.loads(capture.getvalue());assert analysis==json.loads((HERE/'actual_analysis.stdout.txt').read_bytes())
    assert analysis['typed_reference_summary']['edges']==229
    assert analysis['payload_review_pool_summary']['objects']==16
    assert analysis['payload_review_pool_summary']['exact_physical_bytes']==2772902
    assert analysis['confirmed_reclaimable_bytes']==0 and analysis['potential_reclaimable_total_bytes'] is None
    original=json.loads((HERE/'preregistration.json').read_bytes())
    assert len(decode_events(before))==86
    assert sha256(b''.join(before.splitlines(keepends=True)[:80])).hexdigest()==original['original_registry_sha256']
    protection=json.loads((HERE/'runtime_protection.json').read_bytes())
    assert sha256(before).hexdigest()==protection['registry_sha256']
    assert sha256((ROOT/'config/budget.json').read_bytes()).hexdigest()==protection['budget_sha256']
    assert snapshot['usage']==protection['usage']
    cycle=registry.configuration_cycle_snapshot();assert cycle['usage']['total']==5 and cycle['capacity']['total']==13
    assert snapshot['usage']['configurations']['total']==18 and snapshot['usage']['research']['total']==19 and snapshot['usage']['lean']['total']==4
    round_record=registry.engineering_rounds_snapshot()['stage2-object-store-inventory015']
    assert round_record['status']=='closed' and round_record['usage']=={'configurations':1,'research':1,'lean':0}
    source=source_manifest();software=json.loads((HERE/'software_report.json').read_bytes())
    test=json.loads((ROOT/'audit/stage_verification.json').read_bytes())
    assert test['local_tests_passed'] and 'Ran 1135 tests' in test['test_output']
    assert test['source_hash']==software['full_source_manifest_hash']
    assert [name for name in source['source_files'] if source['source_files'][name]!=test['source_files'][name]]==['config/budget.json']
    assert execution_source_manifest()['source_hash']==software['stable_execution_source_manifest_hash']==protection['stable_execution_source_hash']
    for name in ('current_review_status.json','current_review_package.json','stage2_current_readiness.json'):
        value=json.loads((ROOT/'audit'/name).read_bytes())
        assert value['stage2_accepted'] is False and value['financial_evidence'] is False and value['final_test_enabled'] is False
        assert value['storage_inventory_WR31']['independently_closed'] is True
        assert value['current_storage_inventory']['status']=='completed'
        assert value['current_storage_inventory']['round_status']=='closed'
    execution=json.loads((ROOT/'config/development.json').read_bytes())['execution']
    assert all(execution[k] is False for k in ('market_research_enabled','llm_runtime_enabled','final_test_enabled','live_trading_enabled'))
    assert (ROOT/'audit/runtime/registry/events.jsonl').read_bytes()==before
    print(json.dumps({'runtime_metadata_files_verified':len(manifest['files']),'native_same_attempt_replayed':True,
        'native_status':'completed','round_closed':True,'worker_source_exact':True,'actual_Research_executions':1,
        'new_Research_calls_by_this_verifier':0,'actual_LEAN_submissions':0,'objects':488,'object_hashes':438,
        'typed_refs':229,'free_bytes':53895,'LEAN_byte_shortfall':19833,'confirmed_reclaimable_bytes':0,
        'configuration_cycle_used':5,'Research_used':19,'LEAN_used':4,'Registry_events':86,'old80_raw_prefix_preserved':True,
        'full_product_tests_at_fixed_software_source':1135,'new_independent_acceptance':False,
        'stage2_accepted':False,'financial_evidence':False,'final_test_enabled':False},sort_keys=True))
if __name__=='__main__':main()
