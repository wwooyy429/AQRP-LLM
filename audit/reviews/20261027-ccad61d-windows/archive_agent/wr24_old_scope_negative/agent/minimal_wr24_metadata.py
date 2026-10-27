"""Read-only metadata consistency reproduction; no product or market tests."""
from pathlib import Path
import hashlib,json,subprocess,sys
S=Path(__file__).resolve().parent.parent/'source'
G=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\repo')
B='deb85d9f27441b275ab8b108f0232ecd2707a1e8';C='ea6053e3e9ef4be17db246daf18a4cf9b2e5be58'
d=json.loads((S/'audit/stage2_current_readiness.json').read_bytes())
delta=subprocess.check_output(['git','-C',str(G),'diff','--name-only',B,C],text=True).splitlines()
source_delta={p for p in delta if p.startswith(('cloud/','tests/','tools/')) and p.endswith('.py')}
declared=set(d['source_changed_this_round'])
baseline_journal=subprocess.check_output(['git','-C',str(G),'show',B+':audit/runtime/registry/events.jsonl'])
current_journal=(S/'audit/runtime/registry/events.jsonl').read_bytes()
assert current_journal==baseline_journal, 'Precondition: authoritative journal must be byte-identical'
assert d['new_configuration_count']==d['new_Research_execution_count']==0
assert d['current_candidate_change_scope']=='offline_WR20_WR21_only_no_new_real_dispatch'
claims={
    'current_new_config_and_Research_scope':not ('One new engineering configuration' in d['source_configuration_budget_changed_scope'] and 'one Research precharge' in d['source_configuration_budget_changed_scope']),
    'current_source_changed_this_round_matches_pinned_diff':declared==source_delta,
}
result={'finding':'WR-24','source_commit':C,'baseline_commit':B,'readonly':True,
    'journal_raw_sha256':hashlib.sha256(current_journal).hexdigest(),
    'journal_equal_baseline':True,'new_configuration_count':d['new_configuration_count'],'new_Research_execution_count':d['new_Research_execution_count'],
    'current_candidate_change_scope':d['current_candidate_change_scope'],
    'stale_source_configuration_budget_changed_scope':d['source_configuration_budget_changed_scope'],
    'stale_current_read_scope':d['read_or_polled_this_turn_scope'],
    'declared_unchanged_files':sorted(declared-source_delta),'missing_changed_files':sorted(source_delta-declared),
    'checks':claims,'failure_is_documentation_metadata_not_actual_budget_consumption':True,'independent_product_test_methods':0}
print(json.dumps(result,ensure_ascii=False,indent=2))
assert all(claims.values()),'WR-24: active current-round metadata still carries previous-round claims'
