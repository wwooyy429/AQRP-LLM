from pathlib import Path
import hashlib,json,os,shutil,subprocess,sys,zipfile
R=Path(__file__).resolve().parent
OUT=Path('B:/BaiduSyncdisk/学习/投资/量化/量化交易比赛/LLM审核/review-4a42c18-20261028')
report=json.loads((R/'formal_report.json').read_bytes());report_hash=hashlib.sha256((R/'formal_report.json').read_bytes()).hexdigest()
assert report['findings'][0]['id']=='WR-28'and report['findings'][0]['status']=='confirmed_open'
assert report['software_acceptance']['candidate_delivery_validation']=='failed_WR28'and report['financial_evidence']is False
for name in ['policy_agent','bridge_agent','evidence_agent']:
 p=R/name/'qa.txt';assert p.is_file()and report_hash in p.read_text(encoding='utf-8'),name
assert not OUT.exists()and not OUT.with_suffix('.zip').exists();OUT.mkdir()
skip={'__pycache__','.git','verification_source','cases','work','private_context'}
for folder,dirs,files in os.walk(R):
 folder=Path(folder);rel=folder.relative_to(R)
 immutable=bool(rel.parts and(rel.parts[0]in{'source','archive_source'}or rel.parts[:3]==('baselines','8d65c29','source')))
 if not immutable:
  dirs[:]=[d for d in dirs if d not in skip and not(folder/d).is_symlink()and(folder/d).resolve().is_relative_to(R)]
 for name in files:
  if not immutable and(name.endswith(('.pyc','.tar'))or name in{'package_result.json','package_smoke_execution.json'}):continue
  src=folder/name;assert src.resolve().is_relative_to(R),src
  dest=OUT/rel/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dest)
sources=json.loads((OUT/'source_git_manifest.json').read_bytes())
for name,item in sources.items():
 S=OUT/item['directory'];actual={p.relative_to(S).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()for p in S.rglob('*')if p.is_file()};assert actual==item['files'],name
print('Copied evidence and verified all3 complete immutable Git trees',flush=True)
(OUT/'requirements-audit.txt').write_text(''.join(n+'=='+v+'\n'for n,v in report['environment']['dependencies'].items()),encoding='utf-8')
readme='''AQRP-LLM independent EOF-v2 review,2026-10-28 Asia/Shanghai.
Fixed code4a42c18f0b78bea2068d589bc12f1615712354c6; baseline8d65c290773547c83549c098172f1eb8c3376cd7; archive1cf26578da59eebd37e138ca5d6d076991386470. All3 complete Git trees retained at source,baselines/8d65c29/source,archive_source. Archive5-file changes contain only audit material; no cloud/tools/config/tests code changes.
Outcome: tested EOF-v2 core/bridge functionality PASSED within disclosed scope; candidate delivery reconciliation FAILED WR-28/P2; full phase2 NOT accepted. No candidate cloud success or financial effectiveness certification.
Verify this independent evidence seal: python -B verify_artifacts.py
That verifies complete source maps and every sealed raw artifact. It does NOT turn failed candidate checks into passes.
Reproduce WR28: python -B minimal_wr28.py source
Expected on exact candidate: exit1, protected122/mismatches3. The same failure occurs with archive_source. The reviewed product command python -B audit/review_packages/deployment-eof-v2/verify_candidate.py fails at line29 in a clean source copy. DO NOT edit expected hashes, convert protected files toCRLF or disable assertions to obtain a pass.
Wrong declarations are protected_before.json:2,122,123 for audit/data_exposure.json,config/research.json,config/workflow.json. They equal hypotheticalCRLF hashes, whereas root.gitattributes requires GitLF. Actual122 files are byte-identical across baseline/candidate/archive;119 declarations match. This is a delivery/reproducibility defect, not evidence that budget or exposure bytes changed. Root and child independently confirmed it. The source and erroneous declarations are preserved unmodified.
New materials fix should retain original erroneous manifest/failures, anchor corrected raw expectations to the immutable Git baseline, regenerate dependent artifact/results references, then run unmodified reconciliation in a second clean Git export and LF-policy checkout plus deliberate protected-byte rejection. This reviewer did not implement that fix.
Fresh executions: repository825 methods; developer auxiliary35; prior compatibility12/Pearson10/numeric16/atomic19/recognized-adapted56; independent core13methods/509named scenarios plus supplement3/20; independent bridge10/45. All those final scopes passed, but the required metadata checker failed. Method/scenario/process/static populations overlap, never sum as unique tests.
Supplement first3methods had2pass/1reviewer fixture error from Windows reserved directory label nul before entering product. Separate corrected script changes only label tozero-byte-source, preserving NUL input/assertions. Bridge first10 had9pass/1reviewer helper error from routing a collection plan into an engineering helper; actual legacy collection path corrected with original output/diff preserved. Evidence continuation initially used the wrong MCP hash level; corrected only independent expected level, while3 protected static checks remain false. Root static first had an else1 syntax typo before product import; first file/transcript retained. No product source fixes.
Evidence logical static40 =37pass+3failed aggregates (one perGit tree, same3 paths);8 readonly metadata and5 synthetic checks pass. Continuation process exit0 means it finished, not thatWR28 passed. Compact developer artifact manifest10 raw references and full offline stdout/stderr links verified separately.
For repository replay copy source to a new unsealed scratch directory, install requirements-audit.txt withPython3.10.11 and run python -B tools/research.py build and python -B tools/stages.py verify. Never let generated output overwrite sealed files. Actual command/cwd/exit/stdout/stderr hashes are in root_execution_records.json and agent records. Native/Git historical reconciliation requires a local readonly Git object repository containing662ccd8; the private Git repo is not included. StandaloneWR28 MRE uses only standard library and complete included source.
Core/manual controls are policy_agent/manual_eof_mre.py --source <tree> --out <scratch> --expected-v2 yes|no; baseline usesno and candidateyes. Both preserve strict legacy EOF; only explicit candidatev2 worker accepts bounded terminalLF; body changes reject. Original source identity retains inheritedUTF8sig/universal-newline normalization, not physical raw equality. Local freeze/firstprepare/precharge/PROJECT remain strict original identity; original v1 admissions never get rebuilt from currentv2.
New configuration3dd0b9832dff6ce1afdee616054f93dbdbdb3de5dbcb4f7c3545c560da0ab695 and34-file manifest8eb1e822... are unregistered/undeployed. This is a semantic policy change requiring valid new configuration capacity; current configuration usage12/12 leaves none. No old configuration/failedattempt rebinding or new quota authorized.
Actual original37dc/3e688 native result isRuntimeError/ledgerfailed, original runtime662ccd8 andv1. Actual7 success checks andorders remainnull. Native result rawSHA61d3578b184d8667e73a53b2cdbfabc5c83570b6a652b17c554a9f076b92d497; logpacket056c07438969fbfd462317c9500aa5ae7bed8f071aca0b1ed5fbe783ae2bff60. One LF appended to frozenengineering_smoke.py exactly recreates source_format hash/bytecount/line counts. It does not prove a platform packaging layer, all worker files or old39cafa cause. Empty searched logs do not establish0orders.
Budget48events SHA256ff0440eb196fc5e79be54ab0d6113630510a058313251be667fae6d064a4c71d preserves original46 rawprefixf50d4c...; new events47 originalfailure and48 roundclose only. Usage12/15/2, no refunds/newdebits/configregistration. Original input8c9de804... and actual failed replay in privateMemory unchanged. All liveQC/Research/LEAN/compile/model/provider calls and production/authoritative writes0; no terminal polling or online result/log retrieval.
Full historicalUS200/SID economic ambiguity/financial numeric catalog/vintage/publication/actual delivery/ingestion evidence and charged native certification dispatch remain incomplete. Certification computation kernel exists. Formal research, autonomousGPT, trading and final evaluation remain closed.2024-2025 exposure remains;2026 independence uncertified. NoIC/return/cost/risk/NAV metrics invented.
Only redundant derived scratch source/stores/cases and bytecode outside immutable fixed trees are omitted. Original first failures, scripts, exact output and correction diffs, QA, known failing developer artifacts and complete source trees retained. ZIP hash is a companion outside its self-seal.
'''
(OUT/'README.txt').write_text(readme,encoding='utf-8')
manifest={p.relative_to(OUT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()for p in OUT.rglob('*')if p.is_file()}
(OUT/'artifact_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
verified=subprocess.run([sys.executable,'-B',str(OUT/'verify_artifacts.py')],capture_output=True);assert verified.returncode==0,verified.stderr;print(verified.stdout.decode(),flush=True)
archive=OUT.with_suffix('.zip')
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6)as z:
 for p in OUT.rglob('*'):
  if p.is_file():z.write(p,OUT.name+'/'+p.relative_to(OUT).as_posix())
with zipfile.ZipFile(archive)as z:
 assert z.testzip()is None
 assert set(z.namelist())=={OUT.name+'/'+n for n in set(manifest)|{'artifact_manifest.json'}}
 for name,digest in manifest.items():assert hashlib.sha256(z.read(OUT.name+'/'+name)).hexdigest()==digest,name
result={'directory':str(OUT),'zip':str(archive),'zip_bytes':archive.stat().st_size,'zip_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'manifest_entries':len(manifest),'source_counts':{k:v['count']for k,v in sources.items()},'portable_verifier_exit':verified.returncode,'formal_report_sha256':hashlib.sha256((OUT/'formal_report.json').read_bytes()).hexdigest(),'WR28_still_open':True,'candidate_delivery_passed':False}
(R/'package_result.json').write_text(json.dumps(result,ensure_ascii=True,indent=2)+'\n',encoding='utf-8');print(json.dumps(result,ensure_ascii=True),flush=True)
