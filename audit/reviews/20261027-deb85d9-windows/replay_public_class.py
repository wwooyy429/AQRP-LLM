"""Run archived independent classes without machine-specific main helpers."""
from pathlib import Path
import argparse,hashlib,importlib.util,io,json,math,os,shutil,socket,sys,tempfile,unittest
def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--script',type=Path,required=True);p.add_argument('--class-name',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);source=a.source.resolve();raw=a.script.read_bytes()
    source_files={f.relative_to(source).as_posix():hashlib.sha256(f.read_bytes()).hexdigest() for d in ['cloud','config','tools'] for f in (source/d).rglob('*') if f.is_file() and f.suffix in ['.py','.json']}
    def clean(v):
        if isinstance(v,float) and not math.isfinite(v):return None
        if isinstance(v,dict):return {k:clean(x) for k,x in v.items()}
        if isinstance(v,(list,tuple)):return [clean(x) for x in v]
        return v
    class Result(unittest.TextTestResult):
        def __init__(self,*args,**kwargs):super().__init__(*args,**kwargs);self.subcases=0
        def addSubTest(self,test,subtest,error):self.subcases+=1;super().addSubTest(test,subtest,error)
    with tempfile.TemporaryDirectory(prefix='aqrp-independent-class-') as temp:
        work=Path(temp);shutil.copytree(source,work/'source');folder=work/'archived';folder.mkdir();script=folder/'original.py';script.write_bytes(raw)
        def deny(*args,**kwargs):raise AssertionError('Offline audit class replay forbids networking')
        socket.socket.connect=deny
        spec=importlib.util.spec_from_file_location('archived_independent',script);mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod)
        stream=io.StringIO();r=unittest.TextTestRunner(stream=stream,verbosity=2,resultclass=Result).run(unittest.defaultTestLoader.loadTestsFromTestCase(getattr(mod,a.class_name)))
        def identity(test):return getattr(test,'test_case',test).id()
        failed={identity(t) for t,_ in r.failures};errors={identity(t) for t,_ in r.errors};skipped={identity(t) for t,_ in r.skipped}
        report={'actually_executed':True,'entrypoint':a.class_name+' methods only; original main not run','script_sha256':hashlib.sha256(raw).hexdigest(),'source_files':source_files,
            'methods':r.testsRun,'passed_methods':r.testsRun-len(failed|errors|skipped),'failed_methods':len(failed),'error_methods':len(errors),'skipped':len(skipped),'subcases':r.subcases,
            'failure_records':len(r.failures),'error_records':len(r.errors),'expected_failures':len(r.expectedFailures),'unexpected_successes':len(r.unexpectedSuccesses),
            'failures':[{'test':identity(t),'traceback':tb} for t,tb in r.failures],'errors':[{'test':identity(t),'traceback':tb} for t,tb in r.errors],
            'observations':getattr(mod,'OBS',None),'source_unchanged':all(hashlib.sha256((work/'source'/f).read_bytes()).hexdigest()==h for f,h in source_files.items()),'financial_evidence':False}
        (out/'output.txt').write_text(stream.getvalue(),encoding='utf-8');(out/'results.json').write_text(json.dumps(clean(report),ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
        print(json.dumps({k:report[k] for k in ['methods','passed_methods','failed_methods','error_methods','skipped','subcases']}))
        return int(not (r.wasSuccessful() and not (r.skipped or r.expectedFailures or r.unexpectedSuccesses) and report['source_unchanged']))
if __name__=='__main__':raise SystemExit(main())
