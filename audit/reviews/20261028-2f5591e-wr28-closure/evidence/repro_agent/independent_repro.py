"""Independent WR28 CLI/fixture reproduction; no developer test fixture imports."""
from pathlib import Path
from hashlib import sha256,sha1
from copy import deepcopy
import argparse,contextlib,io,json,os,shutil,subprocess,sys,tempfile,time,traceback,unittest

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'source'
BASELINE=ROOT/'baselines/1cf2657/source'
OUT=Path(__file__).resolve().parent
WORK=OUT/'work'/'no_git_export'
PY=Path(sys.executable)
GIT=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\repo')
PKG=Path('audit/review_packages/deployment-eof-v2')
MANIFEST=PKG/'protected_git_baseline.json'
LEGACY=PKG/'protected_before.json'
FIXTURE=PKG/'fixtures/engineering_smoke_662ccd.py'
RECORDS=[];SCENARIOS=[];DIRECT=[]
ENV=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
for k in ['GIT_DIR','GIT_WORK_TREE','GIT_INDEX_FILE']:ENV.pop(k,None)

def snapshot(root):
 return {p.relative_to(root).as_posix():sha256(p.read_bytes()).hexdigest()for p in root.rglob('*')if p.is_file()}
def write_json(path,value):
 path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,ensure_ascii=True,indent=2)+'\n',encoding='utf-8')
def command(label,argv,cwd):
 t=time.monotonic();p=subprocess.run(list(map(str,argv)),cwd=cwd,env=ENV,capture_output=True)
 target=OUT/'raw';target.mkdir(exist_ok=True)
 (target/(label+'.stdout')).write_bytes(p.stdout);(target/(label+'.stderr')).write_bytes(p.stderr)
 row={'label':label,'command':list(map(str,argv)),'cwd':str(cwd),'exit_code':p.returncode,'seconds':time.monotonic()-t,'stdout_sha256':sha256(p.stdout).hexdigest(),'stderr_sha256':sha256(p.stderr).hexdigest()}
 RECORDS.append(row);write_json(OUT/'execution_records.json',RECORDS)
 return p
def checker(label,root=WORK,trap_subprocess=False):
 if trap_subprocess:
  code='import subprocess,runpy;\ndef deny(*a,**k):raise RuntimeError("independent no-subprocess gate");\nsubprocess.run=deny;subprocess.check_output=deny;subprocess.Popen=deny;runpy.run_path("verify_candidate.py",run_name="__main__")'
  return command(label,[PY,'-B','-c',code],root/PKG)
 return command(label,[PY,'-B',str(root/PKG/'verify_candidate.py')],root)
@contextlib.contextmanager
def changed(items):
 original={}
 try:
  for rel,value in items.items():
   path=(WORK/rel).resolve();assert path.is_relative_to(WORK.resolve())
   original[rel]=path.read_bytes()if path.exists()else None
   if value is None:path.unlink()
   else:path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(value)
  yield
 finally:
  for rel,raw in original.items():
   path=WORK/rel
   if raw is None:
    if path.exists():path.unlink()
   else:path.write_bytes(raw)
def named(label,kind,expected,actual):SCENARIOS.append({'name':label,'kind':kind,'expected':expected,'actual':actual})
def negative(self,label,changes):
 with changed(changes):
  p=checker(label);self.assertNotEqual(p.returncode,0,label);named(label,'CLI_rejection','nonzero_exit',p.returncode)
 self.assertEqual(snapshot(WORK),INITIAL_COPY,label+' did not restore exact private source')

class ReproTests(unittest.TestCase):
 def test_01_exact_candidate_without_git_and_no_subprocess(self):
  self.assertFalse((WORK/'.git').exists())
  for label,trap in [('candidate_plain',False),('candidate_subprocess_forbidden',True)]:
   p=checker(label,trap_subprocess=trap);self.assertEqual(p.returncode,0,p.stderr.decode(errors='replace'));d=json.loads(p.stdout)
   self.assertEqual(d['protected_files_unchanged'],122)
   self.assertEqual(d['protected_git_baseline']['legacy_declared_vs_git_blob_mismatch_count'],3)
   self.assertEqual(d['registry_events'],48);self.assertEqual(d['global_usage'],dict(configurations=12,research=15,lean=2))
   self.assertEqual(d['actual_original_LEAN_status'],'runtime_error');self.assertEqual(d['original_ledger_status'],'failed')
   self.assertEqual(d['legacy_manifest_version'],1);self.assertFalse(d['replay_is_worker_file_observation'])
   self.assertEqual(d['cloud_calls'],0);self.assertFalse(d['stage2_accepted']);self.assertFalse(d['final_test_enabled'])
   self.assertEqual(snapshot(WORK),INITIAL_COPY);named(label,'CLI_positive','exit0_and122',{'exit':p.returncode,'verified':122})

 def test_02_original_baseline_stays_failed(self):
  raw=json.loads((BASELINE/LEGACY).read_bytes());bad=[n for n,h in raw.items()if sha256((BASELINE/n).read_bytes()).hexdigest()!=h]
  self.assertEqual(set(bad),{'audit/data_exposure.json','config/research.json','config/workflow.json'})
  p=checker('baseline_original_failed',root=BASELINE);self.assertEqual(p.returncode,1);self.assertIn(b'audit/data_exposure.json',p.stderr)
  named('original_WR28_preserved','CLI_negative','exit1_and3_legacy_mismatches',{'exit':p.returncode,'mismatch_paths':sorted(bad)})

 def test_03_actual_protected_file_changes(self):
  names=['audit/data_exposure.json','config/research.json','config/workflow.json']
  for i,n in enumerate(names):
   raw=(WORK/n).read_bytes();negative(self,'protected_same_size_flip_'+str(i),{n:bytes([raw[0]^1])+raw[1:]})
  n='config/research.json';raw=(WORK/n).read_bytes()
  negative(self,'research_CRLF',{n:raw.replace(b'\n',b'\r\n')})
  negative(self,'research_BOM',{n:b'\xef\xbb\xbf'+raw})
  negative(self,'research_missing',{n:None})
  for label,n in [('budget_journal_one_byte','audit/runtime/registry/events.jsonl'),('budget_baseline_one_byte','audit/runtime/registry/baseline.json'),('old_admission_one_byte','audit/runtime/engineering/admitted-inputs/37dc855045e14ca49c88fd9d75f40cf7.json')]:
   self.assertIn(n,json.loads((WORK/LEGACY).read_bytes()));raw=(WORK/n).read_bytes();negative(self,label,{n:raw+b' '})

 def test_04_manifest_and_legacy_source_rejections(self):
  m=json.loads((WORK/MANIFEST).read_bytes());name='config/research.json'
  changes=[('record_SHA',lambda x:x['files'][name].__setitem__('sha256','0'*64)),('record_OID',lambda x:x['files'][name].__setitem__('git_blob_oid','0'*40)),('record_size',lambda x:x['files'][name].__setitem__('byte_count',x['files'][name]['byte_count']+1)),('snapshot_commit',lambda x:x['git_snapshots']['baseline'].__setitem__('commit','0'*40)),('snapshot_tree',lambda x:x['git_snapshots']['materials'].__setitem__('tree','0'*40)),('path_list_origin',lambda x:x['path_list_source'].__setitem__('sha256','0'*64)),('manifest_bool_count',lambda x:x.__setitem__('protected_file_count',True)),('manifest_unknown_field',lambda x:x.__setitem__('unapproved','independent_repro_marker'))]
  for label,mutate in changes:
   value=deepcopy(m);mutate(value);negative(self,label,{MANIFEST:json.dumps(value).encode()})
  raw=(WORK/MANIFEST).read_bytes();duplicate=b'{"schema_version":1,'+raw.lstrip()[1:]
  negative(self,'manifest_duplicate_JSON_key',{MANIFEST:duplicate})
  negative(self,'manifest_BOM',{MANIFEST:b'\xef\xbb\xbf'+raw})
  raw=(WORK/LEGACY).read_bytes();negative(self,'legacy_source_extra_LF',{LEGACY:raw+b'\n'})

 def test_05_portable_fixture_rejections(self):
  raw=(WORK/FIXTURE).read_bytes()
  for label,value in [('fixture_missing',None),('fixture_extra_LF',raw+b'\n'),('fixture_BOM',b'\xef\xbb\xbf'+raw),('fixture_body_append',raw+b'INDEPENDENT_CHANGED_VALUE = 1\n')]:
   negative(self,label,{FIXTURE:value})

 def test_06_fixture_exact_blob_and_legacy_v2_known_answers(self):
  raw=(WORK/FIXTURE).read_bytes()
  p=command('fixture_git_662_blob',['git','-C',GIT,'show','662ccd876b67ca0949f921a53c4c33df37cfbbf1:cloud/engineering_smoke.py'],OUT)
  self.assertEqual(p.returncode,0);self.assertEqual(raw,p.stdout)
  self.assertEqual(len(raw),3561);self.assertEqual(sha256(raw).hexdigest(),'33ffa365d6b54d0a823574eaba5831c2f53c6aae7f2dff2c885b1d7ac0c9ca90')
  self.assertEqual(sha256(raw+b'\n').hexdigest(),'5b7111b3806c2f4a8f93b85ffb8a54fa63cebdefb126bcc449c6020b95d3c4e5')
  sys.path.insert(0,str(SOURCE/'cloud'))
  from qresearch.artifacts import content_hash
  from qresearch.deployment_sources import build_manifest
  from qresearch.engineering_data import verify_deployment,verify_deployment_observation,DeploymentVerificationError
  legacy={'engineering_smoke.py':sha256(raw).hexdigest()};v2=build_manifest({'engineering_smoke.py':raw})
  with tempfile.TemporaryDirectory(prefix='wr28-independent-replay-')as td:
   target=Path(td)/'engineering_smoke.py';target.write_bytes(raw)
   self.assertEqual(verify_deployment(legacy,content_hash(legacy),source_root=td),content_hash(legacy));named('fixture_v1_original','direct_known_answer','accept',True)
   target.write_bytes(raw+b'\n')
   with self.assertRaises(DeploymentVerificationError)as caught:verify_deployment(legacy,content_hash(legacy),source_root=td,worker_diagnostics=True)
   self.assertEqual(caught.exception.diagnostics['observed_sha256'],sha256(raw+b'\n').hexdigest());named('fixture_v1_extra_LF','direct_known_answer','reject',True)
   observation=verify_deployment_observation(v2,content_hash(v2),source_root=td);self.assertEqual(observation['eof_normalized_file_count'],1);self.assertFalse(observation['original_source_identity_match']);named('fixture_v2_worker_extra_LF','direct_known_answer','accept_and_normalized1',True)
   with self.assertRaises(DeploymentVerificationError):verify_deployment(v2,content_hash(v2),source_root=td,require_source_bytes=True)
   named('fixture_v2_strict_extra_LF','direct_known_answer','reject',True)
   target.write_bytes(raw+b'# independent same-program comment\n')
   with self.assertRaises(DeploymentVerificationError):verify_deployment(v2,content_hash(v2),source_root=td)
   named('fixture_v2_body_comment','direct_known_answer','reject',True)
  named('fixture_exact_original_git_blob','metadata_known_answer',{'bytes':3561,'SHA':'33ffa365...'},True)

 def test_07_trusted_manifest_authenticity_boundary(self):
  # Replacing both trusted source artifact and data invalidates the pinned Git
  # review version. This demonstrates that byte validation is not a remote
  # signature; it is not silently counted as a tamper rejection.
  rel='config/research.json';raw=(WORK/rel).read_bytes().replace(b'\n',b'\r\n');m=json.loads((WORK/MANIFEST).read_bytes());item=m['files'][rel]
  item['sha256']=sha256(raw).hexdigest();item['git_blob_oid']=sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest();item['byte_count']=len(raw)
  changed_manifest=json.dumps(m,sort_keys=True).encode()
  with changed({rel:raw,MANIFEST:changed_manifest}):
   p=checker('selfconsistent_manifest_and_source_trust_boundary');self.assertEqual(p.returncode,0,p.stderr.decode(errors='replace'));d=json.loads(p.stdout)
   self.assertEqual(d['protected_files_unchanged'],122);self.assertEqual(d['protected_git_baseline']['legacy_declared_vs_git_blob_mismatch_count'],2)
   self.assertNotEqual(sha256(changed_manifest).hexdigest(),INITIAL_COPY[MANIFEST.as_posix()])
   named('selfconsistent_replaced_trusted_manifest','authenticity_boundary_not_negative','accepted_locally_but_changed_fixed_source_version',{'exit':p.returncode,'legacy_discrepancies':2,'original_manifest_version_invalidated':True})
  self.assertEqual(snapshot(WORK),INITIAL_COPY)

class Result(unittest.TextTestResult):
 def __init__(self,*a,**k):super().__init__(*a,**k);self.passed=[]
 def addSuccess(self,t):super().addSuccess(t);self.passed.append(t.id())

if __name__=='__main__':
 OUT.mkdir(parents=True,exist_ok=True);before=snapshot(SOURCE);base_before=snapshot(BASELINE)
 assert not WORK.exists();WORK.parent.mkdir(parents=True,exist_ok=True);shutil.copytree(SOURCE,WORK)
 INITIAL_COPY=snapshot(WORK);assert INITIAL_COPY==before
 started=time.monotonic();stream=io.StringIO();runner=unittest.TextTestRunner(stream=stream,verbosity=2,resultclass=Result);result=runner.run(unittest.defaultTestLoader.loadTestsFromTestCase(ReproTests))
 first=OUT/'first';first.mkdir(exist_ok=True);(first/'unittest.txt').write_text(stream.getvalue(),encoding='utf-8')
 after=snapshot(SOURCE);base_after=snapshot(BASELINE);private_after=snapshot(WORK)
 report={'reviewed_source_commit':'2f5591e28c0748ac42caeae7bbf3977141d031cb','methods':result.testsRun,'passed_methods':len(result.passed),'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),'named_scenarios':len(SCENARIOS),'scenario_records':SCENARIOS,'unittest_subtest_count':None,'actually_executed_processes':len(RECORDS),'actual_checker_processes':sum(x['label']!='fixture_git_662_blob'for x in RECORDS),'readonly_Git_blob_processes':sum(x['label']=='fixture_git_662_blob'for x in RECORDS),'seconds':time.monotonic()-started,'first_run':True,'success':result.wasSuccessful(),'source_guard':{'candidate_files':len(before),'candidate_original_bytes_unchanged':before==after,'baseline_files':len(base_before),'baseline_original_bytes_unchanged':base_before==base_after,'private_copy_restored':INITIAL_COPY==private_after,'no_git_in_private_copy':not(WORK/'.git').exists()},'failure_details':[{'test':str(t),'traceback':e}for t,e in result.failures],'error_details':[{'test':str(t),'traceback':e}for t,e in result.errors],'actual_platform_model_market_budget_calls':0}
 write_json(first/'results.json',report);print(stream.getvalue());print(json.dumps(report,ensure_ascii=True));raise SystemExit(0 if result.wasSuccessful()and before==after and base_before==base_after and INITIAL_COPY==private_after else 1)
