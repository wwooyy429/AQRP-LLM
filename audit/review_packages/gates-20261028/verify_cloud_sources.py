from pathlib import Path
import hashlib
import json
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
def sha(raw):return hashlib.sha256(raw).hexdigest()
def normalized(raw):return raw.removeprefix('\ufeff').replace('\r\n','\n').replace('\r','\n')
rows=json.loads((OUT/'cloud-source-native.json').read_bytes())
observed=[]
for row in rows:
    result=row['result']
    assert result.get('isError') is not True
    payload=result.get('structuredContent')
    if payload is None:payload=json.loads(next(c['text'] for c in result['content'] if c['type']=='text'))
    assert payload['filePath']==row['path']
    text=normalized(payload['content'])
    digest=sha(text.encode('utf-8'))
    observed.append(dict(path=row['path'],expected_sha256=row['expected'],observed_sha256=digest,
        equal=digest==row['expected'],native_read_receipt_sha256=sha(json.dumps(result,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode())))
assert len(observed)==32 and all(x['equal'] for x in observed)
report=dict(schema_version=1,kind='actual_current_project_source_readback',project_id=38436695,
    normalization='UTF8 BOM and CRLF to LF only; EOF preserved',declared_files_checked=32,
    all_declared_project_sources_equal_frozen=True,full_project_inventory_certified=False,
    worker_files_checked=1,other_worker_files_certified=False,
    source_receipts_retained_privately='cloud-source-native.json; no duplicate source tree in Git',files=observed,
    worker_source_difference_does_not_imply_editor_source_change=True,financial_evidence=False,final_test_enabled=False)
(OUT/'cloud_sources_result.json').write_bytes((json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode())
print(json.dumps(dict(project_sources_verified=32,all_equal=True,full_project_inventory_certified=False,
    worker_full_inventory_certified=False)))
