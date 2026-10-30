from pathlib import Path
from hashlib import sha256
import os,sys,json,shutil,subprocess,zipfile
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parent
D=R/'sealed_package';Z=R/'sealed_package.zip'
P=Path(r'B:\BaiduSyncdisk\学习\投资\量化\量化交易比赛\LLM审核\review-c2e63ac-20261029');PZ=P.with_suffix('.zip')
assert all(not x.exists() for x in (D,Z,P,PZ)),'Refuse overwrite'
expected='3e8f605973c618ba9aa1761ade0a9901b9fb7003fb609492664621d99c517470'
assert sha256((R/'formal_report.json').read_bytes()).hexdigest()==expected
for folder in ('entry_agent','api_agent','archive_agent'):
    q=json.loads((R/folder/'formal_QA_final.json').read_text(encoding='utf-8'))
    assert expected in json.dumps(q) and not q.get('issues'),folder
maps=json.loads((R/'source_git_manifest.json').read_text(encoding='utf-8'))
for folder,item in maps.items():assert all(sha256((R/folder/n).read_bytes()).hexdigest()==v['sha256'] for n,v in item['files'].items()),folder
mre=json.loads((R/'original_MRE_replay.json').read_text(encoding='utf-8'))
assert [r['assertion_program_exit'] for r in mre['records']]==[1,0]
files=[]
for folder,dirs,names in os.walk(R):
    base=Path(folder);rel=base.relative_to(R)
    immutable=bool(rel.parts and rel.parts[0] in {'source','materials'})
    if not rel.parts:dirs[:]=[n for n in dirs if n not in {'work_source','materials_checkout','sealed_package'}]
    if not immutable:
        dirs[:]=[n for n in dirs if n not in {'.git','__pycache__'}]
        if rel.as_posix() in {'api_agent/replay_context','archive_agent/replay_context'}:dirs[:]=[n for n in dirs if n!='source']
    for name in names:
        p=base/name
        if not immutable and (p.suffix=='.pyc' or name.endswith('.baiduyun.uploading.cfg') or (not rel.parts and name in {'sealed_package.zip','package_result.json','artifact_manifest.json'})):continue
        files.append(p)
D.mkdir()
for p in sorted(files):
    dest=D/p.relative_to(R);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
(D/'README.txt').write_text('''AQRP-20261029-C2E63AC-WR29-27 独立复验
WR29在c2e63ac原CLI/stdio合法factory缺陷范围修复后通过并关闭；阶段2整体仍未通过。
固定source c2e63ac、materials f698a38完整Git原始字节分别7448/7766文件；218身份，原44云端部署未因此执行。
原MRE脚本完全不改：旧2d0/2/2，断言exit1；新c2 0/0/0，exit0；旧失败不倒改。
实际1012仓库、原host19、新entry6、scope7通过；独立原stdio15/61+4/12、API12/63+6/26、原锁18/37、通知12/79+6/27、周期7/28当前源重放通过；新增entry8/51、append3/28通过。计数重叠，不合计独有总数。
真实Win32共享拒写：原生错误32，Python CRT errno13/winerrorNone。首审核OS字段期望错及更正保留；等效新测试不证明开发早期2条未取trace异常根因。
开发79/84、89/90和确切EACCES trace分别保留；原store未归档，8/8和10/10仅核对原记录，未在本轮独立重跑，也未追认历史全绿。
161选择原件恢复、原报告224a...、原ZIPfeff...与旧Git完整映射已核对；selected不是完整原包。348开发worktree守卫前后相等，5份CRLF与Git差异单列，不冒称全部Git raw相同。
71权威事件和原69前缀不变；配置周期3/13累计16、Research17/20LEAN3/16、008关闭。QC/Research/LEAN/compile/模型/市场/生产automation调用及权威预算/生产源码写入均0。
formal_report_pre_QA.*及首QA问题保留：10个顶层定义含私有helper，最终已精确表述；报告/QA辅助引号和JSON形状/编码首错记录均保留。不是产品失败，不计unit。
为去重仅省略根work_source、materials_checkout、api_agent/replay_context/source及archive_agent/replay_context/source重复树；原完整source/materials、独立脚本、原始失败、输出与QA均保留。非Git同步临时旁文件不收入。
封存在C本地完成严格集合/全hash/ZIP CRC检查后复制B；B公开目录仅提供报告/最小脚本副本，完整证据/校验器在ZIP。
最小正例：python -B original_minimal_wr29.py source（新c2应exit0）。
旧负例：用原2d Git检出或旧完整包的source目录作同一脚本参数，应0/2/2且脚本exit1；本包保存实际旧负例原输出，不需要修改成功预期。
完整仓库回归请另建source临时副本执行python -B tools/stages.py verify，会生成audit/stage_verification.json，不写封存目录。
材料verify_review.py须真实固定Git检出，本次已在独立Git副本实际运行。各root/agent命令与退出码均保存。
封存校验：python -B verify_artifacts.py。文件校验通过不授予阶段2或金融验收。
真实factory/transport/通知/云端链、完整回执、数据与计费认证仍缺；未来1/1/1未授权无ID。正式研究、自动GPT、交易和最终测试继续关闭，financial_evidence=false。
''',encoding='utf-8')
manifest={}
for p in sorted(D.rglob('*')):
    if p.is_file():
        raw=p.read_bytes();manifest[p.relative_to(D).as_posix()]={'sha256':sha256(raw).hexdigest(),'bytes':len(raw)}
(D/'artifact_manifest.json').write_text(json.dumps({'review_id':'AQRP-20261029-C2E63AC-WR29-27','files':manifest},ensure_ascii=False,indent=2),encoding='utf-8')
check=subprocess.run([sys.executable,'-B',str(D/'verify_artifacts.py')],cwd=D,capture_output=True)
assert check.returncode==0,check.stdout+check.stderr
with zipfile.ZipFile(Z,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in sorted(D.rglob('*')):
        if p.is_file():z.write(p,p.relative_to(D).as_posix())
with zipfile.ZipFile(Z) as z:
    assert z.testzip() is None
    assert set(z.namelist())==set(manifest)|{'artifact_manifest.json'}
    for name,v in manifest.items():assert sha256(z.read(name)).hexdigest()==v['sha256'],name
shutil.copyfile(Z,PZ)
assert sha256(PZ.read_bytes()).hexdigest()==sha256(Z.read_bytes()).hexdigest()
P.mkdir()
for name in ('formal_report.json','formal_report.txt','README.txt','original_minimal_wr29.py','original_MRE_replay.json'):shutil.copyfile(D/name,P/name)
assert sha256((P/'formal_report.json').read_bytes()).hexdigest()==expected
result={'directory':str(P),'sealed_directory':str(D),'zip':str(PZ),'zip_bytes':PZ.stat().st_size,'zip_sha256':sha256(PZ.read_bytes()).hexdigest(),'manifest_entries':len(manifest),'formal_report_sha256':expected,'portable_verifier_exit':check.returncode,'WR29':'fixed_verified_closed_at_c2e63ac','local_tested_software_scope_passed':True,'phase2_accepted':False}
(R/'package_result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False),flush=True)
