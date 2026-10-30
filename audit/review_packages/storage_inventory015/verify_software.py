"""Verify this fixed pre-dispatch software packet without market/provider calls."""
from pathlib import Path
from hashlib import sha256
import base64,json,sys,zlib
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
def main():
    manifest=json.loads((HERE/'software_packet_manifest.json').read_bytes())
    for item in manifest['files']:
        p=(ROOT/item['path']).resolve();assert p.is_relative_to(ROOT)
        assert sha256(p.read_bytes()).hexdigest()==item['sha256'],item['path']
    result=json.loads((HERE/'full_offline.stdout.txt').read_bytes())
    assert result['local_tests_passed'] and 'Ran 1135 tests' in result['test_output'] and 'OK' in result['test_output']
    sys.path[:0]=[str(ROOT/'cloud'),str(ROOT/'tools')]
    from stages import source_manifest
    from collection_task_cli import execution_source_manifest,built_deployment_manifest
    from qresearch.artifacts import content_hash
    from qresearch.storage_inventory_tasks import InventoryTaskPlan
    source=source_manifest();assert source['source_hash']==result['source_hash']
    assert len(source['source_files'])==238
    summary=json.loads((HERE/'software_report.json').read_bytes())
    assert execution_source_manifest()['source_hash']==summary['stable_execution_source_manifest_hash']
    deployment=built_deployment_manifest();assert len(deployment['files'])==49
    assert content_hash(deployment)==summary['full_local49_deployment_hash']
    preview=json.loads((HERE/'plan_preview.stdout.txt').read_bytes())
    plan=InventoryTaskPlan.from_dict(preview['plan'],discovered_project_ids=(38436695,))
    assert plan.hash==preview['plan_hash']
    assert sha256((ROOT/'cloud/qresearch/storage_inventory.py').read_bytes()).hexdigest()==preview['worker_source']['worker_sha256']
    assert content_hash(preview['package'])==preview['configuration_hash']
    original=json.loads((HERE/'preregistration.json').read_bytes())
    journal=(ROOT/'audit/runtime/registry/events.jsonl').read_bytes()
    assert len(journal.splitlines())==80 and sha256(journal).hexdigest()==original['original_registry_sha256']
    assert sha256((ROOT/'config/budget.json').read_bytes()).hexdigest()==original['original_budget_sha256']
    index=json.loads((HERE/'development_originals_index.json').read_bytes())
    encoded=(HERE/'development_originals.zlib.base64').read_bytes()
    assert sha256(encoded).hexdigest()==index['encoded_sha256'] and 0<index['decoded_bytes']<4*1024*1024
    d=zlib.decompressobj();raw=d.decompress(base64.b64decode(encoded.strip(),validate=True),index['decoded_bytes']+1)
    assert d.eof and not d.unconsumed_tail and not d.unused_data
    assert len(raw)==index['decoded_bytes'] and sha256(raw).hexdigest()==index['decoded_sha256']
    files=json.loads(raw);assert set(files)=={item['path'] for item in index['files']}
    for item in index['files']:
        content=base64.b64decode(files[item['path']],validate=True)
        assert len(content)==item['bytes'] and sha256(content).hexdigest()==item['sha256']
    assert json.loads((HERE/'synthetic_cell_roundtrip.execution.json').read_bytes())['exit_code']==0
    assert summary['registered_or_Research_executed_at_software_freeze'] is False
    assert summary['final_test_enabled'] is False and summary['independent_acceptance'] is False
    print(json.dumps({'software_full_source_hash':source['source_hash'],'source_files':238,'local_candidate_cloud_files':49,
        'fixed_worker_sha256':preview['worker_source']['worker_sha256'],'actual_synthetic_product_tests':1135,
        'metadata_files_verified':len(manifest['files']),'archived_development_originals':len(index['files']),
        'registry_events_before_dispatch':80,'Research_used_before_dispatch':18,'Research_executions_by_this_check':0,
        'stage2_accepted':False,'financial_evidence':False,'final_test_enabled':False},sort_keys=True))
if __name__=='__main__':main()
