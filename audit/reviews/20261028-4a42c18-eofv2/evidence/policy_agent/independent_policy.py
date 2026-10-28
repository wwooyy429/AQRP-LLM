"""Independent fixed-byte deployment-policy oracles; synthetic filesystem only."""
import argparse,ast,copy,hashlib,io,json,os,subprocess,sys,time,unittest,warnings
from pathlib import Path
from unittest.mock import patch
sys.dont_write_bytecode=True
P=argparse.ArgumentParser();P.add_argument('--source',type=Path,required=True);P.add_argument('--out',type=Path,required=True);A=P.parse_args()
S=A.source.resolve();O=A.out.resolve();O.mkdir(parents=True,exist_ok=True);sys.path.insert(0,str(S/'cloud'))
from qresearch.artifacts import content_hash
from qresearch.deployment_sources import (canonical_source_bytes,source_record,source_sha256,
 normalize_source_bytes,build_manifest,parse_manifest,validate_record_against_source,SourceIdentityError)
from qresearch.engineering_data import verify_deployment,verify_deployment_observation,DeploymentVerificationError
from qresearch.deployment_observation import validate_deployment_observation,validate_observation_binding

POLICY='utf8_sig_universal_newlines_terminal_lf_v1';SCENARIOS=[];META={}
def H(v):return hashlib.sha256(v).hexdigest()
def snap():return{p.relative_to(S).as_posix():H(p.read_bytes())for p in S.rglob('*')if p.is_file()}
BEFORE=snap()
def known_record(body,count):return{'source_sha256':H(body+b'\n'*count),'canonical_sha256':H(body+b'\n'),'terminal_lf_count':count}
def manual_manifest(files):return{'schema_version':2,'source_identity_policy':POLICY,'files':files}
def put(name,data):
 p=O/'cases'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data);return p
class Tests(unittest.TestCase):
 def scenario(self,name):SCENARIOS.append(name)
 def reject(self,func,*args,kind=ValueError,**kwargs):
  with self.assertRaises(kind)as c:func(*args,**kwargs)
  self.assertNotIn('SYNTHETIC-PRIVATE-CONTENT',str(c.exception));self.assertNotIn(str(O),str(c.exception));return c.exception
 def test_all_bounded_EOF_pairs_have_direct_hash_answers(self):
  body=b'VALUE = 17 # reviewer synthetic'
  for frozen_count in (0,1,2,7,64):
   frozen=known_record(body,frozen_count);self.assertEqual(source_record(body+b'\n'*frozen_count),frozen)
   for actual_count in range(65):
    self.scenario(f'eof/{frozen_count}/{actual_count}')
    raw=body+b'\n'*actual_count
    self.assertEqual(canonical_source_bytes(raw),body+b'\n');self.assertEqual(validate_record_against_source(raw,frozen),frozen)
    if actual_count==frozen_count:self.assertEqual(validate_record_against_source(raw,frozen,True),frozen)
    else:self.reject(validate_record_against_source,raw,frozen,True,kind=SourceIdentityError)
 def test_inherited_BOM_and_newline_equivalence_known_bytes(self):
  body='TITLE = "审阅é"\nVALUE = (3 + 4)'.encode('utf-8')
  for count in (0,1,2,64):
   expected=known_record(body,count)
   for bom in (b'',b'\xef\xbb\xbf'):
    for sep in (b'\n',b'\r\n',b'\r'):
     self.scenario('encoding/'+str((count,bool(bom),sep)))
     raw=bom+(body+b'\n'*count).replace(b'\n',sep)
     self.assertEqual(source_record(raw),expected);self.assertEqual(validate_record_against_source(raw,expected,True),expected)
 def test_valid_program_variants_and_AST_preservation(self):
  bodies=[b'',b'# final comment\\',b'VALUE = "\\\\"',b'VALUE = """first\n\nlast"""',
   b'VALUE = (\n  1+2\n)',b'VALUE = (1 + \\\n2)',b'def f(x):\n    return x + 1',
   b'from __future__ import annotations\nVALUE: list[int] = []',b'VALUE = 1; OTHER = 2',
   b'# coding: utf8\nVALUE = "text"',b'# coding: cp65001\nVALUE = 1']
  for i,body in enumerate(bodies):
   for count in (0,1,2):
    self.scenario(f'valid/{i}/{count}');raw=body+b'\n'*count
    self.assertEqual(canonical_source_bytes(raw),body+b'\n')
    self.assertEqual(source_record(raw),known_record(body,count))
    self.assertEqual(ast.dump(ast.parse(raw)),ast.dump(ast.parse(canonical_source_bytes(raw))))
 def test_equal_AST_does_not_authorize_changed_body_bytes(self):
  body=b'VALUE = (1 + 2) # reviewer';record=known_record(body,1)
  changes=[b'VALUE=(1+2) # reviewer',b'VALUE = (1 + 2) # REVIEWER',b'VALUE = (1 + 2) # reviewer ',
   b'VALUE = (1 + 2)\t# reviewer',b'VALUE = ((1 + 2)) # reviewer',b'\nVALUE = (1 + 2) # reviewer']
  for i,changed in enumerate(changes):
   self.scenario(f'sameAST-byte-change/{i}');self.assertEqual(ast.dump(ast.parse(changed)),ast.dump(ast.parse(body)))
   self.reject(validate_record_against_source,changed+b'\n',record,kind=SourceIdentityError)
  for i,changed in enumerate([body+b'\n ',body+b'\n#extra',b'import os\n'+body,b'VALUE = (1 + 3) # reviewer',b'VALUE = """first\nlast"""']):
   self.scenario(f'other-body-change/{i}');self.reject(validate_record_against_source,changed+b'\n',record,kind=SourceIdentityError)
 def test_invalid_encoding_syntax_continuation_and_static_errors(self):
  bad=[b'VALUE = 1\\\n',b'VALUE = 1\\\n\n',b'\xff',b'VALUE = "SYNTHETIC-PRIVATE-CONTENT',
   b'\x00SYNTHETIC-PRIVATE-CONTENT',b'# coding: latin1\nVALUE = 1',b'# coding: ascii\nVALUE = 1',
   b'\xef\xbb\xbf# coding: latin1\nVALUE = 1',b'# coding: nonexistent-SYNTHETIC-PRIVATE-CONTENT\nVALUE = 1',
   b'VALUE = 1\nfrom __future__ import annotations',b'if True:\nVALUE = 1',b'VALUE = (1 +\n']
  for i,raw in enumerate(bad):
   self.scenario(f'invalid/{i}');err=self.reject(canonical_source_bytes,raw,kind=SourceIdentityError)
   self.assertIsNone(err.__cause__);self.assertTrue(err.__suppress_context__)
  raw=b'VALUE = (1 is "SYNTHETIC-PRIVATE-CONTENT")\n'
  stream=io.StringIO()
  with patch.object(sys,'stderr',stream),warnings.catch_warnings(record=True)as seen:
   warnings.simplefilter('always');self.assertEqual(canonical_source_bytes(raw),raw)
  self.scenario('warning-content-closed');self.assertEqual(seen,[]);self.assertEqual(stream.getvalue(),'')
  self.scenario('not-executed');self.assertEqual(canonical_source_bytes(b'raise RuntimeError("SYNTHETIC-PRIVATE-CONTENT")'),b'raise RuntimeError("SYNTHETIC-PRIVATE-CONTENT")\n')
 def test_closed_types_records_and_manifest_schema(self):
  base=known_record(b'VALUE=1',1);m=manual_manifest({'a.py':base})
  class D(dict):pass
  class B(bytes):pass
  for i,v in enumerate([None,False,'',bytearray(b'VALUE=1'),memoryview(b'VALUE=1'),B(b'VALUE=1')]):
   self.scenario(f'bytes-type/{i}');self.reject(canonical_source_bytes,v,kind=SourceIdentityError)
  invalid=[dict(m,schema_version=v)for v in [True,2.0,'2',0,1,3,None]]
  invalid+=[dict(m,source_identity_policy=v)for v in [None,False,'terminal_lf',POLICY+' ']]
  invalid+=[dict(m,extra=1),dict(m,files={}),D(m),{'a.py':base},{'files':{'a.py':base}}]
  for i,v in enumerate(invalid):self.scenario(f'envelope/{i}');self.reject(parse_manifest,v,kind=SourceIdentityError)
  bad_records=[dict(base,terminal_lf_count=v)for v in [True,False,-1,65,1.0,None,'1']]
  bad_records+=[dict(base,source_sha256=v)for v in ['F'*64,'a'*63,None,False]]
  bad_records+=[dict(base,canonical_sha256='a'*65),dict(base,unexpected=True),D(base)]
  for i,v in enumerate(bad_records):
   self.scenario(f'record/{i}');self.reject(parse_manifest,manual_manifest({'a.py':v}),kind=SourceIdentityError)
  for i,v in enumerate([0,1,'true',None]):
   self.scenario(f'selector/{i}');self.reject(validate_record_against_source,b'VALUE=1\n',base,v,kind=SourceIdentityError)
  v,records=parse_manifest(m);records['a.py']['source_sha256']='0'*64
  self.scenario('manifest-copy');self.assertEqual(m['files']['a.py'],base)
 def test_reconstruction_and_full_wrapper_binding(self):
  raw=b'VALUE=1\n';record=known_record(b'VALUE=1',1)
  for i,r in enumerate([dict(record,source_sha256='0'*64),dict(record,canonical_sha256='1'*64),dict(record,terminal_lf_count=0),dict(record,terminal_lf_count=2)]):
   self.scenario(f'reconstruct/{i}');self.reject(validate_record_against_source,raw+b'\n',r,kind=SourceIdentityError)
  root=put('wrapper/a.py',raw).parent;m=manual_manifest({'a.py':record});full=content_hash(m)
  self.scenario('wrapper-valid');self.assertEqual(verify_deployment(m,full,source_root=root),full)
  for i,wrong in enumerate([content_hash(m['files']),content_hash({'a.py':record['source_sha256']}),record['canonical_sha256']]):
   self.scenario(f'wrapper-hash/{i}');self.reject(verify_deployment,m,wrong,source_root=root,kind=DeploymentVerificationError)
  self.scenario('no-bare-record-map');self.reject(verify_deployment,m['files'],content_hash(m['files']),source_root=root,kind=DeploymentVerificationError)
  other=manual_manifest({'a.py':known_record(b'VALUE=1',2)})
  self.scenario('self-consistent-new-identity');self.assertNotEqual(content_hash(other),full)
  self.assertEqual(validate_record_against_source(raw,other['files']['a.py']),other['files']['a.py'])
  self.reject(verify_deployment,other,full,source_root=root,kind=DeploymentVerificationError)
 def test_safe_paths_aliases_and_all_paths_before_reads(self):
  rec=known_record(b'VALUE=1',1)
  names=['../a.py','/a.py','C:a.py','a\\b.py','a//b.py','a/../b.py','a/./b.py','NUL.py','q/CON.py','q/a?.py','q/a.py:stream',
   'a\x00.py','a\x7f.py','\ud800.py','_engineering_task_input.py','q/_COLLECTION_TASK_INPUT.py']
  for i,n in enumerate(names):
   self.scenario(f'path/{i}');m=manual_manifest({n:rec});self.reject(parse_manifest,m,kind=SourceIdentityError)
  for i,names in enumerate([['a.py','A.py'],['K.py','k.py'],['ß.py','ss.py'],['A.py','a.py/child.py']]):
   self.scenario(f'alias/{i}');self.reject(parse_manifest,manual_manifest(dict.fromkeys(names,rec)),kind=SourceIdentityError)
  self.scenario('all-paths-first');bad=manual_manifest({'a.py':rec,'z/../bad.py':rec})
  with patch.object(Path,'read_bytes',side_effect=AssertionError('source read before all path validation')):
   self.reject(verify_deployment,bad,content_hash(bad),source_root=O,kind=DeploymentVerificationError)
  self.scenario('unicode-safe-path');self.assertIn('模块.py',build_manifest({'模块.py':b'VALUE=1'})['files'])
 def test_protocol_resource_bounds_and_legacy_unbounded_hash(self):
  self.scenario('LF65');self.reject(canonical_source_bytes,b'VALUE=1'+b'\n'*65,kind=SourceIdentityError)
  self.scenario('raw-byte-limit-exact');at=b'#'+b'x'*(2*1024*1024-1);self.assertEqual(canonical_source_bytes(at),at+b'\n')
  self.scenario('raw-byte-limit-over');self.reject(canonical_source_bytes,at+b'x',kind=SourceIdentityError)
  self.assertEqual(source_sha256(at+b'x'),H(at+b'x'))
  records={f'f{i}.py':known_record(b'VALUE=1',1)for i in range(512)}
  self.scenario('files512');self.assertEqual(len(parse_manifest(manual_manifest(records))[1]),512)
  self.scenario('files513');self.reject(parse_manifest,manual_manifest(dict(records,extra=known_record(b'VALUE=1',1))),kind=SourceIdentityError)
  name='q/'*500+'x'*21+'.py';self.assertEqual(len(name.encode()),1024)
  self.scenario('path1024');self.assertIn(name,parse_manifest(manual_manifest({name:known_record(b'VALUE=1',1)}))[1])
  self.scenario('path1025');self.reject(parse_manifest,manual_manifest({'x'+name:known_record(b'VALUE=1',1)}),kind=SourceIdentityError)
  self.scenario('legacy-over-limit-retained');self.assertEqual(parse_manifest(dict.fromkeys([f'f{i}.py'for i in range(513)],H(b'x')))[0],1)
 def test_filesystem_v1_strict_v2_worker_and_project_aggregate(self):
  root=O/'cases'/'aggregate';root.mkdir(parents=True,exist_ok=True)
  raw={'a.py':b'A=1','b.py':b'B=2\n','q/c.py':b'C=3\n\n'}
  for n,b in raw.items():p=root/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
  m=manual_manifest({n:known_record(b.rstrip(b'\n'),len(b)-len(b.rstrip(b'\n')))for n,b in raw.items()});digest=content_hash(m)
  self.scenario('aggregate-original');summary=verify_deployment_observation(m,digest,source_root=root)
  self.assertEqual((summary['declared_file_count'],summary['verified_file_count'],summary['eof_normalized_file_count'],summary['original_source_identity_match']),(3,3,0,True))
  for n in ['a.py','q/c.py']:(root/n).write_bytes(raw[n]+b'\n')
  self.scenario('aggregate-worker-LF');summary=verify_deployment_observation(m,digest,source_root=root)
  self.assertEqual((summary['deployment_hash'],summary['eof_normalized_file_count'],summary['original_source_identity_match']),(digest,2,False))
  self.assertEqual(summary['verification_mode'],'worker_terminal_lf')
  self.scenario('aggregate-strict-reject');self.reject(verify_deployment,m,digest,source_root=root,require_source_bytes=True,kind=DeploymentVerificationError)
  legacy={n:H(b)for n,b in raw.items()};self.scenario('legacy-EOF-reject');self.reject(verify_deployment,legacy,content_hash(legacy),source_root=root,kind=DeploymentVerificationError)
  for n,b in raw.items():(root/n).write_bytes(b)
  self.scenario('aggregate-project');project=verify_deployment_observation(m,digest,source_root=root,require_source_bytes=True);self.assertEqual(project['verification_mode'],'project_original_source')
  self.assertEqual(verify_deployment(legacy,content_hash(legacy),source_root=root),content_hash(legacy))
 def test_real_windows_junction_cannot_escape_before_read(self):
  inside=O/'cases'/'junction-root';outside=O/'cases'/'outside';inside.mkdir(parents=True,exist_ok=True);outside.mkdir(parents=True,exist_ok=True)
  (outside/'secret.py').write_bytes(b'SYNTHETIC_PRIVATE = 1\n');link=inside/'linked'
  def quote(p):return "'"+str(p).replace("'","''")+"'"
  command=['powershell.exe','-NoLogo','-NoProfile','-NonInteractive','-Command',f"New-Item -ItemType Junction -Path {quote(link)} -Target {quote(outside)} | Out-Null"]
  result=subprocess.run(command,capture_output=True);META['junction']={'command':command,'exit_code':result.returncode,'stdout_sha256':H(result.stdout),'stderr_sha256':H(result.stderr)}
  self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace'));self.assertEqual(link.resolve(),outside.resolve())
  rec=known_record(b'SYNTHETIC_PRIVATE = 1',1);m=manual_manifest({'linked/secret.py':rec})
  self.scenario('junction-escape-real-Windows')
  with patch.object(Path,'read_bytes',side_effect=AssertionError('out-of-root file was read')):
   self.reject(verify_deployment,m,content_hash(m),source_root=inside,kind=DeploymentVerificationError)
 def test_static_diagnostics_do_not_leak_source_or_absolute_root(self):
  root=put('privacy/secret.py',b'VALUE = "SYNTHETIC-PRIVATE-CONTENT"\n').parent
  m=manual_manifest({'secret.py':known_record(b'VALUE=0',1)})
  self.scenario('body-privacy');err=self.reject(verify_deployment,m,content_hash(m),source_root=root,worker_diagnostics=True,kind=DeploymentVerificationError)
  self.assertEqual(err.diagnostics['observed_sha256'],H((root/'secret.py').read_bytes()))
  self.assertEqual(err.diagnostics['expected_sha256'],H(b'VALUE=0\n'))
  self.assertNotEqual(err.diagnostics['observed_sha256'],m['files']['secret.py']['canonical_sha256'])
  self.scenario('missing-privacy');self.reject(verify_deployment,manual_manifest({'missing.py':known_record(b'V=1',1)}),content_hash(manual_manifest({'missing.py':known_record(b'V=1',1)})),source_root=root,worker_diagnostics=True,kind=DeploymentVerificationError)
 def test_observation_schema_and_frozen_binding(self):
  m=manual_manifest({'a.py':known_record(b'A=1',0)});digest=content_hash(m)
  summary={'schema_version':1,'source_identity_policy':POLICY,'deployment_hash':digest,'verification_mode':'worker_terminal_lf','declared_file_count':1,'verified_file_count':1,'eof_normalized_file_count':1,'original_source_identity_match':False,'canonical_sources_verified':True}
  self.scenario('observation-positive');self.assertEqual(validate_deployment_observation(summary,deployment_hash=digest),summary);validate_observation_binding({'deployment_verification':summary},m,digest)
  mutations=[dict(summary,verified_file_count=True),dict(summary,declared_file_count=0),dict(summary,original_source_identity_match=True),dict(summary,canonical_sources_verified=1),dict(summary,verification_mode='project_original_source'),dict(summary,eof_normalized_file_count=2),dict(summary,schema_version=True),dict(summary,extra=True),dict(summary,deployment_hash='0'*64)]
  for i,v in enumerate(mutations):self.scenario(f'observation-mutation/{i}');self.reject(validate_observation_binding,{'deployment_verification':v},m,digest)
  for i,e in enumerate([{}, {'deployment_verification':dict(summary,declared_file_count=2,verified_file_count=2)}]):
   self.scenario(f'observation-missing-or-count/{i}');self.reject(validate_observation_binding,e,m,digest)
  legacy={'a.py':H(b'A=1')};self.scenario('legacy-no-v2-summary');self.reject(validate_observation_binding,{'deployment_verification':summary},legacy,content_hash(legacy))

suite=unittest.defaultTestLoader.loadTestsFromTestCase(Tests);stream=io.StringIO();t=time.monotonic();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
(O/'unittest.txt').write_text(stream.getvalue(),encoding='utf-8');AFTER=snap();unchanged=AFTER==BEFORE
doc={'methods':result.testsRun,'failure_records':len(result.failures),'error_records':len(result.errors),'skipped':len(result.skipped),'named_scenarios':len(SCENARIOS),'scenario_labels':SCENARIOS,'success':result.wasSuccessful(),'source_raw_unchanged':unchanged,'source_files':len(BEFORE),'seconds':time.monotonic()-t,'failures':[{'test':str(x),'traceback':y}for x,y in result.failures],'errors':[{'test':str(x),'traceback':y}for x,y in result.errors],'metadata':META,'QC_calls':0,'market_calls':0,'authoritative_budget_writes':0}
(O/'results.json').write_text(json.dumps(doc,ensure_ascii=True,indent=2)+'\n',encoding='utf-8');print(json.dumps({k:v for k,v in doc.items()if k not in ['scenario_labels','failures','errors']}));print(stream.getvalue());raise SystemExit(int(not result.wasSuccessful()or not unchanged))
