"""Verify fixed inventory metadata, recompute the assessment, never contact QC."""
from pathlib import Path
from hashlib import sha256
import base64
import importlib.util
import json
import sys
import zlib

PACKET = Path(__file__).resolve().parent
ROOT = PACKET.parents[2]


def main():
    manifest = json.loads((PACKET/'packet_manifest.json').read_bytes())
    for item in manifest['files']:
        path = (ROOT/item['path']).resolve()
        assert path.is_relative_to(ROOT)
        assert sha256(path.read_bytes()).hexdigest() == item['sha256'], item['path']
    proof = json.loads((PACKET/'protection_check.json').read_bytes())
    journal = (ROOT/'audit/runtime/registry/events.jsonl').read_bytes()
    assert len(journal.splitlines()) == 80 and sha256(journal).hexdigest() == proof['registry_sha256']
    assert sha256((ROOT/'config/budget.json').read_bytes()).hexdigest() == proof['budget_sha256']
    sys.path.insert(0, str(ROOT/'tools'))
    from stages import source_manifest
    source = source_manifest()
    assert source['source_hash'] == proof['full_source_manifest_hash']
    assert len(source['source_files']) == 232
    index = json.loads((PACKET/'raw_UI_metadata_index.json').read_bytes())
    encoded = (PACKET/index['path']).read_bytes()
    assert sha256(encoded).hexdigest() == index['encoded_sha256']
    assert 0 < index['decoded_bytes'] < 4*1024*1024
    decoder = zlib.decompressobj()
    original = decoder.decompress(base64.b64decode(encoded.strip(), validate=True), index['decoded_bytes']+1)
    assert decoder.eof and not decoder.unconsumed_tail and not decoder.unused_data
    assert len(original) == index['decoded_bytes'] and sha256(original).hexdigest() == index['decoded_sha256']
    originals = json.loads(original)
    assert originals['capacity_blocks'][-1]['observation']['display_usage'] == 'Usage: 49.95 MB/50 MB'
    spec = importlib.util.spec_from_file_location('fixed_inventory_metadata_analyzer', PACKET/'analyze_inventory.py')
    analyzer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(analyzer)
    names = {'observations':'ui_observations.json','roots':'local_reference_roots.json','rules':'reference_rules.json'}
    inputs = {key:(PACKET/value).read_bytes() for key,value in names.items()}
    recomputed = analyzer.analyze(*(json.loads(inputs[key]) for key in ('observations','roots','rules')))
    recomputed['input_sha256'] = {key:sha256(raw).hexdigest() for key,raw in inputs.items()}
    assert recomputed == json.loads((PACKET/'object_assessment.pagination_fixed.json').read_bytes())
    assert recomputed['unique_UI_leaf_objects'] == 456
    assert recomputed['directories_observed'] == 31
    assert all(row['all_entries_observed_at_UI_metadata_level'] for row in recomputed['directories'])
    assert len(recomputed['unvisited_child_directories']) == 10
    assert recomputed['global_reference_closure_complete'] is False
    assert recomputed['confirmed_reclaimable_bytes'] == 0 and recomputed['potential_reclaimable_total_bytes'] is None
    assert all(row['deletion_authorized'] is False for row in recomputed['objects'])
    print(json.dumps({'metadata_files_verified':len(manifest['files']),
        'assessment_recomputed':True,'source_files_unchanged':232,'registry_events_unchanged':80,
        'observed_UI_leaf_objects':456,'visited_directories':31,'protected_unvisited_subtrees':10,
        'confirmed_reclaimable_bytes':0,'potential_reclaimable_bytes':None,
        'cloud_calls':0,'budget_changes':0,'cloud_deletions':0,
        'independent_acceptance':False,'financial_evidence':False,'final_test_enabled':False},sort_keys=True))


if __name__ == '__main__':
    main()
