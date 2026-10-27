"""Independent WR17 actual-CLI and filesystem-ledger recovery tests."""
import argparse
import base64
from copy import deepcopy
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import unittest

ap=argparse.ArgumentParser();ap.add_argument('--source',required=True);ap.add_argument('--out',required=True)
arg=ap.parse_args();ROOT=Path(arg.source).resolve();OUT=Path(arg.out).resolve();OUT.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(ROOT/'cloud'))
from qresearch.artifacts import FilesystemArtifactStore,MemoryArtifactStore,canonical_json,content_hash
from qresearch.registry import Registry
from qresearch.engineering_tasks import EngineeringTaskPlan,EngineeringTaskBridge,JOINT_PROBE_CHECKS
from qresearch.engineering_data import _finish
from qresearch.collection import HistoricalCollectionPlan

LOG=[];INPUTS=[];STATS={'actual_CLI_processes':0,'direct_freeze_processes':0,'synthetic_metadata_finish_calls':0,'actual_worker_executions':0}
ENV=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
CHECK_FILES=['tools/stage2.py','cloud/qresearch/engineering_tasks.py','cloud/qresearch/registry.py','config/budget.json','audit/runtime/registry/events.jsonl']
BEFORE={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in CHECK_FILES}
def dump(path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(canonical_json(value))
def files(root):return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
def registry(case):
    store=FilesystemArtifactStore(case/'audit/runtime')
    return Registry(store,json.loads(store.read_bytes('registry/baseline.json')))
def invoke(case,args,label,*,direct=False):
    index=len(LOG);argv=[sys.executable,'-B',*(args if direct else [str(case/'tools/stage2.py'),*map(str,args)])]
    if direct:STATS['direct_freeze_processes']+=1
    else:STATS['actual_CLI_processes']+=1
    started=time.monotonic();r=subprocess.run(argv,cwd=case,env=ENV,capture_output=True,timeout=55)
    folder=OUT/'commands';folder.mkdir(exist_ok=True)
    stdout=folder/(str(index).zfill(3)+'-'+label+'.stdout');stderr=folder/(str(index).zfill(3)+'-'+label+'.stderr')
    stdout.write_bytes(r.stdout);stderr.write_bytes(r.stderr)
    LOG.append({'index':index,'label':label,'argv':argv,'cwd':str(case),'exit_code':r.returncode,'seconds':time.monotonic()-started,
        'stdout':str(stdout.relative_to(OUT)),'stderr':str(stderr.relative_to(OUT)),
        'stdout_sha256':hashlib.sha256(r.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(r.stderr).hexdigest()})
    return r
def okay(result):
    if result.returncode:raise AssertionError(result.stderr.decode('utf-8',errors='replace'))
    return json.loads(result.stdout)
def plan_input(version,tag):
    value={'schema_version':version,'plan_id':'INDEPENDENT-WR17-'+tag,'scope':'engineering','project_id':None,
        'source_manifest_hash':None,'deployment_hash':None,'request_mode':'symbol_resolution',
        'request_template':{'dataset':'US Equities','fields':['close'],'start':'2018-01-01T00:00:00-05:00','end':'2019-01-01T00:00:00-05:00',
            'data_version':'SYNTHETIC-WR17-'+tag,'universe_hash':None,'normalization':'raw','timezone':'America/New_York'},
        'symbol_resolution':{'tickers':['AAPL','MSFT'],'as_of':'2019-01-01T00:00:00-05:00','method':'QuantBook.add_equity/as-of fixed fixture'},
        'observation_window':{'start':'2018-01-03T00:00:00-05:00','end_exclusive':'2018-01-06T00:00:00-05:00'},
        'required_checks':{'research':['raw_data_received','second_prefetch_no_history'], 'lean':['raw_data_received','no_orders','corporate_action_received']},
        'max_retries':{'research':0,'lean':0},'report_namespace':'independent-wr17/'+tag,
        'orders_enabled':False,'financial_metrics_enabled':False,'economic_factor':None,'economic_model':None}
    if version==2:
        value['required_checks']['research']+=sorted(JOINT_PROBE_CHECKS)
        value['collection_probe']={'collection_plan':{'schema_version':1,'plan_id':'INDEPENDENT-WR17-child','scope':'engineering',
            'source':'quantconnect_fundamental_universe','data_version':'SYNTHETIC-child-'+tag,'start':'2018-01-01T00:00:00-05:00',
            'end_exclusive':'2018-02-10T00:00:00-05:00','timezone':'America/New_York',
            'fields':['dollar_volume','has_fundamental_data','time','end_time'],'calendar_days_per_request':1,
            'max_batch_records':1000,'max_records_per_window':50000,'source_manifest_hash':None},'field_catalog':None}
    return value
def fresh(label):
    case=OUT/'cases'/label/'source';case.parent.mkdir(parents=True,exist_ok=True)
    # Complete execution source/config tree; historical audit archives are not
    # runtime inputs. Start a separately identified synthetic ledger, retaining
    # the original budget document as its unchanged aggregate baseline.
    for item in ROOT.iterdir():
        if item.name=='audit':continue
        if item.is_dir():shutil.copytree(item,case/item.name,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        else:
            (case/item.name).parent.mkdir(parents=True,exist_ok=True);shutil.copy2(item,case/item.name)
    (case/'audit').mkdir(exist_ok=True);shutil.copy2(ROOT/'audit/deployment.json',case/'audit/deployment.json')
    for version in (1,2):dump(case/('config/independent-v'+str(version)+'.json'),plan_input(version,'v'+str(version)))
    active=json.loads((case/'config/quantconnect.json').read_text(encoding='utf-8'))['active_project_id']
    listing=case.parent/'synthetic-projects.json';dump(listing,{'success':True,'projects':[{'projectId':active}]})
    return case,listing
def setup_case(version,label):
    case,listing=fresh(label)
    okay(invoke(case,['freeze','--plan-file','config/independent-v'+str(version)+'.json','--projects-file',listing],label+'-freeze'))
    pointer=(case/'audit/engineering_current.json').read_bytes()
    okay(invoke(case,['register'],label+'-register'))
    attempt=okay(invoke(case,['claim','--stage','research'],label+'-claim'))['attempt_id']
    admission=okay(invoke(case,['prepare','--attempt',attempt],label+'-prepare'))
    return {'case':case,'listing':listing,'attempt':attempt,'admission':admission,'pointer':pointer,'version':version}
def admission_key(attempt):return 'engineering/admitted-inputs/'+attempt+'.json'
def synthetic_report(context,admission,stage):
    payload=admission['payload'];plan=EngineeringTaskPlan.from_dict(payload['plan'],discovered_project_ids=(payload['identity']['project_id'],))
    cloud=MemoryArtifactStore();refs={}
    if stage=='research':
        for key in ('resolved_registry_ref','resolved_request_ref'):
            data={'synthetic_fixture':True,'kind':key};name='independent-cloud/'+context['attempt']+'/'+key+'.json'
            cloud.write_once(name,canonical_json(data));refs[key]={'key':name,'sha256':content_hash(data)}
        resolution={'resolved_registry_hash':refs['resolved_registry_ref']['sha256'],'resolved_request_hash':refs['resolved_request_ref']['sha256'],
            'resolution_artifact_hash':content_hash(refs),'tickers':['AAPL','MSFT'],'ticker_count':2,'permanent_sid_count':2,
            'method':'QuantBook.add_equity/as-of fixed fixture',**refs}
    else:resolution=payload['research_resolution']
    evidence={}
    if plan.to_dict()['schema_version']==2 and stage=='research':
        child=plan.to_dict()['collection_probe'];cp=HistoricalCollectionPlan.from_dict(child['collection_plan'],field_catalog=child['field_catalog'])
        key=plan.to_dict()['report_namespace']+'/collection-probes/'+plan.hash+'/'+payload['identity']['attempt_id']+'.json'
        synthetic={'synthetic_fixture':True,'identity':payload['identity']};cloud.write_once(key,canonical_json(synthetic))
        evidence['collection_probe']={'schema_version':1,'plan_hash':cp.hash,'receipt_ref':{'key':key,'sha256':content_hash(synthetic)},
            'window_count':40,'record_count':40,'source_fetch_calls':40,'reused_windows':0,'empty_windows':0,'cache_only_source_fetch_calls':0,
            'missing_values':{field:0 for field in cp.field_catalog},'full_historical_US200_certified':False,
            'actual_availability_certified':False,'research_certified':False,'row_values_exported':False,'financial_vintage_certified':False}
    checks={name:True for name in plan.to_dict()['required_checks'][stage]}
    statistics={'record_count':6,'history_calls_first':1,'history_calls_second':0,'expected_formation_count':3} if stage=='research' else {
        'data_event_count':6,'slice_count':3,'orders_submitted':0,'runtime_error_count':0,'dividend_event_count':1}
    STATS['synthetic_metadata_finish_calls']+=1
    wrapper=_finish(cloud,payload,checks,statistics,resolution,evidence=evidence)
    return wrapper
def envelopes(context,admission,stage):
    wrapper=synthetic_report(context,admission,stage);payload=admission['payload'];project=payload['identity']['project_id']
    text=base64.b64encode(canonical_json(wrapper)).decode();folder=context['case'].parent/'native';folder.mkdir(exist_ok=True)
    if stage=='research':
        result={'outputs':[{'output_type':'stream','name':'stdout','text':'AQRP_ENGINEERING_JSON '+text}],'status':'ok','success':True}
        path=folder/'research.json';dump(path,{'tool_name':'mcp__quantconnect__jupyter_execute_cell','arguments':{'projectId':project,'index':4},
            'result':{'structuredContent':result,'content':[{'type':'text','text':json.dumps(result)}]}})
        return {'result':path}
    external='synthetic-wr17-'+payload['identity']['attempt_id'];sub=folder/'submission.json';read=folder/'read.json';logs=folder/'logs.json'
    dump(sub,{'tool_name':'mcp__quantconnect__create_backtest','arguments':{'projectId':project,'backtestName':'independent-offline'},
        'result':{'success':True,'errors':[],'backtestId':external}})
    dump(read,{'tool_name':'mcp__quantconnect__read_backtest','arguments':{'projectId':project,'backtestId':external},
        'result':{'success':True,'errors':[],'backtest':{'backtestId':external,'projectId':project,'completed':True,'progress':1,
            'status':'Completed.','hasInitializeError':False,'statistics':{'Total Orders':'0'}}}})
    parts=[text[i:i+500] for i in range(0,len(text),500)]
    lines=['AQRP_ENGINEERING '+payload['identity']['attempt_id']+' '+str(i)+'/'+str(len(parts))+' '+s for i,s in enumerate(parts)]
    dump(logs,[{'tool_name':'mcp__quantconnect__search_backtest_logs','arguments':{'projectId':project,'backtestId':external,
        'query':'AQRP_ENGINEERING '+payload['identity']['attempt_id'],'page':1},'result':{'success':True,'errors':[],'logs':lines,'totalPages':1}}])
    return {'submission':sub,'result':read,'logs':logs}
def restore_files(case,saved):
    for relative,content in saved.items():
        path=case/relative
        if content is None:
            if path.exists():path.unlink()
        else:path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(content)
def drift(context,attempt):
    case=context['case'];names=['audit/engineering_current.json','audit/deployment.json','config/source_catalog.json','cloud/research_config.py']
    saved={name:(case/name).read_bytes() if (case/name).exists() else None for name in names}
    for name in names[:3]:(case/name).unlink(missing_ok=True)
    with (case/names[3]).open('ab') as stream:stream.write(b'\n# INDEPENDENT historical settlement source drift\n')
    local=case/('audit/task_inputs/'+attempt+'.py');local.unlink(missing_ok=True)
    return saved

class RecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.contexts={v:setup_case(v,'base-v'+str(v)) for v in (1,2)}
    def case(self,**params):INPUTS.append({'method':self._testMethodName,**params});return self.subTest(**params)
    def test_freeze_all_versions_states_entrypoints_no_write(self):
        for version,context in self.contexts.items():
            case=context['case'];reg=registry(case)
            for state in ('started','pending','ambiguous'):
                if state=='pending':reg.pending(context['attempt'],external_id='synthetic-pending-'+context['attempt'])
                if state=='ambiguous':reg.ambiguous(context['attempt'],reason='synthetic unknown submission')
                for target in (1,2):
                    for entry in ('cli','function-process'):
                        with self.case(original_version=version,state=state,target_version=target,entry=entry):
                            before=files(case)
                            if entry=='cli':r=invoke(case,['freeze','--plan-file','config/independent-v'+str(target)+'.json','--projects-file',context['listing']],f'freeze-v{version}-{state}-to{target}')
                            else:r=invoke(case,[str(OUT/'direct_freeze_entry.py'),str(case),'config/independent-v'+str(target)+'.json',str(context['listing'])],f'direct-v{version}-{state}-to{target}',direct=True)
                            self.assertNotEqual(r.returncode,0);self.assertIn(b'Unresolved engineering work',r.stderr)
                            self.assertEqual(files(case),before)
    def test_two_process_mixed_freeze_cannot_change_pointer(self):
        for version,context in self.contexts.items():
            with self.case(original_version=version,concurrency='two-CLI-v1-v2'):
                case=context['case'];before=files(case)
                processes=[]
                for target in (1,2):
                    argv=[sys.executable,'-B',str(case/'tools/stage2.py'),'freeze','--plan-file','config/independent-v'+str(target)+'.json','--projects-file',str(context['listing'])]
                    STATS['actual_CLI_processes']+=1;processes.append((target,argv,subprocess.Popen(argv,cwd=case,env=ENV,stdout=subprocess.PIPE,stderr=subprocess.PIPE)))
                for target,argv,process in processes:
                    stdout,stderr=process.communicate(timeout=55);index=len(LOG);folder=OUT/'commands';folder.mkdir(exist_ok=True)
                    sp=folder/(str(index).zfill(3)+'-parallel.stdout');ep=folder/(str(index).zfill(3)+'-parallel.stderr');sp.write_bytes(stdout);ep.write_bytes(stderr)
                    LOG.append({'index':index,'label':'parallel-v'+str(target),'argv':argv,'cwd':str(case),'exit_code':process.returncode,'stdout':str(sp.relative_to(OUT)),'stderr':str(ep.relative_to(OUT))})
                    self.assertNotEqual(process.returncode,0);self.assertIn(b'Unresolved engineering work',stderr)
                self.assertEqual(files(case),before)
    def test_original_attempt_research_and_lean_settlement_after_drift(self):
        for version in (1,2):
            with self.case(version=version,chain='actual-CLI-Research-and-LEAN'):
                context=setup_case(version,'settle-v'+str(version));case=context['case'];attempt=context['attempt']
                native=envelopes(context,context['admission'],'research');usage=registry(case).snapshot()['usage']
                saved=drift(context,attempt)
                before=files(case)
                restored=okay(invoke(case,['prepare','--attempt',attempt],f'old-v{version}-prepare-drift'))
                self.assertEqual(restored,context['admission']);self.assertFalse((case/restored['input_path']).exists());self.assertEqual(files(case),before)
                status=okay(invoke(case,['status','--attempt',attempt],f'old-v{version}-status-drift'));self.assertEqual(status['usage'],usage)
                finished=okay(invoke(case,['research-result','--attempt',attempt,'--tool-file',native['result']],f'old-v{version}-research-drift'))
                self.assertEqual(finished['status'],'completed');self.assertEqual(registry(case).snapshot()['usage'],usage)
                restore_files(case,saved)
                # A legal zero-charge plan B freeze after Research terminal must
                # not stop reading the already admitted final A input.
                pointer=case/'audit/engineering_current.json';old_pointer=pointer.read_bytes()
                okay(invoke(case,['freeze','--plan-file','config/independent-v'+str(3-version)+'.json','--projects-file',context['listing']],f'old-v{version}-freeze-B'))
                self.assertEqual(okay(invoke(case,['prepare','--attempt',attempt],f'old-v{version}-read-final-A')),context['admission'])
                self.assertEqual(registry(case).snapshot()['usage'],usage);pointer.write_bytes(old_pointer)
                lean=okay(invoke(case,['claim','--stage','lean'],f'old-v{version}-lean-claim'))['attempt_id']
                admission=okay(invoke(case,['prepare','--attempt',lean],f'old-v{version}-lean-prepare'))
                native_lean=envelopes(context,admission,'lean');lean_usage=registry(case).snapshot()['usage'];saved=drift(context,lean)
                self.assertEqual(okay(invoke(case,['prepare','--attempt',lean],f'old-v{version}-lean-prepare-drift')),admission)
                self.assertFalse((case/admission['input_path']).exists())
                pending=okay(invoke(case,['backtest-submission','--attempt',lean,'--tool-file',native_lean['submission']],f'old-v{version}-lean-submission'))
                self.assertEqual(pending['status'],'pending')
                terminal=okay(invoke(case,['backtest-result','--attempt',lean,'--tool-file',native_lean['result'],'--logs-file',native_lean['logs']],f'old-v{version}-lean-result'))
                self.assertEqual(terminal['status'],'completed');self.assertEqual(registry(case).snapshot()['usage'],lean_usage)
                context['final_lean']=lean;context['final_admission']=admission
                # Missing admission on a finalized attempt must not turn a
                # settlement read into permission to generate fresh input.
                store=registry(case).store;store._path(admission_key(lean)).unlink();before=files(case)
                self.assertNotEqual(invoke(case,['prepare','--attempt',lean],f'old-v{version}-final-fresh-input').returncode,0)
                self.assertEqual(files(case),before)
    def test_missing_tampered_foreign_admission_and_input_rejected_no_write(self):
        mutations=['missing','input_hash','foreign_attempt','cloud_path','extra_field','noncanonical','local_input_bytes']
        for version,context in self.contexts.items():
            for mutation in mutations:
                with self.case(version=version,mutation=mutation):
                    original=context['case'];case=OUT/'cases'/('negative-v'+str(version)+'-'+mutation)/'source'
                    shutil.copytree(original,case,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
                    store=registry(case).store;path=store._path(admission_key(context['attempt']));value=json.loads(path.read_bytes())
                    if mutation=='missing':path.unlink()
                    elif mutation=='local_input_bytes':
                        with (case/value['input_path']).open('ab') as stream:stream.write(b'\nraise RuntimeError("must never execute")\n')
                    else:
                        if mutation=='input_hash':value['deployment']['input_hash']='f'*64
                        elif mutation=='foreign_attempt':value['payload']['identity']['attempt_id']='f'*32
                        elif mutation=='cloud_path':value['cloud_input_path']='other.py'
                        elif mutation=='extra_field':value['rows']=['SYNTHETIC-UNKNOWN-SIDE-DATA']
                        data=json.dumps(value,indent=2).encode() if mutation=='noncanonical' else canonical_json(value)
                        path.write_bytes(data)
                    before=files(case);usage=registry(case).snapshot()['usage']
                    # Missing admission is specifically a result-read error;
                    # a new active attempt's first prepare may legitimately create it.
                    command=['research-result','--attempt',context['attempt'],'--tool-file',case.parent/'not-read.json'] if mutation=='missing' else ['prepare','--attempt',context['attempt']]
                    self.assertNotEqual(invoke(case,command,'reject-v'+str(version)+'-'+mutation).returncode,0)
                    self.assertEqual(files(case),before);self.assertEqual(registry(case).snapshot()['usage'],usage)
    def test_unknown_attempt_rejected_without_pointer_dependency_or_write(self):
        for version,context in self.contexts.items():
            for command in ('prepare','status'):
                with self.case(version=version,command=command):
                    before=files(context['case'])
                    self.assertNotEqual(invoke(context['case'],[command,'--attempt','f'*32],'unknown-'+str(version)+'-'+command).returncode,0)
                    self.assertEqual(files(context['case']),before)

class CountResult(unittest.TextTestResult):
    def __init__(self,*a,**kw):super().__init__(*a,**kw);self.subcases=0;self.first_failure=None
    def addSubTest(self,test,subtest,err):
        self.subcases+=1
        if err and self.first_failure is None:self.first_failure={'method':str(test),'subtest':str(subtest),'traceback':self._exc_info_to_string(err,test)}
        super().addSubTest(test,subtest,err)
    def addError(self,test,err):
        if self.first_failure is None:self.first_failure={'method':str(test),'traceback':self._exc_info_to_string(err,test)}
        super().addError(test,err)

stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2,resultclass=CountResult).run(unittest.defaultTestLoader.loadTestsFromTestCase(RecoveryTests))
raw=stream.getvalue();(OUT/'first_run_unittest.txt').write_text(raw,encoding='utf-8')
after={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in CHECK_FILES}
summary={'commit':'ae2b8985f3799c246e90341370f86d80483f63ed','argv':sys.argv,'methods':result.testsRun,'subcases':result.subcases,
    'failure_records':len(result.failures),'error_records':len(result.errors),'skipped':len(result.skipped),'success':result.wasSuccessful(),
    'first_failure':result.first_failure,'inputs':INPUTS,'stats':STATS,'source_hashes_before':BEFORE,'source_hashes_after':after,
    'source_and_authority_unchanged':BEFORE==after,'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'scope':'Actual isolated production CLI subprocesses and Filesystem Registry; fabricated bounded metadata reports via actual _finish, not SDK/workers/platform evidence',
    'actions':{'real_SDK':0,'QC':0,'Research':0,'LEAN':0,'models':0,'market':0,'real_budget_changes':0,'production_source_edits':0}}
(OUT/'first_run_summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf-8')
(OUT/'command_log.json').write_text(json.dumps(LOG,indent=2,ensure_ascii=False),encoding='utf-8')
print(raw);print(json.dumps({k:v for k,v in summary.items() if k not in {'inputs','first_failure'}},ensure_ascii=False))
sys.exit(0 if result.wasSuccessful() and summary['source_and_authority_unchanged'] else 1)
