from pathlib import Path
import json

root=Path.cwd()
for name in ['audit/stage2_current_readiness.json', 'audit/review_tracking.json']:
    obj=json.loads((root/name).read_text(encoding='utf-8-sig'))
    excluded={'historical_independent_scope','latest_completed_independent_review','stage_acceptance','closed_findings','closed_software_findings_from_independent_reports'}
    print(name)
    print(json.dumps({k:v for k,v in obj.items() if k not in excluded},ensure_ascii=True,indent=2))
