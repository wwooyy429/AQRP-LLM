from pathlib import Path
import hashlib,io,json,os,shutil,subprocess,sys,tarfile,zipfile
R=Path(__file__).parent
OUT=Path(r'B:\BaiduSyncdisk\学习\投资\量化\量化交易比赛\LLM审核\review-66ff72f-20261027')
GIT=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\repo')
D=json.loads((R/'formal_report.json').read_text(encoding='utf-8'))
assert D['financial_evidence']is False and D['software_acceptance']['full_phase2']is False and D['findings']==[]
for p in ['evidence_agent/qa.txt','preflight_agent/qa.txt','native_agent/qa.txt']:assert(R/p).exists(),p
assert not OUT.exists()and not OUT.with_suffix('.zip').exists()
OUT.mkdir()
skip={'__pycache__','.git','cases','quick_cases','repository_source','evidence_build_source','isolated_fixed81',
    'cli_cases','pure_cases','preflight_cli_cases'}
for base,dirs,files in os.walk(R):
    p=Path(base);rel=p.relative_to(R)
    if not rel.parts or rel.parts[0]!='source':
        dirs[:]=[n for n in dirs if n not in skip and(n!='source'or p==R)]
    for name in files:
        if name.endswith(('.pyc','.tar'))or name=='package_result.json':continue
        src=p/name;dst=OUT/rel/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
def raw(commit):
    data=subprocess.check_output(['git','-C',str(GIT),'archive',commit])
    with tarfile.open(fileobj=io.BytesIO(data))as archive:
        return{m.name:archive.extractfile(m).read()for m in archive.getmembers()if m.isfile()}
sources={}
for name,commit,directory,expected_count in[
 ('candidate',D['reviewed_source_commit'],'source',3178),
 ('baseline_84414ab',D['baseline_commit'],'baselines/84414ab/source',2890),
 ('software_81fbe52',D['evidence_commits']['previous_software_acceptance'],'baselines/81fbe52/source',2374)]:
    expected=raw(commit);assert len(expected)==expected_count,name;dest=OUT/directory
    if name!='candidate':
        for rel,data in expected.items():
            f=(dest/rel).resolve();assert f.is_relative_to(dest.resolve());f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(data)
    actual={p.relative_to(dest).as_posix():p.read_bytes()for p in dest.rglob('*')if p.is_file()}
    assert actual==expected,name
    sources[name]={'commit':commit,'directory':directory,'count':len(expected),'files':{k:hashlib.sha256(v).hexdigest()for k,v in expected.items()}}
def write(name,value):(OUT/name).write_bytes((json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
write('source_git_manifest.json',sources)
(OUT/'change.diff').write_bytes(subprocess.check_output(['git','-C',str(GIT),'diff',D['baseline_commit'],D['reviewed_source_commit']]))
(OUT/'requirements-audit.txt').write_bytes(''.join(n+'=='+v+'\n'for n,v in D['environment']['dependencies'].items()).encode())
(OUT/'README.txt').write_bytes('''AQRP-LLM 66ff72ffaaff8c91c008898e6527c91131176c2a 独立审核（2026-10-27 Windows）
结论：明确测试的离线软件范围通过；阶段2整体仍待验收，financial_evidence=false。
先读formal_report.txt/.json、test_execution_summary.json。正式JSON及最小探针也在聊天直接交付。
当前3178、基线84414ab2890、软件基线81fbe522374份Git原字节全量核对；全部哈希见source_git_manifest.json。
只读封包校验：python -B verify_artifacts.py，无需项目依赖或网络。
便携最小探针：python -B verify_phase2_scope.py source；使用requirements-audit.txt锁定依赖，4链通过，只有临时合成文件和归档失败元数据，无平台调用/Registry写入。实际重放两次不算8独有链。
仓库入口：先将source复制到新工作目录，再 python -B tools/stages.py verify（会生成报告，不在封包只读原件内运行）；本轮530通过。
历史16套件248方法2307子例（含已认可adapted56，原raw56旧异常仍在）、Collection12/36、worker9/81、fraction10/803、工程恢复5/46、quick7/0、WR16原9/4、WR18合同9/39、旧完成3/28，均在说明的夹具/辅助位置适配后通过。
新增预检12/70与原生失败/拒绝6/62通过；另原失败4、写入故障4手工探针、327证据检查。方法/子例/CLI/metadata_finish/worker/静态检查严格分列，跨套件有重叠，不宣传独有总数。
首次错误不覆盖：pure审核器surrogate外部hash；旧pending夹具遇现13条failed账本；恢复漏放辅助文件；静态读取/正式报告计数字段读取错误。首稿、raw/trace、适配差异、修正结果均保留，不改生产和期望断言。
所有实际argv、stdout/stderr及结果保留。旧脚本字面旧commit不改，外层实际source与hash标明本轮66。历史完整脚本部分保留本机venv/路径，跨机器全套未认证；需写输出脚本先复制scripts/support到新目录。可重构的大case/source与source.tar不重复入包，但固定source树内历史文件全部保存；旧C/B证据未删除。
审核者实际只读QC：先list_projects；project38436695 open_project；26份Python read_file，25旧实现+原input逐字节匹配；排除research.ipynb，不读数据/日志；已交付旧LEAN39cafa... read_backtest一次，原生Runtime Error，冻结部署初始化不一致。原回执/本轮原回执rawSHA相同。
这是当前返回源码引用，不证明失败worker快照、全集或根因已修复。新candidate未部署或运行；无Research、LEAN提交、模型调用、交易或预算新增。
旧失败原件在隔离81镜像12→13→13，保持费用无退款无成功产物；实际权威13条账本未写。配置6/12、Research9/20、LEAN1/16；工程各1/2。
下一步补失败worker具体差异、固定新版实际成功联合任务、Research原生异常适配/真实回执，以及完整历史US200/财务版本/实际送达数据认证。市场执行须单独授权且先准入，不能为调试自动重试。
正式研究、自动GPT、最终测试、交易仍关闭；2024–2025已暴露、2026独立性未知。阶段3–7未验收，软件通过不代表金融有效。
本轮未修改开发者源码、预算或配置，未提交/推送/批准/合并PR。
'''.encode('utf-8'))
write('artifact_verification.json',{'candidate_files':3178,'baseline_844_files':2890,'software_81_files':2374,'raw_source_equal_Git':True,'full_phase2_accepted':False,'financial_evidence':False})
manifest={p.relative_to(OUT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()for p in OUT.rglob('*')if p.is_file()}
write('artifact_manifest.json',manifest)
checked=subprocess.run([sys.executable,'-B',str(OUT/'verify_artifacts.py')],capture_output=True)
assert checked.returncode==0,checked.stderr.decode(errors='replace')
archive=OUT.with_suffix('.zip')
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9)as z:
    for p in OUT.rglob('*'):
        if p.is_file():z.write(p,OUT.name+'/'+p.relative_to(OUT).as_posix())
with zipfile.ZipFile(archive)as z:
    assert z.testzip()is None
    for name,digest in manifest.items():assert hashlib.sha256(z.read(OUT.name+'/'+name)).hexdigest()==digest,name
result={'directory':str(OUT),'zip':str(archive),'zip_bytes':archive.stat().st_size,'zip_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'manifest_entries':len(manifest),'portable_verifier_exit':checked.returncode,'portable_verifier_stdout':checked.stdout.decode('utf-8')}
(R/'package_result.json').write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode('utf-8'));print(json.dumps(result,ensure_ascii=False))
