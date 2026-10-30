"""Recompute the saved 012 metadata with 013, without provider calls or writes."""
from hashlib import sha256
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / 'storage_inventory012'

def check():
    spec = importlib.util.spec_from_file_location('WR31_actual_metadata_analyzer', HERE/'analyze_inventory.py')
    analyzer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(analyzer)
    names = {'observations':'ui_observations.json', 'roots':'local_reference_roots.json', 'rules':'reference_rules.json'}
    inputs = {key:(OLD/name).read_bytes() for key,name in names.items()}
    docs = {key:json.loads(raw) for key,raw in inputs.items()}
    result = analyzer.analyze(*(docs[key] for key in ('observations','roots','rules')))
    result['input_sha256'] = {key:sha256(raw).hexdigest() for key,raw in inputs.items()}
    original = json.loads((OLD/'object_assessment.pagination_fixed.json').read_bytes())
    assert result == original, 'Saved actual metadata assessment changed'
    observations = docs['observations']['observations']
    assert len(observations) == 63
    for observation in observations:
        assert isinstance(observation['paging'], list) and len(observation['paging']) == 2
        assert sum(bool(analyzer.RANGE.fullmatch(text.strip(' \t'))) for text in observation['paging']) == 1
        assert sum(bool(analyzer.PAGE.fullmatch(text.strip(' \t'))) for text in observation['paging']) == 1
    assert result['unique_UI_leaf_objects'] == 456 and result['directories_observed'] == 31
    assert all(row['all_entries_observed_at_UI_metadata_level'] for row in result['directories'])
    assert len(result['unvisited_child_directories']) == 10
    assert len(result['same_digest_basename_review_groups']) == 96
    assert result['confirmed_reclaimable_objects'] == [] and result['confirmed_reclaimable_bytes'] == 0
    assert result['potential_reclaimable_total_bytes'] is None
    assert result['global_reference_closure_complete'] is False
    assert all(row['deletion_authorized'] is False for row in result['objects'])
    canonical = json.dumps(result,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode('utf-8')
    # These are resolver boundary checks only; they never create output files.
    for raw, output in [(OLD/'forbidden_output.json',True),(HERE.parent/'outside.json',False),
                        (HERE/'../storage_inventory012/forbidden_output.json',True)]:
        try:
            analyzer.packet_path(raw,output=output)
        except ValueError:
            pass
        else:
            raise AssertionError('Path boundary unexpectedly allowed')
    assert analyzer.packet_path(OLD/'ui_observations.json') == (OLD/'ui_observations.json').resolve()
    assert analyzer.packet_path(HERE/'future_output.json',output=True) == (HERE/'future_output.json').resolve()
    return {'saved_observations_recomputed':63,'complete_labels_checked':126,'semantic_assessment_unchanged':True,
            'semantic_assessment_sha256':sha256(canonical).hexdigest(),'observed_leaf_objects':456,
            'visited_directories':31,'protected_unvisited_subtrees':10,'same_digest_identity_groups':96,
            'confirmed_reclaimable_bytes':0,'potential_reclaimable_bytes':None,
            'path_resolver_checks':5,'cloud_calls':0,'cloud_deletions':0,'budget_changes':0,
            'financial_evidence':False,'independent_acceptance':False,'final_test_enabled':False}

if __name__ == '__main__':
    print(json.dumps(check(),sort_keys=True))
