from pathlib import Path
import hashlib,json
R=Path(__file__).resolve().parent;ROOT=R.parent;S=ROOT/'source';A=ROOT/'archive_source'
checks=[]
for folder in ['audit/reviews/20261028-4a42c18-eofv2','audit/review_packages/wr28/originals']:
 left={p.relative_to(S/folder).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()for p in(S/folder).rglob('*')if p.is_file()}
 right={p.relative_to(A/folder).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()for p in(A/folder).rglob('*')if p.is_file()}
 checks.append({'path':folder,'files':len(left),'candidate_to_later_archive_exact_raw_bytes':left==right})
 assert left==right,folder
result={'logical_static_checks':2,'passed':2,'unit_methods':0,'checks':checks,'source_or_budget_writes':0,'platform_calls':0}
(R/'final_preservation_results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result))
