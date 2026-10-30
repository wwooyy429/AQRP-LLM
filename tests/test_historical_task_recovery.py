"""Historical metadata recovery only; no real data, provider or cloud dispatch.

The immutable round009 plan/receipts contain permitted engineering metadata.
Registry exercises use an isolated in-memory copy, never the real ledger.
"""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'cloud'), str(ROOT / 'tools'), str(ROOT / 'tests')]
from qresearch.artifacts import MemoryArtifactStore, canonical_json, content_hash
from qresearch.collection import CollectionError, HistoricalCollectionPlan
from qresearch.collection_storage import (StableCollectionCache, processing_contract_sha256,
    validate_storage_policy, validate_storage_policy_structure)
from qresearch.engineering_tasks import EngineeringTaskPlan, EngineeringTaskBridge
from qresearch.engineering_receipts import ReceiptParseError, research_observation
from qresearch.registry import Registry
from qresearch.task_followup import TaskFollowupController
import qresearch.engineering_data as worker
import stage2
from test_engineering_rounds import context, documents, package

PLAN = '6a875a9e894baaae251fe6304e38bfb95d05c173235b111ba4175ccd79ea997b'
CONFIG = '64e7ef0354b78b69d97bd97b5e2a0210c0545bf08c921b53fbde98f6a0f2810a'
RESEARCH = '44eda8401c554e0b87bc01598169c919'
LEAN = '11147fc5a7ac4f6c951a86d021d069b2'
OLD_CONTRACT = '5ef61ef75f80ee7de0abcfd5461896a427a20d4c621d10759855b4cd11468219'


class HistoricalTaskRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frozen = json.loads((ROOT / 'audit/runtime/engineering/frozen-plans' / (PLAN+'.json')).read_bytes())
        cls.baseline = json.loads((ROOT/'audit/runtime/registry/baseline.json').read_bytes())
        cls.original = {path.relative_to(ROOT/'audit/runtime').as_posix():path.read_bytes()
            for path in (ROOT/'audit/runtime').rglob('*')
            if path.is_file() and not {'.locks','.staging'} & set(path.parts)}

    def historical(self, raw=None):
        return EngineeringTaskPlan.from_dict(deepcopy(self.frozen if raw is None else raw),
            discovered_project_ids=(38436695,),historical_decode=True)

    def copied_registry(self):
        store=MemoryArtifactStore();store._data.update(self.original)
        return store,Registry(store,self.baseline)

    def assert_no_writes(self,store,operation):
        before=dict(store._data)
        with self.assertRaises((ValueError,CollectionError)):
            operation()
        self.assertEqual(store._data,before)

    def test_original_real_plan_hash_survives_but_default_decoder_stays_strict(self):
        plan=self.historical()
        self.assertEqual(plan.hash,PLAN)
        self.assertEqual(content_hash({'engineering_task_schema_version':1,'plan':plan.to_dict()}),CONFIG)
        self.assertEqual(plan.to_dict(),self.frozen)
        self.assertEqual(plan.to_dict()['storage_policy']['collection_cache']['processing_contract_sha256'],OLD_CONTRACT)
        self.assertNotEqual(processing_contract_sha256(),OLD_CONTRACT)
        with self.assertRaises(CollectionError):
            EngineeringTaskPlan.from_dict(self.frozen,discovered_project_ids=(38436695,))

    def test_no_document_switch_and_nonboolean_python_selection_reject(self):
        for name in ('historical_decode','historical','skip_processing_check'):
            with self.subTest(name=name),self.assertRaises(ValueError):
                self.historical(self.frozen|{name:True})
        for selection in (1,0,None,'true'):
            with self.subTest(selection=selection),self.assertRaises(ValueError):
                EngineeringTaskPlan.from_dict(self.frozen,discovered_project_ids=(38436695,),historical_decode=selection)

    def test_historical_decode_keeps_all_structural_and_provenance_guards(self):
        for edit in (lambda d:d.update(orders_enabled=True),
                lambda d:d['storage_policy']['capacity']['lean'].update(required_bytes=1),
                lambda d:d['storage_policy']['collection_cache']['legacy'].update(processing_contract_sha256='0'*64),
                lambda d:d['storage_policy']['collection_cache']['legacy'].update(plan_hash='0'*64),
                lambda d:d['storage_policy']['collection_cache']['legacy']['receipt_ref'].update(key='../private.json'),
                lambda d:d['storage_policy']['collection_cache'].update(extra=True),
                lambda d:d['collection_probe']['collection_plan'].update(source_manifest_hash='0'*64)):
            changed=deepcopy(self.frozen);edit(changed)
            with self.subTest(edit=edit),self.assertRaises(ValueError):self.historical(changed)

    def test_structural_cache_decoder_grants_no_cache_or_worker_compatibility(self):
        document=self.historical().to_dict();probe=document['collection_probe']
        child=HistoricalCollectionPlan.from_dict(probe['collection_plan'],field_catalog=probe['field_catalog'])
        policy=document['storage_policy']['collection_cache']
        self.assertEqual(validate_storage_policy_structure(policy,child),policy)
        with self.assertRaises(CollectionError):validate_storage_policy(policy,child)
        store=MemoryArtifactStore();before=dict(store._data)
        with self.assertRaises(CollectionError):StableCollectionCache(store,child,policy,synthetic=True)
        self.assertEqual(store._data,before)
        payload=json.loads((ROOT/'audit/runtime/engineering/admitted-inputs'/(RESEARCH+'.json')).read_bytes())['payload']
        with self.assertRaises(CollectionError):worker._context(payload,'research')

    def test_real_metadata_registry_replays_and_old_attempt_bridge_recovers_without_writes(self):
        store,registry=self.copied_registry();before=dict(store._data)
        snapshot=registry.snapshot()
        self.assertTrue(any(item['attempt_id']==LEAN for item in snapshot['attempts']))
        bridge=stage2.bridge_for_attempt(LEAN,registry=registry)
        self.assertEqual(bridge.plan.hash,PLAN)
        self.assertEqual(bridge.config_id,CONFIG)
        self.assertEqual(bridge.payload(LEAN)['identity']['attempt_id'],LEAN)
        admission=stage2.admitted_input(bridge,LEAN)
        self.assertEqual(admission['payload']['plan'],self.frozen)
        self.assertEqual(store._data,before)

    def test_real_research_receipt_parses_original_context_and_replays_settlement_idempotently(self):
        store,registry=self.copied_registry();before=dict(store._data)
        bridge=stage2.bridge_for_attempt(RESEARCH,registry=registry)
        admission=stage2.admitted_input(bridge,RESEARCH)
        binding=stage2._read_research_dispatch(bridge,admission['payload'],admission['deployment'],require_dispatch=True)
        native=json.loads((ROOT/'audit/review_packages/live009/research_native_execution.json').read_bytes())
        observed=research_observation(admission['payload'],admission['deployment'],native,
            dispatch_binding=binding,dispatch_required=True)
        self.assertEqual(observed['completion']['cloud_report'],registry.read_result(RESEARCH)['cloud_report'])
        settled=stage2.settle_research_result(bridge,RESEARCH,native)
        self.assertEqual(settled.status,'completed')
        self.assertFalse(settled.should_execute)
        self.assertEqual(store._data,before)

    def test_historical_receipt_still_rejects_identity_or_admitted_input_tampering(self):
        store,registry=self.copied_registry();bridge=stage2.bridge_for_attempt(RESEARCH,registry=registry)
        admission=stage2.admitted_input(bridge,RESEARCH)
        native=json.loads((ROOT/'audit/review_packages/live009/research_native_execution.json').read_bytes())
        payload=deepcopy(admission['payload']);payload['identity']['plan_hash']='0'*64
        with self.assertRaises(ReceiptParseError):
            research_observation(payload,admission['deployment'],native)
        key='engineering/admitted-inputs/'+RESEARCH+'.json'
        altered=json.loads(store._data[key]);altered['payload']['report_key']='synthetic/changed.json'
        store._data[key]=canonical_json(altered)
        with self.assertRaises(ValueError):stage2.admitted_input(bridge,RESEARCH)

    def test_historical_plan_objects_cannot_register_claim_or_directly_charge_new_work(self):
        store,registry=context();plan=self.historical();bridge=EngineeringTaskBridge(registry,plan)
        self.assert_no_writes(store,lambda:bridge.register())
        self.assert_no_writes(store,lambda:registry.register_config(bridge.package))
        # Simulate the old runtime in this isolated synthetic Registry only.
        with patch('qresearch.collection_storage.processing_contract_sha256',return_value=OLD_CONTRACT):
            bridge.register()
        self.assert_no_writes(store,lambda:bridge.register())
        self.assert_no_writes(store,lambda:bridge.claim('research'))
        self.assert_no_writes(store,lambda:registry.begin_attempt(bridge.config_id,'research',
            operation_key='engineering-plan:'+PLAN+':research'))
        self.assertEqual(registry.snapshot()['usage']['research']['total'],0)

    def test_all_closed_bridge_kinds_register_through_their_own_schema(self):
        # Module aliases avoid exposing imported TestCase classes to discovery.
        import test_engineering_receipts as engineering_fixture
        import test_collection_tasks as collection_fixture
        import test_certification_tasks as certification_fixture
        from qresearch.collection_tasks import CollectionTaskBridge
        from qresearch.certification_tasks import CertificationTaskBridge
        certification_fixture.fixture_data.DataCertificationTests.setUpClass()
        for kind in ('engineering','historical_collection','data_certification'):
            with self.subTest(kind=kind):
                _,registry=context()
                allocation='normal'
                if kind=='engineering':
                    raw=engineering_fixture.context('research')[0]['plan']
                    plan=EngineeringTaskPlan.from_dict(raw,discovered_project_ids=(17,))
                    bridge=EngineeringTaskBridge(registry,plan)
                elif kind=='historical_collection':
                    bridge=CollectionTaskBridge(registry,collection_fixture.plan())
                else:
                    bridge=CertificationTaskBridge(registry,certification_fixture.plan())
                    certification_fixture.authorize(registry,bridge.package)
                    allocation='reserve'
                config_id=bridge.register(allocation=allocation)
                self.assertEqual(config_id,bridge.config_id)
                self.assertEqual(registry.snapshot()['usage']['configurations']['total'],1)
                self.assertEqual(registry.snapshot()['usage']['research']['total'],0)
                self.assertEqual(registry.snapshot()['usage']['lean']['total'],0)

    def test_new_round_authorization_and_binding_cannot_admit_historical_contract(self):
        store,registry=context();plan=self.historical();old={'engineering_task_schema_version':1,'plan':plan.to_dict()}
        grant,authority=documents(registry,project=38436695,limits={'configurations':2,'research':1,'lean':1})
        self.assert_no_writes(store,lambda:registry.authorize_engineering_round(grant,[old],authority))
        current=package('current-no-storage',project=38436695)
        registry.authorize_engineering_round(grant,[current],authority)
        self.assert_no_writes(store,lambda:registry.bind_engineering_configuration(grant['round_id'],old))

    def test_old_followup_status_decodes_pinned_submission_without_dispatch_or_writes(self):
        store,registry=self.copied_registry();before=dict(store._data)
        controller=TaskFollowupController(registry,json.loads((ROOT/'config/task_followup.json').read_bytes()))
        status=controller.status(LEAN)
        self.assertEqual(status['attempt_id'],LEAN)
        self.assertEqual(status['backtest_id'],'6347a33efc37e761f486f982e804dbac')
        self.assertFalse(status['should_execute'])
        self.assertEqual(store._data,before)


if __name__=='__main__':unittest.main()
