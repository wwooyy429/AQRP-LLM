"""Check this fixed metadata migration; no provider or product-test execution."""
from pathlib import Path
from hashlib import sha256
import base64,json,sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
def main():
    manifest=json.loads((HERE/'packet_manifest.json').read_bytes())
    for item in manifest['files']:
        p=(ROOT/item['path']).resolve();assert p.is_relative_to(ROOT)
        assert sha256(p.read_bytes()).hexdigest()==item['sha256'],item['path']
    previous=json.loads((HERE/'previous_state.json').read_bytes())
    for item in previous['files']:
        raw=base64.b64decode(item['raw_base64'],validate=True)
        assert len(raw)==item['bytes'] and sha256(raw).hexdigest()==item['sha256']
        json.loads(raw)
    report=json.loads((HERE/'status_report.json').read_bytes())
    for item in (report['current_native_runtime_evidence'],report['current_independent_review_evidence']):
        assert sha256((ROOT/item['path']).read_bytes()).hexdigest()==item['sha256']
    state=json.loads((ROOT/'audit/stage2_current_readiness.json').read_bytes())
    runtime=state['current_real_runtime'];assert runtime['status']=='failed' and runtime['Registry_status']=='failed'
    assert runtime['round_closed'] is True and runtime['round_status']=='closed'
    assert runtime['failure_code']=='byte_capacity_insufficient' and runtime['automatic_notification_observed'] is False
    assert state['latest_completed_independent_review']['review_id']=='AQRP-20261030-D177619-WR31-30'
    assert 'current_real_runtime' in state['historical_state_references']
    assert state['current_activity']['new_settlement_and_closure_events']==0
    for name in ('stage2_current_readiness.json','current_review_status.json','current_review_package.json'):
        value=json.loads((ROOT/'audit'/name).read_bytes())
        assert value['stage2_accepted'] is False and value['financial_evidence'] is False and value['final_test_enabled'] is False
        assert value['storage_inventory_WR31']['independently_closed'] is True
    proof=json.loads((HERE/'raw_preservation.json').read_bytes())
    protected=0
    for path,expected in proof['unchanged_files'].items():
        # The original migration assertion covered all same-workspace raw files.
        # Git may carry LF source/config forms; archived runtime/history stays raw.
        if path.startswith(('audit/runtime/','audit/review_packages/')):
            assert sha256((ROOT/path).read_bytes()).hexdigest()==expected,path
            protected+=1
    journal=(ROOT/'audit/runtime/registry/events.jsonl').read_bytes()
    assert len(journal.splitlines())==80 and sha256(journal).hexdigest()==proof['registry_sha256']
    assert sha256((ROOT/'config/budget.json').read_bytes()).hexdigest()==proof['budget_sha256']
    sys.path.insert(0,str(ROOT/'tools'))
    from stages import source_manifest
    source=source_manifest();assert len(source['source_files'])==232
    assert source['source_hash']=='397c9cfe2130a0c36d7c8b8bd7cd0051a93c1556562dc03a9575139ba54c099c'
    print(json.dumps({'updated_current_documents':3,'old009_status':'failed/closed','WR31_scoped_closed':True,
        'metadata_files_verified':len(manifest['files']),'archived_runtime_history_raw_files_unchanged':protected,
        'source_files_unchanged':232,'registry_events':80,'product_tests_rerun':False,'cloud_calls_by_this_check':0,
        'budget_changes':0,'stage2_accepted':False,'final_test_enabled':False},sort_keys=True))
if __name__=='__main__':main()
