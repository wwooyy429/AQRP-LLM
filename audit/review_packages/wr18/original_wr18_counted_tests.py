from pathlib import Path
import hashlib
import importlib
import io
import json
import os
import shutil
import sys
import time
import unittest

root=Path(__file__).resolve().parents[2]
phase=sys.argv[1]
out=root/'.git/repair-work'/('wr18-counted-'+phase)
out.mkdir(parents=True,exist_ok=True)
if phase=='before':
    source=out/'source'
    original=root.parent/'LLM审核/review-ae2b898-20261027/source'
    for folder in ('cloud','tools','config','tests'):
        shutil.copytree(original/folder,source/folder,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    shutil.copyfile(root/'tests/test_wr18_completion_dependency.py',source/'tests/test_wr18_completion_dependency.py')
else:
    source=root
sys.path[:0]=[str(source/'cloud'),str(source/'tools'),str(source/'tests')]
target=source/'tests/test_wr18_completion_dependency.py'
shutil.copyfile(target,out/'test_input.py')
class Counted(unittest.TextTestResult):
    def __init__(self,*a,**kw):super().__init__(*a,**kw);self.subcases=0
    def addSubTest(self,test,sub,error):self.subcases+=1;super().addSubTest(test,sub,error)
module=importlib.import_module('test_wr18_completion_dependency')
stream=io.StringIO();start=time.monotonic()
result=unittest.TextTestRunner(stream=stream,verbosity=2,resultclass=Counted).run(unittest.defaultTestLoader.loadTestsFromModule(module))
text=stream.getvalue();(out/'stderr').write_bytes(text.encode('utf-8'));(out/'stdout').write_bytes(b'')
def method(t):return getattr(t,'test_case',t).id()
failed={method(t) for t,_ in result.failures};errors={method(t) for t,_ in result.errors}
record={'phase':phase,'source':str(source),'command':[sys.executable,'-B',str(Path(__file__).resolve()),phase],
    'methods':result.testsRun,'passed_methods':result.testsRun-len(failed|errors),'failed_methods':len(failed),'error_methods':len(errors),
    'failure_records':len(result.failures),'error_records':len(result.errors),'subcases':result.subcases,'skipped':len(result.skipped),
    'test_raw_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'seconds':time.monotonic()-start,
    'source_raw_sha256':{name:hashlib.sha256((source/'cloud/qresearch'/name).read_bytes()).hexdigest() for name in ('registry.py','engineering_tasks.py')},
    'exit_code':0 if result.wasSuccessful() else 1,'actual_cloud_or_model_calls':0}
(out/'execution.json').write_bytes((json.dumps(record,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
print(json.dumps(record,ensure_ascii=True))
raise SystemExit(record['exit_code'])
