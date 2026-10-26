import hashlib
import io
import json
from pathlib import Path
import sys
import time
import unittest

root=Path(__file__).resolve().parents[3]
out=Path(__file__).resolve().parent
sys.path[:0]=[str(root/'cloud'),str(root/'tests')]

class Counts(unittest.TextTestResult):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.subcases=0
    def addSubTest(self,test,subtest,error):
        self.subcases+=1
        super().addSubTest(test,subtest,error)

capture=io.StringIO()
start=time.monotonic()
suite=unittest.defaultTestLoader.discover(str(root/'tests'),pattern='test_phase2_joint_boundaries.py')
result=unittest.TextTestRunner(stream=capture,verbosity=2,resultclass=Counts).run(suite)
text=capture.getvalue()
(out/'joint_boundary_targeted.stdout').write_bytes(b'')
(out/'joint_boundary_targeted.stderr').write_bytes(text.encode('utf-8'))
files=['tests/test_phase2_joint_boundaries.py','cloud/qresearch/engineering_tasks.py',
       'cloud/qresearch/engineering_receipts.py','cloud/qresearch/registry.py']
report={'methods':result.testsRun,'subcases':result.subcases,'success':result.wasSuccessful(),
    'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),
    'seconds':time.monotonic()-start,'python':sys.version,'executable':sys.executable,
    'source_sha256':{p:hashlib.sha256((root/p).read_text(encoding='utf-8-sig').encode()).hexdigest() for p in files},
    'new_Research_executions':0,'new_LEAN_submissions':0,'new_market_or_model_calls':0,
    'scope':'Developer peer synthetic boundary tests only, not GPT Work independent acceptance or data certification'}
(out/'joint_boundary_targeted_summary.json').write_bytes((json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode())
print(json.dumps(report,ensure_ascii=True))
raise SystemExit(not result.wasSuccessful())
