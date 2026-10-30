"""Independent strict-vs-canonical diagnostic distinction and v1 limits."""
import argparse,hashlib,io,json,sys,time,unittest
from pathlib import Path
sys.dont_write_bytecode=True
p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();S=a.source.resolve();O=a.out.resolve();O.mkdir(parents=True,exist_ok=True);sys.path.insert(0,str(S/'cloud'))
from qresearch.artifacts import content_hash
from qresearch.engineering_data import verify_deployment,verify_deployment_observation,DeploymentVerificationError
def H(b):return hashlib.sha256(b).hexdigest()
def snap():return{p.relative_to(S).as_posix():H(p.read_bytes())for p in S.rglob('*')if p.is_file()}
before=snap();cases=[]
class Tests(unittest.TestCase):
 def root(self,label,raw):
  q=O/'cases'/label;q.mkdir(parents=True,exist_ok=True);(q/'a.py').write_bytes(raw);return q
 def test_v2_errors_keep_real_strict_hashes_not_canonical_hashes(self):
  body=b'VALUE=7';changed=b'VALUE=8 #SYNTHETIC-PRIVATE-CONTENT'
  for original_lfs in (0,2,64):
   frozen={'source_sha256':H(body+b'\n'*original_lfs),'canonical_sha256':H(body+b'\n'),'terminal_lf_count':original_lfs};manifest={'schema_version':2,'source_identity_policy':'utf8_sig_universal_newlines_terminal_lf_v1','files':{'a.py':frozen}}
   for observed_lfs in (0,2):
    actual=changed+b'\n'*observed_lfs;root=self.root(f'v2-{original_lfs}-{observed_lfs}',actual)
    for detailed in (False,True):
     cases.append(f'v2-strict-diag/{original_lfs}/{observed_lfs}/{detailed}')
     with self.assertRaises(DeploymentVerificationError)as c:verify_deployment(manifest,content_hash(manifest),source_root=root,worker_diagnostics=detailed)
     d=c.exception.diagnostics;self.assertEqual(d['expected_sha256'],frozen['source_sha256']);self.assertEqual(d['observed_sha256'],H(actual));self.assertNotEqual(d['expected_sha256'],frozen['canonical_sha256']);self.assertNotEqual(d['observed_sha256'],H(changed+b'\n'));self.assertEqual(d['schema_version'],1);self.assertNotIn('SYNTHETIC-PRIVATE-CONTENT',str(c.exception));self.assertNotIn(str(root),str(c.exception))
 def test_legacy_default_and_explicit_diagnostics_preserve_versions(self):
  original=b'VALUE=7';legacy={'a.py':H(original)}
  for label,actual,kind in [('lf',original+b'\n\n','source_hash_mismatch'),('utf8',b'\xffSYNTHETIC-PRIVATE-CONTENT','source_decode_error')]:
   root=self.root('v1-'+label,actual)
   for detailed in (False,True):
    cases.append(f'v1-diag/{label}/{detailed}')
    with self.assertRaises(DeploymentVerificationError)as c:verify_deployment(legacy,content_hash(legacy),source_root=root,worker_diagnostics=detailed)
    d=c.exception.diagnostics;self.assertEqual(d['schema_version'],2 if detailed else 1);self.assertEqual(d['failure_kind'],kind);self.assertEqual(d['expected_sha256'],H(original));self.assertNotIn('SYNTHETIC-PRIVATE-CONTENT',str(c.exception));self.assertNotIn(str(root),str(c.exception))
    if label=='lf':self.assertEqual(d['observed_sha256'],H(actual))
    if detailed:
     fmt=d['worker_observation']['source_format'];self.assertEqual(fmt['raw_sha256'],H(actual));self.assertEqual(fmt['byte_count'],len(actual));self.assertIs(d['worker_observation']['strict_identity_relaxed'],False)
     self.assertEqual(fmt['normalized_trailing_lf_count'],2 if label=='lf'else None)
 def test_legacy_worker_adds_no_v2_AST_size_or_EOF_constraints(self):
  for label,raw in [('invalidsyntax',b'VALUE ='),('nul',b'\x00'),('EOF65',b'VALUE=7'+b'\n'*65),('bytesover2MiB',b'#'+b'x'*(2*1024*1024))]:
   cases.append('legacy-unrestricted/'+label);root=self.root(label,raw);manifest={'a.py':H(raw)};digest=content_hash(manifest);self.assertEqual(verify_deployment(manifest,digest,source_root=root),digest);self.assertIsNone(verify_deployment_observation(manifest,digest,source_root=root))
stream=io.StringIO();t=time.monotonic();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests));doc={'methods':result.testsRun,'named_scenarios':len(cases),'scenario_labels':cases,'failure_records':len(result.failures),'error_records':len(result.errors),'skipped':len(result.skipped),'success':result.wasSuccessful(),'source_raw_unchanged':before==snap(),'source_files':len(before),'seconds':time.monotonic()-t,'failures':[{'test':str(t),'traceback':s}for t,s in result.failures],'errors':[{'test':str(t),'traceback':s}for t,s in result.errors]};(O/'unittest.txt').write_text(stream.getvalue(),encoding='utf-8');(O/'results.json').write_text(json.dumps(doc,indent=2)+'\n',encoding='utf-8');print(json.dumps({k:v for k,v in doc.items()if k not in ['scenario_labels','failures','errors']}));print(stream.getvalue());raise SystemExit(int(not result.wasSuccessful()or not doc['source_raw_unchanged']))
