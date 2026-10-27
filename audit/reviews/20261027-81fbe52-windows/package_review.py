from pathlib import Path
import hashlib,io,json,os,shutil,subprocess,sys,tarfile,zipfile
R=Path(__file__).parent
OUT=Path(r'B:\BaiduSyncdisk\学习\投资\量化\量化交易比赛\LLM审核\review-81fbe52-20261027')
GIT=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\repo')
D=json.loads((R/'formal_report.json').read_text(encoding='utf-8'))
assert D['financial_evidence'] is False and D['WR18_acceptance']['status']=='修复后通过'
assert [x['id']for x in D['findings']]==['WR-19'] and D['findings'][0]['blocking'] is False
assert all((R/n).exists()for n in ['evidence_agent/qa.txt','admission_agent/qa.txt','recovery_agent/qa.txt'])
assert not OUT.exists() and not OUT.with_suffix('.zip').exists()
OUT.mkdir()
skip={'__pycache__','.git','cases','quick_cases','repository_source','evidence_build_source'}
for base,dirs,files in os.walk(R):
    p=Path(base);rel=p.relative_to(R)
    if not rel.parts or rel.parts[0]!='source':
        dirs[:]=[n for n in dirs if n not in skip and (n!='source' or p==R)]
    for name in files:
        if name.endswith(('.pyc','.tar')) or name=='package_result.json':continue
        src=p/name;dst=OUT/rel/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
def raw(commit):
    data=subprocess.check_output(['git','-C',str(GIT),'archive',commit])
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        return {m.name:archive.extractfile(m).read() for m in archive.getmembers() if m.isfile()}
sources={}
for name,commit,directory in [('candidate',D['reviewed_source_commit'],'source'),('baseline_ae',D['baseline_commit'],'baselines/ae2b898/source')]:
    expected=raw(commit);dest=OUT/directory
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
(OUT/'README.txt').write_bytes('''AQRP-LLM 81fbe529独立复验（2026-10-27，Windows）
固定SHA 81fbe5294055423e88ee5aeae48ca6223e7971da。
WR18在本轮范围修复后通过，未发现新增阻断性软件缺陷；WR19/P3为非阻断历史摘要错配。阶段2整体及3–7未验收，financial_evidence=false。
先读formal_report.txt/.json、findings.json；正式JSON和当前发现最小复现也在聊天直接提供。
source2374与baseline ae1843份Git原字节均全量核对；source_git_manifest.json保存所有hash。
只读封包校验：python -B verify_artifacts.py，无需项目依赖或网络。
实际依赖：Python3.10.11、requirements-audit.txt锁定版本；原生Windows已执行，其他环境未认证。
便携修复断言：python -B verify_wr18_repair.py source（本候选0，baselines/ae2b898/source负对照1）。只用内存；合法匹配允许、冲突回执拒绝且完整artifact/usage不变。原短MRE不改，adapter diff明确保留。
当前非阻断最小：python -B minimal_wr19.py source，当前12声明/13计算，exit1；只读所引用ae候选29与旧25已知文件参考。4条不在旧参考不证明实际云端缺4或全集；不覆历史dc49的12。
完整WR18原MRE在original_probes/minimal_checked_dependency.py，复制该脚本到一个没有既有结果文件的新目录后运行<新脚本> <source绝对路径>，修复版0、baseline ae1。脚本在自己旁写结果，避免覆盖本包只读原件。
仓库规定入口453全过；16旧248/2307、Collection12/36、注解10/803、联合worker9/81、原7都过；WR18原9/4及新增修正版9/39全过；恢复原5/46、新3/28与4手工合成失败探针全过。套件有重叠，不汇总为独有测试总数。
新增共享合同首9方法8过1审核输入错误（矛盾的collection_nonempty=false），修正为raw_data_received=false，不改断言/生产；首稿及raw/diff保留。元数据首634有6审核器CRLF测量错误，修正后633过1真实WR19不符；不算产品软件失败。
历史script里写死旧ae commit文字保持原字节；本轮实际命令、argv、source hash和外层81身份独立记录，不把旧literal当本轮身份。
全部实际命令、rawstdout/stderr、报告、首轮错误、QA及Git源码保存。完整可重建case/source副本、source.tar和__pycache__不重复装包；固定Git source内部全部路径保留，不删旧C/B证据。
run_main_checks及历史完整回归保留本机venv/旧负对照路径，跨机器全套未认证；便携两个主脚本不依赖这些本机路径。需要写输出的独立代理脚本应先复制相应scripts/support到新工作目录。
本轮无QC访问，不读旧回测状态/结果/日志，不更新/部署/派发。平台25+1核对只是前轮归档历史，不冒称当前源/终态核验。旧LEAN39cafa...完成/失败仍未知。
12事件回放预算6/12、Research9/20、LEAN1/16，工程各用1/2；无新增真实执行/模型/部署/预算。2024–25暴露、2026独立性未知保留，正式研究/自动GPT/最终测试/交易关闭。
真实候选运行、原生失败、US200与财务版本/实际可用性等认证仍缺；离线软件通过不构成金融有效性结论，也未修改、批准或合并开发成果。
'''.encode('utf-8'))
write('artifact_verification.json',{'candidate_files':2374,'baseline_ae_files':1843,'raw_source_equal_Git':True,'WR18':'passed_retested_scope','nonblocking_findings':['WR-19'],'financial_evidence':False})
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
