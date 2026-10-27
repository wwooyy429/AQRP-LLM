from pathlib import Path
import hashlib,io,json,os,shutil,subprocess,sys,tarfile,zipfile
R=Path(__file__).parent
OUT=Path(r'B:\BaiduSyncdisk\学习\投资\量化\量化交易比赛\LLM审核\review-ae2b898-20261027')
GIT=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\repo')
D=json.loads((R/'formal_report.json').read_text(encoding='utf-8'))
assert D['financial_evidence'] is False and [x['id'] for x in D['findings']]==['WR-18']
assert all((R/n).exists()for n in ['evidence_agent/qa.txt','admission_agent/qa.txt','recovery_agent/report.json'])
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
for name,commit,directory in [('candidate',D['reviewed_source_commit'],'source'),('baseline8f',D['baseline_commit'],'baselines/8f7236e/source')]:
    expected=raw(commit);dest=OUT/directory
    if name!='candidate':
        for rel,data in expected.items():
            f=(dest/rel).resolve();assert f.is_relative_to(dest.resolve());f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(data)
    actual={p.relative_to(dest).as_posix():p.read_bytes() for p in dest.rglob('*') if p.is_file()}
    assert actual==expected,name
    sources[name]={'commit':commit,'directory':directory,'count':len(expected),'files':{k:hashlib.sha256(v).hexdigest() for k,v in expected.items()}}
def write(name,value): (OUT/name).write_bytes((json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
write('source_git_manifest.json',sources)
(OUT/'change.diff').write_bytes(subprocess.check_output(['git','-C',str(GIT),'diff',D['baseline_commit'],D['reviewed_source_commit']]))
(OUT/'requirements-audit.txt').write_bytes(''.join(n+'=='+v+'\n' for n,v in D['environment']['dependencies'].items()).encode())
(OUT/'README.txt').write_bytes('''AQRP-LLM ae2b898独立复验（2026-10-27，Windows）
完整SHA ae2b8985f3799c246e90341370f86d80483f63ed。
WR16原三类准入、WR17原MRE和5/46恢复范围修复后通过；新增WR18/P2，候选软件失败，阶段2整体及3–7未验收。financial_evidence=false。
先读formal_report.txt/.json和findings.json。正式JSON、短MRE同时在聊天直接交付；附件保留全部原件。
source1843份、baseline8f1563份已与固定git archive全部原字节核对，source_git_manifest.json含逐文件hash。
只读包校验：python -B verify_artifacts.py，不依赖项目包/网络。
项目依赖：Python3.10.11，pip install -r requirements-audit.txt；本轮实际Windows固定venv，其余环境未认证。
便携主复现：python -B minimal_wr18.py source。只使用内存，当前exit1；先有合法匹配完成准入正控，再显示input_hash冲突被Bridge拒绝却被Registry准入、LEAN0→1。
完整三负一正MRE：先把root_confirmation/minimal_checked_dependency.py复制至不存在结果文件的新目录，再python -B <新脚本路径> <本包source绝对路径>，当前exit1；脚本会把JSON写在脚本旁，避免覆盖封包原结果。
原两个完整MRE在original_probes/下；root原字节重放旧8f各exit1、ae各exit0。原短inline Registry仍exit1是新RegistryError安全早拒绝未被旧脚本捕获，不能当原bug未修。原始失败/退出和说明全部保留。
本地442、16旧套件248/2307、Collection12/36、注解10/803、联合worker9/81、原7全过；新准入9方法6过3失败/4子例；WR17新5/46全过。额外旧6与原7重叠。
WR17补4失败结算为手工合成场景，不是4新增单元方法或真实原生失败；100个主/补CLI+12直接freeze、10次metadata_finish、实际worker0。原MRE另有子进程，未混算。
全部套件/子例重复不声称独有总数；WR18原MRE及短主例是重复确认，不加方法。准入首次原6/新9外层stderr未独立重定向的限制如实保存，MRE及root复验raw stdout/stderr齐全。
364元数据检查通过，0unit方法；两build/两preview无变化。证据代理猜错文件名的只读命令、QA枚举测量的首稿修正均保存，不算产品测试错误。
只读QC：先list_projects，读25实现raw等Git75/cloud，另1input raw等已准入archive。目录仅列18py却8份漏列可读，不认证全集；未读notebook/任何回测状态结果日志，未编译/写云端/执行任务。
旧LEAN39cafa...当前完成/失败未知；pending仅归档。不新增真实Research/LEAN/模型/部署或预算；12事件仍6/12、9/20、1/16。2024–25暴露、2026独立性未知及关闭开关保留。
新独立脚本及support均在admission_agent/、recovery_agent/，有完整source复制/CLI/合成元数据重建，不导入开发测试。重放需要写结果的脚本请先复制相关脚本/支持到新工作目录，保留封包只读。run_main_checks.py及历史脚本保留本机解释器/旧负对照路径；跨机器完整重放未认证，便携主MRE不依赖它们。
实际命令、原始stdout/stderr、首次错误、hash、QA和固定Git源保留。可重建完整case/source副本、source.tar与__pycache__不重复装包，未删除任何原C/B证据。固定Git source内部所有目录均完整保留。
修复任务：统一共享事务内提交/完成合同，核对原提交存在、全部deployment含input_hash、非空回执，并保留合法路径/幂等/FS/并发，再提交新SHA独立复验。
'''.encode('utf-8'))
write('artifact_verification.json',{'candidate_files':1843,'baseline8f_files':1563,'raw_source_equal_Git':True,'WR16':'passed_original_scope','WR17':'passed_retested_scope','findings':['WR-18'],'financial_evidence':False})
manifest={p.relative_to(OUT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.rglob('*') if p.is_file()}
write('artifact_manifest.json',manifest)
checked=subprocess.run([sys.executable,'-B',str(OUT/'verify_artifacts.py')],capture_output=True)
assert checked.returncode==0,checked.stderr.decode(errors='replace')
archive=OUT.with_suffix('.zip')
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for p in OUT.rglob('*'):
        if p.is_file():z.write(p,OUT.name+'/'+p.relative_to(OUT).as_posix())
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    for name,digest in manifest.items():assert hashlib.sha256(z.read(OUT.name+'/'+name)).hexdigest()==digest,name
result={'directory':str(OUT),'zip':str(archive),'zip_bytes':archive.stat().st_size,'zip_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'manifest_entries':len(manifest),'portable_verifier_exit':checked.returncode,'portable_verifier_stdout':checked.stdout.decode('utf-8')}
(R/'package_result.json').write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode('utf-8'));print(json.dumps(result,ensure_ascii=False))
