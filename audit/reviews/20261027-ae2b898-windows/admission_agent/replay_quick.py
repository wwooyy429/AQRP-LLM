from pathlib import Path
from hashlib import sha256
import io,json,sys,unittest
sys.dont_write_bytecode=True
import quick_joint_probes as h
R=Path(__file__).resolve().parent
OLD=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-8f7236e-20261027\admission_agent')
names=[name for name in unittest.defaultTestLoader.getTestCaseNames(h.JointProbes) if 'legacy_freeze' not in name]
stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.TestSuite(h.JointProbes(n) for n in names))
data={'reviewed_source_commit':'ae2b8985f3799c246e90341370f86d80483f63ed','actual_source':str(h.SOURCE),
 'methods':result.testsRun,'passed_methods':result.testsRun-len(result.failures)-len(result.errors),'failed_methods':len(result.failures),
 'error_methods':len(result.errors),'subcases':0,'skipped':len(result.skipped),'names':names,
 'failures':[{'method':t.id(),'traceback':tb} for t,tb in result.failures],'errors':[{'method':t.id(),'traceback':tb} for t,tb in result.errors],
 'originals_byte_equal':{name:(R/name).read_bytes()==(OLD/name).read_bytes() for name in ['quick_joint_probes.py','minimal_joint_registry.py']},
 'original_script_sha256':{name:sha256((R/name).read_bytes()).hexdigest() for name in ['quick_joint_probes.py','minimal_joint_registry.py']},
 'observations':h.OBS,'command':[sys.executable,'-B',str(Path(__file__).resolve())],
 'exit_code':0 if result.wasSuccessful() else 1}
(R/'replay_quick_first.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(R/'replay_quick_first.stdout').write_text(stream.getvalue(),encoding='utf-8')
print(stream.getvalue());print(json.dumps({k:data[k] for k in ['methods','passed_methods','failed_methods','error_methods','exit_code']}))
raise SystemExit(data['exit_code'])
