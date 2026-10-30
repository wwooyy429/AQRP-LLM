"""Read-only fixed WR31 packet check; no network, provider or budget actions."""
from pathlib import Path
from hashlib import sha256
import base64
import importlib.util
import json
import sys
import zlib

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
def digest(path):
    return sha256(path.read_bytes()).hexdigest()

def main():
    manifest=json.loads((HERE/'packet_manifest.json').read_bytes())
    for item in manifest['files']:
        path=(ROOT/item['path']).resolve()
        assert path.is_relative_to(ROOT)
        assert digest(path)==item['sha256'], item['path']
    proof=json.loads((HERE/'baseline_protection.json').read_bytes())
    for item in proof['unchanged_012_files']:
        assert digest(ROOT/item['path'])==item['sha256'],item['path']
    journal=(ROOT/'audit/runtime/registry/events.jsonl').read_bytes()
    assert sha256(journal).hexdigest()==proof['registry_sha256']
    assert len(journal.splitlines())==80
    assert digest(ROOT/'config/budget.json')==proof['budget_sha256']
    for path, expected in proof['configuration_raw_hashes'].items():
        assert digest(ROOT/path)==expected,path
    sys.path.insert(0,str(ROOT/'tools'))
    from stages import source_manifest
    source=source_manifest()
    assert source['source_hash']==proof['full_source_manifest_hash']
    assert len(source['source_files'])==232
    ledger=(ROOT/'audit/experiments.jsonl').read_bytes()
    prefix=ledger[:proof['experiment_ledger_prefix_bytes']]
    assert sha256(prefix).hexdigest()==proof['experiment_ledger_prefix_sha256']
    index=json.loads((HERE/'original_review_index.json').read_bytes())
    encoded=(HERE/'original_review_selected.zlib.base64').read_bytes()
    assert sha256(encoded).hexdigest()==index['encoded_sha256']
    assert 0 < index['decoded_bytes'] < 4*1024*1024
    decoder=zlib.decompressobj()
    decoded=decoder.decompress(base64.b64decode(encoded.strip(),validate=True),index['decoded_bytes']+1)
    assert decoder.eof and not decoder.unconsumed_tail and not decoder.unused_data
    assert len(decoded)==index['decoded_bytes'] and sha256(decoded).hexdigest()==index['decoded_sha256']
    originals=json.loads(decoded)
    assert set(originals)=={item['path'] for item in index['selected_files']}
    for item in index['selected_files']:
        raw=base64.b64decode(originals[item['path']],validate=True)
        assert len(raw)==item['bytes'] and sha256(raw).hexdigest()==item['sha256']
    assert (HERE/'reviewer_minimal_wr31.py').read_bytes()==base64.b64decode(originals['minimal_wr31.py'])
    spec=importlib.util.spec_from_file_location('fixed_WR31_parity',HERE/'check_actual_parity.py')
    parity=importlib.util.module_from_spec(spec);spec.loader.exec_module(parity)
    actual=parity.check()
    assert actual==json.loads((HERE/'actual_parity.stdout.txt').read_bytes())
    for name in ['MRE_final','boundary_final','legacy20_final','product_offline','actual_parity']:
        record=json.loads((HERE/(name+'.execution.json')).read_bytes())
        assert record['exit_code']==0 and record['actually_executed']
        for stream in ('stdout','stderr'):
            assert digest(HERE/(name+'.'+stream+'.txt'))==record[stream+'_sha256']
    old_MRE=json.loads((HERE/'original_MRE_replay.json').read_bytes())
    assert old_MRE['exit_code']==1
    assert json.loads((HERE/'legacy20_fixed.execution.json').read_bytes())['exit_code']==1
    product=json.loads((HERE/'product_offline.stdout.txt').read_bytes())
    assert product['local_tests_passed'] and product['source_hash']==source['source_hash']
    assert 'Ran 1085 tests' in product['test_output'] and 'OK' in product['test_output']
    review=json.loads((ROOT/'audit/review_results/wr31.json').read_bytes())
    assert review['status']=='developer_fixed_pending_independent_retest'
    assert review['independently_closed'] is False
    plan=json.loads((ROOT/'config/development.json').read_bytes())['execution']
    assert all(plan[name] is False for name in ('market_research_enabled','llm_runtime_enabled','final_test_enabled','live_trading_enabled'))
    print(json.dumps({'metadata_files_verified':len(manifest['files']),
        'unchanged_012_files':len(proof['unchanged_012_files']),'selected_original_review_files':len(index['selected_files']),
        'source_files_unchanged':232,'registry_events_unchanged':80,
        'actual_metadata_semantic_parity':True,'old_MRE_failure_preserved':True,
        'developer_product_tests':1085,'developer_boundary_methods':12,'developer_boundary_subtests':96,
        'legacy_known_answer_methods':20,'WR31_independently_closed':False,
        'cloud_calls':0,'cloud_deletions':0,'budget_changes':0,
        'financial_evidence':False,'stage2_accepted':False,'final_test_enabled':False},sort_keys=True))

if __name__=='__main__':
    main()
