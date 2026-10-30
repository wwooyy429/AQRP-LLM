from pathlib import Path
import hashlib
import json
import subprocess

ROOT=Path(__file__).resolve().parents[3]
COMMIT='4a94430144cd3d9e4b5469bd2b6e4a48d80d5fc7'
OUT=Path(__file__).resolve().parent
CACHE={}
def digest(data):return hashlib.sha256(data).hexdigest()
def blob(path):return CACHE[path] if path in CACHE else subprocess.check_output(['git','show',COMMIT+':'+path],cwd=ROOT)
mfpath='audit/review_packages/wr14/developer_outputs_manifest.json'
vfpath='audit/review_packages/wr14/developer_verification.json'
mfraw=blob(mfpath)
vf=json.loads(blob(vfpath))
mf=json.loads(mfraw)
work=(ROOT/mfpath).read_bytes()
baseline={'declared':vf['developer_outputs_manifest_raw_sha256'],
 'fixed_git_raw_sha256':digest(mfraw),'working_raw_sha256_at_observation':digest(work),
 'fixed_git_CRLF_sha256':digest(mfraw.replace(b'\n',b'\r\n')),
 'fixed_git_LF_count':mfraw.count(b'\n'),'fixed_git_CR_count':mfraw.count(b'\r'),
 'mismatch_reproduced':digest(mfraw)!=vf['developer_outputs_manifest_raw_sha256'],
 'CRLF_alone_explains_declared':digest(mfraw.replace(b'\n',b'\r\n'))==vf['developer_outputs_manifest_raw_sha256']}
print(json.dumps({'manifest_keys':list(mf),'first_file':mf['files'][0]},ensure_ascii=True))
paths=subprocess.check_output(['git','ls-tree','-r','--name-only','-z',COMMIT],cwd=ROOT).decode('utf-8').split('\0')
paths=[p for p in paths if p]
stream=subprocess.run(['git','cat-file','--batch'],cwd=ROOT,input=''.join(COMMIT+':'+p+'\n' for p in paths).encode('utf-8'),capture_output=True,check=True).stdout
cursor=0
for p in paths:
    end=stream.index(b'\n',cursor);header=stream[cursor:end].split();assert header[1]==b'blob'
    size=int(header[2]);cursor=end+1;CACHE[p]=stream[cursor:cursor+size];cursor+=size+1
assert cursor==len(stream)
active=[p for p in paths if p.startswith('audit/') and p.endswith('.json') and not p.startswith('audit/reviews/') and not Path(p).name.startswith('original_')]
pointers=[]
for path in active:
    try:doc=json.loads(blob(path))
    except ValueError:continue
    if not isinstance(doc,dict):continue
    if 'archive_manifest_raw_sha256' in doc and isinstance(doc.get('archive_manifest'),str):
        pointers.append((path,'archive_manifest_raw_sha256',doc['archive_manifest'],doc['archive_manifest_raw_sha256']))
    elif path=='audit/7bf_acceptance_archive_check.json':
        pointers.append((path,'archive_manifest_raw_sha256','audit/reviews/20261026-7bf716f-windows/archive_manifest.json',doc['archive_manifest_raw_sha256']))
    if 'original_archive_manifest_raw_sha256' in doc:
        report=doc.get('original_independent_report') or doc.get('original_failure_report')
        if isinstance(report,str) and report.startswith('audit/reviews/'):
            pointers.append((path,'original_archive_manifest_raw_sha256',str(Path(report).parent/'archive_manifest.json').replace('\\','/'),doc['original_archive_manifest_raw_sha256']))
    if 'developer_outputs_manifest_raw_sha256' in doc:
        pointers.append((path,'developer_outputs_manifest_raw_sha256',str(Path(path).parent/'developer_outputs_manifest.json').replace('\\','/'),doc['developer_outputs_manifest_raw_sha256']))
checks=[]
for path,key,target,declared in pointers:
    data=blob(target)
    checks.append(dict(source=path,key=key,target=target,declared=declared,actual=digest(data),passed=digest(data)==declared))
result=dict(scope='Fixed Git raw-byte audit of active explicit manifest pointers; historical archived reports and external unattached hashes not reinterpreted',
 commit=COMMIT,baseline=baseline,active_json_files=len(active),pointer_checks=checks,
 actual_market_model_cloud_calls=0,production_files_modified=False)
file_checks=[]
for record in mf['files']:
    target='audit/review_packages/wr14/'+record['archive_path']
    data=blob(target)
    item=dict(path=target,declared_sha256=record['raw_sha256'],actual_sha256=digest(data),
              declared_bytes=record['bytes'],actual_bytes=len(data))
    item['passed']=item['declared_sha256']==item['actual_sha256'] and item['declared_bytes']==item['actual_bytes']
    file_checks.append(item)
result['WR14_original_output_checks']=file_checks
result['WR14_original_outputs_all_passed']=all(x['passed'] for x in file_checks)
result['WR14_original_outputs_count']=len(file_checks)
assert len(file_checks)==48 and result['WR14_original_outputs_all_passed']
output_maps=[]
for path in active:
    try:doc=json.loads(blob(path))
    except ValueError:continue
    if not isinstance(doc,dict) or not isinstance(doc.get('raw_byte_sha256'),dict):continue
    for relative,declared in doc['raw_byte_sha256'].items():
        target=str(Path(path).parent/relative).replace('\\','/')
        actual=digest(blob(target))
        output_maps.append({'source':path,'target':target,'declared':declared,'actual':actual,'passed':actual==declared})
result['other_active_raw_output_map_checks']=output_maps
assert all(x['passed'] for x in output_maps)
(OUT/'pre_fix_hash_audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'baseline':baseline,'active_json_files':len(active),'explicit_manifest_pointers':len(checks),'mismatches':[x for x in checks if not x['passed']], 'original_outputs_count':len(file_checks),'outputs_all_passed':result['WR14_original_outputs_all_passed'],'other_active_raw_output_maps':len(output_maps),'other_output_maps_all_passed':all(x['passed'] for x in output_maps)},ensure_ascii=True))
