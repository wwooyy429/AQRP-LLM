"""Independent diagnostic and MCP reference preflight; synthetic inputs only."""
from pathlib import Path,PureWindowsPath
from copy import deepcopy
from hashlib import sha256
from unittest.mock import patch
from uuid import uuid4
import io,json,sys,unittest
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parent;SOURCE=ROOT.parent/'source'
sys.path[:0]=[str(SOURCE/'cloud'),str(SOURCE/'tools')]
from qresearch.artifacts import content_hash,canonical_json
from qresearch.engineering_data import verify_deployment,source_bytes_sha256,DeploymentVerificationError
from deployment_preflight import read_project_preflight
RUN=ROOT/'pure_cases'/uuid4().hex[:8];RUN.mkdir(parents=True)
OBS={}
BAD=['../x.py','C:/x.py','a\\x.py','CON.py','COM9.py','x:stream.py','a\x7f.py','a?.py','_engineering_task_input.py','a\ud800.py']
def project():
    files=[{'filePath':'app.py','content':'marker = 1\n'},{'filePath':'lib/模块.py','content':'label = "工程"\n'}]
    manifest={f['filePath']:source_bytes_sha256(f['content'].encode()) for f in files}
    notebook='NOTEBOOK_SENTINEL_66f_'+str(uuid4())
    input_text='TASK_INPUT_JSON = "{}"\r\n'
    files += [{'filePath':'Research.ipynb','content':json.dumps({'outputs':[notebook]})},
              {'filePath':'_engineering_task_input.py','content':input_text}]
    native={'success':True,'project':{'projectId':931707,'name':'independent-only','language':'Py','files':files}}
    tool={'tool_name':'mcp__quantconnect__read_project','arguments':{'projectId':931707},'result':native}
    listing={'success':True,'projects':[{'projectId':931707,'name':'synthetic','language':'Py'}]}
    return tool,listing,manifest,sha256(input_text.encode()).hexdigest(),notebook
def preflight(t,l,m,i):return read_project_preflight(t,l,m,content_hash(m),project_id=931707,input_sha256=i)
def mirror(value):
    return {'structuredContent':value,'content':[{'type':'text','text':json.dumps(value,ensure_ascii=False)}],'isError':False}

class PurePreflight(unittest.TestCase):
    def test_universal_newline_BOM_and_EOF_contract(self):
        expected=sha256(b'x=1\n').hexdigest()
        for raw in [b'x=1\n',b'x=1\r\n',b'x=1\r',b'\xef\xbb\xbfx=1\n']:
            with self.subTest(raw=repr(raw)):self.assertEqual(source_bytes_sha256(raw),expected)
        for raw in [b'x=1',b'x=1\n\n']:
            with self.subTest(EOF=repr(raw)):self.assertNotEqual(source_bytes_sha256(raw),expected)
        for raw in [b'\xff',None,'x=1\n']:
            with self.subTest(invalid=repr(raw)):
                with self.assertRaises(ValueError):source_bytes_sha256(raw)

    def test_all_manifest_paths_validated_before_first_read(self):
        for bad in BAD:
            with self.subTest(path=repr(bad)):
                manifest={'app.py':sha256(b'first\n').hexdigest(),bad:'a'*64};reads=[]
                with patch.object(Path,'read_bytes',lambda p:reads.append(str(p)) or b'first\n'):
                    with self.assertRaises(DeploymentVerificationError) as error:
                        verify_deployment(manifest,content_hash(manifest),source_root=RUN)
                self.assertEqual(reads,[]);self.assertEqual(error.exception.diagnostics['failure_kind'],'invalid_path')
                self.assertNotIn(bad,str(error.exception))
                self.assertNotIn(str(RUN),str(error.exception))

    def test_single_observation_diagnostics_and_safe_OS_decode_errors(self):
        manifest={'app.py':sha256(b'expected\n').hexdigest()}
        for mode in ['mismatch','unreadable','decode']:
            with self.subTest(mode=mode):
                reads=[]
                def reading(path):
                    reads.append(str(path))
                    if mode=='unreadable':raise OSError('ABSOLUTE_SECRET_'+str(RUN))
                    return b'actual\n' if mode=='mismatch' else b'\xff'
                with patch.object(Path,'read_bytes',reading):
                    with self.assertRaises(DeploymentVerificationError) as e:
                        verify_deployment(manifest,content_hash(manifest),source_root=RUN)
                self.assertEqual(len(reads),1);self.assertNotIn(str(RUN),str(e.exception));self.assertNotIn('ABSOLUTE_SECRET',str(e.exception))
                self.assertEqual(e.exception.diagnostics['expected_sha256'],manifest['app.py'])
                if mode=='mismatch':self.assertEqual(e.exception.diagnostics['observed_sha256'],sha256(b'actual\n').hexdigest())
                OBS[mode]=e.exception.diagnostics

    def test_unicode_positive_and_diagnostic_path_hash(self):
        folder=RUN/'unicode';(folder/'模块').mkdir(parents=True)
        (folder/'模块'/'é.py').write_bytes(b'# independent\n')
        m={'模块/é.py':sha256(b'# independent\n').hexdigest()}
        self.assertEqual(verify_deployment(m,content_hash(m),source_root=folder),content_hash(m))
        m['模块/é.py']='0'*64
        with self.assertRaises(DeploymentVerificationError) as e:verify_deployment(m,content_hash(m),source_root=folder)
        self.assertNotIn('path',e.exception.diagnostics);self.assertIn('path_sha256',e.exception.diagnostics)
        self.assertNotIn('模块',str(e.exception))

    def test_MCP_positive_carriers_no_notebook_or_dispatch_certification(self):
        for carrier in ['native','structured','text','mirrored']:
            with self.subTest(carrier=carrier):
                t,l,m,i,secret=project();v=t['result']
                if carrier=='structured':t['result']={'structuredContent':v}
                if carrier=='text':t['result']={'content':[{'type':'text','text':json.dumps(v)}]}
                if carrier=='mirrored':t['result']=mirror(v);l={'tool_name':'mcp__quantconnect__list_projects','arguments':{},'result':mirror(l)}
                result=preflight(t,l,m,i)
                self.assertTrue(result['preflight_passed']);self.assertTrue(result['input_binding_verified'])
                self.assertEqual(result['ignored_non_python_file_count'],1)
                self.assertNotIn(secret,json.dumps(result))
                for flag in ['ready_to_dispatch','budget_admission_performed','worker_source_verified','full_cloud_inventory_certified','financial_evidence']:
                    self.assertIs(result[flag],False)
        t,l,m,i,secret=project();a=preflight(t,l,m,i);t['result']['project']['files'][2]['content']='CHANGED_NOTEBOOK_SECRET'
        self.assertEqual(preflight(t,l,m,i),a)

    def test_returned_reference_missing_extra_EOF_and_input_mismatch(self):
        for mode in ['missing','extra','EOF','input_CRLF_changed']:
            with self.subTest(mode=mode):
                t,l,m,i,_=project();files=t['result']['project']['files']
                if mode=='missing':files.pop(0)
                if mode=='extra':files.append({'filePath':'extra.py','content':'extra=1\n'})
                if mode=='EOF':files[0]['content']+='\n'
                if mode=='input_CRLF_changed':files[-1]['content']=files[-1]['content'].replace('\r\n','\n')
                result=preflight(t,l,m,i)
                self.assertFalse(result['preflight_passed']);self.assertIs(result['ready_to_dispatch'],False)
                if mode=='input_CRLF_changed':self.assertTrue(result['source_reference_matches']);self.assertFalse(result['input_binding_verified'])

    def test_invalid_paths_aliases_and_carrier_conflicts_are_rejected(self):
        for mode in ['case_alias','bad_return_path','bad_manifest_path','wrong_args','wrong_internal_id','wrong_listing_id','mirror_conflict','notebook_mirror_conflict','annotation_rows','image_carrier','unknown_meta','duplicate_json']:
            with self.subTest(mode=mode):
                t,l,m,i,_=project();native=t['result']
                if mode=='case_alias':native['project']['files'].append({'filePath':'APP.py','content':'marker = 1\n'})
                if mode=='bad_return_path':native['project']['files'][0]['filePath']='AUX.py'
                if mode=='bad_manifest_path':m={'x\x7f.py':'a'*64}
                if mode=='wrong_args':t['arguments']['projectId']=931708
                if mode=='wrong_internal_id':native['project']['projectId']=931708
                if mode=='wrong_listing_id':l['projects'][0]['projectId']=931708
                if mode in ['mirror_conflict','notebook_mirror_conflict']:
                    other=deepcopy(native)
                    if mode=='mirror_conflict':other['project']['files'][0]['content']+='different'
                    else:other['project']['files'][2]['content']='SECRET_HIDDEN_IN_DIFFERENT_MIRROR'
                    t['result']={'structuredContent':native,'content':[{'type':'text','text':json.dumps(other)}]}
                if mode=='annotation_rows':t['result']={'structuredContent':native,'content':[{'type':'text','text':json.dumps(native),'annotations':{'rows':[1]}}]}
                if mode=='image_carrier':t['result']={'structuredContent':native,'content':[{'type':'image','data':'SECRET','mimeType':'image/png'}]}
                if mode=='unknown_meta':t['result']={'structuredContent':native,'_meta':{'rows':[1]}}
                if mode=='duplicate_json':t['result']={'content':[{'type':'text','text':'{"success":true,"success":false}'}]}
                with self.assertRaises(ValueError):preflight(t,l,m,i)

class Counted(unittest.TextTestResult):
    def __init__(self,*a,**k):super().__init__(*a,**k);self.subcases=0
    def addSubTest(self,test,sub,error):self.subcases+=1;super().addSubTest(test,sub,error)
def main():
    stream=io.StringIO();r=unittest.TextTestRunner(stream=stream,verbosity=2,resultclass=Counted).run(unittest.defaultTestLoader.loadTestsFromTestCase(PurePreflight))
    ident=lambda t:getattr(t,'test_case',t).id()
    failed={ident(t) for t,_ in r.failures};errors={ident(t) for t,_ in r.errors}
    d={'source_commit':'66ff72ffaaff8c91c008898e6527c91131176c2a','methods':r.testsRun,'passed_methods':r.testsRun-len(failed|errors),'failed_methods':len(failed),'error_methods':len(errors),
       'subcases':r.subcases,'skips':len(r.skipped),'failures':[{'method':ident(t),'traceback':tb} for t,tb in r.failures],'errors':[{'method':ident(t),'traceback':tb} for t,tb in r.errors],
       'observations':OBS,'actual_QC_market_model_worker_calls':0,'script_sha256':sha256(Path(__file__).read_bytes()).hexdigest(),'exit_code':0 if r.wasSuccessful() else 1}
    (ROOT/'pure_first_results.json').write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8')
    print(stream.getvalue());print(json.dumps({k:d[k] for k in ['methods','passed_methods','failed_methods','error_methods','subcases','exit_code']}));return d['exit_code']
if __name__=='__main__':raise SystemExit(main())
