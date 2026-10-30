from pathlib import Path
import hashlib,io,json,os,shutil,subprocess,sys,tarfile,zipfile
R=Path(__file__).parent;OUT=Path(r'B:\BaiduSyncdisk\学习\投资\量化\量化交易比赛\LLM审核\review-44676db-20261027');G=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\repo')
D=json.loads((R/'formal_report.json').read_bytes())
assert D['financial_evidence']is False and D['software_acceptance']['full_phase2_accepted']is False
assert D['findings']==[] and D['software_acceptance']['blocking']==[]
for name in ['archive_agent','cert_agent','protocol_agent']:assert(R/name/'qa.txt').is_file(),name
assert not OUT.exists()and not OUT.with_suffix('.zip').exists();OUT.mkdir()
skip={'__pycache__','.git','cases','quick_cases','repository_source','build_source','evidence_build_source','cli_cases','pure_cases','preflight_cli_cases','worker_cases','native-base','isolated_fixed81','alternate_root'}
for base,dirs,files in os.walk(R):
 folder=Path(base);rel=folder.relative_to(R)
 if not rel.parts or rel.parts[0]!='source':dirs[:]=[d for d in dirs if d not in skip and(d!='source'or folder==R)]
 for name in files:
  if name.endswith(('.pyc','.tar'))or name=='package_result.json':continue
  q=OUT/rel/name;q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(folder/name,q)
def tree(commit):
 raw=subprocess.check_output(['git','-C',str(G),'archive',commit])
 with tarfile.open(fileobj=io.BytesIO(raw))as t:return{m.name:t.extractfile(m).read()for m in t.getmembers()if m.isfile()}
sources={}
for name,commit,where,count in [('candidate',D['reviewed_source_commit'],'source',5433),('baseline_ccad',D['baseline_commit'],'baselines/ccad61d/source',4977),('actual_cloud7fc',D['evidence_commits']['actual_cloud_execution'],'baselines/7fc5ef2/source',4204)]:
 expected=tree(commit);assert len(expected)==count;dest=OUT/where
 if name!='candidate':
  for p,raw in expected.items():
   q=(dest/p).resolve();assert q.is_relative_to(dest.resolve());q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(raw)
 assert{p.relative_to(dest).as_posix():p.read_bytes()for p in dest.rglob('*')if p.is_file()}==expected,name
 sources[name]={'commit':commit,'directory':where,'count':count,'files':{p:hashlib.sha256(raw).hexdigest()for p,raw in expected.items()}}
def write(name,obj):(OUT/name).write_bytes((json.dumps(obj,ensure_ascii=False,indent=2)+'\n').encode())
write('source_git_manifest.json',sources)
(OUT/'requirements-audit.txt').write_bytes(''.join(n+'=='+v+'\n'for n,v in D['environment']['dependencies'].items()).encode())
readme='''AQRP-LLM独立复验44676db609b3b7c2175fa7fa4f19c8ccf8165458，Windows，2026-10-27。
先读formal_report.txt/.json、test_execution_summary.json；完整JSON和最小复现也直接在聊天交付，本包为补充。
本轮WR25/26/27原修复及注明相邻离线边界通过，未发现新增已复现软件问题；阶段2整体仍待真实成功联合链与数据认证，阶段3–7未验收，financial_evidence=false。通过仅限本次已测离线范围，不认证无缺陷、供应商或金融效果。
封包核验：python -B verify_artifacts.py，仅标准库、无网络。artifact_manifest.json为本包当前raw校验权威；source_git_manifest.json列三固定Git树全部hash。5433候选、4977失败ccad基线、4204实际cloud7fc均完整导出原字节，逐文件重比；固定source内部历史路径完全不裁剪。
重放先复制到新目录，Python3.10.11及requirements-audit.txt版本。正常入口python -B tools/stages.py verify在新完整可写副本运行，668通过；不向sealed包写输出。root另实际执行tools/research.py build，完整副本全部字节不变。
原7场景MRE字节不改：python -B minimal_wr25_wr26.py --source <固定source> --output <新JSON>。旧ccad exit1三误过，新446 exit0；明确stock/null/unknown/future/missing应不足，etf/unlisted仍可排除。原创fixture来自固定Git内历史独立审核，不导入开发者夹具。根独立再次确认在root_repair_confirmation。
WR27原MRE在旧ccad负控exit1。原字节直接跑新候选先因旧baseline断言停在产品CLI之前，首次保留，不记产品失败或通过；仅C/B两版本常量窄适配、原预期断言不改后新候选exit0。复现：python -B archive_agent/adapted_minimal_wr27.py --source <固定source> --git-repository <已有Git对象库> --output <新目录>。默认0、错误S哈希1、正确T哈希0；相对root及7目标拒绝也正确；root第二次独立确认在root_wr27_confirmation。
原WR20 13/43、WR22 9/23、上轮WR25/26边界9/29及新增资格套件、协议5/21、native9/90、manual8、recovery5/46、f5d6/91等实际结果详正式JSON。16历史248方法2307子例通过；方法/场景/子例/CLI/静态及重复复现有重叠，不计独有总数。67来源检查、WR27 9组/7拒绝为静态或只读CLI，非产品unit。
所有实际argv/cwd/exit/stdout/stderr/hash、首次失败及版本/夹具适配保留。原native/recovery合法绑定及WR21明确四字段前置为已认可适配；原脚本内旧literal SHA/静态目标标签保留，实际身份由外层绑定。协议并发在v1/v2每组4实际Windows进程只发1许可，不扩为OS kill/断电认证。
可重建cases、嵌套derived source、build_source、alternate_root和source.tar不重复入包；固定source树内部全部保留。开发省略binary Git index原件实际存在且rawhash吻合，仅临时工件未转码；原打包UTF8失败与纠正及61开发输出/381选择归档核验保留，不冒称完整上轮包。
权威17事件、7/12配置、10/20Research、1/16LEAN与ccad原字节一致；工程2/2/1停止，无退款。本轮真实QC/Research/LEAN/model/deploy/trading/账本写入0，生产源码/Git index不改，PR保持草稿未批准合并。
实际云端仍7fc归档Research CollectionError失败，底层原因未知；旧LEAN归档初始化源码不符失败，均非本轮live read。归档31云端参考对当前31为28同3异，不认证当前inventory/旧失败worker。正常原生失败恢复15→17→17；故障15→16→18→18的pending非新扣费。
新版真实Research→缓存→LEAN成功联合链、全历史US200、财务版本、真实送达/摄入仍证据不足；history API次数/接收行数/真实订单/金融统计null。正式研究、自动GPT、交易、最终测试关闭；2024–2025已暴露，2026独立性未知。
下一步是由有权执行者处理工程停止条件及真实联调/数据证据；本轮审核不授权新增执行、扩大额度或金融测试。
'''
(OUT/'README.txt').write_bytes(readme.encode())
write('artifact_verification.json',{'source_files':{k:v['count']for k,v in sources.items()},'fixed_Git_equal':True,'original_fix_scope_passed':True,'full_phase2_accepted':False,'financial_evidence':False})
manifest={p.relative_to(OUT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()for p in OUT.rglob('*')if p.is_file()};write('artifact_manifest.json',manifest)
p=subprocess.run([sys.executable,'-B',str(OUT/'verify_artifacts.py')],capture_output=True);assert p.returncode==0,p.stderr.decode(errors='replace')
archive=OUT.with_suffix('.zip')
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9)as z:
 for q in OUT.rglob('*'):
  if q.is_file():z.write(q,OUT.name+'/'+q.relative_to(OUT).as_posix())
with zipfile.ZipFile(archive)as z:
 assert z.testzip()is None
 for name,digest in manifest.items():assert hashlib.sha256(z.read(OUT.name+'/'+name)).hexdigest()==digest,name
result={'directory':str(OUT),'zip':str(archive),'zip_bytes':archive.stat().st_size,'zip_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'manifest_entries':len(manifest),'portable_verifier_exit':p.returncode,'portable_verifier_stdout':p.stdout.decode()}
(R/'package_result.json').write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode());print(json.dumps(result,ensure_ascii=False))
