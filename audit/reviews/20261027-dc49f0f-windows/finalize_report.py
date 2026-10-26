"""Preserve draft snapshots and publish byte-preserving wording correction."""
from pathlib import Path
import hashlib,json,zipfile
R=Path(__file__).parent
OUT=Path(r'B:\BaiduSyncdisk\学习\投资\量化\量化交易比赛\LLM审核\review-dc49f0f-20261027')
for root in [R,OUT]:
    current=root/'formal_report.txt';saved=root/'formal_report.wording_revision_raw.txt';assert not saved.exists();saved.write_bytes(current.read_bytes())
    before=(root/'formal_report.initial.txt').read_bytes()
    old='前面的66–69正则'.encode('utf-8');new='前面的69–70正则'.encode('utf-8');assert before.count(old)==1
    current.write_bytes(before.replace(old,new));assert b'\r\r\n' not in current.read_bytes()
previous=OUT/'report_revision.initial.json';assert not previous.exists();previous.write_bytes((OUT/'report_revision.json').read_bytes())
revision={'type':'Explanatory source-line wording and draft text line endings only','before':'66–69','after':'69–70; main line76 and JSON unchanged','initial_and_intermediate_reports_preserved':True,'all_previous_ZIPs_preserved':True,'conclusions_and_test_inputs_unchanged':True,'final_report_sha256':hashlib.sha256((OUT/'formal_report.txt').read_bytes()).hexdigest()}
(OUT/'report_revision.json').write_bytes((json.dumps(revision,indent=2)+'\n').encode('utf-8'))
(OUT/Path(__file__).name).write_bytes(Path(__file__).read_bytes())
manifest={p.relative_to(OUT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.rglob('*') if p.is_file() and p.name!='artifact_manifest.json'}
(OUT/'artifact_manifest.json').write_bytes((json.dumps(manifest,indent=2)+'\n').encode('utf-8'))
archive=OUT.parent/(OUT.name+'-verified.zip');assert not archive.exists()
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for p in OUT.rglob('*'):
        if p.is_file():z.write(p,OUT.name+'/'+p.relative_to(OUT).as_posix())
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    for name,digest in manifest.items():assert hashlib.sha256(z.read(OUT.name+'/'+name)).hexdigest()==digest
result={'zip':str(archive),'zip_bytes':archive.stat().st_size,'zip_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'manifest_entries':len(manifest),'final_report_sha256':revision['final_report_sha256']}
(R/'verified_package_result.json').write_bytes((json.dumps(result,indent=2)+'\n').encode('utf-8'));print(json.dumps(result,ensure_ascii=False))
