"""Independent WR12 recovery checks using actual CLI and full copied sources.

No author tests/fixtures are imported. The --worker mode executes only an
independently generated synthetic source through production collection code.
"""
from pathlib import Path
from copy import deepcopy
from hashlib import sha256
from uuid import uuid4
from types import SimpleNamespace as NS
import ast,io,json,os,shutil,subprocess,sys,unittest

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parent;SOURCE=ROOT.parent/'source';RUN=ROOT/'cases'/uuid4().hex[:8]
COMMANDS=[];OBS={};API_ERRORS=('ValueError','RuntimeError','FileNotFoundError','RegistryError','CorruptRegistry','EngineeringTaskError','ReceiptParseError','ArtifactConflict','JSONDecodeError')
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8')
def digest(x):return sha256(canonical(x)).hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def write(path,x):Path(path).parent.mkdir(parents=True,exist_ok=True);Path(path).write_bytes(canonical(x))
def raw_task(name='independent-A',project=734001):
    return {'schema_version':1,'task_kind':'historical_collection','scope':'engineering','plan_id':name,
      'project_id':project,'source_manifest_hash':None,'deployment_hash':None,'field_catalog':None,
      'report_namespace':'independent/recovery','max_retries':1,
      'collection_plan':{'schema_version':1,'plan_id':'snapshots-'+name,'scope':'engineering',
       'source':'quantconnect_fundamental_universe','data_version':'independent-recovery-v1',
       'start':'2022-09-06T00:00:00-04:00','end_exclusive':'2022-09-08T00:00:00-04:00',
       'timezone':'America/New_York','fields':['dollar_volume','has_fundamental_data'],
       'calendar_days_per_request':1,'max_batch_records':2,'max_records_per_window':6,'source_manifest_hash':None}}

def special(mode,case,argument=None):
    case=Path(case);sys.path[:0]=[str(case/'cloud'),str(case/'tools')]
    import collection_task_cli as cli
    from qresearch.artifacts import MemoryArtifactStore,canonical_json
    if mode=='--worker':
        import pandas as pd
        from qresearch.collection_execution import run_collection_task,stdout_marker
        admission=read(case/'audit/runtime/collection/admitted-inputs'/ (argument+'.json'))
        payload=admission['payload'];catalog=payload['plan']['field_catalog']
        class Source:
            calls=0
            def fetch(self,start,end,fields):
                self.calls+=1
                for sid,value in [('independent-missing',None),('independent-zero',0),('independent-positive',91)]:
                    yield {'sid':sid,'snapshot_at':(start+pd.Timedelta(hours=10)).isoformat(),
                           'values':{'dollar_volume':value,'has_fundamental_data':False}}
        source=Source();wrapper=run_collection_task(payload,field_catalog=catalog,store=MemoryArtifactStore(),source=source,
                                                  synthetic=True,source_root=case/'cloud')
        marker=stdout_marker(wrapper,payload=payload,field_catalog=catalog)
        tool={'tool_name':'mcp__quantconnect__jupyter_execute_cell','arguments':{'projectId':734001,'index':4},
              'result':{'structuredContent':{'status':'completed','outputs':[{'output_type':'stream','name':'stdout','text':marker+'\n'}]}}}
        write(case/'synthetic-tool.json',tool)
        print(json.dumps({'source_calls':source.calls,'statistics':wrapper['cloud_report']['statistics'],
                          'missing_values':wrapper['cloud_report']['evidence']['missing_values']}));return 0
    if mode=='--api':
        request=read(argument);action=request['action'];attempt=request.get('attempt')
        if action=='resolve':
            bridge=cli.bridge_for_attempt(attempt)
            value={'config_id':bridge.config_id,'plan':bridge.plan.to_dict(),'payload':bridge.payload(attempt)}
        elif action=='admitted':
            bridge=cli.bridge_for_attempt(attempt);value=cli.admitted_input(bridge,attempt)
        else:raise ValueError(action)
        print(json.dumps(value));return 0
    raise ValueError(mode)

def call(case,args,kind='cli'):
    case=Path(case)
    cmd=[sys.executable,'-B',str(case/'tools/stage2_collection.py'),*map(str,args)] if kind=='cli' else [sys.executable,'-B',str(Path(__file__).resolve()),kind,str(case),*map(str,args)]
    result=subprocess.run(cmd,cwd=case,text=True,encoding='utf-8',capture_output=True,timeout=40,
       env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1'))
    COMMANDS.append({'command':cmd,'cwd':str(case),'returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr})
    if result.returncode==0:
        try:result.value=json.loads(result.stdout)
        except Exception as e:raise RuntimeError('AUDITOR_OUTPUT_PARSE_ERROR: '+repr(e)+' '+result.stdout) from e
    return result
def success(result):
    if result.returncode:raise AssertionError('Unexpected command failure: '+result.stderr)
    return result.value
def attempt_record(case,attempt):
    state=None
    for line in (Path(case)/'audit/runtime/registry/events.jsonl').read_bytes().splitlines():
        event=json.loads(line)['event']
        if event.get('attempt_id')==attempt:state=event.get('kind')
    return state
def budget_usage(case):return read(Path(case)/'config/budget.json')['usage']
def journal(case):return (Path(case)/'audit/runtime/registry/events.jsonl').read_bytes()
def admission_path(case,attempt):return Path(case)/'audit/runtime/collection/admitted-inputs'/(attempt+'.json')
def api(case,action,attempt):
    file=Path(case)/'api-request.json';write(file,{'action':action,'attempt':attempt});return call(case,[str(file)],'--api')

class RecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        RUN.mkdir(parents=True)
        cls.base=RUN/'prepared';shutil.copytree(SOURCE,cls.base,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        cls.source_bytes={p.relative_to(SOURCE).as_posix():sha256(p.read_bytes()).hexdigest() for p in SOURCE.rglob('*') if p.is_file()}
        write(cls.base/'task-A.json',raw_task());write(cls.base/'projects.json',{'success':True,'projects':[{'projectId':734001},{'projectId':734002}]})
        success(call(cls.base,['freeze-task','--task-file','task-A.json','--projects-file','projects.json']))
        success(call(cls.base,['register-task']))
        cls.attempt=success(call(cls.base,['claim-task']))['attempt_id']
        cls.unprepared=RUN/'unprepared';shutil.copytree(cls.base,cls.unprepared)
        cls.admission=success(call(cls.base,['prepare-task','--attempt',cls.attempt]))
        cls.worker=success(call(cls.base,[cls.attempt],'--worker'))
        cls.usage=budget_usage(cls.base)
        OBS['base']={'attempt':cls.attempt,'usage':cls.usage,'worker':cls.worker,'source_copy_complete':True,
                     'source_file_count':len(cls.source_bytes)}
    def case(self,prepared=True):
        path=RUN/uuid4().hex[:8];shutil.copytree(self.base if prepared else self.unprepared,path);return path
    def settle(self,case,attempt=None,tool='synthetic-tool.json'):
        return call(case,['research-result','--attempt',self.attempt if attempt is None else attempt,'--tool-file',tool])
    def assert_reject(self,result,*needles):
        self.assertNotEqual(result.returncode,0,result.stdout)
        self.assertTrue(any(e in result.stderr for e in API_ERRORS),result.stderr)
        if needles:self.assertTrue(any(n in result.stderr for n in needles),result.stderr)
    def switch(self,case):
        write(case/'task-B.json',raw_task('independent-B',734002))
        return success(call(case,['freeze-task','--task-file','task-B.json','--projects-file','projects.json']))
    def unchanged_refusal(self,case,result):
        self.assert_reject(result);self.assertEqual(budget_usage(case),self.usage);self.assertEqual(attempt_record(case,self.attempt),'attempt_started')

    def test_A_to_B_actual_CLI_settles_old_A_idempotently_without_charge(self):
        case=self.case();self.switch(case);before=budget_usage(case)
        result=success(self.settle(case));self.assertEqual(result['status'],'completed')
        self.assertEqual(result['attempt_id'],self.attempt);self.assertEqual(result['config_id'],self.admission['payload']['identity']['config_id'])
        recorded=journal(case);again=success(self.settle(case));self.assertEqual(again['status'],'completed')
        self.assertEqual(journal(case),recorded);self.assertEqual(budget_usage(case),before)
        OBS['A_to_B']={'status':result['status'],'repeat_status':again['status'],'journal_repeat_unchanged':True,'budget':before}

    def test_catalog_source_changes_pointer_deletion_and_process_restart_preserve_recovery(self):
        for change in ['catalog','source','no-pointer','invalid-pointer','catalog-absent','combined']:
            with self.subTest(change=change):
                case=self.case()
                if change in ['catalog','combined']:
                    catalog=read(case/'config/source_catalog.json');catalog['fields']['dollar_volume']['unit']='shares-changed-today';write(case/'config/source_catalog.json',catalog)
                if change in ['source','combined']:
                    p=case/'cloud/qresearch/cache.py';p.write_bytes(p.read_bytes()+b'\n# independent source-version change\n')
                if change in ['no-pointer','combined']:(case/'audit/collection_current.json').unlink()
                if change=='invalid-pointer':(case/'audit/collection_current.json').write_text('not json',encoding='utf-8')
                if change=='catalog-absent':(case/'config/source_catalog.json').unlink()
                status=success(call(case,['task-status','--attempt',self.attempt]));self.assertEqual(status['attempts'][-1]['status'],'started')
                self.assertEqual(success(self.settle(case))['status'],'completed');self.assertEqual(budget_usage(case),self.usage)

    def test_prepared_input_read_after_source_change_has_no_new_file_or_charge(self):
        case=self.case();self.switch(case);p=case/'cloud/qresearch/cache.py';p.write_bytes(p.read_bytes()+b'\n# changed later\n')
        before=journal(case);input_path=case/self.admission['input_path'];input_bytes=input_path.read_bytes()
        again=success(call(case,['prepare-task','--attempt',self.attempt]));self.assertEqual(again,self.admission)
        self.assertEqual(input_path.read_bytes(),input_bytes);self.assertEqual(journal(case),before);self.assertEqual(budget_usage(case),self.usage)

    def test_missing_local_input_settles_from_admission_without_recreating_file(self):
        case=self.case();path=case/self.admission['input_path'];path.unlink();(case/'audit/collection_current.json').unlink()
        self.assertEqual(success(api(case,'admitted',self.attempt)),self.admission)
        self.assertFalse(path.exists());self.assertEqual(success(self.settle(case))['status'],'completed')
        self.assertFalse(path.exists());self.assertEqual(budget_usage(case),self.usage)

    def test_new_input_for_never_prepared_attempt_cannot_bypass_current_identity(self):
        for change in ['source','deployment','catalog']:
            with self.subTest(change=change):
                case=self.case(prepared=False)
                if change=='source':
                    path=case/'cloud/qresearch/cache.py';path.write_bytes(path.read_bytes()+b'\n# not the frozen source\n')
                elif change=='deployment':
                    raw=read(case/'audit/deployment.json');raw['source_files']['qresearch/cache.py']='0'*64;write(case/'audit/deployment.json',raw)
                else:
                    raw=read(case/'config/source_catalog.json');raw['fields']['dollar_volume']['unit']='shares-new';write(case/'config/source_catalog.json',raw)
                before=journal(case);result=call(case,['prepare-task','--attempt',self.attempt])
                self.assert_reject(result,'Re-freeze');self.assertEqual(journal(case),before)
                self.assertFalse(admission_path(case,self.attempt).exists());self.assertFalse((case/self.admission['input_path']).exists())
                self.assertEqual(budget_usage(case),self.usage)

    def test_current_register_claim_still_require_current_catalog_and_source(self):
        for change in ['source','catalog']:
            for command in ['register-task','claim-task']:
                with self.subTest(change=change,command=command):
                    case=self.case()
                    if change=='source':
                        p=case/'cloud/qresearch/cache.py';p.write_bytes(p.read_bytes()+b'\n# source changed\n')
                    else:
                        raw=read(case/'config/source_catalog.json');raw['fields']['dollar_volume']['unit']='changed-unit';write(case/'config/source_catalog.json',raw)
                    before=journal(case);self.assert_reject(call(case,[command]),'Re-freeze','Source identity and selected trusted catalog')
                    self.assertEqual(journal(case),before);self.assertEqual(budget_usage(case),self.usage)

    def test_unknown_unregistered_and_old_noncollection_attempt_cannot_self_authorize(self):
        case=self.case();before=journal(case)
        # A frozen but unregistered document is deliberately made available; it
        # cannot make an invented attempt known to the charged event stream.
        self.switch(case)
        for attempted in ['f'*32,'not-an-attempt',self.admission['payload']['identity']['config_id']]:
            with self.subTest(attempt=attempted):self.assert_reject(api(case,'resolve',attempted),'existing canonical','Unknown charged')
        status=success(call(case,['task-status']))
        legacy=next(a for a in status['attempts'] if a['stage']=='lean')['attempt_id']
        self.assert_reject(api(case,'resolve',legacy),'immutable collection configuration')
        self.assertEqual(journal(case),before);self.assertEqual(budget_usage(case),self.usage)

    def test_registered_frozen_catalog_is_accepted_only_with_matching_immutable_config(self):
        case=self.case();bridge=success(api(case,'resolve',self.attempt))
        self.assertEqual(bridge['plan']['field_catalog'],self.admission['payload']['plan']['field_catalog'])
        self.assertEqual(bridge['config_id'],self.admission['payload']['identity']['config_id'])
        path=case/'audit/runtime/configurations'/(bridge['config_id']+'.json');raw=read(path)
        raw['plan']['field_catalog']['dollar_volume']['unit']='silently rewritten';write(path,raw)
        before=journal(case);self.assert_reject(api(case,'resolve',self.attempt),'Configuration artifact identity mismatch','Registry replay failed')
        self.assertEqual(journal(case),before)

    def test_admission_payload_manifest_config_attempt_and_paths_tampering_is_rejected(self):
        changes=['attempt','config','plan','report-key','manifest-digest','manifest-traversal','input-hash','source-hash','input-path','cloud-path','extra','noncanonical']
        for change in changes:
            with self.subTest(change=change):
                case=self.case();path=admission_path(case,self.attempt);a=read(path)
                if change=='attempt':a['payload']['identity']['attempt_id']='f'*32
                elif change=='config':a['payload']['identity']['config_id']='0'*64
                elif change=='plan':a['payload']['plan']['field_catalog']['dollar_volume']['unit']='other'
                elif change=='report-key':a['payload']['report_key']='other/report.json'
                elif change=='manifest-digest':a['payload']['deployment_manifest']['qresearch/cache.py']='0'*64
                elif change=='manifest-traversal':a['payload']['deployment_manifest']['../outside.py']='0'*64
                elif change=='input-hash':a['deployment']['input_hash']='0'*64
                elif change=='source-hash':a['deployment']['source_manifest_hash']='0'*64
                elif change=='input-path':a['input_path']='audit/collection_task_inputs/other.py'
                elif change=='cloud-path':a['cloud_input_path']='_engineering_task_input.py'
                elif change=='extra':a['untrusted']='extra'
                if change in ['attempt','config','plan','report-key','manifest-digest','manifest-traversal']:
                    # Recompute the easy input digest so a stronger binding,
                    # rather than merely stale text hashing, must reject it.
                    text='TASK_INPUT_JSON = '+repr(canonical(a['payload']).decode('utf-8'))+'\n'
                    a['deployment']['input_hash']=sha256(text.encode()).hexdigest()
                path.write_text(json.dumps(a,indent=2),encoding='utf-8') if change=='noncanonical' else write(path,a)
                before=journal(case);self.assert_reject(self.settle(case));self.assertEqual(journal(case),before)
                self.assertEqual(budget_usage(case),self.usage);self.assertEqual(attempt_record(case,self.attempt),'attempt_started')

    def test_missing_admission_and_modified_local_bytes_fail_without_release_or_retry(self):
        for change in ['missing-admission','malformed-admission','extra-local-code','changed-local-text']:
            with self.subTest(change=change):
                case=self.case();a=admission_path(case,self.attempt);p=case/self.admission['input_path']
                if change=='missing-admission':a.unlink()
                elif change=='malformed-admission':a.write_bytes(b'not-json')
                elif change=='extra-local-code':p.write_bytes(p.read_bytes()+b'\nprint("synthetic-extra")\n')
                else:p.write_text('TASK_INPUT_JSON = "{}"\n',encoding='utf-8')
                before=journal(case);self.assert_reject(self.settle(case));self.assertEqual(journal(case),before)
                self.assertEqual(budget_usage(case),self.usage)

    def test_wrong_tool_and_report_identity_do_not_finalize_or_change_charge(self):
        for change in ['project','attempt','config','report-path']:
            with self.subTest(change=change):
                case=self.case();tool=read(case/'synthetic-tool.json')
                if change=='project':tool['arguments']['projectId']=734002
                else:
                    import base64
                    wrapper=json.loads(base64.b64decode(tool['result']['structuredContent']['outputs'][0]['text'].split()[1]))
                    if change=='attempt':wrapper['cloud_report']['identity']['attempt_id']='f'*32
                    elif change=='config':wrapper['cloud_report']['identity']['config_id']='0'*64
                    else:wrapper['report_ref']['key']='other/report.json'
                    wrapper['report_ref']['sha256']=digest(wrapper['cloud_report'])
                    tool['result']['structuredContent']['outputs'][0]['text']='AQRP_ENGINEERING_JSON '+base64.b64encode(canonical(wrapper)).decode()+'\n'
                write(case/'synthetic-tool.json',tool);before=journal(case)
                self.assert_reject(self.settle(case));self.assertEqual(journal(case),before);self.assertEqual(budget_usage(case),self.usage)

    def test_completed_attempt_cannot_prepare_new_input_even_with_admission(self):
        case=self.case();self.assertEqual(success(self.settle(case))['status'],'completed');before=journal(case)
        self.assert_reject(call(case,['prepare-task','--attempt',self.attempt]),'Finalized collection tasks')
        self.assertEqual(journal(case),before);self.assertEqual(budget_usage(case),self.usage)

class Counted(unittest.TextTestResult):
    def __init__(self,*a,**k):super().__init__(*a,**k);self.subcases=0
    def addSubTest(self,test,sub,error):self.subcases+=1;super().addSubTest(test,sub,error)

def main():
    output=io.StringIO();r=unittest.TextTestRunner(stream=output,verbosity=2,resultclass=Counted).run(unittest.defaultTestLoader.loadTestsFromTestCase(RecoveryTests))
    (ROOT/'first_output.txt').write_text(output.getvalue(),encoding='utf-8')
    def method(t):return getattr(t,'test_case',t).id()
    failures={method(t) for t,_ in r.failures};errors={method(t) for t,_ in r.errors}
    result={'commit':'be9442603a31481a9a71e51ca794df77650c7411','methods':r.testsRun,'passed_methods':r.testsRun-len(failures|errors),
       'failed_methods':len(failures),'error_methods':len(errors),'skipped':len(r.skipped),'subcases':r.subcases,
       'failure_records':len(r.failures),'error_records':len(r.errors),'failures':[{'method':method(t),'traceback':tb} for t,tb in r.failures],
       'errors':[{'method':method(t),'traceback':tb} for t,tb in r.errors],'observations':OBS,
       'command':[sys.executable,'-B',str(Path(__file__).resolve())],'original_script_sha256':sha256(Path(__file__).read_bytes()).hexdigest(),
       'actual_external_calls':0,'author_test_helpers_imported':False,'full_source_copy_actual_CLI':True,
       'production_source_bytes_unchanged':all(sha256((SOURCE/name).read_bytes()).hexdigest()==value for name,value in getattr(RecoveryTests,'source_bytes',{}).items()),
       'exit_code':0 if r.wasSuccessful() else 1}
    write(ROOT/'first_results.json',result);write(ROOT/'command_log.json',COMMANDS)
    print(output.getvalue());print(json.dumps({k:result[k] for k in ['methods','passed_methods','failed_methods','error_methods','skipped','subcases','exit_code']}))
    return result['exit_code']

if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1] in ['--worker','--api']:raise SystemExit(special(sys.argv[1],sys.argv[2],sys.argv[3] if len(sys.argv)>3 else None))
    raise SystemExit(main())
