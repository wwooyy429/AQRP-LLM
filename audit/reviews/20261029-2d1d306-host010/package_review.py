from pathlib import Path
from hashlib import sha256
import os,sys,json,shutil,subprocess,zipfile
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parent
D=R/'sealed_package'; Z=R/'sealed_package.zip'
P=Path(r'B:\BaiduSyncdisk\学习\投资\量化\量化交易比赛\LLM审核\review-2d1d306-20261029')
PZ=P.with_suffix('.zip')
assert all(not p.exists() for p in (D,Z,P,PZ)),'Refuse overwrite audit artifacts'
expected='224a7b8a0e7667b6759e685f71dae0fd54ba0eb6c914ced1c9c1332deb009e14'
assert sha256((R/'formal_report.json').read_bytes()).hexdigest()==expected
for folder in ('host_api_agent','stdio_agent','archive_agent'):
    qa=json.loads((R/folder/'formal_QA.json').read_text(encoding='utf-8'))
    assert expected in json.dumps(qa) and not qa.get('issues'),folder
maps=json.loads((R/'source_git_manifest.json').read_text(encoding='utf-8'))
for folder,item in maps.items():assert all(sha256((R/folder/name).read_bytes()).hexdigest()==v['sha256'] for name,v in item['files'].items()),folder
minimum=json.loads((R/'minimum_execution.json').read_text(encoding='utf-8'))
assert minimum['exit_code']==1 and minimum['observed']['documented_script']['actual_exit']==2
files=[]
for folder,dirs,names in os.walk(R):
    base=Path(folder);rel=base.relative_to(R)
    immutable=bool(rel.parts and rel.parts[0] in {'source','materials'})
    if not rel.parts:dirs[:]=[n for n in dirs if n not in {'work_source','materials_checkout','sealed_package'}]
    if not immutable:
        dirs[:]=[n for n in dirs if n not in {'.git','__pycache__'}]
        if rel.as_posix()=='archive_agent/replay_context':dirs[:]=[n for n in dirs if n!='source']
    for name in names:
        p=base/name
        if not immutable and (p.suffix=='.pyc' or name.endswith('.baiduyun.uploading.cfg') or (not rel.parts and name in {'sealed_package.zip','package_result.json','artifact_manifest.json'})):continue
        files.append(p)
D.mkdir()
for p in sorted(files):
    dest=D/p.relative_to(R);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
(D/'README.txt').write_text('''AQRP-20261029-2D1D306-HOST010-26 独立复审
结论：新宿主启用CLI/stdio不通过，WR-29/P1；阶段2整体未通过。
1006仓库、19宿主子集、7元数据自测通过；API18/89通过；stdio19方法17过2失败、69成功完成场景。计数重叠不合计独有总数。
source2d1d306与materials fe08846完整原Git字节保留，7080/7445文件；216份身份中原213未变、新增3，原44份云端部署未因本轮改变或重新运行。
root_execution_records.json、各agent/execution_records及archive replay保存实际命令/退出码。所有首跑失败、夹具/审核helper修正、stdio产品失败和原始日志均保留。
WR29：标准factory导入followup_host.FollowupHost，官方脚本/-m定义__main__.FollowupHost，第469行精确同一性比较拒绝合法对象。canonical import控制exit0，两个可执行入口exit2（应0）。不修改产品或失败预期。
最小复现：python -B minimal_wr29.py source
注意：当前最小复现的合法路径断言应失败、程序exit1，这是真实产品失败，不是通过或expectedFailure；minimum_execution.json保留控制0/脚本2/模块2。
材料verify_review.py需实际固定Git检出；本次已在独立Git副本运行成功。tools/stages.py verify需在另建临时source副本运行，会生成audit/stage_verification.json，不得写封存目录。
原975 Windows18/37、通知12/79+6/27、周期7/28原脚本在当前source全部首跑通过；内嵌旧SHA只作历史标签，实际source明确为2d。
旧975完整ZIP hash c4437f...14330项及CRC、旧7045+7076 Git blobs核对。205原件恢复，100直接原字节+105LF镜像/raw.base64；selected不是完整原包。
346开发守卫前后相等，其中5项是已重建核对的工作树CRLF表示，不能称全部与Git原字节一致。71账本/原69前缀不变，配置周期3/13累计16、Research17/20LEAN3/16、008关轮。
本轮QC/Research/LEAN/compile/市场/模型/生产automation调用和真实预算/生产源码写入均0。旧b1a云端证据不继承新宿主。未来1/1/1无授权/准入/真实任务ID。
为去重，只省略根work_source、materials_checkout及archive_agent/replay_context/source重复树；原完整source/materials、原脚本、结果和首次失败均保留。不收入非Git的同步临时旁文件。
严格封存在C临时区完成，ZIP逐项hash/CRC通过后复制B盘；B目录只提供报告和最小复现副本，完整包与校验器在ZIP。
封存校验：python -B verify_artifacts.py（校验文件，不表示软件验收通过）。
正式研究、自动GPT、交易及最终测试保持关闭，financial_evidence=false。
''',encoding='utf-8')
manifest={}
for p in sorted(D.rglob('*')):
    if p.is_file():
        raw=p.read_bytes();manifest[p.relative_to(D).as_posix()]={'sha256':sha256(raw).hexdigest(),'bytes':len(raw)}
(D/'artifact_manifest.json').write_text(json.dumps({'review_id':'AQRP-20261029-2D1D306-HOST010-26','files':manifest},ensure_ascii=False,indent=2),encoding='utf-8')
check=subprocess.run([sys.executable,'-B',str(D/'verify_artifacts.py')],cwd=D,capture_output=True)
assert check.returncode==0,check.stdout+check.stderr
with zipfile.ZipFile(Z,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in sorted(D.rglob('*')):
        if p.is_file():z.write(p,p.relative_to(D).as_posix())
with zipfile.ZipFile(Z) as z:
    assert z.testzip() is None
    assert set(z.namelist())==set(manifest)|{'artifact_manifest.json'}
    for name,item in manifest.items():assert sha256(z.read(name)).hexdigest()==item['sha256'],name
shutil.copyfile(Z,PZ)
assert sha256(PZ.read_bytes()).hexdigest()==sha256(Z.read_bytes()).hexdigest()
P.mkdir()
for name in ('formal_report.json','formal_report.txt','README.txt','minimal_wr29.py','minimum_execution.json'):shutil.copyfile(D/name,P/name)
assert sha256((P/'formal_report.json').read_bytes()).hexdigest()==expected
result={'directory':str(P),'sealed_directory':str(D),'zip':str(PZ),'zip_bytes':PZ.stat().st_size,'zip_sha256':sha256(PZ.read_bytes()).hexdigest(),'manifest_entries':len(manifest),'formal_report_sha256':expected,'portable_verifier_exit':check.returncode,'WR29':'confirmed_open_P1_at2d1d306','software_passed':False,'phase2_accepted':False}
(R/'package_result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False),flush=True)
