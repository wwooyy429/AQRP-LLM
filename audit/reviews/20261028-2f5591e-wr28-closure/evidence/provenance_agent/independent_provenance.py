"""Independent raw-Git provenance and closed audit-verifier boundaries."""
import argparse,copy,hashlib,importlib.util,io,json,os,platform,shutil,subprocess,sys,tarfile,time,unittest
from pathlib import Path
sys.dont_write_bytecode=True
P=argparse.ArgumentParser();P.add_argument('--source',type=Path,required=True);P.add_argument('--git',type=Path,required=True);P.add_argument('--out',type=Path,required=True);A=P.parse_args()
S=A.source.resolve();G=A.git.resolve();O=A.out.resolve();O.mkdir(parents=True,exist_ok=False);W=O/'work';W.mkdir()
PACKAGE=S/'audit/review_packages/deployment-eof-v2'
spec=importlib.util.spec_from_file_location('reviewed_git_protection',PACKAGE/'git_protection.py');M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
RAW=(PACKAGE/'protected_before.json').read_bytes();DECLARED=json.loads(RAW);MANIFEST_RAW=(PACKAGE/'protected_git_baseline.json').read_bytes();MANIFEST=json.loads(MANIFEST_RAW)
BEFORE={p.relative_to(S).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()for p in S.rglob('*')if p.is_file()}
CALLS=[];SCENARIOS=[];RAW_BASE={};TREE_MAPS={};ORACLE={}
ENV=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8')
def h(raw):return hashlib.sha256(raw).hexdigest()
def oid(raw):return hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
def execute(label,argv,cwd=O):
 t=time.monotonic();p=subprocess.run(list(map(str,argv)),cwd=cwd,env=ENV,capture_output=True)
 (O/(label+'.stdout')).write_bytes(p.stdout);(O/(label+'.stderr')).write_bytes(p.stderr)
 row={'label':label,'command':list(map(str,argv)),'cwd':str(cwd),'exit_code':p.returncode,'seconds':time.monotonic()-t,'stdout_sha256':h(p.stdout),'stderr_sha256':h(p.stderr)};CALLS.append(row);(O/'execution_records.json').write_text(json.dumps(CALLS,indent=2)+'\n',encoding='utf-8');return p
def check(label):SCENARIOS.append(label)
def protected_view(root):
 root.mkdir(parents=True)
 for name,raw in RAW_BASE.items():p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
 return root
class Tests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  assert len(DECLARED)==122
  commits={'baseline':'8d65c290773547c83549c098172f1eb8c3376cd7','candidate':'4a42c18f0b78bea2068d589bc12f1615712354c6','materials':'1cf26578da59eebd37e138ca5d6d076991386470'}
  for name,c in commits.items():
   p=execute('oracle_tree_'+name,['git','-C',G,'ls-tree','-r','-z','--full-tree',c]);assert p.returncode==0
   tree={}
   for record in p.stdout.split(b'\0'):
    if record:
     meta,path=record.split(b'\t',1);mode,kind,obj=meta.split(b' ')
     if kind==b'blob':tree[path.decode()]=obj.decode()
   TREE_MAPS[name]=tree
  p=execute('oracle_raw_baseline_archive',['git','-C',G,'archive',commits['baseline'],*DECLARED]);assert p.returncode==0
  with tarfile.open(fileobj=io.BytesIO(p.stdout))as tf:
   for member in tf.getmembers():
    if member.isfile():RAW_BASE[member.name]=tf.extractfile(member).read()
  assert set(RAW_BASE)==set(DECLARED)
  for name,raw in RAW_BASE.items():ORACLE[name]={'sha256':h(raw),'git_blob_oid':oid(raw),'byte_count':len(raw),'legacy_declared_sha256':DECLARED[name]}
  (O/'independent_raw_Git_oracle.json').write_text(json.dumps({'fixed_commits':commits,'files':ORACLE,'raw_archive_sha256':h(p.stdout),'oracle_uses_git_archive_not_product_builder':True},indent=2)+'\n',encoding='utf-8')
 def rejected(self,label,fn):
  check(label)
  with self.assertRaises(M.ProtectionError):fn()
 def test_01_all122_real_Git_records_and_export(self):
  self.assertEqual(MANIFEST['files'],ORACLE)
  for name,record in ORACLE.items():
   with self.subTest(path=name):
    check('raw_git_all122:'+name)
    for tree in TREE_MAPS.values():self.assertEqual(tree[name],record['git_blob_oid'])
    self.assertEqual((S/name).read_bytes(),RAW_BASE[name])
  self.assertEqual(M.build_manifest(G,RAW),MANIFEST)
  actual=M.verify_export(S,M.load_manifest(MANIFEST_RAW,RAW),RAW)
  self.assertEqual(actual['protected_git_blobs_verified'],122);self.assertEqual(actual['legacy_declared_vs_git_blob_mismatch_count'],3);self.assertFalse(actual['legacy_declarations_rewritten'])
 def test_02_builder_ignores_mutable_private_worktree_and_output_conflict(self):
  private=W/'private_git';p=execute('private_git_clone',['git','clone','--shared','--no-checkout',G,private]);self.assertEqual(p.returncode,0,p.stderr)
  target=private/'audit/data_exposure.json';target.parent.mkdir(parents=True);target.write_bytes(b'REVIEWER PRIVATE WORKTREE MUTATION\n')
  check('git_builder_ignores_mutable_worktree');self.assertEqual(M.build_manifest(private,RAW),MANIFEST)
  output=W/'built_manifest.json';args=[sys.executable,'-B',PACKAGE/'build_git_protection.py','--repository',private,'--output',output]
  p=execute('builder_fresh_output',args);self.assertEqual(p.returncode,0,p.stderr);self.assertEqual(output.read_bytes(),MANIFEST_RAW)
  before=output.read_bytes();p=execute('builder_idempotent_output',args);self.assertEqual(p.returncode,0,p.stderr);self.assertEqual(output.read_bytes(),before);check('builder_identical_output_no_rewrite')
  output.write_bytes(b'PRIVATE CONFLICT');p=execute('builder_conflict_output',args);self.assertNotEqual(p.returncode,0);self.assertEqual(output.read_bytes(),b'PRIVATE CONFLICT');check('builder_conflict_output_preserved')
 def test_03_closed_envelope_source_and_snapshot_metadata(self):
  mutations=[('unknown_field',lambda d:d.update(extra=1)),('missing_field',lambda d:d.pop('kind')),('schema_bool',lambda d:d.update(schema_version=True)),('schema_float',lambda d:d.update(schema_version=1.0)),('schema_two',lambda d:d.update(schema_version=2)),('kind',lambda d:d.update(kind='other')),('policy',lambda d:d.update(identity_policy='other')),('count_bool',lambda d:d.update(protected_file_count=True)),('count_float',lambda d:d.update(protected_file_count=122.0)),('count_short',lambda d:d.update(protected_file_count=121)),('count_long',lambda d:d.update(protected_file_count=123)),('source_path',lambda d:d['path_list_source'].update(path='../other')),('source_sha',lambda d:d['path_list_source'].update(sha256='0'*64)),('source_oid',lambda d:d['path_list_source'].update(git_blob_oid='0'*40)),('source_commit',lambda d:d['path_list_source'].update(git_commit='0'*40)),('source_policy',lambda d:d['path_list_source'].update(legacy_hash_policy='normalize')),('source_extra',lambda d:d['path_list_source'].update(extra=1)),('snapshot_commit',lambda d:d['git_snapshots']['baseline'].update(commit='0'*40)),('snapshot_tree',lambda d:d['git_snapshots']['candidate'].update(tree='0'*40)),('snapshot_extra',lambda d:d['git_snapshots'].update(other={})),('files_short',lambda d:d['files'].pop(next(iter(d['files'])))),('files_extra',lambda d:d['files'].update({'extra.json':copy.deepcopy(next(iter(d['files'].values())))})),('files_alias',lambda d:d['files'].__setitem__('AUDIT/data_exposure.json',d['files'].pop('audit/data_exposure.json')))]
  for label,mutate in mutations:
   with self.subTest(case=label):d=copy.deepcopy(MANIFEST);mutate(d);self.rejected('envelope:'+label,lambda:M.validate_manifest(d,RAW))
 def test_04_record_closed_types_and_bounds(self):
  path='config/research.json'
  variants=[('sha_upper',{'sha256':'A'*64}),('sha_short',{'sha256':'0'*63}),('sha_nonhex',{'sha256':'x'*64}),('oid_upper',{'git_blob_oid':'A'*40}),('oid_short',{'git_blob_oid':'0'*39}),('oid_bool',{'git_blob_oid':True}),('bytes_bool',{'byte_count':True}),('bytes_float',{'byte_count':1.0}),('bytes_negative',{'byte_count':-1}),('bytes_over',{'byte_count':16*1024*1024+1}),('legacy_changed',{'legacy_declared_sha256':'0'*64}),('legacy_bool',{'legacy_declared_sha256':True}),('extra_field',{'extra':1})]
  for label,patch in variants:
   with self.subTest(case=label):d=copy.deepcopy(MANIFEST);d['files'][path].update(patch);self.rejected('record:'+label,lambda:M.validate_manifest(d,RAW))
  d=copy.deepcopy(MANIFEST);d['files'][path].pop('byte_count');self.rejected('record:missing_field',lambda:M.validate_manifest(d,RAW))
 def test_05_json_and_fixed_path_list_byte_identity(self):
  bad=[b'\xef\xbb\xbf'+MANIFEST_RAW,MANIFEST_RAW.decode().encode('utf-16'),b'{"a":1,"a":2}',b'{"a":NaN}',b'{"a":Infinity}',b'{"a":-Infinity}',b'\xff',b'[]',b'null',b'{',b'['*1200+b'0'+b']'*1200,b' '*(16*1024*1024+1)]
  for i,raw in enumerate(bad):
   with self.subTest(case=i):self.rejected('json:'+str(i),lambda:M.load_manifest(raw,RAW))
  for label,raw in [('path_list_BOM',b'\xef\xbb\xbf'+RAW),('path_list_CRLF',RAW.replace(b'\r\n',b'\n').replace(b'\n',b'\r\n')),('path_list_bit',b'X'+RAW[1:])]:
   # Original pinned list may already containCRLF; force the alternate form.
   if raw==RAW:raw=RAW.replace(b'\r\n',b'\n')
   self.rejected(label,lambda:M.validate_manifest(MANIFEST,raw))
  check('valid_json_whitespace');self.assertEqual(M.load_manifest(b' \n'+MANIFEST_RAW+b' \t',RAW),MANIFEST)
 def test_06_each_of122_private_protected_byte_mutations(self):
  view=protected_view(W/'all122_view');self.assertEqual(M.verify_export(view,MANIFEST,RAW)['protected_git_blobs_verified'],122)
  for name,raw in RAW_BASE.items():
   with self.subTest(path=name):
    path=view/name;path.write_bytes((bytes([raw[0]^1])+raw[1:])if raw else b'X')
    self.rejected('protected_byte:'+name,lambda:M.verify_export(view,MANIFEST,RAW));path.write_bytes(raw)
  for name in ['audit/data_exposure.json','config/research.json','config/workflow.json']:
   raw=RAW_BASE[name];path=view/name
   for label,mutant in [('CRLF',raw.replace(b'\n',b'\r\n')),('BOM',b'\xef\xbb\xbf'+raw)]:
    path.write_bytes(mutant);self.rejected('protected_'+label+':'+name,lambda:M.verify_export(view,MANIFEST,RAW));path.write_bytes(raw)
  self.assertEqual(M.verify_export(view,MANIFEST,RAW)['protected_git_blobs_verified'],122)
 def test_07_trusted_manifest_boundary_and_Git_rebuild_contrast(self):
  view=protected_view(W/'trusted_manifest_view');name='config/research.json';raw=RAW_BASE[name]+b' ';(view/name).write_bytes(raw)
  fake=copy.deepcopy(MANIFEST);fake['files'][name].update(sha256=h(raw),git_blob_oid=oid(raw),byte_count=len(raw))
  check('self_consistent_manifest_is_not_remote_authentication');self.assertEqual(M.verify_export(view,fake,RAW)['protected_git_blobs_verified'],122)
  check('fixed_Git_reconstruction_exposes_forged_table');self.assertNotEqual(M.build_manifest(G,RAW),fake)
  self.rejected('frozen_published_manifest_rejects_same_bytes',lambda:M.verify_export(view,MANIFEST,RAW))
 def test_08_paths_missing_files_and_windows_junction_escape(self):
  paths=['','../a','a/../b','/absolute','C:/drive','a\\b','a//b','a/.','NUL/file.json','a/COM1.txt','a/trail.','a/trail ','a\x00b','a\x7fb','x'*4097,True,None]
  for i,value in enumerate(paths):
   with self.subTest(case=i):self.rejected('path:'+str(i),lambda:M._path(value))
  view=protected_view(W/'missing_view');(view/'audit/data_exposure.json').unlink();self.rejected('missing_protected_file',lambda:M.verify_export(view,MANIFEST,RAW))
  outside=W/'junction_target';outside.mkdir();shutil.copytree(W/'all122_view'/'config',outside/'config')
  view=protected_view(W/'junction_view');assert (view/'config').resolve().is_relative_to(W.resolve());shutil.rmtree(view/'config')
  # The reparse point and target are both owned private test directories.
  cmd="New-Item -ItemType Junction -Path '"+str(view/'config')+"' -Target '"+str(outside/'config')+"' | Out-Null"
  p=execute('native_junction',['powershell.exe','-NoProfile','-NonInteractive','-Command',cmd]);self.assertEqual(p.returncode,0,p.stderr)
  self.rejected('Windows_junction_escape',lambda:M.verify_export(view,MANIFEST,RAW))
if __name__=='__main__':
 start=time.monotonic();suite=unittest.defaultTestLoader.loadTestsFromTestCase(Tests)
 with (O/'unittest.txt').open('w',encoding='utf-8')as log:result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
 after={p.relative_to(S).as_posix():h(p.read_bytes())for p in S.rglob('*')if p.is_file()};assert after==BEFORE
 summary={'methods':result.testsRun,'passed_methods':result.testsRun-len({x.id()for x,_ in result.failures+result.errors}),'failure_records':len(result.failures),'error_records':len(result.errors),'skipped':len(result.skipped),'named_scenarios':len(SCENARIOS),'unittest_subtest_count':None,'success':result.wasSuccessful(),'seconds':time.monotonic()-start,'source_files':len(BEFORE),'source_unchanged':True,'scenarios':SCENARIOS,'Git_oracle_paths':len(ORACLE),'actual_processes':len(CALLS),'QC_calls':0,'real_budget_writes':0}
 (O/'results.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8');print(json.dumps({k:v for k,v in summary.items()if k!='scenarios'}));raise SystemExit(0 if result.wasSuccessful()else 1)
