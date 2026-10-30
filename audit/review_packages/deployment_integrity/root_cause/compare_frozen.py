from pathlib import Path
import hashlib
import json
import subprocess

ROOT=Path(__file__).resolve().parents[3]
WORK=Path(__file__).resolve().parent
COMMIT='75f24629d3b7f94ff3aa906c3ce8a2b8b9a8d3c4'
ATTEMPT='bfd00f2611fd4496b9498d4597618a8e'
def sha(raw):return hashlib.sha256(raw).hexdigest()
def blob(name):return subprocess.check_output(['git','show',COMMIT+':'+name],cwd=ROOT)
def logical(raw):return raw.decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n').encode('utf-8')
admission=json.loads((ROOT/'audit/runtime/engineering/admitted-inputs'/f'{ATTEMPT}.json').read_bytes())
manifest=admission['payload']['deployment_manifest']
deployment=json.loads((ROOT/'audit/stage2_cloud_deployment.json').read_bytes())
preflight=json.loads((ROOT/'audit/stage2_next_preflight.json').read_bytes())
cloud={x['path']:x for x in preflight['source_comparisons']}
old_deployment=json.loads(blob('audit/deployment.json'))
rows=[]
for name,expected in sorted(manifest.items()):
    raw=blob('cloud/'+name)
    rows.append({'path':name,'frozen_sha256':expected,'git75_raw_sha256':sha(raw),
        'git75_runtime_text_sha256':sha(logical(raw)),
        'cloud_archived_UTF8_sha256':cloud[name]['UTF8_sha256'],
        'old_deployment_sha256':old_deployment['source_files'].get(name),
        'deployment_record_sha256':deployment['source_files'].get(name),
        'git75_bytes':len(raw),'git75_tail_hex':raw[-10:].hex(),
        'frozen_matches_git75_runtime_text':expected==sha(logical(raw)),
        'frozen_matches_cloud_archived_UTF8':expected==cloud[name]['UTF8_sha256']})
report={'kind':'readonly_frozen_manifest_direct_comparison','commit':COMMIT,'attempt':ATTEMPT,
    'paths':rows,'file_count':len(rows),
    'frozen_vs_git75_runtime_mismatches':[x['path'] for x in rows if not x['frozen_matches_git75_runtime_text']],
    'frozen_vs_cloud_archive_mismatches':[x['path'] for x in rows if not x['frozen_matches_cloud_archived_UTF8']],
    'frozen_equals_original_deployment':manifest==old_deployment['source_files'],
    'frozen_equals_original_upload_record':manifest==deployment['source_files'],
    'source_commit75_manifest':json.loads(blob('audit/stage_verification.json')).get('source_hash'),
    'market_or_QC_calls':0,'tracked_files_modified':False}
(WORK/'frozen_comparison.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='paths'}))
