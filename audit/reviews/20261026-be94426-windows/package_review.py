from pathlib import Path
import ast,hashlib,io,json,shutil,subprocess,tarfile,zipfile
R=Path(__file__).parent
OUT=Path(r'B:\BaiduSyncdisk\学习\投资\量化\量化交易比赛\LLM审核\review-be94426-20261026')
GIT=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\repo')
def read(name):return json.loads((R/name).read_text(encoding='utf-8'))
def copy(name):
    src=R/name;dst=OUT/name;dst.parent.mkdir(parents=True,exist_ok=True)
    if src.is_dir():shutil.copytree(src,dst,ignore=shutil.ignore_patterns('__pycache__'))
    else:shutil.copy2(src,dst)
def raw(sha):
    data=subprocess.check_output(['git','-C',str(GIT),'archive',sha])
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:return {m.name:tar.extractfile(m).read() for m in tar.getmembers() if m.isfile()}
D=read('formal_report.json')
assert D['software_acceptance']['blocking_findings']==['WR-13'] and D['financial_evidence'] is False
assert read('recovery_agent/first_results.json')['passed_methods']==12
for record in read('runs/execution_records.json'):assert record['exit_code']==(2 if record['label']=='e513_receipts' else 0)
assert read('runs/e513_receipts_resolved.command.json')['exit_code']==0
for record in read('original_probes/execution_records.json'):assert record['exit_code']==record['expected_exit_code']
for name in ['run_offline_review.py','minimal_nested_annotations.py','verify_artifacts.py']:ast.parse((R/name).read_text(encoding='utf-8'))
OUT.mkdir(exist_ok=False)
for name in ['source','receipt_agent','evidence_agent','original_probes']:copy(name)
(OUT/'recovery_agent').mkdir()
for file in (R/'recovery_agent').iterdir():
    if file.is_file():copy('recovery_agent/'+file.name)
for file in (R/'runs').iterdir():
    if file.name=='repository_source':copy('runs/repository_source/audit/stage_verification.json')
    else:copy('runs/'+file.name)
for name in ['formal_report.txt','formal_report.json','environment.json','github_metadata.json','qc_source_readback.json','change.diff','full_pr2.diff','change_stat.txt','harness_notes.json','minimal_cli_switch.py','minimal_parallel_carrier.py','minimal_nested_annotations.py','run_original_probes.py','run_resolved_receipts.py','root_nested_annotations.json','root_nested_commands.json','run_root_nested_probes.py','run_main_checks.py','replay_archived_script.py','replay_public_class.py','run_offline_review.py','verify_artifacts.py','build_formal_report.py','package_review.py']:copy(name)
for file in R.glob('root_nested_*.txt'):copy(file.name)
versions=read('environment.json')['dependencies'];(OUT/'requirements-audit.txt').write_text(''.join(k+'=='+v+'\n' for k,v in versions.items()),encoding='utf-8')
source_manifest={}
for label,sha,path in [('candidate',D['reviewed_source_commit'],OUT/'source'),('baselinee513',D['baseline_commit'],OUT/'baselines/e513c66/source'),('baselinefbe','fbe2454e6ea10aa59211c01f236c54bb251527be',OUT/'baselines/fbe2454/source')]:
    expected=raw(sha)
    if label!='candidate':
        for name,data in expected.items():
            file=path/name;assert file.resolve().is_relative_to(path.resolve());file.parent.mkdir(parents=True,exist_ok=True);file.write_bytes(data)
    assert expected=={p.relative_to(path).as_posix():p.read_bytes() for p in path.rglob('*') if p.is_file()},label
    source_manifest[label]={'commit':sha,'count':len(expected),'files':{n:hashlib.sha256(b).hexdigest() for n,b in expected.items()}}
(OUT/'source_git_manifest.json').write_text(json.dumps(source_manifest,indent=2),encoding='utf-8')
(OUT/'README.txt').write_text('''AQRP-LLM be94426 独立复审包
正式结论：WR-11、WR-12在原问题及离线测试范围修复后通过；WR-13/P2阻断回执边界。阶段2及全系统未验收，无金融证据。
source为891份固定Git原件；基线e513的608份、fbe的313份原件另存。
Python3.10：pip install -r requirements-audit.txt
校验：python -B verify_artifacts.py
最小复现：python -B minimal_nested_annotations.py source（当前exit1）
完整有效报告链：python -B receipt_agent/nested_annotations_probe.py --source source --out <新JSON路径>（当前exit1，2正例完成/3误接受）
完整重现：python -B run_offline_review.py --out <不存在的新目录>
聚合脚本本轮仅检查语法和help；各底层验收命令均实际执行。不声称聚合脚本已整段重跑。该脚本会记录纯审核者解释器/基线/去重引用路径绑定diff。
聚合器核对预期结果后exit0不表示软件验收通过，WR13仍为失败。原始首跑、测量修正和差异全部保留。
recovery_agent/cases和runs/repository_source重复生成源码副本未装入包；所有独立测试、合成输入生成、61条CLI命令/输出和状态观察均保留，可由固定source重建。原临时目录未删除。
原run_main_checks最后一次原回执路径不存在而exit2，执行0方法；run_resolved_receipts按归档去重引用核对原字节后14/54通过。没有把它计为产品缺陷。
历史运行记录中绝对路径和脚本历史SHA字面量保持原样，以外层实际固定Git/源码hash绑定身份。
没有修改开发者源码或真实预算，没有新增Research、LEAN、模型、部署、交易或数据访问。
''',encoding='utf-8')
verification={'candidate_Git_files':891,'baselinee513_Git_files':608,'baselinefbe_Git_files':313,'source_bytes_match':True,'WR11_WR12':'passed_after_fix_in_tested_scope','WR13':'failed','whole_system':'not_accepted','financial_evidence':False}
(OUT/'artifact_verification.json').write_text(json.dumps(verification,indent=2),encoding='utf-8')
manifest={p.relative_to(OUT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.rglob('*') if p.is_file()}
(OUT/'artifact_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
archive=OUT.with_suffix('.zip');assert not archive.exists()
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for file in OUT.rglob('*'):
        if file.is_file():z.write(file,OUT.name+'/'+file.relative_to(OUT).as_posix())
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    for name,digest in manifest.items():assert hashlib.sha256(z.read(OUT.name+'/'+name)).hexdigest()==digest,name
result={'directory':str(OUT),'zip':str(archive),'zip_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'zip_bytes':archive.stat().st_size,'manifest_entries':len(manifest),'verification':verification}
(R/'package_result.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False))
