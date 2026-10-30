"""Independent bounded source observations and extraction; no executed imports."""
from pathlib import Path
from copy import deepcopy
from hashlib import sha256
from unittest.mock import patch
from uuid import uuid4
import ast,html,io,json,sys,unittest
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parent;SOURCE=ROOT.parent/'source'
sys.path.insert(0,str(SOURCE/'cloud'))
from qresearch.artifacts import content_hash,canonical_json
from qresearch.engineering_data import verify_deployment,DeploymentVerificationError
from qresearch.worker_identity import source_format_observation,extract_worker_diagnostics,validate_source_observation,path_fingerprint,MAX_AST_SOURCE_BYTES
RUN=ROOT/'worker_cases'/uuid4().hex[:8];RUN.mkdir(parents=True)
OBS={}
def diagnostic(raw=b'# independent\n',mode='mismatch',controlled=True):
    calls=[]
    def reading(path):
        calls.append(str(path))
        if mode=='missing':raise FileNotFoundError('ABSOLUTE_SECRET'+str(path))
        if mode=='permission':raise PermissionError('ABSOLUTE_SECRET'+str(path))
        return raw if len(calls)==1 else b'changed second read\n'
    manifest={'module.py':'0'*64}
    with patch.object(Path,'read_bytes',reading):
        try:verify_deployment(manifest,content_hash(manifest),source_root=RUN,worker_diagnostics=controlled)
        except DeploymentVerificationError as e:return e,calls
    raise AssertionError('Mismatch should fail strict deployment')
def error_from(doc):
    messages={'source_hash_mismatch':'Cloud implementation differs from the frozen deployment','source_unreadable':'Implementation source is unavailable','source_decode_error':'Implementation source is not UTF-8'}
    return messages[doc['failure_kind']]+'; diagnostics='+json.dumps(doc,separators=(',',':'))
class WorkerIdentity(unittest.TestCase):
    def test_known_answer_format_AST_without_executing_imports(self):
        raw=b'\xef\xbb\xbffrom __future__ import annotations\r\nimport AlgorithmImports as A\rfrom AlgorithmImports import *\n\n'
        d=source_format_observation(raw)
        for key,value in {'raw_sha256':sha256(raw).hexdigest(),'byte_count':len(raw),'utf8_bom':True,'crlf_count':1,'standalone_cr_count':1,'lf_count':3,'normalized_trailing_lf_count':2,'syntax_status':'parsed','algorithm_import_count':1,'algorithm_from_import_count':1,'algorithm_star_import_count':1,'future_import_count':1}.items():
            with self.subTest(field=key):self.assertEqual(d[key],value)
        other=source_format_observation(b'# import AlgorithmImports\ns="from AlgorithmImports import *"\nfrom .AlgorithmImports import X\n')
        self.assertEqual(other['algorithm_import_count'],0);self.assertEqual(other['algorithm_from_import_count'],0)
        self.assertNotIn('AlgorithmImports',sys.modules)

    def test_invalid_syntax_UTF8_size_and_type_boundaries(self):
        for raw,status in [(b'\xff','invalid_utf8'),(b'if:\n','invalid_syntax'),(b'#'+b'x'*MAX_AST_SOURCE_BYTES,'not_inspected_size_limit')]:
            with self.subTest(status=status):
                d=source_format_observation(raw);self.assertEqual(d['syntax_status'],status)
                for key in ['algorithm_import_count','algorithm_from_import_count','algorithm_star_import_count','future_import_count']:self.assertIsNone(d[key])
        for raw in ['bytes?',bytearray(b'a'),None,True]:
            with self.subTest(type=type(raw).__name__):
                with self.assertRaises(ValueError):source_format_observation(raw)

    def test_schema1_default_and_schema2_same_single_read(self):
        for mode,raw,kind in [('mismatch',b'import AlgorithmImports\r\n','source_hash_mismatch'),('mismatch',b'\xff','source_decode_error'),('missing',b'','source_unreadable'),('permission',b'','source_unreadable')]:
            with self.subTest(mode=mode,kind=kind):
                error,calls=diagnostic(raw,mode);d=error.diagnostics
                self.assertEqual(len(calls),1);self.assertEqual(d['schema_version'],2);self.assertEqual(d['failure_kind'],kind)
                self.assertNotIn(str(RUN),str(error));self.assertNotIn('ABSOLUTE_SECRET',str(error))
                worker=d['worker_observation'];validate_source_observation(worker)
                self.assertFalse(worker['strict_identity_relaxed']);self.assertFalse(worker['old_worker_root_cause_proven'])
                if kind!='source_unreadable':self.assertEqual(worker['source_format']['raw_sha256'],sha256(raw).hexdigest())
                if kind=='source_hash_mismatch':
                    self.assertEqual(d['observed_sha256'],sha256(b'import AlgorithmImports\n').hexdigest())
                parsed=extract_worker_diagnostics([str(error)]);self.assertEqual(parsed['diagnostic'],d)
        e,_=diagnostic(controlled=False);self.assertEqual(e.diagnostics['schema_version'],1)
        self.assertNotIn('worker_observation',e.diagnostics)

    def test_controlled_path_hash_and_field_mutation_cannot_leak(self):
        self.assertEqual(path_fingerprint('C:/秘密/\ud800'),sha256('C:/秘密/\ud800'.encode('utf-8',errors='surrogatepass')).hexdigest())
        e,_=diagnostic();copy=e.diagnostics;copy['worker_observation']['root_context']['root_selection']='poison'
        self.assertEqual(e.diagnostics['worker_observation']['root_context']['root_selection'],'explicit')
        for path in ['../module.py','C:/module.py','CON.py','COM9.py','module\x7f.py','module\ud800.py']:
            with self.subTest(path=repr(path)):
                with self.assertRaises(DeploymentVerificationError) as bad:verify_deployment({path:'0'*64},'0'*64,source_root=RUN,worker_diagnostics=True)
                self.assertEqual(bad.exception.diagnostics['schema_version'],1)
                self.assertEqual(bad.exception.diagnostics['failure_kind'],'invalid_path')

    def test_message_plain_HTML_duplicates_and_count_limits(self):
        e,_=diagnostic();message=str(e)
        for messages,count in [([message],1),([html.escape(message)],1),([message,message],2),([message*4 for _ in range(16)],64)]:
            with self.subTest(count=count,html='&quot;' in messages[0]):
                got=extract_worker_diagnostics(messages);self.assertEqual(got['matching_occurrence_count'],count)
                self.assertFalse(got['remote_provenance_verified']);self.assertFalse(got['old_worker_root_cause_proven']);self.assertFalse(got['financial_evidence'])
                expected=sha256(json.dumps(messages,ensure_ascii=True,separators=(',',':')).encode('ascii')).hexdigest()
                self.assertEqual(got['input_messages_sha256'],expected)
        for messages in [[html.escape(html.escape(message))],[message]*17,['x'*32769],['x'*30000]*5,[message*4]*15+[message*5]]:
            with self.subTest(negative_len=len(messages)):
                with self.assertRaises(ValueError):extract_worker_diagnostics(messages)
        self.assertIsNone(extract_worker_diagnostics(['normal source-unrelated error']))
        e,_=diagnostic(mode='missing');other=str(e)
        with self.assertRaises(ValueError):extract_worker_diagnostics([message,other])

    def test_invalid_diagnostic_fields_paths_and_typed_aliases_reject(self):
        e,_=diagnostic();base=e.diagnostics
        for mode in ['schema_bool','unknown','missing_path','absolute','device','DEL','input_path','byte_bool','root_bool','relaxed','equal_hashes','legacy','duplicate_json']:
            with self.subTest(mode=mode):
                d=deepcopy(base)
                if mode=='schema_bool':d['schema_version']=True
                if mode=='unknown':d['rows']=[1]
                if mode=='missing_path':d.pop('path')
                if mode=='absolute':d['path']='C:/private.py'
                if mode=='device':d['path']='CON.py'
                if mode=='DEL':d['path']='mod\x7f.py'
                if mode=='input_path':d['path']='_engineering_task_input.py'
                if mode=='byte_bool':d['worker_observation']['source_format']['byte_count']=True
                if mode=='root_bool':d['worker_observation']['root_context']['verifier_within_source_root']=1
                if mode=='relaxed':d['worker_observation']['strict_identity_relaxed']=True
                if mode=='equal_hashes':d['observed_sha256']=d['expected_sha256']
                if mode=='legacy':d['schema_version']=1
                message=error_from(d)
                if mode=='duplicate_json':message=message.replace('"schema_version":2','"schema_version":2,"schema_version":2',1)
                with self.assertRaises(ValueError):extract_worker_diagnostics([message])

class Counted(unittest.TextTestResult):
    def __init__(self,*a,**k):super().__init__(*a,**k);self.subcases=0
    def addSubTest(self,test,sub,error):self.subcases+=1;super().addSubTest(test,sub,error)
def main():
    stream=io.StringIO();r=unittest.TextTestRunner(stream=stream,verbosity=2,resultclass=Counted).run(unittest.defaultTestLoader.loadTestsFromTestCase(WorkerIdentity))
    ident=lambda t:getattr(t,'test_case',t).id();failed={ident(t) for t,_ in r.failures};errors={ident(t) for t,_ in r.errors}
    d={'source_commit':'deb85d9f27441b275ab8b108f0232ecd2707a1e8','methods':r.testsRun,'passed_methods':r.testsRun-len(failed|errors),'failed_methods':len(failed),'error_methods':len(errors),'subcases':r.subcases,'skips':len(r.skipped),
       'failures':[{'method':ident(t),'traceback':tb} for t,tb in r.failures],'errors':[{'method':ident(t),'traceback':tb} for t,tb in r.errors],
       'actual_source_workers_market_QC_calls':0,'script_sha256':sha256(Path(__file__).read_bytes()).hexdigest(),'exit_code':0 if r.wasSuccessful() else 1}
    (ROOT/'worker_identity_first_results.json').write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8')
    print(stream.getvalue());print(json.dumps({k:d[k] for k in ['methods','passed_methods','failed_methods','error_methods','subcases','exit_code']}));return d['exit_code']
if __name__=='__main__':raise SystemExit(main())
