"""Synthetic CLI exit-code and notebook-redaction coverage."""
from pathlib import Path
from copy import deepcopy
from hashlib import sha256
import io,json,os,subprocess,sys,unittest
sys.dont_write_bytecode=True
import independent_preflight_corrected as h
ROOT=Path(__file__).resolve().parent;COMMANDS=[]
class PreflightCLI(unittest.TestCase):
    def test_cli_exit_codes_do_not_export_notebook(self):
        for mode,expected in [('valid',0),('source_mismatch',1),('invalid_arguments',2),('mirror_conflict',2)]:
            with self.subTest(mode=mode):
                folder=ROOT/'preflight_cli_cases'/mode;folder.mkdir(parents=True,exist_ok=True)
                t,l,m,i,secret=h.project()
                if mode=='source_mismatch':t['result']['project']['files'][0]['content']+='\n'
                if mode=='invalid_arguments':t['arguments']['projectId']=931708
                if mode=='mirror_conflict':
                    other=deepcopy(t['result']);other['project']['files'][2]['content']='MIRROR_NOTEBOOK_SECRET'
                    t['result']={'structuredContent':t['result'],'content':[{'type':'text','text':json.dumps(other)}]}
                for name,value in [('tool.json',t),('listing.json',l),('manifest.json',m)]:
                    (folder/name).write_text(json.dumps(value),encoding='utf-8')
                cmd=[sys.executable,'-B',str(h.SOURCE/'tools/deployment_preflight.py'),
                  '--project-tool-file',str(folder/'tool.json'),'--projects-file',str(folder/'listing.json'),
                  '--manifest-file',str(folder/'manifest.json'),'--deployment-hash',h.content_hash(m),
                  '--project-id','931707','--input-sha256',i]
                p=subprocess.run(cmd,cwd=ROOT,text=True,encoding='utf-8',capture_output=True,timeout=30,
                    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8',OPENBLAS_NUM_THREADS='1'))
                COMMANDS.append({'mode':mode,'command':cmd,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
                self.assertEqual(p.returncode,expected);self.assertNotIn(secret,p.stdout+p.stderr)
                self.assertNotIn('MIRROR_NOTEBOOK_SECRET',p.stdout+p.stderr)
                result=json.loads(p.stdout);self.assertIs(result['ready_to_dispatch'],False)
                self.assertEqual(result['preflight_passed'],mode=='valid')
class Counted(unittest.TextTestResult):
    def __init__(self,*a,**k):super().__init__(*a,**k);self.subcases=0
    def addSubTest(self,test,sub,error):self.subcases+=1;super().addSubTest(test,sub,error)
def main():
    stream=io.StringIO();r=unittest.TextTestRunner(stream=stream,verbosity=2,resultclass=Counted).run(unittest.defaultTestLoader.loadTestsFromTestCase(PreflightCLI))
    d={'source_commit':'66ff72ffaaff8c91c008898e6527c91131176c2a','methods':r.testsRun,'subcases':r.subcases,'failures':len(r.failures),'errors':len(r.errors),'skips':len(r.skipped),'actual_CLI_processes':len(COMMANDS),'actual_QC_market_model_worker_calls':0,'exit_code':0 if r.wasSuccessful() else 1}
    (ROOT/'preflight_cli_first_results.json').write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8')
    (ROOT/'preflight_cli_command_log.json').write_text(json.dumps(COMMANDS,indent=2)+'\n',encoding='utf-8')
    print(stream.getvalue());print(json.dumps(d));return d['exit_code']
if __name__=='__main__':raise SystemExit(main())
