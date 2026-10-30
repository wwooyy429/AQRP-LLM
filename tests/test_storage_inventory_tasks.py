"""Synthetic inventory charging/source/native boundaries; no QC or market data."""
from copy import deepcopy
from hashlib import sha256
import base64
import json
from pathlib import Path
import sys
import unittest
import zlib

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'cloud'),str(ROOT/'tools')]
from qresearch.artifacts import MemoryArtifactStore,canonical_json,content_hash
from qresearch.budget_cycles import authorization_reference
from qresearch.registry import Registry,RegistryError,BudgetExceeded,CorruptRegistry
from qresearch.storage_inventory import LIMITS,run_inventory
from qresearch.storage_inventory_tasks import (InventoryTaskPlan,InventoryTaskBridge,prepare_input,
    admitted_input,cell_source,reserve_dispatch,stdout_marker,native_observation,settle_result,
    MARKER,PREFIX)
from qresearch.engineering_receipts import ReceiptParseError


def raw_plan():
    return {'schema_version':1,'task_kind':'object_store_inventory','scope':'engineering',
        'plan_id':'synthetic-inventory','project_id':17,'source_manifest_hash':'a'*64,'worker_sha256':'a'*64,
        'inventory_policy':{'schema_version':1,'metadata_keys':[],**LIMITS},'max_retries':0,
        'final_test_enabled':False,'orders_enabled':False,'market_history_enabled':False}


def make_registry():
    store=MemoryArtifactStore()
    registry=Registry(store,{k:{'normal':4,'reserve':4,'total':8} for k in ('configurations','research','lean')})
    cycle={'schema_version':1,'cycle_id':'SYNTHETIC-inventory-cycle',
        'previous_state_hash':registry.configuration_cycle_snapshot()['state_hash'],
        'capacity':registry.limits['configurations'],'final_test_enabled':False,'extra_spend_usd':0}
    auth=deepcopy(cycle)|{'authority_kind':'explicit_human_user_message','scope':'configuration_cycle_reset_v1',
        'request_text':'Synthetic fixture cycle only, no actual user authorization'}
    cycle['authorization_ref']=authorization_reference(auth)
    registry.authorize_configuration_cycle(cycle,auth)
    return registry


def authorization(registry,package,*,limits=None,allocation='normal'):
    grant={'schema_version':2,'round_id':'SYNTHETIC-inventory-round','project_id':17,'allocation':allocation,
        'limits':limits or {'configurations':1,'research':1,'lean':0},'configuration_cycle_id':'SYNTHETIC-inventory-cycle',
        'final_test_enabled':False,'extra_spend_usd':0}
    auth=deepcopy(grant)|{'authority_kind':'explicit_human_user_message',
        'scope':'stage2_normal_allocation_exception' if allocation=='normal' else 'stage2_engineering_round',
        'global_limits_hash':content_hash(registry.limits),'request_text':'Synthetic explicit one read-only inventory'}
    if allocation=='normal':auth['normal_allocation_approval']={'direct_request':auth['request_text']}
    digest=content_hash(auth)
    grant['authorization_ref']={'key':'engineering/rounds/user-authorizations/'+digest+'.json','sha256':digest}
    return registry.authorize_engineering_round(grant,[package],auth)


class Event:
    def __init__(self):self.handlers=[]
    def __iadd__(self,callback):self.handlers.append(callback);return self
    def __isub__(self,callback):self.handlers.remove(callback);return self


class EmptyCloudStore:
    max_size=1048576
    max_files=1000
    keys=[]
    def __init__(self):self.error_raised=Event()
    def contains_key(self,key):raise AssertionError('No object expected in empty fixture')
    def get_file_path(self,key):raise AssertionError('Must not materialize missing data')
    def read_bytes(self,key):raise AssertionError('No payload expected in empty fixture')
    def save(self,*args):raise AssertionError('Writes forbidden')
    delete=save
    clear=save


class InventoryTaskTests(unittest.TestCase):
    def setUp(self):
        self.registry=make_registry();self.store=self.registry.store
        self.plan=InventoryTaskPlan.from_dict(raw_plan(),discovered_project_ids=[17])
        self.bridge=InventoryTaskBridge(self.registry,self.plan)
        authorization(self.registry,self.bridge.package)
        self.bridge.register();self.attempt=self.bridge.claim()
        self.admission=prepare_input(self.bridge,self.attempt);self.payload=self.admission['payload']

    def bind(self,index=3):
        source=cell_source(self.payload)
        envelope={'tool_name':'mcp__quantconnect__jupyter_read_cell','arguments':{'projectId':17,'index':index},
            'result':{'structuredContent':{'cellType':'code','source':source.splitlines(keepends=True)}}}
        return reserve_dispatch(self.bridge,self.attempt,envelope)

    def report(self):
        return run_inventory(EmptyCloudStore(),self.payload['plan']['inventory_policy'],self.payload['identity'])

    def envelope(self,*,report=None,index=3):
        return {'tool_name':'mcp__quantconnect__jupyter_execute_cell','arguments':{'projectId':17,'index':index},
            'result':{'structuredContent':{'status':'ok','success':True,'cell_index':index,
                'outputs':[{'output_type':'stream','name':'stdout','text':stdout_marker(self.report() if report is None else report,self.payload)+'\n'}]}}}

    def reject_no_change(self,action,errors=(ValueError,RegistryError)):
        before=deepcopy(self.store._data)
        with self.assertRaises(errors):action()
        self.assertEqual(self.store._data,before)

    def test_precharge_known_answer_native_completion_and_replay(self):
        usage=self.registry.snapshot()['usage']
        self.assertEqual((usage['configurations']['total'],usage['research']['total'],usage['lean']['total']),(1,1,0))
        self.assertTrue(self.bind()['should_execute'])
        result=settle_result(self.bridge,self.attempt,self.envelope())
        self.assertEqual(result.status,'completed')
        saved=self.bridge.read_result(result)
        self.assertEqual(saved['report']['capacity_before']['used_size_bytes'],0)
        self.assertFalse(saved['report']['retention']['global_reference_closure'])
        self.assertFalse(saved['financial_evidence'])
        before=deepcopy(self.store._data)
        self.assertEqual(settle_result(self.bridge,self.attempt,self.envelope()).status,'completed')
        self.assertEqual(self.store._data,before)
        reopened=Registry(self.store,{k:{'normal':4,'reserve':4,'total':8} for k in ('configurations','research','lean')})
        self.assertEqual(reopened.snapshot(),self.registry.snapshot())

    def test_unknown_execution_stays_charged_and_cannot_redispatch(self):
        self.assertTrue(self.bind()['should_execute'])
        before=self.registry.snapshot()['usage']
        self.reject_no_change(lambda:settle_result(self.bridge,self.attempt,{'tool_name':'mcp__quantconnect__jupyter_execute_cell',
            'arguments':{'projectId':17,'index':3},'result':{'isError':True,'content':[{'type':'text','text':'Transport lost'}]}}))
        self.assertFalse(self.bind()['should_execute'])
        self.assertFalse(self.bridge.claim().should_execute)
        self.assertEqual(self.registry.snapshot()['usage'],before)

    def test_public_lifecycle_cannot_forge_native_completion_failure_or_pending(self):
        for action in (lambda:self.registry.complete(self.attempt,{'status':'completed'}),
                       lambda:self.registry.fail(self.attempt,{'failure_code':'invented'}),
                       lambda:self.registry.pending(self.attempt,external_id='qc-inventory:17:'+self.attempt.attempt_id)):
            with self.subTest(action=action):self.reject_no_change(action)

    def test_native_error_is_failure_without_private_diagnostics_in_registry(self):
        self.bind()
        error={'output_type':'error','ename':'ValueError','evalue':'PRIVATE_VALUE_482',
            'traceback':['Traceback PRIVATE_VALUE_482','ValueError: PRIVATE_VALUE_482']}
        envelope={'tool_name':'mcp__quantconnect__jupyter_execute_cell','arguments':{'projectId':17,'index':3},
            'result':{'isError':True,'structuredContent':error}}
        result=settle_result(self.bridge,self.attempt,envelope)
        self.assertEqual(result.status,'failed')
        self.assertNotIn('PRIVATE_VALUE_482',str(self.store._data))
        self.assertEqual(self.registry.snapshot()['usage']['research']['total'],1)
        self.assertEqual(settle_result(self.bridge,self.attempt,envelope).status,'failed')

    def test_zero_retries_rejects_even_direct_registry_retry(self):
        self.bind()
        report=self.report();report['status']='failed';report['failure_codes']=['sdk_error']
        report['metadata_observation_stable']=False
        settle_result(self.bridge,self.attempt,self.envelope(report=report))
        self.reject_no_change(lambda:self.registry.begin_attempt(self.bridge.config_id,'research',
            operation_key='object-store-inventory:'+self.plan.hash+':research',retry_of=self.attempt.attempt_id,reason='retry'))

    def test_wrong_operation_stage_and_allocation_rejected_before_charge(self):
        for stage,operation,allocation in [('lean','object-store-inventory:'+self.plan.hash+':research','normal'),
                ('research','another-op','normal'),('research','object-store-inventory:'+self.plan.hash+':research','reserve')]:
            with self.subTest(stage=stage,operation=operation,allocation=allocation):
                self.reject_no_change(lambda:self.registry.begin_attempt(self.bridge.config_id,stage,allocation,operation_key=operation))

    def test_explicit_inventory_grant_required_and_no_generic_kind_downgrade(self):
        registry=make_registry();before=deepcopy(registry.store._data)
        with self.assertRaises(BudgetExceeded):registry.register_config(self.bridge.package)
        self.assertEqual(registry.store._data,before)
        for changes in ({'task_kind':'historical_collection'},{'task_kind':'generic'},{'scope':'research'}):
            package=deepcopy(self.bridge.package);package['plan'].update(changes)
            before=deepcopy(registry.store._data)
            with self.subTest(changes=changes),self.assertRaises((ValueError,RegistryError)):registry.register_config(package)
            self.assertEqual(registry.store._data,before)
        package=deepcopy(self.bridge.package);package.pop('engineering_task_schema_version')
        with self.assertRaises(ValueError):registry.register_config(package)

    def test_wrong_grant_shape_rejected_without_reserving_or_charging(self):
        for limits,allocation in [({'configurations':1,'research':2,'lean':0},'normal'),
                                  ({'configurations':1,'research':1,'lean':1},'normal'),
                                  ({'configurations':1,'research':1,'lean':0},'reserve')]:
            registry=make_registry();before=deepcopy(registry.store._data)
            with self.subTest(limits=limits,allocation=allocation),self.assertRaises((ValueError,RegistryError)):
                authorization(registry,self.bridge.package,limits=limits,allocation=allocation)
            self.assertEqual(registry.store._data,before)

    def test_discovered_projects_hashes_and_closed_plan_fields(self):
        for changes in ({'project_id':True},{'project_id':18},{'max_retries':1},{'max_retries':False},
                {'worker_sha256':'b'*64},{'final_test_enabled':0},{'orders_enabled':True},
                {'market_history_enabled':True},{'unrestricted_payload':[]}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                InventoryTaskPlan.from_dict(raw_plan()|changes,discovered_project_ids=[17])

    def test_actual_cell_source_and_project_are_required(self):
        source=cell_source(self.payload)
        base={'tool_name':'mcp__quantconnect__jupyter_read_cell','arguments':{'projectId':17,'index':3},
            'result':{'structuredContent':{'cellType':'code','source':source.splitlines(keepends=True)}}}
        mutations=[]
        changed=deepcopy(base);changed['arguments']['projectId']=18;mutations.append(changed)
        changed=deepcopy(base);changed['result']['structuredContent']['source'][0]+='# altered';mutations.append(changed)
        changed=deepcopy(base);changed['result']['structuredContent']['rows']=[{'private':1}];mutations.append(changed)
        changed=deepcopy(base);changed['arguments']['index']=True;mutations.append(changed)
        for envelope in mutations:
            with self.subTest(envelope=envelope):self.reject_no_change(lambda:reserve_dispatch(self.bridge,self.attempt,envelope))

    def test_changed_cell_binding_cannot_gain_second_dispatch(self):
        first=self.bind();self.assertTrue(first['should_execute'])
        self.assertFalse(self.bind()['should_execute'])
        self.reject_no_change(lambda:self.bind(index=4))

    def test_execute_wrong_index_or_project_rejected(self):
        self.bind()
        for project,index in [(18,3),(17,4),(17,True)]:
            value=self.envelope(index=3);value['arguments']={'projectId':project,'index':index}
            with self.subTest(project=project,index=index):self.reject_no_change(lambda:settle_result(self.bridge,self.attempt,value))

    def test_extra_stdout_stderr_display_and_rows_are_rejected(self):
        self.bind()
        for output in [{'output_type':'stream','name':'stdout','text':'private'},
                       {'output_type':'stream','name':'stderr','text':'private'},
                       {'output_type':'display_data','data':{'text/plain':'private'}},
                       {'rows':[{'private':1}]}]:
            envelope=self.envelope();envelope['result']['structuredContent']['outputs'].append(output)
            with self.subTest(output=output):self.reject_no_change(lambda:settle_result(self.bridge,self.attempt,envelope))

    def test_wrong_report_identity_extra_rows_and_retention_changes_rejected(self):
        self.bind()
        for mutation in ('identity','rows','retention'):
            report=self.report()
            if mutation=='identity':report['identity']['attempt_id']='b'*32
            elif mutation=='rows':report['rows']=[{'private':1}]
            else:report['retention']['safe_deletion_authorized']=True
            wire=MARKER+base64.b64encode(zlib.compress(canonical_json(report))).decode()
            envelope=self.envelope();envelope['result']['structuredContent']['outputs'][0]['text']=wire
            with self.subTest(mutation=mutation):self.reject_no_change(lambda:settle_result(self.bridge,self.attempt,envelope))

    def test_compressed_bomb_and_concatenated_wire_are_rejected(self):
        self.bind()
        valid=zlib.compress(canonical_json(self.report()))
        for raw in (valid+b'garbage',valid+valid,zlib.compress(b'x'*(LIMITS['max_report_bytes']+1))):
            envelope=self.envelope();envelope['result']['structuredContent']['outputs'][0]['text']=MARKER+base64.b64encode(raw).decode()
            with self.subTest(bytes=len(raw)):self.reject_no_change(lambda:settle_result(self.bridge,self.attempt,envelope))

    def test_conflicting_mirrored_native_carriers_rejected(self):
        self.bind();envelope=self.envelope();envelope['result']['content']=[{'type':'text','text':'{"status":"ok","outputs":[]}'}]
        self.reject_no_change(lambda:settle_result(self.bridge,self.attempt,envelope))

    def test_later_native_result_cannot_replace_original_proof(self):
        self.bind();settle_result(self.bridge,self.attempt,self.envelope())
        other=self.envelope();other['result']['structuredContent']['execution_count']=2
        self.reject_no_change(lambda:settle_result(self.bridge,self.attempt,other),errors=(ValueError,RegistryError,FileExistsError))

    def test_proof_tamper_fails_registry_replay(self):
        self.bind();settle_result(self.bridge,self.attempt,self.envelope())
        key=PREFIX+'native-receipts/'+self.attempt.attempt_id+'.json'
        proof=json.loads(self.store._data[key]);proof['native_arguments']['index']=4
        self.store._data[key]=canonical_json(proof)
        with self.assertRaises(CorruptRegistry):self.registry.snapshot()

    def test_plan_and_original_admission_are_immutable(self):
        raw=self.plan.to_dict();raw['inventory_policy']['metadata_keys'].append('not-allowed')
        self.assertEqual(self.plan.to_dict()['inventory_policy']['metadata_keys'],[])
        prepared=prepare_input(self.bridge,self.attempt)
        self.assertEqual(prepared,self.admission)
        key=PREFIX+'admissions/'+self.attempt.attempt_id+'.json'
        value=json.loads(self.store._data[key]);value['cell_source_sha256']='f'*64
        self.store._data[key]=canonical_json(value)
        with self.assertRaises(ValueError):admitted_input(self.bridge,self.attempt)

    def test_native_carrier_depth_and_size_are_bounded_before_parsing(self):
        self.bind()
        deep='text'
        for _ in range(70):deep=[deep]
        for result in (deep,{'text':'x'*2097153}):
            envelope={'tool_name':'mcp__quantconnect__jupyter_execute_cell',
                'arguments':{'projectId':17,'index':3},'result':result}
            with self.subTest(kind=type(result).__name__):
                self.reject_no_change(lambda:settle_result(self.bridge,self.attempt,envelope))

    def test_duplicate_native_error_mirrors_match_but_mixed_output_rejected(self):
        self.bind()
        error={'output_type':'error','ename':'ValueError','evalue':'PRIVATE_NATIVE_VALUE',
            'traceback':['ValueError: PRIVATE_NATIVE_VALUE']}
        envelope={'tool_name':'mcp__quantconnect__jupyter_execute_cell','arguments':{'projectId':17,'index':3},
            'result':{'isError':True,'content':[{'type':'text','text':json.dumps(error)},
                                             {'type':'text','text':json.dumps(error)}]}}
        mixed=deepcopy(envelope);mixed['result']['content'][1]['text']='extra private'
        self.reject_no_change(lambda:settle_result(self.bridge,self.attempt,mixed))
        self.assertEqual(settle_result(self.bridge,self.attempt,envelope).status,'failed')
        self.assertNotIn('PRIVATE_NATIVE_VALUE',str(self.store._data))

    def test_native_error_wrapper_forms_settle_same_attempt_without_text_export(self):
        error={'output_type':'error','ename':'ValueError','evalue':'PRIVATE_WRAPPED_ERROR',
            'traceback':['Traceback PRIVATE_WRAPPED_ERROR','ValueError: PRIVATE_WRAPPED_ERROR']}
        shapes=[{'outputs':[error]}, {'status':'error','outputs':[error],'cell_index':3},
                {'result':{'outputs':[error]},'success':False},
                {'type':'text','text':json.dumps({'outputs':[error]})}]
        for shape in shapes:
            for tool_error in (True,False):
                with self.subTest(shape=shape,tool_error=tool_error):
                    registry=make_registry();bridge=InventoryTaskBridge(registry,self.plan)
                    authorization(registry,bridge.package);bridge.register();attempt=bridge.claim()
                    payload=prepare_input(bridge,attempt)['payload'];source=cell_source(payload)
                    reserve_dispatch(bridge,attempt,{'tool_name':'mcp__quantconnect__jupyter_read_cell',
                        'arguments':{'projectId':17,'index':3},'result':{'structuredContent':{'cellType':'code','source':source.splitlines(keepends=True)}}})
                    result=settle_result(bridge,attempt,{'tool_name':'mcp__quantconnect__jupyter_execute_cell',
                        'arguments':{'projectId':17,'index':3},'result':{'isError':tool_error,'structuredContent':shape}})
                    self.assertEqual(result.status,'failed')
                    self.assertEqual(result.attempt_id,attempt.attempt_id)
                    self.assertNotIn('PRIVATE_WRAPPED_ERROR',str(registry.store._data))
                    self.assertEqual(registry.snapshot()['usage']['research']['total'],1)

    def test_error_wrappers_with_extra_outputs_or_contradictory_metadata_rejected(self):
        self.bind();error={'output_type':'error','ename':'ValueError','evalue':'private','traceback':['private']}
        for shape in [
            {'outputs':[error,{'output_type':'stream','name':'stdout','text':'private'}]},
            {'outputs':[error,{'output_type':'stream','name':'stderr','text':'private'}]},
            {'outputs':[error,error]}, {'outputs':[error],'success':True},
            {'outputs':[error],'status':'ok'}, {'outputs':[error],'cell_index':4},
            {'outputs':[error],'rows':[{'private':1}]},
            {'outputs':[error],'metadata':{'private':1}},
        ]:
            envelope={'tool_name':'mcp__quantconnect__jupyter_execute_cell','arguments':{'projectId':17,'index':3},
                'result':{'isError':True,'structuredContent':shape}}
            with self.subTest(shape=shape):self.reject_no_change(lambda:settle_result(self.bridge,self.attempt,envelope))


if __name__=='__main__':unittest.main(verbosity=2)
