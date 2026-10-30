"""Independent WR-14 known answers and worker/receipt/ledger branch tests."""
import base64
from copy import copy,deepcopy
import hashlib
import io
import json
from pathlib import Path
import platform
import sys
import unittest
import independent_fractional_harness as h
from qresearch.engineering_receipts import _annotations,_text_node,_native,_research_stdout,ReceiptParseError
from qresearch.engineering_receipts import backtest_submission,backtest_observation
from qresearch.engineering_data import _finish

OUT=h.OUT;ROOT=h.ROOT
INPUTS=[]
FILES=['cloud/qresearch/engineering_receipts.py','cloud/qresearch/engineering_data.py','cloud/qresearch/engineering_tasks.py',
    'cloud/qresearch/collection_execution.py','cloud/qresearch/collection_tasks.py','cloud/qresearch/quantconnect.py','cloud/qresearch/registry.py']
BEFORE={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in FILES}
GOOD={'audience':['assistant','user','assistant'],'priority':0.75,'lastModified':'2000-02-29T12:34:56.7-03:30'}
def enc(wrapper):return base64.b64encode(h.canonical_json(wrapper)).decode()
def mark(wrapper):return 'AQRP_ENGINEERING_JSON '+enc(wrapper)
def clock_forms():
    # Explicit decimal values, not a reimplementation of the parser grammar.
    yield 'whole',''
    for separator in ('.',','):
        for digits in ('7','70','700','7000','70000','700000'):
            yield separator+str(len(digits)),separator+digits
def node(text,annotation):return {'type':'text','text':text,'annotations':deepcopy(annotation)}
def shaped(text,annotation,shape):
    if shape=='root':return node(text,annotation)
    if shape=='deep_json':
        result={'outputs':[node(text,annotation)],'status':'ok'}
        for _ in range(3):result=node(json.dumps(result),GOOD)
        return {'results':{'cells':[{'output':result}]},'status':'completed'}
    if shape=='outer':return {'outputs':[{'output_type':'stream','name':'stdout','text':text}],'status':'ok'}
    raise AssertionError(shape)
def fork(base):
    # One real pure-Python synthetic worker is executed for each family. Each
    # observation then gets a fresh metadata-ledger clone at the same admitted
    # attempt. These branches never rerun a source or share mutated ledgers.
    result=copy(base);result.local=h.MemoryArtifactStore();result.local._data=deepcopy(base.local._data)
    result.reg=h.Registry(result.local,h.BUDGET);result.bridge=type(base.bridge)(result.reg,base.bridge.plan)
    result.payload=deepcopy(base.payload);result.deploy=deepcopy(base.deploy);return result

class IndependentFractionBoundaries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bases={family:h.Harness(family) for family in ('collection','old_research')}
    def case(self,**params):INPUTS.append({'method':self._testMethodName,**params});return self.subTest(**params)
    def test_fixed_primary_schema_and_reviewer_helper_identity(self):
        schema_file=OUT/'official_mcp_schema_2025-11-25.json'
        schema=json.loads(schema_file.read_text(encoding='utf-8'))['$defs']
        checks={'schema_sha':hashlib.sha256(schema_file.read_bytes()).hexdigest()=='268a5f82ba70fd7e4b6dc4aa1e64f116f74b4d0edcb69dc046829c79dd4e97e7',
            'reviewer_helper_sha':hashlib.sha256((OUT/'independent_fractional_harness.py').read_bytes()).hexdigest()=='d6f469e02b6e8129af4ecdaf679e7d877dee5959edc13f3f68a991777a19cf25',
            'annotation_fields':set(schema['Annotations']['properties'])=={'audience','priority','lastModified'},
            'roles':set(schema['Role']['enum'])=={'user','assistant'}}
        for name,okay in checks.items():
            with self.case(identity_check=name):self.assertTrue(okay)
    def test_zero_to_six_digits_point_comma_offset_case_and_unchanged_hint(self):
        for form,fraction in clock_forms():
            for separator in ('T','t',' '):
                for suffix in ('','Z','z','+00:00','-00:00','+05:45','-03:30','+23:59','-23:59'):
                    stamp='2000-02-29'+separator+'23:59:59'+fraction+suffix
                    with self.case(form=form,clock=stamp):
                        value={'audience':[],'priority':0,'lastModified':stamp};before=deepcopy(value)
                        _annotations(value);self.assertEqual(value,before)
                        observation=node('AQRP_ENGINEERING_JSON known-answer',value);saved=deepcopy(observation)
                        self.assertEqual(_text_node(observation),'AQRP_ENGINEERING_JSON known-answer')
                        self.assertEqual(observation,saved)
    def test_calendar_known_answers_and_long_fraction_without_conversion(self):
        valid_dates=['0001-01-01','1600-02-29','1900-02-28','2000-02-29','2024-02-29','2100-02-28','9999-12-31']
        for date in valid_dates:
            for digits in ('', '1', '01234', '9'*9, '0'*17, '3141592653'*41, '9'*4096):
                stamp=date+'T00:00:00'+('.'+digits if digits else '')+'+05:45'
                with self.case(valid_date=date,fraction_length=len(digits)):
                    value={'lastModified':stamp};before=json.dumps(value);_annotations(value)
                    self.assertEqual(json.dumps(value),before)
        for stamp in ('0001-01-01','1600-02-29','2000-02-29','9999-12-31'):
            with self.case(date_only=stamp):_annotations({'lastModified':stamp})
    def test_invalid_calendar_and_time_offset_grammar_still_rejected(self):
        dates=['0000-01-01','1500-02-29','1700-02-29','1800-02-29','1900-02-29','2000-02-30','2100-02-29',
            '2024-04-31','2024-00-01','2024-01-00','2024-13-01','9999-02-29','10000-01-01']
        for date in dates:
            for fraction in ('','.5',',12345','.'+'1'*4096):
                with self.case(invalid_date=date,fraction_length=len(fraction)):
                    with self.assertRaises(ReceiptParseError):_annotations({'lastModified':date+'T00:00:00'+fraction+'Z'})
        tails=['T24:00:00.5Z','T23:60:00.5Z','T23:59:60.5Z','T12:34:56.5+24:00','T12:34:56.5-24:00',
            'T12:34:56.5+00:60','T12:34:56.5+05:60','T12:34:56.5+5:30','T12:34:56.5+0530',
            'T12:34:56.5+00:00:01','T12:34:56.Z','T12:34:56,Z','T12:34:56.-1Z','T12:34:56.1e3Z',
            'T12:34:56.１２Z','T12:34:56.١٢Z','T12:34:56.5ZZ','T12:34:56.5Z\n','T12:34:56.5Z ',
            'T12:34','Z','T12:34:56.5+00','T12:34:56.5+00:00junk']
        for tail in tails:
            with self.case(invalid_or_unregistered_tail=tail):
                with self.assertRaises(ReceiptParseError):_annotations({'lastModified':'2024-02-29'+tail})
    def test_wr13_unknown_annotations_priority_and_text_types_unchanged(self):
        values=[{'rows':[h.SECRET]},{'errors':[h.SECRET]},{'outputs':[h.SECRET]},{'_meta':{'rows':[h.SECRET]}},
            {'audience':['system']},{'audience':[True]},{'audience':'assistant'},
            {'priority':True},{'priority':False},{'priority':'0.5'},{'priority':float('nan')},{'priority':float('inf')},
            {'priority':float('-inf')},{'priority':-0.001},{'priority':1.001},{'priority':10**500},
            {'lastModified':None},{'lastModified':[]},{'lastModified':{}},[],True]
        for index,value in enumerate(values):
            with self.case(bad_annotation=index,value=str(value)):
                with self.assertRaises(ReceiptParseError):_annotations(value)
        for value in (None,False,True,0,1.5,[],{}, {'outputs':['AQRP_ENGINEERING_JSON known-answer']}):
            with self.case(nonstring_text=str(value)):
                with self.assertRaises(ReceiptParseError):_text_node(node(value,GOOD))
    def test_annotated_json_recursion_keeps_width_and_side_load_checks(self):
        for fraction in ('.7',',70','.7000',',70000','.'+'1'*4096):
            for annotation in ({'lastModified':'2000-02-29T23:59:59'+fraction+'Z'}, {'rows':[h.SECRET]}, {'errors':[h.SECRET]}):
                with self.case(fraction_length=len(fraction),annotation_keys=list(annotation)):
                    native=shaped('AQRP_ENGINEERING_JSON known-answer',annotation,'deep_json')
                    if set(annotation)=={'lastModified'}:
                        self.assertEqual(_research_stdout(_native(h.carriers(native,outer_annotation=GOOD))),'known-answer')
                    else:
                        with self.assertRaises(ReceiptParseError):_research_stdout(_native(h.carriers(native,outer_annotation=GOOD)))
    def test_new_old_worker_reports_complete_all_microsecond_widths(self):
        for family,base in self.bases.items():
            fetches=base.source.calls if family=='collection' else base.qb.history_calls
            for form,fraction in clock_forms():
                for suffix in ('Z','+05:45',''):
                    for shape in ('outer','root','deep_json'):
                        stamp='2000-02-29T12:34:56'+fraction+suffix
                        with self.case(family=family,form=form,suffix=suffix,shape=shape):
                            branch=fork(base);usage=deepcopy(branch.reg.snapshot()['usage'])
                            annotation={'lastModified':stamp,'audience':['assistant'],'priority':0.5}
                            native=shaped(mark(branch.wrapper),annotation,shape);before=h.canonical_json(native)
                            parsed=branch.parse(native,outer_annotation=annotation if shape=='outer' else {})
                            final=branch.finish(parsed);self.assertEqual(final.status,'completed')
                            self.assertEqual(h.canonical_json(native),before)
                            self.assertEqual(branch.reg.snapshot()['usage'],usage)
                            branch.assert_no_rows(self);self.assertFalse(branch.bridge.read_result(final)['financial_evidence'])
                            self.assertFalse(branch.bridge.claim('research').should_execute)
                            self.assertEqual(base.source.calls if family=='collection' else base.qb.history_calls,fetches)
            self.assertEqual(base.bridge._record(base.attempt)['status'],'started')
    def test_new_old_rejects_invalid_side_loads_clocks_without_ledger_mutation(self):
        bad=[{'lastModified':'1900-02-29T12:34:56.5Z'}, {'lastModified':'2000-02-29T12:34:56.5+24:00'},
            {'lastModified':'2000-02-29T12:34:56.Z'}, {'lastModified':'2000-02-29T12:34:56.5Z','rows':[h.SECRET]},
            {'errors':[h.SECRET]},{'priority':True}]
        for family,base in self.bases.items():
            for shape in ('outer','root','deep_json'):
                for index,annotation in enumerate(bad):
                    with self.case(family=family,shape=shape,invalid_case=index):
                        branch=fork(base);before=deepcopy(branch.local._data);usage=deepcopy(branch.reg.snapshot()['usage'])
                        native=shaped(mark(branch.wrapper),annotation,shape)
                        with self.assertRaises(ReceiptParseError):branch.parse(native,outer_annotation=annotation if shape=='outer' else {})
                        self.assertEqual(branch.local._data,before);self.assertEqual(branch.reg.snapshot()['usage'],usage)
                        self.assertEqual(branch.bridge._record(branch.attempt)['status'],'started');branch.assert_no_rows(self)
    def test_rejection_then_corrected_same_attempt_no_refetch_or_recharge(self):
        for family,base in self.bases.items():
            with self.case(family=family,recovery='same-prepaid-attempt'):
                branch=fork(base);usage=deepcopy(branch.reg.snapshot()['usage']);before=deepcopy(branch.local._data)
                invalid=shaped(mark(branch.wrapper),{'lastModified':'2000-02-29T12:34:56.5+24:00'},'deep_json')
                with self.assertRaises(ReceiptParseError):branch.parse(invalid,outer_annotation={})
                self.assertEqual(branch.local._data,before)
                valid=shaped(mark(branch.wrapper),{'lastModified':'2000-02-29T12:34:56.5+05:45'},'deep_json')
                self.assertEqual(branch.finish(branch.parse(valid,outer_annotation={})).status,'completed')
                self.assertEqual(branch.reg.snapshot()['usage'],usage);branch.assert_no_rows(self)
    def test_old_lean_three_stage_clock_hints_remain_compatible(self):
        base=self.bases['old_research'];branch=fork(base)
        branch.finish(branch.parse(shaped(mark(branch.wrapper),GOOD,'root'),outer_annotation={}))
        attempt=branch.bridge.claim('lean');payload=branch.bridge.payload(attempt)
        deployment={'source_manifest_hash':h.SOURCE_HASH,'deployment_hash':h.content_hash(h.MANIFEST),'input_hash':'6'*64}
        store=h.MemoryArtifactStore();wrapper=_finish(store,payload,{'raw_data_received':True,'no_orders':True},
            {'data_event_count':6,'slice_count':3,'orders_submitted':0,'runtime_error_count':0},branch.wrapper['cloud_report']['resolution'])
        external='independent-wr14-offline-lean'
        sub=h.tool('mcp__quantconnect__create_backtest',payload,{'success':True,'errors':[],'backtestId':external})
        read=h.tool('mcp__quantconnect__read_backtest',payload,{'success':True,'errors':[],
            'backtest':{'backtestId':external,'projectId':99852,'completed':True,'progress':1,'status':'Completed.',
                'hasInitializeError':False,'statistics':{'Total Orders':'0'}}},external=external)
        text=enc(wrapper);parts=[text[i:i+500] for i in range(0,len(text),500)]
        lines=['AQRP_ENGINEERING '+payload['identity']['attempt_id']+' '+str(i)+'/'+str(len(parts))+' '+s for i,s in enumerate(parts)]
        logs=[h.tool('mcp__quantconnect__search_backtest_logs',payload,{'success':True,'errors':[],'logs':lines,'totalPages':1},external=external)]
        for stage,observation,stamp in [('submission',sub,'2000-02-29T00:00:00.7Z'),('read',read,'2000-02-29T00:00:00,70+05:45'),('logs',logs[0],'2000-02-29T00:00:00.70000-03:30')]:
            with self.case(lean_stage=stage,lastModified=stamp):observation['result']['content'][0]['annotations']={'lastModified':stamp}
        with self.case(lean_complete='all-three-stage-hints'):
            ack=backtest_submission(payload,deployment,sub);branch.bridge.record_submission(attempt,ack)
            completed=backtest_observation(payload,deployment,external,read,logs)
            self.assertEqual(branch.bridge.consume_completion(attempt,completion_source=lambda _:completed).status,'completed')
            branch.assert_no_rows(self)

class AuditResult(unittest.TextTestResult):
    def __init__(self,*a,**kw):super().__init__(*a,**kw);self.subcases=0;self.first_failure=None
    def addSubTest(self,test,subtest,err):
        self.subcases+=1
        if err and self.first_failure is None:self.first_failure={'method':str(test),'subtest':str(subtest),'traceback':self._exc_info_to_string(err,test)}
        super().addSubTest(test,subtest,err)
    def addError(self,test,err):
        if self.first_failure is None:self.first_failure={'method':str(test),'traceback':self._exc_info_to_string(err,test)}
        super().addError(test,err)
    def addFailure(self,test,err):
        if self.first_failure is None:self.first_failure={'method':str(test),'traceback':self._exc_info_to_string(err,test)}
        super().addFailure(test,err)

stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2,resultclass=AuditResult).run(unittest.defaultTestLoader.loadTestsFromTestCase(IndependentFractionBoundaries))
raw=stream.getvalue();(OUT/'first_run_unittest.txt').write_text(raw,encoding='utf-8')
after={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in FILES}
summary={'commit':'4a94430144cd3d9e4b5469bd2b6e4a48d80d5fc7','command_argv':sys.argv,'python':sys.version,
    'platform':platform.platform(),'numpy':h.np.__version__,'pandas':h.pd.__version__,
    'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'source_raw_sha256_before':BEFORE,
    'source_raw_sha256_after':after,'source_unchanged':BEFORE==after,
    'methods':result.testsRun,'subcases':result.subcases,'failure_records':len(result.failures),'error_records':len(result.errors),
    'skipped':len(result.skipped),'success':result.wasSuccessful(),'first_failure':result.first_failure,'inputs':INPUTS,
    'worker_execution_design':'One true pure-Python synthetic worker run for collection and one for old Research; independent metadata-ledger clones per observation branch, no source reruns. FakeQB weekday calendar and constant numbers are invented.',
    'actual_worker_runs':2,'scope':'registered grammar/subset only; long numeric fractions are checked lexically without requiring other ISO variants',
    'actions':{'network':0,'real_SDK':0,'Research':0,'LEAN':0,'market':0,'models':0,'deployment':0,'real_budget_changes':0,'candidate_source_edits':0}}
(OUT/'first_run_summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf-8')
print(raw);print(json.dumps({k:v for k,v in summary.items() if k not in {'inputs','first_failure','source_raw_sha256_after'}},ensure_ascii=False))
sys.exit(0 if result.wasSuccessful() and summary['source_unchanged'] else 1)
