"""New parser/recovery interaction probes, reusing only our prior audit helpers."""
from pathlib import Path
from copy import deepcopy
from uuid import uuid4
from hashlib import sha256
import importlib.util,io,json,shutil,sys,unittest

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('prior_independent_recovery',ROOT/'independent_recovery.py')
h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
first=h.read(ROOT/'first_results.json');commands=h.read(ROOT/'command_log.json')
BASE=Path(commands[0]['cwd']);ATTEMPT=first['observations']['base']['attempt'];USAGE=first['observations']['base']['usage']
RUN=ROOT/'parser_cases'/uuid4().hex[:8];OBS=[]

class ParserRecovery(unittest.TestCase):
    def case(self):
        target=RUN/uuid4().hex[:8];shutil.copytree(BASE,target)
        h.write(target/'task-B.json',h.raw_task('independent-parser-B',734002))
        h.success(h.call(target,['freeze-task','--task-file','task-B.json','--projects-file','projects.json']))
        p=target/'cloud/qresearch/cache.py';p.write_bytes(p.read_bytes()+b'\n# independent post-admission source drift\n')
        c=h.read(target/'config/source_catalog.json');c['fields']['dollar_volume']['unit']='changed-after-admission';h.write(target/'config/source_catalog.json',c)
        return target
    def rewrite(self,case,annotations):
        tool=h.read(case/'synthetic-tool.json');marker=tool['result']['structuredContent']['outputs'][0]['text']
        tool['result']['structuredContent']={'status':'completed','content':[{'type':'text','text':marker,'annotations':annotations}]}
        h.write(case/'nested-tool.json',tool)
    def settle(self,case,tool):return h.call(case,['research-result','--attempt',ATTEMPT,'--tool-file',tool])

    def test_illegal_annotations_refuse_old_result_then_corrected_result_completes_same_attempt(self):
        for annotation in [{'rows':[{'sid':'independent-synthetic-side-row','value':73}]},
                           {'error':'independent-synthetic-extra-error'},
                           {'outputs':[{'output_type':'display_data','data':'synthetic-only'}]}]:
            with self.subTest(annotation_key=next(iter(annotation))):
                case=self.case();self.rewrite(case,annotation);before=h.journal(case)
                result=self.settle(case,'nested-tool.json')
                self.assertNotEqual(result.returncode,0,result.stdout)
                self.assertIn('ReceiptParseError',result.stderr)
                self.assertEqual(h.journal(case),before)
                self.assertEqual(h.attempt_record(case,ATTEMPT),'attempt_started')
                self.assertEqual(h.budget_usage(case),USAGE)
                self.assertNotIn(b'independent-synthetic-side-row',h.journal(case))
                corrected=h.success(self.settle(case,'synthetic-tool.json'))
                self.assertEqual(corrected['status'],'completed');self.assertEqual(corrected['attempt_id'],ATTEMPT)
                self.assertEqual(h.budget_usage(case),USAGE)
                OBS.append({'annotation':next(iter(annotation)),'invalid_exit':result.returncode,'unchanged_before_correction':True,
                            'corrected_status':corrected['status'],'charge_unchanged':True})

    def test_legal_nested_annotations_survive_A_to_B_source_and_catalog_drift(self):
        for annotation in [None,{}, {'audience':['assistant','assistant'],'priority':0,'lastModified':'2026-10-27T00:30:00+08:00'}]:
            with self.subTest(annotation=annotation):
                case=self.case();self.rewrite(case,annotation)
                result=h.success(self.settle(case,'nested-tool.json'))
                self.assertEqual(result['status'],'completed');self.assertEqual(result['attempt_id'],ATTEMPT)
                self.assertEqual(h.budget_usage(case),USAGE)
                OBS.append({'legal_annotation':annotation,'status':result['status'],'charge_unchanged':True})

def main():
    stream=io.StringIO();r=unittest.TextTestRunner(stream=stream,verbosity=2,resultclass=h.Counted).run(unittest.defaultTestLoader.loadTestsFromTestCase(ParserRecovery))
    (ROOT/'parser_first_output.txt').write_text(stream.getvalue(),encoding='utf-8')
    def method(t):return getattr(t,'test_case',t).id()
    failures={method(t) for t,_ in r.failures};errors={method(t) for t,_ in r.errors}
    result={'reviewed_source_commit':'dc49f0f3037918f3ce4413665c59b164a8d6e2b7','methods':r.testsRun,
      'passed_methods':r.testsRun-len(failures|errors),'failed_methods':len(failures),'error_methods':len(errors),'subcases':r.subcases,
      'skipped':len(r.skipped),'failure_records':len(r.failures),'error_records':len(r.errors),
      'failures':[{'method':method(t),'traceback':tb} for t,tb in r.failures],
      'errors':[{'method':method(t),'traceback':tb} for t,tb in r.errors],
      'observations':OBS,'command':[sys.executable,'-B',str(Path(__file__).resolve())],
      'script_sha256':sha256(Path(__file__).read_bytes()).hexdigest(),'actual_external_calls':0,
      'test_input_origin':'Only independent prior-auditor source/CLI helpers; new annotations/correction cases; no author fixtures.',
      'exit_code':0 if r.wasSuccessful() else 1}
    h.write(ROOT/'parser_first_results.json',result);h.write(ROOT/'parser_command_log.json',h.COMMANDS)
    print(stream.getvalue());print(json.dumps({k:result[k] for k in ['methods','passed_methods','failed_methods','error_methods','subcases','exit_code']}))
    return result['exit_code']
if __name__=='__main__':raise SystemExit(main())
