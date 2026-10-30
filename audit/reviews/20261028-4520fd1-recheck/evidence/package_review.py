from pathlib import Path
import hashlib,json,os,shutil,subprocess,sys,zipfile
R=Path(__file__).resolve().parent
OUT=Path('B:/BaiduSyncdisk/学习/投资/量化/量化交易比赛/LLM审核/review-4520fd1-20261028-recheck')
OLD=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-4520fd1-20261028')
report=json.loads((R/'formal_report.json').read_bytes());digest=hashlib.sha256((R/'formal_report.json').read_bytes()).hexdigest()
assert report['findings']==[]and report['financial_evidence']is False and report['software_acceptance']['phase2_overall']=='not_accepted'
for n in ['data_recheck','budget_recheck','runtime_recheck']:
 p=R/n/'qa.txt';assert p.is_file()and digest in p.read_text(encoding='utf-8'),n
assert not OUT.exists()and not OUT.with_suffix('.zip').exists();OUT.mkdir()
skip={'__pycache__','.git','verification_source','work','private_context','cases','quick_cases'}
for folder,dirs,files in os.walk(R):
 folder=Path(folder);rel=folder.relative_to(R);immutable=bool(rel.parts and rel.parts[0]=='source')
 if not immutable:dirs[:]=[d for d in dirs if d not in skip]
 for name in files:
  if not immutable and(name.endswith(('.pyc','.tar'))or name in {'package_result.json','package_smoke_execution.json'}):continue
  dest=OUT/rel/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(folder/name,dest)
prior=OUT/'prior_evidence';prior.mkdir()
for n in ['formal_report.json','root_test_execution_summary.json','source_identity.json']:
 shutil.copyfile(OLD/n,prior/n)
shutil.copytree(OLD/'qc_readback',prior/'qc_readback',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
source=json.loads((OUT/'source_git_manifest.json').read_bytes());S=OUT/'source'
actual={p.relative_to(S).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()for p in S.rglob('*')if p.is_file()};assert actual==source['files']and len(actual)==5976
(OUT/'requirements-audit.txt').write_text(''.join(n+'=='+v+'\n'for n,v in report['environment']['dependencies'].items()),encoding='utf-8')
readme='''AQRP-LLM independent phase2 RECHECK,2026-10-28 Asia/Shanghai.
Fixed SHA4520fd1a4421a9b764d2bfd61e5fb5cf4b59a9c8, identical5976 raw Git files to previous review. Current PR remained draft/open/unmerged. Actual repaired cloud runtime662ccd8 is separate from archive4520fd1.
Outcome: bounded rechecked software scope passed with disclosed reviewer corrections; no new confirmed product WR. Phase2 overall NOT accepted. Data certification and financial effectiveness NOT established.
Verify every sealed raw file and complete current Git tree without network: python -B verify_artifacts.py
Minimal synthetic reproduction: python -B minimal_occurrence_known_answer.py --source source
Expected5 retained/3 duplicate projections/1 first-relative conflict/3 batches/0 cache fetches; invalid ordinal gap refused, certification flags false. No provider call.
For repository suite, copy source into an unsealed scratch directory, install requirements-audit.txt in Python3.10.11 and run python -B tools/stages.py verify there. This writes only scratch audit outputs. Actual765-method current result: repository_verification.json and repository_verify.stdout/.stderr, root_execution_records.json.
New independent data tests are data_recheck/adversarial_occurrence.py and additional_closed_checks.py; budget settlement_frontier_tests.py and runtime independent_runtime_recheck_corrected.py. Preserve original first outputs and scope diffs. Relocation may require remapping captured absolute roots or AQRP_REVIEW_SOURCE. Dynamic suites use only synthetic stores; metadata verifiers checking historicalGit objects need an available read-only local Git repo with the frozen commits. The private original Git repo is not included. Never run generated audit writers inside this sealed directory; use scratch output paths.
This round: data10 methods/105 named scenarios plus3/4; budget7/32 with4 native Windows process workers and12 thread tasks; runtime10/57 after disclosed helper and provenance-oracle correction. Named scenarios are not measured unittest subTest counts; all populations overlap.35 archived-native checks,105 matrix source references,8 budget logical checks, capabilities CLI, build and integrity reads are not unit methods.
Runtime first10 methods had8 passing methods and2 failure records. One mutable helper was fixed with deepcopy; the pure native-error parser cannot remotely authenticate an absent attempt/source field. That original rejection oracle is NOT claimed to pass. The corrected suite discloses trusted dispatcher context and separately verifies original completed/failed terminal replacement rejection. This is a contract limitation, not a remote signature or a new product defect.
Reviewer exploratory import created8pyc files in exported scratch source. Original5976 Git bytes stayed unchanged. Exact cache bytes retained under budget_recheck/reviewer_generated_cache/*.pyc.bin; source restored before final guard. Root static first raw-file-set failure retained. A separate root reference-scope error compared88 stage entries to105 full-matrix unique references; original script/output retained, final checker verifies all105 including controls. No product source fix performed.
Correct prior report wording: Research requires13 checks; LEAN requires7. Prior sealed report remains raw and unchanged in prior_evidence; its oldLEAN13 wording is superseded only by the explicit current correction. Earlier derived-summary SHA-label correction also remains preserved.
NewLEAN attempt37dc855045e14ca49c88fd9d75f40cf7 /backtest3e68866a46ca88ff16481c31b3c2c822 has only archived submission and frozen pending ledger. No terminal/logs obtained or read; order count and7 real runtime check results remain null. Developer compile.success summary has no original native compile packet. Synthetic completedLEAN fixtures are not platform evidence.
Research13 engineering checks verified from developer-archived native packets independently decoded offline.208223 projections/27duplicates/0 selected4-field conflicts/13empty/40calendar windows are aggregate program metadata, not reviewer raw-cloud-row recount or full historicalUS200/financial coverage. Price History0/0 reflects existing cache.
Prior independent source readback evidence is copied under prior_evidence/qc_readback and rehashed. Those35 QC source-only calls are historical, not current recheck tool calls or current cloud state. This round made0QC/Research/LEAN/compile/model/market calls and no production/budget/PR writes; final tests remain closed.
Budget46 events,12/12 configurations,15/20Research,2/16LEAN; normal004 actual2/2/1 vs recorded ceiling2/4/2; no refunds/increase, configuration slots0. Current user statement supports already executed past use, not extra grants. Synthetic explicit retries do not authorize real unused quota.
Data certification computation kernel exists. Financial numeric catalog0; canonical capabilities/validate-plan commands do not implement charged native certification dispatch. Complete historicalUS200/SID ambiguity/vintages/publication/actual delivery/ingestion remain uncertified. A source ordinal is not an economic identity or winner. Unique-liquidity conversion rejects occurrence rows.
Stages3-7, financial performance, OS kill/power-loss durability unaccepted.2024-2025 already exposed;2026 independence unverified. Formal research, GPT autonomous calls, orders and final tests remain closed.
Prior full review ZIP is retained separately and was reverified this turn: SHA256bd32d23357f2c7a2478f57264e174bb0843e0219ef9c462d7c4e2fd21f345a56. Its full30647-file seal and CRC passed. Prior248-method/2307-subcase regression scopes and other historical independent suites are referenced, not counted as fresh execution. See prior_report_reference.json.
Only redundant derived working source/store trees and bytecode caches are omitted outside immutable source. Original scripts, first failures, stdout/stderr, command/hash records, correction diffs, private synthetic MRE inputs and QA retained. Companion ZIP hash is outside this self-sealed manifest.
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
result={'directory':str(OUT),'zip':str(archive),'zip_bytes':archive.stat().st_size,'zip_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'manifest_entries':len(manifest),'fixed_source_files':5976,'portable_verifier_exit':verified.returncode,'formal_report_sha256':hashlib.sha256((OUT/'formal_report.json').read_bytes()).hexdigest()}
(R/'package_result.json').write_text(json.dumps(result,ensure_ascii=True,indent=2)+'\n',encoding='utf-8');print(json.dumps(result,ensure_ascii=True),flush=True)
