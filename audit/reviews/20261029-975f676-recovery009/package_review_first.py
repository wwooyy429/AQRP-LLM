from pathlib import Path
from hashlib import sha256
import os, json, shutil, subprocess, sys, zipfile
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parent
D=Path(r'B:\BaiduSyncdisk\学习\投资\量化\量化交易比赛\LLM审核\review-975f676-20261029')
Z=D.with_suffix('.zip')
assert not D.exists() and not Z.exists(),'Refuse overwrite review package'
expected='ef0fa58a5e87d0930ed7b6c6ddbd11a1b96ecc0ea56678dd7989dbee2a890057'
assert sha256((R/'formal_report.json').read_bytes()).hexdigest()==expected
for folder in ('notification_agent','windows_lock_agent','history_agent'):
    q=json.loads((R/folder/'formal_QA_final.json').read_text(encoding='utf-8'))
    assert expected in json.dumps(q),folder
    assert not q.get('issues'),folder
maps=json.loads((R/'source_git_manifest.json').read_text(encoding='utf-8'))
for folder,item in maps.items():
    assert all(sha256((R/folder/name).read_bytes()).hexdigest()==value['sha256'] for name,value in item['files'].items()),folder
with (R/'minimum.stdout').open('wb') as out,(R/'minimum.stderr').open('wb') as err:
    cmd=[sys.executable,'-B',str(R/'minimal_windows.py'),str(R/'source')]
    result=subprocess.run(cmd,cwd=R,stdout=out,stderr=err)
(R/'minimum_execution.json').write_text(json.dumps({'command':cmd,'exit_code':result.returncode,'kind':'standalone_reproduction_not_additional_unit_methods'},indent=2))
assert result.returncode==0
files=[]
for folder, dirs, names in os.walk(R):
    base=Path(folder); rel=base.relative_to(R)
    if not rel.parts:
        dirs[:]=[d for d in dirs if d not in {'work_source','materials_checkout'}]
    immutable=bool(rel.parts and rel.parts[0] in {'source','materials'})
    if not immutable:
        dirs[:]=[d for d in dirs if d not in {'.git','__pycache__'}]
        if rel.as_posix()=='history_agent/replay_context':dirs[:]=[d for d in dirs if d!='source']
    for name in names:
        p=base/name
        if not immutable and (p.suffix=='.pyc' or (not rel.parts and name in {'package_result.json','artifact_manifest.json'})):continue
        files.append(p)
D.mkdir()
for source in sorted(files):
    target=D/source.relative_to(R)
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(source,target)
readme='''独立复审 AQRP-20261029-975F676-RECOVERY009-25
固定源码975f676、审核资料a6a5a16；全量987回归及已测局部软件范围通过，阶段2整体未通过。
本轮没有云端调用、真实行情行读取、真实预算/生产源码修改或PR批准合并。
source/与materials/是完整不可变Git原字节导出，分别7045/7076份文件；source_git_manifest.json逐文件校验。
root_execution_records.json保留两个幂等build、987测试及a6独立Git资料核对的真实命令/退出码。
notification_agent、windows_lock_agent及其supplement、history_agent保存首次失败、夹具适配、补充、stdout/stderr和全部QA（含旧hash不符及读取器错误）。
formal_report_pre_QA.*保留更正适配措辞前草稿。所有产品文件与断言未为获得通过而修改。
历史WR矩阵见history_agent/WR_current_matrix.json：原确认SHA与scope、当前987相关test IDs、额外独立重放及未重跑旧完整套件逐项区分。
旧b1a/ca5平台元数据只作离线重解析，不是新候选真实运行。旧PROJECT/Research43原字节与LEAN43 EOF归一化分开；当前部署44文件。
配置周期3/13、累计16，Research17/20、LEAN3/16，71事件和旧69原前缀保留。原人类新增额度对话本轮未独立获取，不授执行权限。
为去除重复，仅省略可重建的根work_source、materials_checkout Git工作树以及history_agent/replay_context/source重复树；原固定源码、历史脚本、首失败及适配diff/全部结果均已收入。
部分Git来源重建/verify_review重跑要求实际固定Git检出（不是无.git导出）；原实际命令和版本已经记录。历史脚本需要按其runner建立合成上下文，不可将内嵌旧SHA当当前源码。
最小原生Windows检查：python -B minimal_windows.py source
新增根端已知答案：python -B independent_storage_identity.py
仓库回归：在临时source副本执行 python -B tools/stages.py verify，勿覆盖封存目录。
封存校验（只读）：python -B verify_artifacts.py
合成测试、进程请求、子场景、静态检查和重跑重叠，不能累加独有总数。金融证据为false。
'''
(D/'README.txt').write_text(readme,encoding='utf-8')
manifest={}
for p in sorted(D.rglob('*')):
    if p.is_file():
        raw=p.read_bytes();manifest[p.relative_to(D).as_posix()]={'sha256':sha256(raw).hexdigest(),'bytes':len(raw)}
(D/'artifact_manifest.json').write_text(json.dumps({'review_id':'AQRP-20261029-975F676-RECOVERY009-25','files':manifest},ensure_ascii=False,indent=2),encoding='utf-8')
check=subprocess.run([sys.executable,'-B',str(D/'verify_artifacts.py')],capture_output=True,cwd=D)
assert check.returncode==0,check.stdout+check.stderr
with zipfile.ZipFile(Z,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in sorted(D.rglob('*')):
        if p.is_file():z.write(p,p.relative_to(D).as_posix())
with zipfile.ZipFile(Z) as z:
    assert z.testzip() is None
    assert set(z.namelist())==set(manifest)|{'artifact_manifest.json'}
    for name,item in manifest.items():assert sha256(z.read(name)).hexdigest()==item['sha256'],name
result={'directory':str(D),'zip':str(Z),'zip_bytes':Z.stat().st_size,'zip_sha256':sha256(Z.read_bytes()).hexdigest(),'manifest_entries':len(manifest),'formal_report_sha256':expected,'portable_verifier_exit':check.returncode,'portable_verifier_stdout':check.stdout.decode().strip(),'phase2_accepted':False}
(R/'package_result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False),flush=True)
