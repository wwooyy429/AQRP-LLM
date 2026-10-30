"""Independent synthetic native runtime/rejection CLI boundaries; no SDK calls."""
import copy
import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
import unittest
import independent_recovery_support as h
from qresearch.engineering_receipts import ReceiptParseError,backtest_observation,backtest_rejection

INPUTS=[]
SENSITIVE='INDEPENDENT-SYNTHETIC-PRICE-123.456-MUST-NOT-PERSIST'

def native_result(value,*,error=False,dual=True):
    result={'isError':error,'content':[{'type':'text','text':json.dumps(value)}]}
    if dual:result['structuredContent']=copy.deepcopy(value)
    return result

def runtime_envelope(context):
    return {'tool_name':'mcp__quantconnect__read_backtest',
        'arguments':{'projectId':context['admission']['payload']['identity']['project_id'],'backtestId':context['external']},
        'result':native_result({'success':False,'errors':['The backtest ended with a runtime error.',SENSITIVE]},error=True)}

def rejection_envelope(context):
    path=sorted(context['admission']['payload']['deployment_manifest'])[0]
    return {'tool_name':'mcp__quantconnect__create_backtest',
        'arguments':{'projectId':context['admission']['payload']['identity']['project_id'],'backtestName':'independent-new-protocol'},
        'result':native_result({'success':False,'errors':{path:['3:4 '+SENSITIVE]},'warnings':{path:['SYNTHETIC-WARNING-NOT-PERSISTED']}})}

def replace_native(envelope,value):
    envelope['result']=native_result(value,error=envelope['result'].get('isError') is True)
    return envelope

def clone(context,label):
    case=h.OUT/'cases'/label/'source';shutil.copytree(context['case'],case,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    return dict(context,case=case)

def observed_path(context,name,value):
    path=context['case'].parent/(name+'.json');h.dump(path,value);return path

def rec(context):
    return next(item for item in h.registry(context['case']).snapshot()['attempts'] if item['attempt_id']==context['attempt'])

def protocol_path(context):return h.registry(context['case']).store._path('engineering/submission-protocol/'+context['attempt']+'.json')

class NativeBoundaries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.started={};cls.accepted={}
        for version in (1,2):
            context=h.setup_case(version,'native-base-v'+str(version));case=context['case']
            research=h.envelopes(context,context['admission'],'research')
            assert h.okay(h.invoke(case,['research-result','--attempt',context['attempt'],'--tool-file',research['result']],
                'parent-research-v'+str(version)))['status']=='completed'
            lean=h.okay(h.invoke(case,['claim','--stage','lean'],'native-lean-claim-v'+str(version)))['attempt_id']
            admission=h.okay(h.invoke(case,['prepare','--attempt',lean],'native-lean-prepare-v'+str(version)))
            context.update(attempt=lean,admission=admission)
            native=h.envelopes(context,admission,'lean');context['native']=native
            context['external']=json.loads(native['submission'].read_bytes())['result']['backtestId']
            cls.started[version]=context
            accepted=clone(context,'accepted-base-v'+str(version))
            assert h.okay(h.invoke(accepted['case'],['backtest-submission','--attempt',lean,'--tool-file',native['submission']],
                'native-accepted-v'+str(version)))['status']=='pending'
            cls.accepted[version]=accepted

    def case(self,version,variant):
        value={'method':self._testMethodName,'version':version,'variant':variant};INPUTS.append(value);return self.subTest(**value)

    def assert_not_stored(self,context):
        self.assertFalse(any(SENSITIVE.encode() in path.read_bytes() or b'SYNTHETIC-WARNING-NOT-PERSISTED' in path.read_bytes()
            for path in (context['case']/'audit/runtime').rglob('*') if path.is_file()))

    def test_01_runtime_parser_exact_context_and_all_carriers(self):
        variants=('dual_ok','content_ok','transport','missing_isError','no_diagnostics','wrong_id','wrong_project',
                  'carrier_conflict','unknown_payload','diagnostic_type')
        for version,context in self.accepted.items():
            for variant in variants:
                with self.case(version,variant):
                    value=runtime_envelope(context);native=copy.deepcopy(value['result']['structuredContent'])
                    if variant=='content_ok':value['result'].pop('structuredContent')
                    elif variant=='transport':native['errors']=['connection timed out'];replace_native(value,native)
                    elif variant=='missing_isError':value['result'].pop('isError')
                    elif variant=='no_diagnostics':native['errors']=native['errors'][:1];replace_native(value,native)
                    elif variant=='wrong_id':value['arguments']['backtestId']='SYNTHETIC-OTHER-ACCEPTED-ID'
                    elif variant=='wrong_project':value['arguments']['projectId']+=1
                    elif variant=='carrier_conflict':value['result']['content'][0]['text']=json.dumps(dict(native,rows=[SENSITIVE]))
                    elif variant=='unknown_payload':native['rows']=[SENSITIVE];replace_native(value,native)
                    elif variant=='diagnostic_type':native['errors'][1]={'rows':[SENSITIVE]};replace_native(value,native)
                    if variant.endswith('_ok'):
                        result=backtest_observation(context['admission']['payload'],context['admission']['deployment'],context['external'],value,[])
                        self.assertEqual(result['platform']['status'],'runtime_error');self.assertEqual(set(result),{'platform'})
                        self.assertEqual(result['platform']['raw_receipt']['diagnostic_count'],1)
                        self.assertFalse({'completed','progress','orders_count'}&set(result['platform']['raw_receipt']))
                        self.assertNotIn(SENSITIVE,json.dumps(result))
                    else:
                        with self.assertRaises(ReceiptParseError):
                            backtest_observation(context['admission']['payload'],context['admission']['deployment'],context['external'],value,[])

    def test_02_compile_parser_bound_diagnostics_and_ineligible_errors(self):
        variants=('bound_file','input_file','list_ineligible','unknown_file_ineligible','invalid_line_ineligible',
                  'id_present','isError_transport','success_true','carrier_conflict','sensitive_top_rows')
        for version,context in self.started.items():
            for variant in variants:
                with self.case(version,variant):
                    value=rejection_envelope(context);native=copy.deepcopy(value['result']['structuredContent'])
                    path=next(iter(native['errors']))
                    if variant=='input_file':native['errors']={'_engineering_task_input.py':['1:1 '+SENSITIVE]};replace_native(value,native)
                    elif variant=='list_ineligible':native['errors']=['timeout: '+SENSITIVE];replace_native(value,native)
                    elif variant=='unknown_file_ineligible':native['errors']={'outside_frozen.py':['1:1 '+SENSITIVE]};replace_native(value,native)
                    elif variant=='invalid_line_ineligible':native['errors']={path:['0:1 '+SENSITIVE]};replace_native(value,native)
                    elif variant=='id_present':native['backtestId']=None;replace_native(value,native)
                    elif variant=='isError_transport':value['result']['isError']=True
                    elif variant=='success_true':native['success']=True;replace_native(value,native)
                    elif variant=='carrier_conflict':value['result']['content'][0]['text']=json.dumps(dict(native,rows=[SENSITIVE]))
                    elif variant=='sensitive_top_rows':native['rows']=[SENSITIVE];replace_native(value,native)
                    if variant in ('bound_file','input_file') or variant.endswith('_ineligible'):
                        result=backtest_rejection(context['admission']['payload'],context['admission']['deployment'],value)
                        self.assertIs(result['raw_receipt']['settlement_eligible'],not variant.endswith('_ineligible'))
                        self.assertIs(result['accepted'],False);self.assertNotIn('external_id',result)
                        self.assertNotIn(SENSITIVE,json.dumps(result))
                    else:
                        with self.assertRaises(ReceiptParseError):backtest_rejection(context['admission']['payload'],context['admission']['deployment'],value)

    def test_03_compile_cli_started_ambiguous_and_exact_idempotence(self):
        for version,template in self.started.items():
            for state in ('started','ambiguous'):
                with self.case(version,state):
                    context=clone(template,'reject-'+state+'-v'+str(version));case=context['case'];registry=h.registry(case)
                    if state=='ambiguous':registry.ambiguous(context['attempt'],reason='Independent unknown unaccepted submission')
                    expected={'schema_version':1,'protocol':'accepted_identity_before_original_receipt_v1',
                        'identity':context['admission']['payload']['identity'],'deployment':context['admission']['deployment']}
                    self.assertEqual(protocol_path(context).read_bytes(),h.canonical_json(expected))
                    value=rejection_envelope(context);path=observed_path(context,'rejection',value)
                    usage=registry.snapshot()['usage'];events=len(registry.store.read_bytes('registry/events.jsonl').splitlines())
                    failed=h.okay(h.invoke(case,['backtest-rejection','--attempt',context['attempt'],'--tool-file',path],f'reject-{version}-{state}'))
                    self.assertEqual(failed['status'],'failed');self.assertIsNone(failed['external_id']);self.assertFalse(failed['should_execute'])
                    self.assertEqual(registry.snapshot()['usage'],usage)
                    self.assertEqual(len(registry.store.read_bytes('registry/events.jsonl').splitlines()),events+1);self.assert_not_stored(context)
                    before=h.files(case)
                    same=h.okay(h.invoke(case,['backtest-rejection','--attempt',context['attempt'],'--tool-file',path],f'reject-repeat-{version}-{state}'))
                    self.assertEqual(same['status'],'failed');self.assertEqual(h.files(case),before)
                    changed=copy.deepcopy(value);native=changed['result']['structuredContent'];next(iter(native['errors'].values())).append('4:5 a different synthetic diagnostic')
                    replace_native(changed,native);different=observed_path(context,'different-rejection',changed)
                    result=h.invoke(case,['backtest-rejection','--attempt',context['attempt'],'--tool-file',different],f'reject-different-{version}-{state}')
                    self.assertNotEqual(result.returncode,0);self.assertIn(b'Only the identical recorded rejection',result.stderr);self.assertEqual(h.files(case),before)
                    result=h.invoke(case,['backtest-submission','--attempt',context['attempt'],'--tool-file',context['native']['submission']],f'reject-cannot-accept-{version}-{state}')
                    self.assertNotEqual(result.returncode,0);self.assertEqual(h.files(case),before)
                    self.assertEqual(registry.snapshot()['usage'],usage)

    def test_04_compile_cli_protocol_and_acceptance_guards_no_write(self):
        variants=('pending_no_pointer','accepted_pointer_only','missing_protocol','foreign_protocol_attempt',
                  'foreign_protocol_input','missing_admission','tampered_input')
        for version,template in self.started.items():
            for variant in variants:
                with self.case(version,variant):
                    context=clone(template,'guard-'+variant+'-v'+str(version));case=context['case'];registry=h.registry(case)
                    if variant=='pending_no_pointer':registry.pending(context['attempt'],external_id=context['external'])
                    elif variant=='accepted_pointer_only':
                        key='engineering/submissions/'+context['attempt']+'.json';source=h.registry(self.accepted[version]['case']).store
                        registry.store.write_once(key,source.read_bytes(key))
                    elif variant=='missing_protocol':protocol_path(context).unlink()
                    elif variant.startswith('foreign_protocol'):
                        path=protocol_path(context);value=json.loads(path.read_bytes())
                        if variant=='foreign_protocol_attempt':value['identity']['attempt_id']='f'*32
                        else:value['deployment']['input_hash']='f'*64
                        path.write_bytes(h.canonical_json(value))
                    elif variant=='missing_admission':registry.store._path(h.admission_key(context['attempt'])).unlink()
                    else:(case/context['admission']['input_path']).write_bytes(b'INDEPENDENT-TAMPERED-OLD-INPUT\n')
                    if variant=='missing_protocol':
                        before=h.files(case)
                        restored=h.okay(h.invoke(case,['prepare','--attempt',context['attempt']],f'old-no-backfill-v{version}'))
                        self.assertEqual(restored,context['admission']);self.assertFalse(protocol_path(context).exists());self.assertEqual(h.files(case),before)
                    path=observed_path(context,'guard-rejection',rejection_envelope(context));before=h.files(case);usage=registry.snapshot()['usage']
                    result=h.invoke(case,['backtest-rejection','--attempt',context['attempt'],'--tool-file',path],f'guard-{variant}-v{version}')
                    self.assertNotEqual(result.returncode,0);self.assertEqual(h.files(case),before);self.assertEqual(registry.snapshot()['usage'],usage)
                    self.assert_not_stored(context)

    def test_05_runtime_cli_old_input_failure_no_refund_and_no_raw_text(self):
        for version,template in self.accepted.items():
            with self.case(version,'runtime-CLI-old-no-protocol'):
                context=clone(template,'runtime-cli-v'+str(version));case=context['case'];registry=h.registry(case)
                protocol_path(context).unlink();h.drift(context,context['attempt'])
                empty=observed_path(context,'empty-logs',[]);value=runtime_envelope(context)
                for wrong in ('transport','wrong_id'):
                    bad=copy.deepcopy(value)
                    if wrong=='transport':replace_native(bad,{'success':False,'errors':['connection timed out']})
                    else:bad['arguments']['backtestId']='SYNTHETIC-OTHER-ID'
                    path=observed_path(context,'runtime-'+wrong,bad);before=h.files(case)
                    result=h.invoke(case,['backtest-result','--attempt',context['attempt'],'--tool-file',path,'--logs-file',empty],f'runtime-{wrong}-v{version}')
                    self.assertNotEqual(result.returncode,0);self.assertEqual(h.files(case),before)
                native=observed_path(context,'runtime-native',value);usage=registry.snapshot()['usage'];events=len(registry.store.read_bytes('registry/events.jsonl').splitlines())
                result=h.okay(h.invoke(case,['backtest-result','--attempt',context['attempt'],'--tool-file',native,'--logs-file',empty],f'runtime-failed-v{version}'))
                self.assertEqual(result['status'],'failed');self.assertEqual(result['external_id'],context['external'])
                self.assertEqual(registry.snapshot()['usage'],usage);self.assertEqual(len(registry.store.read_bytes('registry/events.jsonl').splitlines()),events+1)
                self.assert_not_stored(context);self.assertFalse(protocol_path(context).exists())
                before=h.files(case)
                repeated=h.okay(h.invoke(case,['backtest-result','--attempt',context['attempt'],'--tool-file',native,'--logs-file',empty],f'runtime-repeat-v{version}'))
                self.assertEqual(repeated['status'],'failed');self.assertEqual(h.files(case),before)

    def test_06_successful_lean_and_parent_resolution_remain_compatible(self):
        for version,template in self.accepted.items():
            with self.case(version,'successful-LEAN-old-no-protocol'):
                context=clone(template,'success-cli-v'+str(version));case=context['case'];registry=h.registry(case)
                protocol_path(context).unlink();usage=registry.snapshot()['usage'];h.drift(context,context['attempt'])
                result=h.okay(h.invoke(case,['backtest-result','--attempt',context['attempt'],'--tool-file',context['native']['result'],
                    '--logs-file',context['native']['logs']],f'success-lean-v{version}'))
                self.assertEqual(result['status'],'completed');self.assertEqual(registry.snapshot()['usage'],usage)
                saved=registry.read_result(context['attempt']);self.assertEqual(saved['cloud_report']['resolution'],context['admission']['payload']['research_resolution'])
                self.assertFalse(saved['financial_evidence']);self.assertFalse(protocol_path(context).exists())

class Result(unittest.TextTestResult):
    def __init__(self,*args,**kwargs):super().__init__(*args,**kwargs);self.subcases=0;self.first_failure=None
    def addSubTest(self,test,subtest,err):
        self.subcases+=1
        if err and self.first_failure is None:self.first_failure={'method':str(test),'subcase':str(subtest),'traceback':self._exc_info_to_string(err,test)}
        super().addSubTest(test,subtest,err)
    def addError(self,test,err):
        if self.first_failure is None:self.first_failure={'method':str(test),'traceback':self._exc_info_to_string(err,test)}
        super().addError(test,err)

stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2,resultclass=Result).run(unittest.defaultTestLoader.loadTestsFromTestCase(NativeBoundaries))
after={path:hashlib.sha256((h.ROOT/path).read_bytes()).hexdigest() for path in h.CHECK_FILES}
summary={'commit':'66ff72ffaaff8c91c008898e6527c91131176c2a','methods':result.testsRun,'subcases':result.subcases,
    'failure_records':len(result.failures),'error_records':len(result.errors),'skipped':len(result.skipped),'first_failure':result.first_failure,
    'success':result.wasSuccessful(),'inputs':INPUTS,'stats':h.STATS,'source_hashes_before':h.BEFORE,'source_hashes_after':after,
    'source_and_authority_unchanged':h.BEFORE==after,'actual_worker_executions':0,
    'scope':'Actual copied production CLI and Filesystem Registry; all native envelopes/diagnostics are self-authored synthetic. No real SDK/Research/LEAN/market execution or authoritative ledger settlement.'}
(h.OUT/'results.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
(h.OUT/'command_log.json').write_text(json.dumps(h.LOG,ensure_ascii=False,indent=2),encoding='utf-8')
(h.OUT/'unittest.txt').write_text(stream.getvalue(),encoding='utf-8')
print(stream.getvalue());print(json.dumps(summary,ensure_ascii=False,indent=2))
sys.exit(0 if result.wasSuccessful() and h.BEFORE==after else 1)
