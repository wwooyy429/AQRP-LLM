from pathlib import Path
import hashlib,json,subprocess
R=Path(__file__).parent
GIT=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\repo')
OLD='75f24629d3b7f94ff3aa906c3ce8a2b8b9a8d3c4'
def sha(raw):return hashlib.sha256(raw).hexdigest()
def norm(raw):return raw.decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n').encode('utf-8')
def canonical(obj):return json.dumps(obj,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8')
data=json.loads((R/'qc_python_source_read.json').read_text(encoding='utf-8'))
assert data['project_id']==38436695 and len(data['requested_python_files'])==26
rows=[];manifest={}
for item in data['results']:
    assert item['status']=='fulfilled'
    result=item['value'];assert not result.get('isError',False)
    value=result.get('structuredContent')
    texts=[json.loads(c['text'])for c in result.get('content',[])if c.get('type')=='text']
    if value is None:value=texts[0]
    assert all(x==value for x in texts)
    path=item['file'];raw=value['content'].encode('utf-8')
    if path=='_engineering_task_input.py':
        reference='source/audit/task_inputs/bfd00f2611fd4496b9498d4597618a8e.py'
        baseline=(R/reference).read_bytes();candidate=None
    else:
        reference=OLD+':cloud/'+path
        baseline=subprocess.check_output(['git','-C',str(GIT),'show',reference])
        candidate=(R/'source/cloud'/path).read_bytes()
        manifest[path]=sha(norm(raw))
    rows.append({'path':path,'utf8_bytes':len(raw),'cloud_raw_sha256':sha(raw),'cloud_normalized_sha256':sha(norm(raw)),
        'reference':reference,'reference_raw_sha256':sha(baseline),'raw_equal_original':raw==baseline,
        'normalized_equal_original':norm(raw)==norm(baseline),'raw_equal_candidate':raw==candidate if candidate is not None else None})
result={'reviewed_source_commit':'66ff72ffaaff8c91c008898e6527c91131176c2a','project_id':data['project_id'],
    'actual_read_file_calls':len(rows),'implementation_files_read':len(manifest),'task_inputs_read':1,
    'raw_original_matches':sum(x['raw_equal_original']for x in rows),'normalized_original_matches':sum(x['normalized_equal_original']for x in rows),
    'raw_candidate_implementation_matches':sum(x['raw_equal_candidate']is True for x in rows),
    'returned_implementation_manifest_hash':sha(canonical(manifest)),
    'input_raw_sha256':next(x['cloud_raw_sha256']for x in rows if x['path']=='_engineering_task_input.py'),
    'excluded_not_read':data['excluded_not_read'],'full_cloud_inventory_certified':False,'worker_source_verified':False,
    'candidate_deployed':False,'new_compile_performed':False,'cloud_writes':0,'financial_evidence':False,
    'source_evidence':'auditor independently read current open-project metadata then each listed Python source; these are read_file carriers, not a fabricated read_project wrapper',
    'terminal_evidence_file':'qc_terminal_native.json','limitation':'Current returned reference matching cannot establish the failed worker snapshot, resolve its exact file difference, or prove a new candidate run.',
    'files':rows}
assert result['raw_original_matches']==26
assert result['returned_implementation_manifest_hash']=='dad57a0513899dc5ed89cef637d648229dd1c5c1b31bb70583ff95962c1c5bc6'
assert result['input_raw_sha256']=='95092b4de264c961895655f0853de639981143ad8cdb41e2c0d22b0adc7136b0'
(R/'cloud_comparison.json').write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
print(json.dumps({k:v for k,v in result.items()if k!='files'},ensure_ascii=False))
