from pathlib import Path
import hashlib,io,json,os,shutil,subprocess,sys,tarfile,zipfile
R=Path(__file__).parent
OUT=Path(r'B:\BaiduSyncdisk\学习\投资\量化\量化交易比赛\LLM审核\review-84414ab-20261027')
GIT=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\repo')
D=json.loads((R/'formal_report.json').read_text(encoding='utf-8'))
assert D['financial_evidence'] is False and not D['findings'] and D['tests']['software_unit_methods']==0
assert D['metadata_acceptance']=='WR19_passed_at84414ab'
assert all((R/n).exists()for n in ['identity_agent/qa.txt','evidence_agent/qa.txt','comparison_agent/qa.txt'])
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
    with tarfile.open(fileobj=io.BytesIO(data))as archive:
        return {m.name:archive.extractfile(m).read()for m in archive.getmembers()if m.isfile()}
sources={}
for name,commit,directory in [('candidate',D['reviewed_source_commit'],'source'),('baseline81',D['baseline_commit'],'baselines/81fbe52/source')]:
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
(OUT/'README.txt').write_bytes('''AQRP-LLM 84414ab WR19元数据局部独立核对（2026-10-27，Windows）
固定SHA 84414ab49c39e25cb50ece1c1debeefa3993c874；软件通过身份保持81fbe5294055423e88ee5aeae48ca6223e7971da。
WR19元数据更正通过，无新增发现。阶段2整体及3–7仍未验收，financial_evidence=false。
先读formal_report.txt/.json；正式JSON及原MRE亦在聊天直接提供，本包为补充原始证据。
source2890份与baseline81的2374份均与固定git archive完整原字节一致，source_git_manifest.json保存全部hash。
只读封包校验：python -B verify_artifacts.py（无第三方依赖/网络）。
原独立MRE：python -B metadata_replay/original_minimal_wr19.py source，本候选声明13/计算13退出0；source替换为baselines/81fbe52/source则声明12/计算13退出1。原脚本SHA4e65b6...不变。
开发核对程序：python -B source/audit/review_packages/wr19/verify_archived_comparison.py source，当前0；本轮独立7变体均按预期拒绝。此程序只核对引用比较，不认证任意readiness字段或远程来源。
只运行元数据/JSON/rawhash/档案/身份函数核对：148、37、591分组均通过，分组重叠不计独有总数。0软件unit/0subcases/0suite/0build/0QC，没有重跑453或原软件套件。453只保留81的原独立结果及当前开发/CI归档记录，不虚列本轮独立软件运行。
首归档590检查中1过严阅读断言已改为历史范围核对（当前scope说明允许澄清），首稿/raw/报告完整保留，补历史d0细表检查后591通过；不当作产品错误。
当前16同哈希，9不同+4不在旧参考=13，候选ae29/旧25参考及原12声明/整81 readiness字节/历史dc49 8+4=12保留。4不在参考不能证明实际云端缺4或全集。
115运行/配置/测试/权威runtime及输入保护文件raw全等81；实现07ba5c...、本地部署25d3c8...、activeconfig272e24...保持。source3d6a236f...、execution432d7f42...因.gitattributes、wr18/wr19文档三路径变化，身份选择算法未变。软件通过不授新派发许可，新派发仍要绑定当前身份和原预算保护。
22开发原件、487旧独立原件及27引用、2202旧证据、4754旧最终artifact/ZIP核对。开发Git-export只作归档审阅，root原MRE在本次最终固定Git导出实际重放。
本轮无QC、云端编译/写入/部署/Research/LEAN/模型；旧LEAN当前完成/失败未知，不查状态/结果/日志。平台25+1只是历史核对，无新平台全集证据。
12事件仍配置6/12、Research9/20、LEAN1/16；工程各1/2，新真实扣费0。2024–25暴露、2026独立性未知保留，正式研究/自动GPT/最终测试/交易关闭。
全部脚本、实际命令、raw stdout/stderr、首次阅读断言、QA、报告和固定源码保留。为重放会写结果的代理脚本，请先复制scripts/support至新工作目录；原包保留只读。完整可重建临时cases/source副本及source.tar不重复装包，固定Git source内部全部路径保留，未删除任何旧C/B证据。
不修改、批准或合并开发成果；后续仍须旧LEAN原生终态结算、新版真实有界运行及回执、US200/财务版本/真实公开与供应商送达和摄入等分别认证。
'''.encode('utf-8'))
write('artifact_verification.json',{'candidate_files':2890,'baseline81_files':2374,'raw_source_equal_Git':True,'WR19':'passed_metadata_correction','software_unit_methods':0,'software_pass_commit':D['software_acceptance_bound_to_commit'],'findings':[],'financial_evidence':False})
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
