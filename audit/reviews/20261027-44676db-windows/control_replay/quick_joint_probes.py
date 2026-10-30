"""Independent joint v2 admission known-answer probes; no author fixtures."""
from pathlib import Path
from uuid import uuid4
from copy import deepcopy
from hashlib import sha256
import io,json,os,shutil,subprocess,sys,unittest

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parent;SOURCE=ROOT.parent/'source';RUN=ROOT/'quick_cases'/uuid4().hex[:8]
sys.path[:0]=[str(SOURCE/'cloud'),str(SOURCE/'tools')]
from qresearch.artifacts import MemoryArtifactStore,canonical_json,content_hash
from qresearch.registry import Registry,RegistryError
from qresearch.engineering_tasks import EngineeringTaskPlan,EngineeringTaskBridge,EngineeringTaskError

CAT={name:{'kind':kind,'role':'independent_observation','unit':unit,'period_accessor':None}
     for name,kind,unit in [('dollar_volume','number','USD'),('has_fundamental_data','boolean','flag'),
                            ('time','text','clock'),('end_time','text','clock')]}
def budget():
    return {'limits':{'full_configurations':12,'research_execution_attempts':20,'lean_submission_attempts':16},
      'allocations':{'full_configurations':{'total':12,'normal':8,'reserve':4},'research_execution_attempts':{'total':20,'normal':12,'reserve':8},
                     'lean_submission_attempts':{'total':16,'normal':8,'reserve':8}},'usage':{}}
def joint(project=931001,name='independent-joint',retries=0):
    raw={'schema_version':2,'plan_id':name,'scope':'engineering','project_id':project,'source_manifest_hash':'a'*64,'deployment_hash':'b'*64,
      'request_mode':'symbol_resolution','request_template':{'dataset':'US Equities','fields':['close','volume'],'start':'2018-01-01T00:00:00-05:00',
        'end':'2019-01-01T00:00:00-05:00','data_version':'independent-parent-v1','universe_hash':'c'*64,'normalization':'raw','timezone':'America/New_York'},
      'symbol_resolution':{'tickers':['AAPL','MSFT'],'as_of':'2019-01-01T00:00:00-05:00','method':'QuantBook.add_equity/as-of fixed fixture'},
      'observation_window':{'start':'2018-01-03T00:00:00-05:00','end_exclusive':'2018-02-01T00:00:00-05:00'},
      'required_checks':{'research':['raw_data_received','collection_windows_completed','collection_cache_only_replay','collection_nonempty'],
                         'lean':['no_orders']},'max_retries':{'research':retries,'lean':retries},
      'report_namespace':'independent/joint','orders_enabled':False,'financial_metrics_enabled':False,'economic_factor':None,'economic_model':None,
      'collection_probe':{'field_catalog':deepcopy(CAT),'collection_plan':{'schema_version':1,'plan_id':'independent-child','scope':'engineering',
          'source':'quantconnect_fundamental_universe','data_version':'independent-child-v1','start':'2018-01-01T00:00:00-05:00',
          'end_exclusive':'2018-02-10T00:00:00-05:00','timezone':'America/New_York','fields':list(CAT),'calendar_days_per_request':1,
          'max_batch_records':1000,'max_records_per_window':50000,'source_manifest_hash':'a'*64}}}
    return EngineeringTaskPlan.from_dict(raw,discovered_project_ids=[project],probe_field_catalog=CAT)
def setup():
    registry=Registry(MemoryArtifactStore(),budget());bridge=EngineeringTaskBridge(registry,joint());bridge.register();return registry,bridge
OBS={};COMMANDS=[]
def cli(case,*args):
    cmd=[sys.executable,'-B',str(case/'tools/stage2.py'),*map(str,args)]
    result=subprocess.run(cmd,cwd=case,text=True,encoding='utf-8',capture_output=True,timeout=40,
        env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1'))
    COMMANDS.append({'command':cmd,'returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr})
    return result

class JointProbes(unittest.TestCase):
    def test_direct_registry_wrong_operation_must_not_charge_joint_task(self):
        r,b=setup();before=r.snapshot()['usage'];error=None;attempt=None
        try:attempt=r.begin_attempt(b.config_id,'research',operation_key='independent-arbitrary-operation')
        except RegistryError as e:error=str(e)
        OBS['wrong_operation']={'attempt':None if attempt is None else vars(attempt),'before':before,'after':r.snapshot()['usage'],'error':error}
        self.assertIsNotNone(error,'A v2 operation outside the fixed parent operation was admitted and charged')
        self.assertEqual(r.snapshot()['usage'],before)

    def test_direct_registry_lean_requires_parent_research_before_debit(self):
        r,b=setup();before=r.snapshot()['usage'];error=None;attempt=None
        try:attempt=r.begin_attempt(b.config_id,'lean',operation_key=b._operation('lean'))
        except RegistryError as e:error=str(e)
        OBS['premature_lean']={'attempt':None if attempt is None else vars(attempt),'before':before,'after':r.snapshot()['usage'],'error':error}
        self.assertIsNotNone(error,'LEAN was granted/charged before any completed parent Research')
        self.assertEqual(r.snapshot()['usage'],before)

    def test_direct_registry_respects_joint_max_retry_zero(self):
        r,b=setup();a=b.claim('research');r.fail(a,'independent known failure');before=r.snapshot()['usage'];error=None;retry=None
        try:retry=r.begin_attempt(b.config_id,'research',operation_key=b._operation('research'),retry_of=a.attempt_id,reason='independent repair')
        except RegistryError as e:error=str(e)
        OBS['zero_retry']={'attempt':None if retry is None else vars(retry),'before':before,'after':r.snapshot()['usage'],'error':error,
                           'bridge_payload_usable':None if retry is None else b.payload(retry)}
        self.assertIsNotNone(error,'A max_retries=0 joint plan obtained an additional fixed-operation execution')
        self.assertEqual(r.snapshot()['usage'],before)

    def test_bridge_lean_guard_is_positive_control(self):
        r,b=setup();before=r.snapshot()['usage']
        with self.assertRaises(EngineeringTaskError):b.claim('lean')
        self.assertEqual(r.snapshot()['usage'],before)

    def test_bridge_retry_guard_is_positive_control(self):
        r,b=setup();a=b.claim('research');r.fail(a,'known synthetic failure');before=r.snapshot()['usage']
        with self.assertRaises(EngineeringTaskError):b.claim('research',retry_of=a.attempt_id,reason='known repair')
        self.assertEqual(r.snapshot()['usage'],before)

    def test_valid_parent_claim_and_reuse_are_single_charged_control(self):
        r,b=setup();a=b.claim('research');again=b.claim('research')
        self.assertTrue(a.should_execute);self.assertFalse(again.should_execute);self.assertEqual(a.attempt_id,again.attempt_id)
        self.assertEqual(r.snapshot()['usage']['research']['total'],1)

    def test_legacy_freeze_must_not_replace_pending_project_pointer(self):
        case=RUN/'source';shutil.copytree(SOURCE,case,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        active=json.loads((case/'config/quantconnect.json').read_text(encoding='utf-8'))['active_project_id']
        listing=case/'synthetic-projects.json';listing.write_bytes(canonical_json({'success':True,'projects':[{'projectId':active}]}))
        pointer=case/'audit/engineering_current.json';before=pointer.read_bytes()
        joint_result=cli(case,'freeze','--plan-file','config/engineering_joint_pilot.json','--projects-file',listing)
        self.assertNotEqual(joint_result.returncode,0,joint_result.stdout)
        self.assertIn('Unresolved engineering work',joint_result.stderr)
        self.assertEqual(pointer.read_bytes(),before)
        legacy=cli(case,'freeze','--plan-file','config/engineering.json','--projects-file',listing)
        after=pointer.read_bytes()
        OBS['legacy_freeze']={'joint_returncode':joint_result.returncode,'legacy_returncode':legacy.returncode,
            'pointer_changed':before!=after,'before':json.loads(before),'after':json.loads(after),
            'ledger_bytes_changed':(case/'audit/runtime/registry/events.jsonl').read_bytes()!=(SOURCE/'audit/runtime/registry/events.jsonl').read_bytes()}
        self.assertNotEqual(legacy.returncode,0,'Legacy freeze bypassed pending protection and replaced the current pointer')
        self.assertEqual(after,before)

def main():
    stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(JointProbes))
    output=stream.getvalue();(ROOT/'quick_first_output.txt').write_text(output,encoding='utf-8')
    def name(t):return t.id()
    data={'source_commit':'8f7236ecbafcb514f07a6af4150a5afdbc1fd474','methods':result.testsRun,'passed_methods':result.testsRun-len(result.failures)-len(result.errors),
        'failed_methods':len(result.failures),'error_methods':len(result.errors),'skipped':len(result.skipped),'subcases':0,
        'failures':[{'method':name(t),'traceback':tb} for t,tb in result.failures],
        'errors':[{'method':name(t),'traceback':tb} for t,tb in result.errors],'observations':OBS,
        'command':[sys.executable,'-B',str(Path(__file__).resolve())],'script_sha256':sha256(Path(__file__).read_bytes()).hexdigest(),
        'actual_external_calls':0,'author_fixture_imports':False,'exit_code':0 if result.wasSuccessful() else 1}
    (ROOT/'quick_first_results.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (ROOT/'quick_command_log.json').write_text(json.dumps(COMMANDS,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(output);print(json.dumps({k:data[k] for k in ['methods','passed_methods','failed_methods','error_methods','exit_code']}))
    return data['exit_code']
if __name__=='__main__':raise SystemExit(main())
