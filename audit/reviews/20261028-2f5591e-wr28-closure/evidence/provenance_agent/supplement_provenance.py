import argparse,hashlib,importlib.util,json,os,platform,subprocess,sys,time,unittest
from pathlib import Path
sys.dont_write_bytecode=True
p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--git',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
S=a.source.resolve();G=a.git.resolve();O=a.out.resolve();O.mkdir(exist_ok=False)
PACKAGE=S/'audit/review_packages/deployment-eof-v2';spec=importlib.util.spec_from_file_location('reviewed_git_protection',PACKAGE/'git_protection.py');M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
RAW=(PACKAGE/'protected_before.json').read_bytes();D=json.loads((PACKAGE/'protected_git_baseline.json').read_bytes());SCENARIOS=[];CALLS=[]
def h(b):return hashlib.sha256(b).hexdigest()
BEFORE={p.relative_to(S).as_posix():h(p.read_bytes())for p in S.rglob('*')if p.is_file()}
def execute(label,args):
 t=time.monotonic();v=subprocess.run(['git','-C',str(G),*args],capture_output=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
 (O/(label+'.stdout')).write_bytes(v.stdout);(O/(label+'.stderr')).write_bytes(v.stderr);CALLS.append({'label':label,'command':['git','-C',str(G),*args],'exit_code':v.returncode,'seconds':time.monotonic()-t,'stdout_sha256':h(v.stdout),'stderr_sha256':h(v.stderr)});assert v.returncode==0;return v.stdout
class Tests(unittest.TestCase):
 def test_outer_source_and_three_snapshot_trees_against_Git(self):
  expected={'baseline':'8d65c290773547c83549c098172f1eb8c3376cd7','candidate':'4a42c18f0b78bea2068d589bc12f1615712354c6','materials':'1cf26578da59eebd37e138ca5d6d076991386470'}
  observed={}
  for name,commit in expected.items():
   tree=execute('raw_tree_'+name,['rev-parse',commit+'^{tree}']).decode().strip();observed[name]={'commit':commit,'tree':tree};SCENARIOS.append('fixed_tree:'+name)
  self.assertEqual(D['git_snapshots'],observed)
  path='audit/review_packages/deployment-eof-v2/protected_before.json';raw=execute('raw_original_path_list',['show',expected['materials']+':'+path]);self.assertEqual(raw,RAW)
  obj=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
  self.assertEqual(D['path_list_source'],{'path':path,'sha256':h(raw),'git_blob_oid':obj,'git_commit':expected['materials'],'legacy_hash_policy':'original_declarations_preserved_without_reinterpretation'})
  self.assertEqual(len(json.loads(raw)),122);SCENARIOS.append('original_path_list_complete_metadata')
 def test_exact_raw_bounds_and_static_errors(self):
  self.assertEqual(M.blob_oid(b''),'e69de29bb2d1d6434b8b29ae775ad8c2e48c5391');SCENARIOS.append('empty_raw_Git_blob_known_answer')
  raw=b'X'*(16*1024*1024);expected=hashlib.sha1(b'blob 16777216\0'+raw).hexdigest();self.assertEqual(M.blob_oid(raw),expected);SCENARIOS.append('blob16MiB_exact')
  raw=b'{}'+b' '*(16*1024*1024-2);self.assertEqual(M._json(raw),{});SCENARIOS.append('json16MiB_exact')
  for label,fn in [('blob_over',lambda:M.blob_oid(b'X'*(16*1024*1024+1))),('blob_mutable',lambda:M.blob_oid(bytearray(b'x'))),('json_over',lambda:M._json(b'{}'+b' '*(16*1024*1024-1)))]:
   with self.subTest(case=label):
    with self.assertRaises(M.ProtectionError)as e:fn()
    self.assertEqual(str(e.exception),'Git raw-byte protection check failed');SCENARIOS.append(label)
 def test_exact_repository_root_required(self):
  private=O.parent/'first/work/private_git'
  self.assertTrue((private/'.git').is_dir())
  for label,repo in [('nested_root',private/'audit'),('non_repository',O),('missing_repository',O/'does-not-exist')]:
   with self.subTest(case=label):
    with self.assertRaises(M.ProtectionError)as e:M.build_manifest(repo,RAW)
    self.assertEqual(str(e.exception),'Git raw-byte protection check failed');SCENARIOS.append(label)
if __name__=='__main__':
 t=time.monotonic()
 with(O/'unittest.txt').open('w',encoding='utf-8')as f:r=unittest.TextTestRunner(stream=f,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
 after={p.relative_to(S).as_posix():h(p.read_bytes())for p in S.rglob('*')if p.is_file()};assert after==BEFORE
 result={'methods':r.testsRun,'failure_records':len(r.failures),'error_records':len(r.errors),'skipped':len(r.skipped),'named_scenarios':len(SCENARIOS),'scenarios':SCENARIOS,'unittest_subtest_count':None,'success':r.wasSuccessful(),'seconds':time.monotonic()-t,'source_files':len(BEFORE),'source_unchanged':True,'explicitly_captured_child_commands':len(CALLS),'QC_calls':0}
 (O/'results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');(O/'execution_records.json').write_text(json.dumps(CALLS,indent=2)+'\n',encoding='utf-8');print(json.dumps({k:v for k,v in result.items()if k!='scenarios'}));raise SystemExit(0 if r.wasSuccessful()else 1)
