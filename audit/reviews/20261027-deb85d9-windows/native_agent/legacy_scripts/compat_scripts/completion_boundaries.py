"""Independent live-settlement boundaries for WR18 shared loader change.

Uses only the reviewer's byte-identical synthetic helper, never developer fixtures.
No worker, SDK, Research, LEAN or network execution occurs.
"""
import copy
import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
import unittest
import independent_recovery_support as h
from qresearch.engineering_receipts import research_observation, backtest_submission, backtest_observation
from qresearch.engineering_tasks import EngineeringTaskError

INPUTS=[]

def bridge(case, admission):
    plan=h.EngineeringTaskPlan.from_dict(admission['payload']['plan'],discovered_project_ids=(admission['payload']['identity']['project_id'],))
    return h.EngineeringTaskBridge(h.registry(case),plan)

def state_paths(item):
    store=item['bridge'].store;attempt=item['attempt']
    summary_path=store._path('engineering/submissions/'+attempt+'.json')
    summary=json.loads(summary_path.read_bytes())
    original_path=store._path(summary['receipt_ref']['key'])
    return summary_path,original_path

def replace_original(item, change):
    summary_path,original_path=state_paths(item)
    summary_bytes=summary_path.read_bytes();original_bytes=original_path.read_bytes()
    summary=json.loads(summary_bytes);original=json.loads(original_bytes);change(original)
    new_sha=h.content_hash(original)
    new_key='engineering/evidence/'+item['attempt']+'/submission/'+new_sha+'.json'
    new_path=item['bridge'].store._path(new_key);new_path.parent.mkdir(parents=True,exist_ok=True)
    new_path.write_bytes(h.canonical_json(original));summary['receipt_ref']={'key':new_key,'sha256':new_sha}
    summary_path.write_bytes(h.canonical_json(summary))
    return summary_path,summary_bytes,new_path

class CompletionBoundaries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.items=[]
        for version in (1,2):
            context=h.setup_case(version,'loader-v'+str(version));case=context['case'];admission=context['admission']
            envelopes=h.envelopes(context,admission,'research')
            observed=research_observation(admission['payload'],admission['deployment'],json.loads(envelopes['result'].read_bytes()))
            b=bridge(case,admission);b.record_submission(context['attempt'],observed['submission'])
            # A separate filesystem branch retains the valid pending Research
            # submission while the original chain proceeds to legal LEAN claim.
            branch=h.OUT/'cases'/('loader-pending-research-v'+str(version))/'source'
            shutil.copytree(case,branch,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
            cls.items.append({'version':version,'stage':'research','case':branch,'attempt':context['attempt'],
                'admission':admission,'bridge':bridge(branch,admission),'observed':observed['completion']})
            assert h.okay(h.invoke(case,['research-result','--attempt',context['attempt'],'--tool-file',envelopes['result']],
                'loader-research-complete-v'+str(version)))['status']=='completed'
            lean=h.okay(h.invoke(case,['claim','--stage','lean'],'loader-lean-claim-v'+str(version)))['attempt_id']
            admitted=h.okay(h.invoke(case,['prepare','--attempt',lean],'loader-lean-prepare-v'+str(version)))
            native=h.envelopes(context,admitted,'lean')
            assert h.okay(h.invoke(case,['backtest-submission','--attempt',lean,'--tool-file',native['submission']],
                'loader-lean-submission-v'+str(version)))['status']=='pending'
            sub=backtest_submission(admitted['payload'],admitted['deployment'],json.loads(native['submission'].read_bytes()))
            terminal=backtest_observation(admitted['payload'],admitted['deployment'],sub['external_id'],
                json.loads(native['result'].read_bytes()),json.loads(native['logs'].read_bytes()))
            cls.items.append({'version':version,'stage':'lean','case':case,'attempt':lean,'admission':admitted,
                'bridge':bridge(case,admitted),'observed':terminal})
        for item in cls.items:
            context={'case':item['case']}
            h.drift(context,item['attempt'])
            # Deliberately malformed current files must not participate in the
            # original immutable attempt's completion loader.
            (item['case']/'audit/engineering_current.json').write_bytes(b'{bad current')
            (item['case']/'config/source_catalog.json').write_bytes(b'{bad catalog')

    def case(self,item,mutation):
        value={'method':self._testMethodName,'version':item['version'],'stage':item['stage'],'mutation':mutation}
        INPUTS.append(value)
        return self.subTest(**value)

    def test_01_loader_rejects_before_completion_read_and_no_write(self):
        for item in self.items:
            for mutation in ('missing_original','self_consistent_empty_raw','self_consistent_unaccepted'):
                with self.case(item,mutation):
                    calls=[];summary_path,original_path=state_paths(item)
                    original_bytes=original_path.read_bytes();undo=None
                    if mutation=='missing_original':original_path.unlink()
                    elif mutation=='self_consistent_empty_raw':undo=replace_original(item,lambda value:value.__setitem__('raw_receipt',{}))
                    else:undo=replace_original(item,lambda value:value.__setitem__('accepted',False))
                    before=h.files(item['case']);usage=item['bridge'].registry.snapshot()['usage']
                    try:
                        with self.assertRaises(EngineeringTaskError):
                            item['bridge'].consume_completion(item['attempt'],completion_source=lambda payload:(calls.append(payload),item['observed'])[1])
                        self.assertEqual(calls,[])
                        self.assertEqual(h.files(item['case']),before)
                        self.assertEqual(item['bridge'].registry.snapshot()['usage'],usage)
                    finally:
                        if mutation=='missing_original':original_path.write_bytes(original_bytes)
                        else:
                            undo[0].write_bytes(undo[1]);undo[2].unlink()

    def test_02_contract_rejects_input_raw_and_rows_without_persistence(self):
        for item in self.items:
            for mutation in ('input_hash','empty_terminal_raw','hidden_rows'):
                with self.case(item,mutation):
                    observed=copy.deepcopy(item['observed'])
                    if mutation=='input_hash':observed['platform']['deployment']['input_hash']='f'*64
                    elif mutation=='empty_terminal_raw':observed['platform']['raw_receipt']={}
                    else:observed['rows']=['INDEPENDENT-SYNTHETIC-ROWS-MUST-NOT-PERSIST']
                    before=h.files(item['case']);usage=item['bridge'].registry.snapshot()['usage'];calls=[]
                    with self.assertRaises(EngineeringTaskError):
                        item['bridge'].consume_completion(item['attempt'],completion_source=lambda payload:(calls.append(payload),observed)[1])
                    self.assertEqual(len(calls),1)
                    self.assertEqual(h.files(item['case']),before)
                    self.assertEqual(item['bridge'].registry.snapshot()['usage'],usage)

    def test_03_legacy_submission_status_success_and_completed_idempotence(self):
        for item in self.items:
            # Optional synchronous submission status is independent of eventual
            # completion. Both missing and completed are declared supported.
            mutation='submission_status_absent' if item['stage']=='research' else 'submission_status_completed'
            with self.case(item,mutation):
                def change(value):
                    if item['stage']=='research':value.pop('status',None)
                    else:value['status']='completed'
                replace_original(item,change)
                usage=item['bridge'].registry.snapshot()['usage']
                result=item['bridge'].consume_completion(item['attempt'],completion_source=lambda payload:item['observed'])
                self.assertEqual(result.status,'completed');self.assertFalse(result.should_execute)
                self.assertEqual(item['bridge'].registry.snapshot()['usage'],usage)
                summary_path,original_path=state_paths(item);summary_path.unlink();original_path.unlink()
                admission=item['bridge'].store._path(h.admission_key(item['attempt']));admission.unlink()
                self.assertFalse((item['case']/item['admission']['input_path']).exists())
                before=h.files(item['case']);calls=[]
                repeat=item['bridge'].consume_completion(item['attempt'],completion_source=lambda payload:calls.append(payload))
                self.assertEqual(repeat.status,'completed');self.assertFalse(repeat.should_execute)
                self.assertEqual(calls,[]);self.assertEqual(h.files(item['case']),before)
                self.assertEqual(item['bridge'].registry.snapshot()['usage'],usage)

class Result(unittest.TextTestResult):
    def __init__(self,*args,**kwargs):super().__init__(*args,**kwargs);self.subcases=0;self.first_failure=None
    def addSubTest(self,test,subtest,err):
        self.subcases+=1
        if err and self.first_failure is None:self.first_failure={'method':str(test),'subcase':str(subtest),'traceback':self._exc_info_to_string(err,test)}
        super().addSubTest(test,subtest,err)
    def addError(self,test,err):
        if self.first_failure is None:self.first_failure={'method':str(test),'traceback':self._exc_info_to_string(err,test)}
        super().addError(test,err)

stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2,resultclass=Result).run(unittest.defaultTestLoader.loadTestsFromTestCase(CompletionBoundaries))
after={path:hashlib.sha256((h.ROOT/path).read_bytes()).hexdigest() for path in h.CHECK_FILES}
summary={'commit':'81fbe5294055423e88ee5aeae48ca6223e7971da','methods':result.testsRun,'subcases':result.subcases,
    'failure_records':len(result.failures),'error_records':len(result.errors),'skipped':len(result.skipped),'first_failure':result.first_failure,
    'success':result.wasSuccessful(),'inputs':INPUTS,'stats':h.STATS,'source_hashes_before':h.BEFORE,'source_hashes_after':after,
    'source_and_authority_unchanged':h.BEFORE==after,'actual_worker_executions':0,'limits':'Synthetic bounded metadata via actual _finish; no SDK or platform execution.'}
(h.OUT/'result.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
(h.OUT/'command_log.json').write_text(json.dumps(h.LOG,ensure_ascii=False,indent=2),encoding='utf-8')
(h.OUT/'unittest.txt').write_text(stream.getvalue(),encoding='utf-8')
print(stream.getvalue());print(json.dumps(summary,ensure_ascii=False,indent=2))
sys.exit(0 if result.wasSuccessful() and h.BEFORE==after else 1)
