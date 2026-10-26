from pathlib import Path
import ast,hashlib,io,json,shutil,subprocess,tarfile,zipfile
R=Path(__file__).parent
OUT=Path(r'B:\BaiduSyncdisk\学习\投资\量化\量化交易比赛\LLM审核\review-4a94430-20261027')
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
assert D['software_acceptance']['blocking_findings']==[] and D['software_acceptance']['nonblocking_findings']==['WR-15']
assert D['financial_evidence'] is False
assert read('recovery_agent/current_execution.json')['passed_methods']==12
assert read('recovery_agent/parser_first_results.json')['passed_methods']==2
for record in read('runs/execution_records.json'):assert record['exit_code']==(1 if record['label']=='dc_annotations_role_corrected' else 0)
assert read('runs/dc_annotations_with_fixture/command.json')['exit_code']==0
assert all(r['exit_code']==r['expected_exit'] for r in read('original_probes/command_log.json'))
for name in ['run_offline_review.py','minimal_manifest_hash.py','verify_artifacts.py']:ast.parse((R/name).read_text(encoding='utf-8'))
assert b'\r\r\n' not in (R/'formal_report.txt').read_bytes()
OUT.mkdir(exist_ok=False)
for name in ['source','receipt_agent','evidence_agent','original_probes']:copy(name)
(OUT/'recovery_agent').mkdir()
for file in (R/'recovery_agent').iterdir():
    if file.is_file():copy('recovery_agent/'+file.name)
for file in (R/'runs').iterdir():
    if file.name=='repository_source':copy('runs/repository_source/audit/stage_verification.json')
    else:copy('runs/'+file.name)
for name in ['formal_report.txt','formal_report.json','environment.json','github_metadata.json','github_ci_jobs.json','qc_source_readback.json','change.diff','full_pr2.diff','change_stat.txt','minimal_cli_switch.py','minimal_parallel_carrier.py','minimal_nested_annotations.py','minimal_fractional_clock.py','minimal_manifest_hash.py','run_original_probes.py','run_schema_fixture_replay.py','run_main_checks.py','replay_archived_script.py','replay_public_class.py','run_offline_review.py','verify_artifacts.py','build_formal_report.py','package_review.py','manifest_hash.stdout.txt','manifest_hash.stderr.txt']:copy(name)
versions=read('environment.json')['dependencies'];(OUT/'requirements-audit.txt').write_bytes(''.join(k+'=='+v+'\n' for k,v in versions.items()).encode('utf-8'))
sources={}
for label,sha,path in [('candidate',D['reviewed_source_commit'],OUT/'source'),('baselinedc',D['baseline_commit'],OUT/'baselines/dc49f0f/source'),('baselinefbe','fbe2454e6ea10aa59211c01f236c54bb251527be',OUT/'baselines/fbe2454/source')]:
    expected=raw(sha)
    if label!='candidate':
        for name,data in expected.items():
            file=path/name;assert file.resolve().is_relative_to(path.resolve());file.parent.mkdir(parents=True,exist_ok=True);file.write_bytes(data)
    assert expected=={p.relative_to(path).as_posix():p.read_bytes() for p in path.rglob('*') if p.is_file()},label
    sources[label]={'commit':sha,'count':len(expected),'files':{n:hashlib.sha256(b).hexdigest() for n,b in expected.items()}}
(OUT/'source_git_manifest.json').write_bytes((json.dumps(sources,indent=2)+'\n').encode('utf-8'))
(OUT/'README.txt').write_bytes('''AQRP-LLM 4a94430 独立复审包，2026-10-27 Asia/Shanghai
WR14在已测离线范围修复后通过，无新的阻断性软件发现；WR15/P3为开发输出清单raw声明对应CRLF而Git为LF，非阻断。阶段2及全系统仍未验收，无金融证据。
固定source1331份、baseline dc1088份、baseline fbe313份Git原字节均独立一致。
Python3.10：pip install -r requirements-audit.txt
校验：python -B verify_artifacts.py
原WR14最小：python -B minimal_fractional_clock.py source（当前0，旧dc1）
原14链脚本在source/audit/reviews/20261027-dc49f0f-windows/receipt_agent/fractional_clock_probe.py，--source source --out <新目录>当前14完成exit0；source改baselines/dc49f0f/source则6完成8误拒绝exit1。同脚本/helper未改。路径推断child label不是实际版本身份，外层full_chain_bindings记录实际路径/哈希。
WR15最小：python -B minimal_manifest_hash.py source（当前exit1，仅声明raw不符，48底层输出原字节都通过）。本包审核者重算manifest可以校验全部文件。
完整离线重现：python -B run_offline_review.py --out <不存在的新目录>
聚合入口本轮仅校验语法/help，各底层验收命令已实际执行，不声称聚合整段重跑。聚合器核对预期结果exit0也不表示完整系统验收；保留WR15非阻断差异。
原注解套件首重放OUT缺schema：12/156有1个环境错误。首输出保留，另建OUT复制同raw官方fixture后原脚本/断言不变12/160通过。聚合复制fixture时有显式diff。
审计首465检查461过4不符，3个是选择嵌套历史报告的ZIP测量错误，1个是实际清单raw差异；首报告/修正保留，最终466=465过1不符，未吞差异。
恢复cases/parser_cases和runs/repository_source重复完整源码副本不入包；测试、合成生成器、命令及输出完整可重建，原临时目录不删除。new_parser_recovery需先生成同目录recovery状态，聚合已排序。
历史脚本be/dc字面量、旧归档和首次失败保持原样，以当前外层命令/source路径/raw哈希绑定真实4a身份。
无生产/真实预算改动、无新增Research/LEAN/模型/市场/部署/购买/交易，未轮询或读取待终态LEAN日志。
'''.encode('utf-8'))
check={'candidate_Git_files':1331,'baselinedc_Git_files':1088,'baselinefbe_Git_files':313,'source_bytes_match':True,'WR14':'passed_after_fix_in_tested_scope','nonblocking':['WR-15'],'whole_system':'not_accepted','financial_evidence':False}
(OUT/'artifact_verification.json').write_bytes((json.dumps(check,indent=2)+'\n').encode('utf-8'))
manifest={p.relative_to(OUT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.rglob('*') if p.is_file()}
(OUT/'artifact_manifest.json').write_bytes((json.dumps(manifest,indent=2)+'\n').encode('utf-8'))
archive=OUT.with_suffix('.zip');assert not archive.exists()
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for file in OUT.rglob('*'):
        if file.is_file():z.write(file,OUT.name+'/'+file.relative_to(OUT).as_posix())
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    for name,digest in manifest.items():assert hashlib.sha256(z.read(OUT.name+'/'+name)).hexdigest()==digest,name
result={'directory':str(OUT),'zip':str(archive),'zip_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'zip_bytes':archive.stat().st_size,'manifest_entries':len(manifest),'verification':check}
(R/'package_result.json').write_bytes((json.dumps(result,indent=2)+'\n').encode('utf-8'));print(json.dumps(result,ensure_ascii=False))
