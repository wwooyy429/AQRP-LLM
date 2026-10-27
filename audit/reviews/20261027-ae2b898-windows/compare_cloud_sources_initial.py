from pathlib import Path
import hashlib,json,subprocess
R=Path(__file__).parent
REPO=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\repo')
OLD='75f24629d3b7f94ff3aa906c3ce8a2b8b9a8d3c4'
def digest(x):return hashlib.sha256(x).hexdigest()
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
data=json.loads((R/'qc_python_source_read.json').read_text(encoding='utf-8'))
rows=[];cloud_manifest={}
for item in data['results']:
    assert item['status']=='fulfilled'
    result=item['value'];assert not result.get('isError',False)
    value=result.get('structuredContent')
    if value is None:
        value=json.loads(next(c['text'] for c in result['content'] if c['type']=='text'))
    path=item['file'];text=value['content'];raw=text.encode('utf-8')
    if path=='_engineering_task_input.py':
        baseline=(R/'source/audit/task_inputs/bfd00f2611fd4496b9498d4597618a8e.py').read_bytes()
        candidate=None
    else:
        baseline=subprocess.check_output(['git','show',OLD+':cloud/'+path],cwd=REPO)
        candidate=(R/'source/cloud'/path).read_bytes()
        cloud_manifest[path]=digest(text.replace('\r\n','\n').encode())
    rows.append({'path':path,'utf8_bytes':len(raw),'cloud_utf8_sha256':digest(raw),'old_git_raw_sha256':digest(baseline),
        'raw_equal_old':raw==baseline,'newline_equal_old':text.replace('\r\n','\n')==baseline.decode('utf-8-sig').replace('\r\n','\n'),
        'terminal_whitespace_normalized_equal_old':text.replace('\r\n','\n').rstrip()==baseline.decode('utf-8-sig').replace('\r\n','\n').rstrip(),
        'candidate_raw_sha256':digest(candidate) if candidate is not None else None,
        'raw_equal_candidate':raw==candidate if candidate is not None else None})
out={'reviewed_source_commit':'ae2b8985f3799c246e90341370f86d80483f63ed','old_cloud_source_commit':OLD,
    'actual_python_files_read':len(rows),'old_implementation_files':len(cloud_manifest),
    'raw_old_matches':sum(x['raw_equal_old'] for x in rows),'newline_old_matches':sum(x['newline_equal_old'] for x in rows),
    'terminal_whitespace_normalized_old_matches':sum(x['terminal_whitespace_normalized_equal_old'] for x in rows),
    'raw_candidate_matches':sum(x['raw_equal_candidate'] is True for x in rows),
    'deployment_hash_newline_normalized':digest(canonical(cloud_manifest)),
    'input_hash':next(x['cloud_utf8_sha256'] for x in rows if x['path']=='_engineering_task_input.py'),
    'listed_python_files':len(data['observed_python_files']),'known_but_not_listed':data['prior_known_but_not_listed'],'full_inventory_certified':False,'files':rows,'excluded_not_read':data['excluded_not_read'],'backtest_status_or_logs_read':False,
    'platform_runtime_terminal_status':None,'compilation_performed':False,'cloud_writes':0,
    'limitation':'源码只读核对；不是完成状态、数据认证或候选部署认证。raw与终端空白归一化分别报告。'}
(R/'cloud_comparison.json').write_bytes(json.dumps(out,ensure_ascii=False,indent=2).encode())
print(json.dumps({k:v for k,v in out.items() if k!='files'},ensure_ascii=False,indent=2))
