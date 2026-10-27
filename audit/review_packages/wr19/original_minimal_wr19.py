"""Recompute the archived comparison; does not read QuantConnect or market data.
Usage: python -B minimal_wr19.py SOURCE. Current metadata assertion exits 1.
"""
from pathlib import Path
import json,sys
S=Path(sys.argv[1]).resolve()
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
archive=S/'audit/reviews/20261027-ae2b898-windows'
summary=read(S/'audit/stage2_current_readiness.json')['platform_comparison_from_independent_review']
manifest=read(archive/'source_git_manifest.json')['candidate']
comparison=read(archive/'cloud_comparison.json')
assert summary['candidate_commit']==manifest['commit']==comparison['reviewed_source_commit']
candidate={k[len('cloud/'):]:v for k,v in manifest['files'].items() if k.startswith('cloud/') and k.endswith('.py')}
reference={x['path']:x['cloud_utf8_sha256'] for x in comparison['files'] if x['path']!='_engineering_task_input.py'}
different=sorted(k for k in candidate.keys()&reference.keys() if candidate[k]!=reference[k])
outside_reference=sorted(candidate.keys()-reference.keys())
expected=len(different)+len(outside_reference)
claimed=summary['candidate_different_or_missing_paths']
print(json.dumps({'candidate_commit':manifest['commit'],'candidate_paths':len(candidate),
 'old_known_reference_paths':len(reference),'different':different,'not_in_old_reference':outside_reference,
 'computed':expected,'declared':claimed,
 'boundary':'Four paths absent from the old known-file reference do not prove current cloud absence or inventory completeness.'},indent=2))
assert claimed==expected,f'WR-19: declared {claimed}, archived comparison computes {expected}'
