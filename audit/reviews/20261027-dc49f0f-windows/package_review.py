from pathlib import Path
import ast,hashlib,io,json,shutil,subprocess,tarfile,zipfile
R=Path(__file__).parent
OUT=Path(r'B:\BaiduSyncdisk\学习\投资\量化\量化交易比赛\LLM审核\review-dc49f0f-20261027')
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
assert D['software_acceptance']['blocking_findings']==['WR-14'] and D['financial_evidence'] is False
assert read('recovery_agent/current_execution.json')['passed_methods']==12
assert read('recovery_agent/parser_first_results.json')['passed_methods']==2
assert all(r['exit_code']==0 for r in read('runs/execution_records.json'))
assert all(r['exit_code']==r['expected_exit_code'] for r in read('original_probes/execution_records.json'))
assert all(r['exit_code']==r['expected_exit'] for r in read('root_receipt_probes/command_log.json'))
assert (R/'receipt_agent/report.json').exists()
for name in ['run_offline_review.py','minimal_fractional_clock.py','verify_artifacts.py']:ast.parse((R/name).read_text(encoding='utf-8'))
OUT.mkdir(exist_ok=False)
for name in ['source','receipt_agent','evidence_agent','original_probes','root_receipt_probes']:copy(name)
(OUT/'recovery_agent').mkdir()
for file in (R/'recovery_agent').iterdir():
    if file.is_file():copy('recovery_agent/'+file.name)
for file in (R/'runs').iterdir():
    if file.name=='repository_source':copy('runs/repository_source/audit/stage_verification.json')
    else:copy('runs/'+file.name)
for name in ['formal_report.txt','formal_report.json','environment.json','github_metadata.json','qc_source_readback.json','change.diff','full_pr2.diff','change_stat.txt','harness_notes.json','minimal_cli_switch.py','minimal_parallel_carrier.py','minimal_nested_annotations.py','minimal_fractional_clock.py','run_original_probes.py','run_root_receipt_probes.py','run_main_checks.py','replay_archived_script.py','replay_public_class.py','run_offline_review.py','verify_artifacts.py','build_formal_report.py','package_review.py','fractional_clock.stdout.txt','fractional_clock.stderr.txt']:copy(name)
versions=read('environment.json')['dependencies'];(OUT/'requirements-audit.txt').write_text(''.join(k+'=='+v+'\n' for k,v in versions.items()),encoding='utf-8')
sources={}
for label,sha,path in [('candidate',D['reviewed_source_commit'],OUT/'source'),('baselinebe',D['baseline_commit'],OUT/'baselines/be94426/source'),('baselinefbe','fbe2454e6ea10aa59211c01f236c54bb251527be',OUT/'baselines/fbe2454/source')]:
    expected=raw(sha)
    if label!='candidate':
        for name,data in expected.items():
            file=path/name;assert file.resolve().is_relative_to(path.resolve());file.parent.mkdir(parents=True,exist_ok=True);file.write_bytes(data)
    assert expected=={p.relative_to(path).as_posix():p.read_bytes() for p in path.rglob('*') if p.is_file()},label
    sources[label]={'commit':sha,'count':len(expected),'files':{n:hashlib.sha256(b).hexdigest() for n,b in expected.items()}}
(OUT/'source_git_manifest.json').write_text(json.dumps(sources,indent=2),encoding='utf-8')
(OUT/'README.txt').write_text('''AQRP-LLM dc49f0f 独立复审包，2026-10-27 Asia/Shanghai
WR13原未知注解旁路修复后通过；新增WR14/P2普通小数秒兼容失败，阶段2及全系统未验收。financial_evidence=false。
source1088份、baselinebe891份、baselinefbe313份均固定Git原字节。
Python3.10：pip install -r requirements-audit.txt
校验：python -B verify_artifacts.py
最小复现：python -B minimal_fractional_clock.py source（当前exit1，等价.500/.500000通过、.5拒绝）
完整新旧worker链：python -B receipt_agent/fractional_clock_probe.py --source source --out <新目录>（当前6完成8误拒绝，exit1）；--source baselines/be94426/source时14完成exit0。
WR13原最小：python -B minimal_nested_annotations.py source（当前0，旧be1）
完整离线重现：python -B run_offline_review.py --out <不存在的新目录>
聚合入口本轮仅检查语法/help；各底层验收命令均实际执行，不声称聚合整段重跑。聚合返回0只表示预期结果重现，WR14仍为软件错误。纯审核者解释器/基线路径绑定有diff。
原脚本的历史commit或按路径推断label不作为实际版本证明；看外层命令、实际source目录和raw源码hash。完整fraction探针相同脚本/helper在新旧source运行，输出目录分开保留。
恢复cases/parser_cases和runs/repository_source重复完整源码副本不入包；原临时目录保留，所有测试、合成fixture生成、命令、输出与状态观察保存，可从source重建。new_parser_recovery需先执行同目录原recovery脚本生成本轮case状态，聚合已排序。
首12/160的Role排序测量失败及合法clock错误都保留；另存Role-only修正版仍保留两条产品错误，不吞异常或改合法clock预期。原5变体适配只增加修复后拒绝处理/状态测量，原件/diff也保存。
无生产源码/真实预算改动，无新增Research/LEAN/模型/市场/部署/购买/交易，未轮询待终态LEAN或读日志。
''',encoding='utf-8')
check={'candidate_Git_files':1088,'baselinebe_Git_files':891,'baselinefbe_Git_files':313,'source_bytes_match':True,'WR13_original_scope':'passed_after_fix','WR14':'failed','whole_system':'not_accepted','financial_evidence':False}
(OUT/'artifact_verification.json').write_text(json.dumps(check,indent=2),encoding='utf-8')
manifest={p.relative_to(OUT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.rglob('*') if p.is_file()}
(OUT/'artifact_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
archive=OUT.with_suffix('.zip');assert not archive.exists()
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for file in OUT.rglob('*'):
        if file.is_file():z.write(file,OUT.name+'/'+file.relative_to(OUT).as_posix())
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    for name,digest in manifest.items():assert hashlib.sha256(z.read(OUT.name+'/'+name)).hexdigest()==digest,name
result={'directory':str(OUT),'zip':str(archive),'zip_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'zip_bytes':archive.stat().st_size,'manifest_entries':len(manifest),'verification':check}
(R/'package_result.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False))
