"""Independent Research native-error parser and original-attempt replay tests."""
import copy,hashlib,importlib.util,io,json,shutil,sys,unittest
from unittest.mock import patch
import independent_recovery_support as h
from qresearch.engineering_receipts import ReceiptParseError,research_cell_source,research_observation,research_dispatch_binding

INPUTS=[];ACTUAL='f5d05f5b964b4a1d924e4b70cd207386';SECRET='INDEPENDENT-SYNTHETIC-ERROR-ROWS-938.125'
ARCHIVE=h.ROOT/'audit/tool_observations'/ (ACTUAL+'-research.json')
ARCHIVE_SHA='14ae4a18636496737862a1ce314d90ae7fcf1abaf35f8a0f27145e0e839af8f3'
ACTUAL_META={};TRAJECTORIES=[]

def node():return {'output_type':'error','ename':'IndependentFailure','evalue':SECRET,'traceback':['first\nsecond','last']}
def envelope(context,shape='dual'):
    error=node();native=error
    if shape=='list':native=[error]
    if shape=='wrapper':native={'status':'error','outputs':[error],'execution_count':2,'cell_index':0,'metadata':{}}
    result={'isError':False,'content':[{'type':'text','text':json.dumps(native)}]}
    if shape in ('dual','dual_structured','annotated','formatted'):
        result['content'].append(copy.deepcopy(result['content'][0]))
    if shape=='structured':result={'structuredContent':error,'isError':False}
    if shape=='dual_structured':result['structuredContent']=copy.deepcopy(error)
    if shape=='annotated':
        for block in result['content']:block['annotations']={'audience':['assistant'],'priority':0.5,'lastModified':'2026-10-27T01:02:03.5Z'}
    if shape=='formatted':result['content'][1]['text']=json.dumps(dict(reversed(list(error.items()))),indent=4)
    return {'tool_name':'mcp__quantconnect__jupyter_execute_cell','arguments':{'projectId':context['admission']['payload']['identity']['project_id'],'index':0},'result':result}

def observe(context,value,binding=None):return research_observation(context['admission']['payload'],context['admission']['deployment'],value,
    dispatch_binding=context['binding'] if binding is None else binding)
def clone_from(source,label):
    destination=h.OUT/'cases'/label/'source';shutil.copytree(source,destination,ignore=shutil.ignore_patterns('__pycache__','*.pyc'));return destination
def store_for(case):return h.registry(case).store
def event_count(case):return len(store_for(case).read_bytes('registry/events.jsonl').splitlines())
def record(case):return next(row for row in h.registry(case).snapshot()['attempts'] if row['attempt_id']==ACTUAL)
def toolfile(case,name,value):
    path=case.parent/(name+'.json');h.dump(path,value);return path
def load_stage(case):
    for name in ('research','stages','collection_task_cli','stage2_collection'):sys.modules.pop(name,None)
    sys.path.insert(0,str(case/'tools'));spec=importlib.util.spec_from_file_location('independent_stage2_'+case.parent.name,case/'tools/stage2.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
def bridge(case):
    reg=h.registry(case);admission=json.loads(reg.store.read_bytes(h.admission_key(ACTUAL)));p=admission['payload']
    plan=h.EngineeringTaskPlan.from_dict(p['plan'],discovered_project_ids=(p['identity']['project_id'],))
    return h.EngineeringTaskBridge(reg,plan)

class ResearchFailureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contexts={}
        for version in (1,2):
            context=h.setup_case(version,'new-research-v'+str(version));case=context['case'];admission=context['admission']
            source=h.okay(h.invoke(case,['research-cell','--attempt',context['attempt']],'source-v'+str(version)))['source']
            read={'tool_name':'mcp__quantconnect__jupyter_read_cell','arguments':{'projectId':admission['payload']['identity']['project_id'],'index':0},
                'result':{'cellType':'code','source':source.splitlines(keepends=True)}}
            path=toolfile(case,'synthetic-read',read)
            pinned=h.okay(h.invoke(case,['research-dispatch','--attempt',context['attempt'],'--tool-file',path],'pin-v'+str(version)))
            assert pinned['should_execute'] is True
            context['binding']=pinned['binding'];cls.contexts[version]=context
        # Actual metadata-only runtime tree, with future ack/completion artifacts
        # removed, reconstructs the independently readable pre-settlement15 state.
        case,_=h.fresh('actual-prefix15');runtime=case/'audit/runtime';shutil.copytree(h.ROOT/'audit/runtime',runtime)
        journal=runtime/'registry/events.jsonl';rows=journal.read_bytes().splitlines(keepends=True);assert len(rows)==17
        journal.write_bytes(b''.join(rows[:15]))
        path=runtime/('engineering/submissions/'+ACTUAL+'.json');path.unlink()
        shutil.rmtree(runtime/('engineering/evidence/'+ACTUAL))
        (case/'audit/task_inputs').mkdir(exist_ok=True);shutil.copy2(h.ROOT/('audit/task_inputs/'+ACTUAL+'.py'),case/('audit/task_inputs/'+ACTUAL+'.py'))
        assert event_count(case)==15 and record(case)['status']=='started'
        cls.actual15=case

    def case(self,**params):
        value={'method':self._testMethodName,**params};INPUTS.append(value);return self.subTest(**value)

    def test_01_supported_carriers_full_original_hash_and_projection(self):
        for version,context in self.contexts.items():
            for shape in ('single','structured','list','wrapper','dual','dual_structured','annotated','formatted'):
                with self.case(version=version,shape=shape):
                    native=envelope(context,shape);result=observe(context,native);raw=result['submission']['raw_receipt']
                    self.assertEqual(raw['response_sha256'],h.content_hash(native['result']));self.assertEqual(raw['traceback_line_count'],2)
                    self.assertEqual(raw['error_output_count'],1);self.assertEqual(result['completion']['platform']['status'],'runtime_error')
                    self.assertEqual(set(result['completion']),{'platform'});self.assertNotIn(SECRET,json.dumps(result))
                    if shape in ('dual','dual_structured','annotated','formatted'):
                        self.assertEqual(raw['native_error_representation_count'],3 if shape=='dual_structured' else 2)
                        projection=copy.deepcopy(native['result']);projection['content']=projection['content'][:1]
                        self.assertNotEqual(raw['response_sha256'],h.content_hash(projection))

    def test_02_reject_carrier_annotations_transport_and_error_grammar(self):
        variants=('different_text','three_texts','json_two_errors','json_wrapped_twins','structured_conflict','annotation_rows',
            'annotations_differ','annotation_bool_priority','outer_meta','unknown_outer','printed_error','transport',
            'two_outputs','unknown_node','traceback_empty','traceback_blank','traceback_nonstring','traceback_too_many',
            'traceback_long_line','duplicate_JSON_key','isError_integer')
        for version,context in self.contexts.items():
            for variant in variants:
                with self.case(version=version,variant=variant):
                    value=envelope(context);error=node()
                    if variant=='different_text':error['evalue']='different';value['result']['content'][1]['text']=json.dumps(error)
                    elif variant=='three_texts':value['result']['content'].append(copy.deepcopy(value['result']['content'][0]))
                    elif variant=='json_two_errors':value['result']['content']=[{'type':'text','text':json.dumps([error,error])}]
                    elif variant=='json_wrapped_twins':
                        for block in value['result']['content']:block['text']=json.dumps([error])
                    elif variant=='structured_conflict':value['result']['structuredContent']=dict(error,evalue='other')
                    elif variant=='annotation_rows':value['result']['content'][1]['annotations']={'rows':[SECRET]}
                    elif variant=='annotations_differ':value['result']['content'][1]['annotations']={'priority':0.5}
                    elif variant=='annotation_bool_priority':
                        for block in value['result']['content']:block['annotations']={'priority':True}
                    elif variant=='outer_meta':value['result']['_meta']={'rows':[SECRET]}
                    elif variant=='unknown_outer':value['result']['rows']=[SECRET]
                    elif variant=='printed_error':value['result']['content']=[{'type':'text','text':json.dumps({'outputs':[{'output_type':'stream','name':'stdout','text':json.dumps(error)}],'status':'ok','success':True})}]
                    elif variant=='transport':value['result']={'isError':True,'content':[{'type':'text','text':json.dumps({'success':False,'errors':['timeout']})}]}
                    elif variant=='two_outputs':value['result']['content']=[{'type':'text','text':json.dumps({'status':'error','outputs':[error,error]})}]
                    elif variant=='unknown_node':error['rows']=[SECRET]
                    elif variant=='traceback_empty':error['traceback']=[]
                    elif variant=='traceback_blank':error['traceback']=['  ','\n']
                    elif variant=='traceback_nonstring':error['traceback']=[{'rows':[SECRET]}]
                    elif variant=='traceback_too_many':error['traceback']=['x']*129
                    elif variant=='traceback_long_line':error['traceback']=['x'*65537]
                    elif variant=='duplicate_JSON_key':
                        for block in value['result']['content']:block['text']='{"output_type":"error",'+json.dumps(error)[1:]
                    elif variant=='isError_integer':value['result']['isError']=0
                    if variant in ('unknown_node','traceback_empty','traceback_blank','traceback_nonstring','traceback_too_many','traceback_long_line'):
                        for block in value['result']['content']:block['text']=json.dumps(error)
                    with self.assertRaises(ReceiptParseError):observe(context,value)

    def test_03_binding_and_typed_boolean_context(self):
        variants=('attempt','project','input','cell','entry_source','schema_bool','index_bool','argument_bool',
            'wrapper_count_bool','wrapper_index_bool','missing_binding')
        for version,context in self.contexts.items():
            for variant in variants:
                with self.case(version=version,variant=variant):
                    value=envelope(context);binding=copy.deepcopy(context['binding'])
                    if variant=='attempt':binding['identity']['attempt_id']='f'*32
                    elif variant=='project':binding['identity']['project_id']+=1
                    elif variant=='input':binding['deployment']['input_hash']='f'*64
                    elif variant=='cell':value['arguments']['index']=1
                    elif variant=='entry_source':binding['cell_source_sha256']='f'*64
                    elif variant=='schema_bool':binding['schema_version']=True
                    elif variant=='index_bool':binding['arguments']['index']=False
                    elif variant=='argument_bool':value['arguments']['index']=False
                    elif variant in ('wrapper_count_bool','wrapper_index_bool'):
                        wrapper={'status':'error','outputs':[node()],'cell_index':0,'execution_count':1}
                        wrapper['execution_count' if variant=='wrapper_count_bool' else 'cell_index']=True if variant=='wrapper_count_bool' else False
                        value['result']={'content':[{'type':'text','text':json.dumps(wrapper)}],'isError':False}
                    else:binding={}
                    with self.assertRaises(ReceiptParseError):observe(context,value,binding)

    def test_04_actual_archive_9_entries_43_physical_lines_and_original_hash(self):
        with self.case(actual_packet=True):
            self.assertEqual(hashlib.sha256(ARCHIVE.read_bytes()).hexdigest(),ARCHIVE_SHA)
            admission=json.loads((h.ROOT/'audit/runtime'/h.admission_key(ACTUAL)).read_bytes())
            binding=json.loads((h.ROOT/('audit/runtime/engineering/research-dispatch/'+ACTUAL+'.json')).read_bytes())
            native=json.loads(ARCHIVE.read_bytes());result=research_observation(admission['payload'],admission['deployment'],native,dispatch_binding=binding)
            errors=[json.loads(block['text']) for block in native['result']['content']]
            self.assertEqual(len(errors),2);self.assertEqual(errors[0],errors[1]);self.assertEqual(len(errors[0]['traceback']),9)
            self.assertEqual(sum(len(item.splitlines()) for item in errors[0]['traceback']),43)
            raw=result['submission']['raw_receipt'];self.assertEqual(raw['traceback_line_count'],9);self.assertEqual(raw['error_output_count'],1)
            self.assertEqual(raw['native_error_representation_count'],2);self.assertEqual(raw['response_sha256'],h.content_hash(native['result']))
            self.assertEqual(raw['response_sha256'],'6a5371b3ff243998baded6dc2f9627b110af793a94907a4a73859ced3d5f4f0b')
            self.assertEqual(result['completion']['platform']['status'],'runtime_error');self.assertEqual(set(result['completion']),{'platform'})
            ACTUAL_META.update(archive_sha256=ARCHIVE_SHA,response_sha256=raw['response_sha256'],traceback_entries=9,physical_lines=43,
                logical_errors=1,representations=2,traceback_line_count_is_entries=True,error_class=errors[0]['ename'])

    def test_05_actual_original_attempt_15_17_17_and_refusal_guards(self):
        case=clone_from(self.actual15,'actual-normal');reg=h.registry(case);usage=reg.snapshot()['usage']
        with self.case(variant='normal15-17-17'):
            result=h.okay(h.invoke(case,['research-result','--attempt',ACTUAL,'--tool-file',ARCHIVE],'actual-settle'))
            self.assertEqual(result['status'],'failed');self.assertEqual(event_count(case),17);self.assertEqual(reg.snapshot()['usage'],usage)
            self.assertFalse(reg.store.exists(record(case)['result_key']));before=h.files(case)
            self.assertEqual(h.okay(h.invoke(case,['research-result','--attempt',ACTUAL,'--tool-file',ARCHIVE],'actual-repeat'))['status'],'failed')
            self.assertEqual(event_count(case),17);self.assertEqual(h.files(case),before)
            TRAJECTORIES.append({'name':'normal','events':[15,17,17],'usage_unchanged':True,'success_result_created':False})
        for variant in ('wrong_cell','wrong_project','binding_attempt','input_hash','entry_missing','changed_response','projection_substitution'):
            with self.case(variant=variant):
                negative=clone_from(case if variant in ('changed_response','projection_substitution') else self.actual15,'actual-negative-'+variant)
                store=store_for(negative);value=json.loads(ARCHIVE.read_bytes())
                if variant=='wrong_cell':value['arguments']['index']+=1
                elif variant=='wrong_project':value['arguments']['projectId']+=1
                elif variant=='binding_attempt':
                    path=store._path('engineering/research-dispatch/'+ACTUAL+'.json');binding=json.loads(path.read_bytes());binding['identity']['attempt_id']='f'*32;path.write_bytes(h.canonical_json(binding))
                elif variant=='input_hash':
                    path=store._path(h.admission_key(ACTUAL));admission=json.loads(path.read_bytes());admission['deployment']['input_hash']='f'*64;path.write_bytes(h.canonical_json(admission))
                elif variant=='entry_missing':store._path('engineering/research-entry-protocol/'+ACTUAL+'.json').unlink()
                elif variant=='changed_response':value['result']['content'][0]['text']=json.dumps(json.loads(value['result']['content'][0]['text']),indent=5)
                else:value['result']['content']=value['result']['content'][:1]
                path=toolfile(negative,'negative',value);before=h.files(negative);used=h.registry(negative).snapshot()['usage']
                result=h.invoke(negative,['research-result','--attempt',ACTUAL,'--tool-file',path],'actual-negative-'+variant)
                self.assertNotEqual(result.returncode,0);self.assertEqual(h.files(negative),before);self.assertEqual(h.registry(negative).snapshot()['usage'],used)

    def test_06_actual_settlement_write_faults_no_refund_or_success(self):
        for boundary in ('completion_write','failure_journal'):
            with self.case(boundary=boundary):
                case=clone_from(self.actual15,'actual-crash-'+boundary);b=bridge(case);store=b.store;reg=b.registry;usage=reg.snapshot()['usage']
                native=json.loads(ARCHIVE.read_bytes());stage=load_stage(case);write=store.write_once;append=reg._append
                class InjectedCrash(RuntimeError):pass
                def writing(key,data):
                    if boundary=='completion_write' and key.startswith('engineering/evidence/'+ACTUAL+'/completion/'):raise InjectedCrash(boundary)
                    return write(key,data)
                def appending(event):
                    if boundary=='failure_journal' and event['kind']=='failed':raise InjectedCrash(boundary)
                    return append(event)
                with patch.object(store,'write_once',side_effect=writing),patch.object(reg,'_append',side_effect=appending):
                    with self.assertRaises(InjectedCrash):stage.settle_research_result(b,ACTUAL,native)
                self.assertEqual(record(case)['status'],'pending');self.assertEqual(reg.snapshot()['usage'],usage);self.assertEqual(event_count(case),16)
                recovered=h.okay(h.invoke(case,['research-result','--attempt',ACTUAL,'--tool-file',ARCHIVE],'actual-crash-recover-'+boundary))
                self.assertEqual(recovered['status'],'failed');self.assertEqual(reg.snapshot()['usage'],usage);self.assertFalse(store.exists(record(case)['result_key']))
                # Existing generic pending acknowledgements append an audit event
                # when replayed; this is not a new execution debit. Record it.
                self.assertEqual(event_count(case),18);before=h.files(case)
                self.assertEqual(h.okay(h.invoke(case,['research-result','--attempt',ACTUAL,'--tool-file',ARCHIVE],'actual-crash-repeat-'+boundary))['status'],'failed')
                self.assertEqual(h.files(case),before)
                TRAJECTORIES.append({'name':boundary,'events':[15,16,18,18],'usage_unchanged':True,'success_result_created':False,
                    'extra_pending_ack_is_not_debit':True})

class Result(unittest.TextTestResult):
    def __init__(self,*args,**kwargs):super().__init__(*args,**kwargs);self.subcases=0;self.first_failure=None
    def addSubTest(self,test,subtest,err):
        self.subcases+=1
        if err and self.first_failure is None:self.first_failure={'method':str(test),'subcase':str(subtest),'traceback':self._exc_info_to_string(err,test)}
        super().addSubTest(test,subtest,err)
    def addError(self,test,err):
        if self.first_failure is None:self.first_failure={'method':str(test),'traceback':self._exc_info_to_string(err,test)}
        super().addError(test,err)
stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2,resultclass=Result).run(unittest.defaultTestLoader.loadTestsFromTestCase(ResearchFailureTests))
after={name:hashlib.sha256((h.ROOT/name).read_bytes()).hexdigest() for name in h.CHECK_FILES}
summary={'commit':'deb85d9f27441b275ab8b108f0232ecd2707a1e8','methods':result.testsRun,'subcases':result.subcases,
    'failure_records':len(result.failures),'error_records':len(result.errors),'skipped':len(result.skipped),'first_failure':result.first_failure,
    'success':result.wasSuccessful(),'inputs':INPUTS,'stats':h.STATS,'actual_archive':ACTUAL_META,'event_trajectories':TRAJECTORIES,
    'source_hashes_before':h.BEFORE,'source_hashes_after':after,'source_and_authority_unchanged':h.BEFORE==after,
    'scope':'Synthetic parser inputs plus offline actual archived failed packet and copied15-event replay. Zero QC/SDK/worker executions or writes to actual17-event source ledger.'}
(h.OUT/'results.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
(h.OUT/'command_log.json').write_text(json.dumps(h.LOG,ensure_ascii=False,indent=2),encoding='utf-8')
(h.OUT/'unittest.txt').write_text(stream.getvalue(),encoding='utf-8')
print(stream.getvalue());print(json.dumps({k:v for k,v in summary.items() if k!='inputs'},ensure_ascii=False,indent=2))
sys.exit(0 if result.wasSuccessful() and h.BEFORE==after else 1)
