"""Read-only registration/original checks, not product tests or market evidence."""
from pathlib import Path
from hashlib import sha256
import base64,json,sys,zlib

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
def digest(path):return sha256(path.read_bytes()).hexdigest()
def main():
    manifest=json.loads((HERE/'packet_manifest.json').read_bytes())
    for item in manifest['files']:
        path=(ROOT/item['path']).resolve();assert path.is_relative_to(ROOT)
        assert digest(path)==item['sha256'],item['path']
    index=json.loads((HERE/'import_index.json').read_bytes())
    for item in index['primary_raw_files']:
        path=HERE/item['saved_path']
        assert len(path.read_bytes())==item['bytes'] and digest(path)==item['sha256']
    encoded=(HERE/'selected_evidence.zlib.base64').read_bytes()
    assert sha256(encoded).hexdigest()==index['encoded_sha256']
    assert 0<index['decoded_bytes']<4*1024*1024
    decoder=zlib.decompressobj()
    raw=decoder.decompress(base64.b64decode(encoded.strip(),validate=True),index['decoded_bytes']+1)
    assert decoder.eof and not decoder.unconsumed_tail and not decoder.unused_data
    assert len(raw)==index['decoded_bytes'] and sha256(raw).hexdigest()==index['decoded_sha256']
    originals=json.loads(raw)
    assert set(originals)=={item['path'] for item in index['selected_archive_files']}
    for item in index['selected_archive_files']:
        value=base64.b64decode(originals[item['path']],validate=True)
        assert len(value)==item['bytes'] and sha256(value).hexdigest()==item['sha256']
    report=json.loads((HERE/'reviewer_formal_report.json').read_bytes())
    finding=report['findings'][0]
    assert report['reviewed_audit_program_commit']=='d1776193d37748ef78da405af370e9190f597e2f'
    assert finding['status']=='fixed_verified_closed_for_tested_offline_audit_scope'
    assert report['new_open_findings']==[]
    product=[item for item in report['tests'] if item['name']=='开发产品全量归档'][0]
    assert product['methods']==1085 and product['actually_executed_by_reviewer_this_round'] is False
    assert product['raw_stdout_stderr_hashes_reparsed'] is True
    result=json.loads((ROOT/'audit/review_results/wr31.json').read_bytes())
    assert result['independently_closed'] is True and result['status']==finding['status']
    assert result['finding']==finding and result['review_id']==report['review_id']
    assert result['reviewer_full_product1085_rerun'] is False
    assert result['reviewer_reparsed_developer1085_records'] is True
    for name in ('current_review_status.json','current_review_package.json','stage2_current_readiness.json'):
        value=json.loads((ROOT/'audit'/name).read_bytes())
        assert value['stage2_accepted'] is False and value['financial_evidence'] is False and value['final_test_enabled'] is False
        nested=value['storage_inventory_WR31']
        assert nested['independently_closed'] is True and nested['status']==finding['status']
        assert nested['fixed_audit_commit']==report['reviewed_audit_program_commit']
        assert nested['whole_phase2_accepted'] is False
    current=json.loads((ROOT/'audit/current_review_status.json').read_bytes())
    assert not any(item['id']=='WR-31' for item in current['known_open_findings'])
    assert len([item for item in current['closed_findings'] if item['id']=='WR-31'])==1
    proof=json.loads((HERE/'protection.json').read_bytes())
    for item in proof['unchanged_historical_packet_files']:
        assert digest(ROOT/item['path'])==item['sha256'],item['path']
    journal=(ROOT/'audit/runtime/registry/events.jsonl').read_bytes()
    assert len(journal.splitlines())==80 and sha256(journal).hexdigest()==proof['registry_sha256']
    assert digest(ROOT/'config/budget.json')==proof['budget_sha256']
    ledger=(ROOT/'audit/experiments.jsonl').read_bytes()
    assert sha256(ledger[:proof['ledger_prefix_bytes']]).hexdigest()==proof['ledger_prefix_sha256']
    assert digest(ROOT/'audit/stage2_storage_inventory013_wr31_report.json')==proof['historical_developer_report_sha256']
    sys.path.insert(0,str(ROOT/'tools'))
    from stages import source_manifest
    source=source_manifest()
    assert len(source['source_files'])==232 and source['source_hash']==proof['source_manifest_hash']
    execution=json.loads((ROOT/'config/development.json').read_bytes())['execution']
    assert all(execution[k] is False for k in ('market_research_enabled','llm_runtime_enabled','final_test_enabled','live_trading_enabled'))
    assert report['visible_inventory']['review_pool_objects']==13
    assert result['objects456_subtrees10_review_pool13_retained'] is True
    assert result['confirmed_reclaimable_bytes']==0 and result['potential_reclaimable_total_bytes'] is None
    print(json.dumps({'WR31_status':finding['status'],'fixed_audit_commit':report['reviewed_audit_program_commit'],
        'metadata_files_verified':len(manifest['files']),'primary_originals':len(index['primary_raw_files']),
        'selected_evidence_originals':len(index['selected_archive_files']),
        'historical_packet_files_unchanged':len(proof['unchanged_historical_packet_files']),
        'product_source_files_unchanged':232,'registry_events_unchanged':80,
        'reviewer1085_rerun':False,'reviewer_reparsed_developer1085_records':True,
        'product_tests_rerun_this_registration':False,'cloud_calls':0,'budget_changes':0,
        'stage2_accepted':False,'financial_evidence':False,'final_test_enabled':False},sort_keys=True))

if __name__=='__main__':main()
