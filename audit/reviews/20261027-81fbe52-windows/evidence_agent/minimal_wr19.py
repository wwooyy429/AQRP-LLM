"""Recompute the declared ae-vs-old25 reference count. Read-only; zero tests.

Usage: python -B minimal_wr19.py <candidate-source> <existing-Git-clone>
No conclusion about actual/current cloud inventory is made.
"""
from pathlib import Path
import hashlib,io,json,subprocess,sys,tarfile
S=Path(sys.argv[1]).resolve();G=Path(sys.argv[2]).resolve()
ready=json.loads((S/'audit/stage2_current_readiness.json').read_text(encoding='utf-8-sig'))
ref=ready['platform_comparison_from_independent_review'];AE=ref['candidate_commit'];OLD=ref['runtime_source_commit']
archived=json.loads((S/'audit/reviews/20261027-ae2b898-windows/cloud_comparison.json').read_text(encoding='utf-8-sig'))
assert AE==archived['reviewed_source_commit']=='ae2b8985f3799c246e90341370f86d80483f63ed'
def sha(b):return hashlib.sha256(b).hexdigest()
def canon(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def lf(b):return b.decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n').encode()
def archive(rev):
 raw=subprocess.check_output(['git','-C',str(G),'archive',rev])
 with tarfile.open(fileobj=io.BytesIO(raw)) as t:return {m.name:t.extractfile(m).read() for m in t.getmembers() if m.isfile()}
ae=archive(AE);old=archive(OLD)
deployment=json.loads(ae['audit/deployment.json']);ae_manifest={p[6:]:sha(lf(b)) for p,b in ae.items() if p.startswith('cloud/') and p.endswith('.py')}
assert len(ae_manifest)==29 and ae_manifest==deployment['source_files']
old25={v['path']:v for v in archived['files'] if v['path']!='_engineering_task_input.py'}
assert len(old25)==25
assert all(sha(old['cloud/'+p])==row['cloud_utf8_sha256']==row['historical_baseline_raw_sha256'] for p,row in old25.items())
assert all(sha(ae['cloud/'+p])==row['candidate_raw_sha256'] for p,row in old25.items())
raw_diff=sorted(p for p in old25 if ae['cloud/'+p]!=old['cloud/'+p])
lf_diff=sorted(p for p in old25 if lf(ae['cloud/'+p])!=lf(old['cloud/'+p]))
absent=sorted(set(ae_manifest)-set(old25));declared=ref['candidate_different_or_missing_paths']
lines=(S/'audit/stage2_current_readiness.json').read_text(encoding='utf-8-sig').splitlines()
line=next(i for i,v in enumerate(lines,1) if '"candidate_different_or_missing_paths"' in v)
out={'fixed_candidate_source':'81fbe5294055423e88ee5aeae48ca6223e7971da','field_candidate_commit':AE,'old25_reference_commit':OLD,
 'source_file':'audit/stage2_current_readiness.json','source_line':line,'original_line':lines[line-1],
 'declared':declared,'raw_different_count':len(raw_diff),'LF_different_count':len(lf_diff),'different_paths':raw_diff,
 'absent_from_old25_reference_count':len(absent),'absent_from_old25_reference_paths':absent,
 'computed_raw_total':len(raw_diff)+len(absent),'computed_LF_total':len(lf_diff)+len(absent),
 'ae29_deployment_hash':sha(canon(ae_manifest)),'ae_manifest_identity_verified':True,
 'historical_top_level_scope_unchanged':ready['deployment_comparison_scope'],
 'limitation':'Only historical old25 known-file reference vs fixed ae29 deployment. Does not certify full old/current cloud inventory or actual absence. No new platform read, software suite or budget mutation.'}
print(json.dumps(out,ensure_ascii=False,indent=2))
raise SystemExit(0 if declared==len(raw_diff)+len(absent)==len(lf_diff)+len(absent) else 1)
