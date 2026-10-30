"""Private synthetic revision/cycle/schema4 admission. No external execution."""
from pathlib import Path
import sys, os, json, hashlib, tempfile, unittest, time, multiprocessing as mp, traceback, io
from unittest.mock import patch
from copy import deepcopy
sys.dont_write_bytecode=True
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]/'source'
sys.path[:0]=[str(ROOT/'cloud'),str(ROOT/'tools')]
from qresearch.artifacts import FilesystemArtifactStore, canonical_json, content_hash, decode_events
from qresearch.registry import Registry, RegistryError, BudgetExceeded
from qresearch.budget_cycles import authorization_reference as cycle_auth_ref
from qresearch.budget_revisions import authorization_reference as revision_auth_ref
from qresearch.engineering_tasks import EngineeringTaskPlan, EngineeringTaskBridge
from qresearch.source_limits import validate_source_sizes, SourceLimitError
import stage2

OBS=[]
LIMITS={'configurations':{'normal':2,'reserve':1,'total':3},'research':{'normal':3,'reserve':3,'total':6},'lean':{'normal':3,'reserve':3,'total':6}}
def note(name,**values): OBS.append({'name':name,**values})
def limits(): return deepcopy(LIMITS)
def state_bytes(directory):
    base=Path(directory)
    return {p.relative_to(base).as_posix():p.read_bytes() for p in base.rglob('*') if p.is_file()}
def reg(directory,usage=None):
    return Registry(FilesystemArtifactStore(directory,data_classification='synthetic',lock_timeout=6),limits(),usage=usage)
def cycle_documents(registry,identifier='SYNTHETIC-independent-cycle'):
    cycle={'schema_version':1,'cycle_id':identifier,'previous_state_hash':registry.configuration_cycle_snapshot()['state_hash'],
           'capacity':deepcopy(registry.limits['configurations']),'final_test_enabled':False,'extra_spend_usd':0}
    auth=deepcopy(cycle)|{'authority_kind':'explicit_human_user_message','scope':'configuration_cycle_reset_v1',
                       'request_text':'SYNTHETIC independent test only; no actual human execution authority.'}
    cycle['authorization_ref']=cycle_auth_ref(auth); return cycle,auth
def revision_documents(registry,identifier='SYNTHETIC-one-reserve'):
    new=deepcopy(registry.limits); new['configurations']['reserve']+=1; new['configurations']['total']+=1
    revision={'schema_version':1,'revision_id':identifier,'previous_limits_hash':content_hash(registry.limits),
              'new_limits':new,'final_test_enabled':False,'extra_spend_usd':0}
    auth=deepcopy(revision)|{'authority_kind':'explicit_human_user_message','scope':'configuration_reserve_increment_v1',
          'request_text':'SYNTHETIC independent reserve increment; not real authority.',
          'approval':{'question':'SYNTHETIC allow exactly one reserve configuration?','answer':'批准'}}
    revision['authorization_ref']=revision_auth_ref(auth); return revision,auth
def round_documents(registry,package,identifier='SYNTHETIC-round-1'):
    cycle=registry.configuration_cycle_snapshot()['cycle_id']
    grant={'schema_version':2,'round_id':identifier,'project_id':package['plan']['project_id'],
           'allocation':'normal','limits':{'configurations':1,'research':1,'lean':1},'configuration_cycle_id':cycle,
           'final_test_enabled':False,'extra_spend_usd':0}
    text='SYNTHETIC independent new-cycle normal engineering1/1/1 only; no actual execution approval.'
    auth=deepcopy(grant)|{'authority_kind':'explicit_human_user_message','scope':'stage2_normal_allocation_exception',
          'global_limits_hash':content_hash(registry.limits),'request_text':text,'normal_allocation_approval':{'direct_request':text}}
    digest=content_hash(auth); grant['authorization_ref']={'key':'engineering/rounds/user-authorizations/'+digest+'.json','sha256':digest}
    return grant,auth
def package(project=6501,name='independent-schema4'):
    # Read current production template/catalog, not a developer test fixture.
    raw=json.loads((ROOT/'config/engineering_storage_round008_pilot.json').read_bytes())
    raw.update(plan_id=name,project_id=project,source_manifest_hash='a'*64,deployment_hash='b'*64)
    raw['request_template']['universe_hash']='c'*64
    raw['collection_probe']['collection_plan']['source_manifest_hash']='a'*64
    catalog=json.loads((ROOT/'config/source_catalog.json').read_bytes())['fields']
    raw['collection_probe']['field_catalog']={key:catalog[key] for key in raw['collection_probe']['collection_plan']['fields']}
    frozen=EngineeringTaskPlan.from_dict(raw,discovered_project_ids=[project],probe_field_catalog=catalog)
    return {'engineering_task_schema_version':1,'plan':frozen.to_dict()}
def bridge(registry,full):
    return EngineeringTaskBridge(registry,EngineeringTaskPlan.from_dict(full['plan'],discovered_project_ids=[full['plan']['project_id']]))
def process_action(directory,usage,action,payload,gate,queue):
    try:
        registry=reg(directory,usage); gate.wait(timeout=20)
        if action=='authorize':
            grant,auth,full=payload; result=registry.authorize_engineering_round(grant,[full],auth)
            queue.put({'ok':True,'round_id':result['grant']['round_id']})
        else:
            full=payload; attempt=bridge(registry,full).claim('research')
            queue.put({'ok':True,'should_execute':attempt.should_execute,'attempt_id':attempt.attempt_id})
    except BaseException as exc:
        queue.put({'ok':False,'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()})

class IndependentCyclesAndRound(unittest.TestCase):
    def reject_unchanged(self,directory,action,exceptions=(ValueError,RegistryError)):
        before=state_bytes(directory)
        with self.assertRaises(exceptions): action()
        self.assertEqual(state_bytes(directory),before)

    def test_01_revision_plus_cycle_preserves_lifetime_and_execution_usage(self):
        usage={'configurations':{'normal':2,'reserve':1,'total':3},'research':{'normal':1,'reserve':1,'total':2},'lean':{'normal':1,'reserve':1,'total':2}}
        with tempfile.TemporaryDirectory(dir=OUT,prefix='revision-cycle-') as directory:
            registry=reg(directory,usage); prefix=registry.store.read_bytes(registry.JOURNAL)
            revision,authority=revision_documents(registry); registry.authorize_budget_revision(revision,authority)
            self.assertEqual(registry.snapshot()['usage'],usage)
            self.assertEqual(registry.limits['configurations'],{'normal':2,'reserve':2,'total':4})
            self.assertEqual(registry.limits['research'],LIMITS['research']); self.assertEqual(registry.limits['lean'],LIMITS['lean'])
            identity=registry.register_config({'SYNTHETIC':'before-cycle'},allocation='reserve')
            for stage in ('research','lean'):
                attempt=registry.begin_attempt(identity,stage,operation_key='synthetic-before-'+stage)
                registry.fail(attempt,'SYNTHETIC terminal failure, no refund')
            before=registry.snapshot(); journal=registry.store.read_bytes(registry.JOURNAL)
            cycle,auth=cycle_documents(registry); current=registry.authorize_configuration_cycle(cycle,auth)
            self.assertEqual(current['usage'],{'normal':0,'reserve':0,'total':0})
            self.assertEqual(current['lifetime_usage'],before['usage']['configurations'])
            self.assertEqual(registry.snapshot()['usage'],before['usage'])
            self.assertEqual(registry.configuration_cycles_snapshot()['initial']['usage']['total'],4)
            self.assertTrue(registry.store.read_bytes(registry.JOURNAL).startswith(journal))
            saved=state_bytes(directory)
            registry.authorize_configuration_cycle(cycle,auth); registry.authorize_budget_revision(revision,authority)
            self.assertEqual(state_bytes(directory),saved)
            self.assertEqual(registry.register_config({'SYNTHETIC':'before-cycle'},allocation='reserve'),identity)
            self.assertEqual(state_bytes(directory),saved)
            new=registry.register_config({'SYNTHETIC':'after-cycle'},allocation='normal')
            snapshot=registry.snapshot()
            self.assertEqual(snapshot['usage']['configurations']['total'],5)
            self.assertEqual(registry.configuration_cycle_snapshot()['usage']['total'],1)
            self.assertEqual(snapshot['usage']['research']['total'],3); self.assertEqual(snapshot['usage']['lean']['total'],3)
            self.assertEqual(snapshot['configuration_origins'][identity]['cycle_id'],'initial')
            self.assertEqual(snapshot['configuration_origins'][new]['cycle_id'],cycle['cycle_id'])
            reopened=reg(directory,usage); self.assertEqual(reopened.snapshot(),snapshot)
            self.assertTrue(reopened.store.read_bytes(registry.JOURNAL).startswith(prefix))
            note('revision_only_one_configuration_reserve',new_config_limit=4)
            note('cycle_only_configuration_capacity_reset',lifetime_configs=5,current_cycle_configs=1,research=3,lean=3)
            note('revision_cycle_and_old_configuration_reuse_idempotent')
            note('old_cycle_origin_and_journal_prefix_preserved')

    def test_02_wrong_revision_capacity_and_stale_cycle_rejected_without_write(self):
        with tempfile.TemporaryDirectory(dir=OUT,prefix='invalid-auth-') as directory:
            registry=reg(directory)
            for name,change in [('two_config_slots',lambda r:r['new_limits']['configurations'].update(reserve=3,total=5)),
                                ('research_increment',lambda r:r['new_limits']['research'].update(reserve=4,total=7))]:
                revision,auth=revision_documents(registry,'SYNTHETIC-'+name); change(revision)
                for key,value in revision.items():
                    if key!='authorization_ref': auth[key]=deepcopy(value)
                revision['authorization_ref']=revision_auth_ref(auth)
                self.reject_unchanged(directory,lambda:registry.authorize_budget_revision(revision,auth)); note('reject_revision_'+name)
            cycle,auth=cycle_documents(registry)
            registry.register_config({'SYNTHETIC':'changes-state'})
            self.reject_unchanged(directory,lambda:registry.authorize_configuration_cycle(cycle,auth)); note('reject_stale_cycle_state')
            fresh,fresh_auth=cycle_documents(registry); registry.authorize_configuration_cycle(fresh,fresh_auth)
            revision,revision_auth=revision_documents(registry,'SYNTHETIC-after-cycle')
            self.reject_unchanged(directory,lambda:registry.authorize_budget_revision(revision,revision_auth)); note('reject_revision_after_cycle')

    def test_03_unresolved_attempt_or_open_new_round_blocks_reset(self):
        with tempfile.TemporaryDirectory(dir=OUT,prefix='quiescence-') as directory:
            registry=reg(directory); identity=registry.register_config({'SYNTHETIC':'pending'})
            attempt=registry.begin_attempt(identity,'research')
            for status in ('started','pending','ambiguous'):
                if status=='pending': registry.pending(attempt,external_id='SYNTHETIC-only')
                if status=='ambiguous': registry.ambiguous(attempt,reason='SYNTHETIC unknown')
                cycle,auth=cycle_documents(registry)
                self.reject_unchanged(directory,lambda:registry.authorize_configuration_cycle(cycle,auth)); note('cycle_blocked_'+status)
            registry.fail(attempt,'SYNTHETIC reconciled failure',reconciliation=True)
            cycle,auth=cycle_documents(registry); registry.authorize_configuration_cycle(cycle,auth)
            full=package(); grant,authority=round_documents(registry,full)
            registry.authorize_engineering_round(grant,[full],authority)
            cycle2,auth2=cycle_documents(registry,'SYNTHETIC-next-cycle')
            self.reject_unchanged(directory,lambda:registry.authorize_configuration_cycle(cycle2,auth2)); note('cycle_blocked_open_schema4_round')
            registry.close_engineering_round(grant['round_id'],'SYNTHETIC unused grant closed')
            cycle3,auth3=cycle_documents(registry,'SYNTHETIC-next-cycle'); registry.authorize_configuration_cycle(cycle3,auth3)
            self.assertEqual(registry.snapshot()['usage']['research']['total'],1); note('closed_round_allows_reset_without_execution_refund')

    def test_04_new_cycle_schema4_one_one_one_parallel_claim_and_closed_round_reuse(self):
        with tempfile.TemporaryDirectory(dir=OUT,prefix='schema4-claim-') as directory:
            registry=reg(directory); cycle,auth=cycle_documents(registry); registry.authorize_configuration_cycle(cycle,auth)
            full=package(); grant,authority=round_documents(registry,full); registry.authorize_engineering_round(grant,[full],authority)
            task=bridge(registry,full); task.register()
            alternate=package(6501,'independent-second-plan')
            self.reject_unchanged(directory,lambda:registry.bind_engineering_configuration(grant['round_id'],alternate)); note('schema4_round_one_config_binding_cap')
            ctx=mp.get_context('spawn'); gate=ctx.Barrier(4); queue=ctx.Queue()
            processes=[ctx.Process(target=process_action,args=(directory,None,'claim',full,gate,queue)) for _ in range(4)]
            for process in processes: process.start()
            results=[queue.get(timeout=35) for _ in processes]
            for process in processes: process.join(timeout=35); self.assertEqual(process.exitcode,0)
            self.assertTrue(all(result.get('ok') for result in results),results)
            self.assertEqual(sum(result['should_execute'] for result in results),1)
            self.assertEqual(len({result['attempt_id'] for result in results}),1)
            winner=results[0]['attempt_id']; registry.fail(winner,'SYNTHETIC actual failure; no refund')
            self.reject_unchanged(directory,lambda:task.claim('research',retry_of=winner,reason='SYNTHETIC forbidden retry'))
            self.reject_unchanged(directory,lambda:task.claim('lean'))
            self.assertEqual(registry.snapshot()['usage']['lean']['total'],0)
            registry.close_engineering_round(grant['round_id'],'SYNTHETIC failed round closed')
            saved=state_bytes(directory); again=registry.authorize_engineering_round(grant,[full],authority)
            self.assertEqual(again['status'],'closed'); self.assertEqual(state_bytes(directory),saved)
            reopened=reg(directory); task2=bridge(reopened,full)
            self.assertEqual(task2.register(),task.config_id)
            reused=task2.claim('research'); self.assertFalse(reused.should_execute); self.assertEqual(reused.attempt_id,winner)
            self.assertEqual(state_bytes(directory),saved)
            self.assertEqual(reopened.engineering_rounds_snapshot()[grant['round_id']]['usage'],{'configurations':1,'research':1,'lean':0})
            self.reject_unchanged(directory,lambda:reopened.bind_engineering_configuration(grant['round_id'],alternate))
            note('schema4_parallel_parent_claim',processes=4,requests=4,dispatch_permissions=1,results=results)
            note('schema4_failure_closed_restart_no_reset_or_refund',usage={'configurations':1,'research':1,'lean':0})
            note('schema4_unverified_Research_cannot_charge_LEAN')

    def test_05_cross_project_rounds_compete_for_one_global_remaining_research_slot(self):
        usage={'configurations':{'normal':2,'reserve':1,'total':3},'research':{'normal':2,'reserve':3,'total':5},'lean':{'normal':1,'reserve':3,'total':4}}
        with tempfile.TemporaryDirectory(dir=OUT,prefix='cross-project-reserve-') as directory:
            registry=reg(directory,usage); cycle,auth=cycle_documents(registry); registry.authorize_configuration_cycle(cycle,auth)
            packages=[package(6601,'independent-project-one'),package(6602,'independent-project-two')]
            docs=[round_documents(registry,full,'SYNTHETIC-project-'+str(full['plan']['project_id'])) for full in packages]
            ctx=mp.get_context('spawn'); gate=ctx.Barrier(2); queue=ctx.Queue()
            processes=[ctx.Process(target=process_action,args=(directory,usage,'authorize',(grant,authority,full),gate,queue)) for full,(grant,authority) in zip(packages,docs)]
            for process in processes: process.start()
            results=[queue.get(timeout=35) for _ in processes]
            for process in processes: process.join(timeout=35); self.assertEqual(process.exitcode,0)
            success=[result for result in results if result.get('ok')]; denied=[result for result in results if not result.get('ok')]
            self.assertEqual(len(success),1,results); self.assertEqual(len(denied),1,results); self.assertEqual(denied[0]['type'],'BudgetExceeded')
            winning_id=success[0]['round_id']; index=next(i for i,(grant,_) in enumerate(docs) if grant['round_id']==winning_id)
            task=bridge(registry,packages[index]); task.register(); attempt=task.claim('research')
            self.assertTrue(attempt.should_execute); registry.fail(attempt,'SYNTHETIC failed global final slot')
            registry.close_engineering_round(winning_id,'SYNTHETIC complete accounting')
            other=1-index; grant,authority=docs[other]
            self.reject_unchanged(directory,lambda:registry.authorize_engineering_round(grant,[packages[other]],authority))
            reopened=reg(directory,usage); self.assertEqual(reopened.snapshot()['usage']['research']['total'],6)
            self.assertEqual(reopened.snapshot()['usage']['lean']['total'],4)
            self.assertEqual(reopened.configuration_cycle_snapshot()['usage']['total'],1)
            self.assertEqual(reopened.engineering_rounds_snapshot()[winning_id]['status'],'closed')
            note('cross_project_new_cycle_global_reservations_atomic',projects=[6601,6602],results=results)
            note('new_round_name_or_project_after_close_cannot_reset_global_research',research=6,lean=4)

    def test_06_exact_source_character_boundaries_are_pure(self):
        answer=validate_source_sizes({'a.py':'中\r\n\ufeff'},max_file_characters=4)
        self.assertEqual(answer['total_characters'],4); self.assertEqual(answer['total_utf8_bytes'],8)
        note('source_exact_CJK_BOM_CRLF_count',characters=4,utf8_bytes=8)
        for name,sources,limit in [('one_over',{'a.py':'12345'},4),('nonBMP',{'a.py':'\U0001f600'},10),('bool_limit',{'a.py':'1'},True),('control',{'a.py':'\x00'},10)]:
            with self.subTest(name=name),self.assertRaises(SourceLimitError): validate_source_sizes(sources,max_file_characters=limit)
            note('source_reject_'+name)

    def test_07_CLI_source_limit_and_followup_policy_reject_before_register_claim_freeze(self):
        for failure in ('source_size','followup_policy'):
            with self.subTest(failure=failure),tempfile.TemporaryDirectory(dir=OUT,prefix='CLI-preflight-') as directory:
                base=Path(directory); root=base/'workspace'; (root/'config').mkdir(parents=True); (root/'audit').mkdir(); (root/'cloud').mkdir()
                raw=b'print(1)\n'; (root/'cloud/main.py').write_bytes(raw)
                manifest={'main.py':hashlib.sha256(raw).hexdigest()}
                (root/'audit/deployment.json').write_text(json.dumps({'source_files':manifest}),encoding='utf-8')
                qc={'active_project_id':6701,'native_source_file_limit':{'schema_version':1,'project_id':6701,'max_file_characters':20}}
                policy={'schema_version':1,'notification_grace_seconds':1800,'max_history_pages':3}
                def files():
                    (root/'config/quantconnect.json').write_text(json.dumps(qc),encoding='utf-8')
                    (root/'config/task_followup.json').write_text(json.dumps(policy),encoding='utf-8')
                files()
                plan_raw=json.loads((ROOT/'config/engineering.json').read_bytes())
                plan_raw.update(project_id=6701,plan_id='independent-cli',source_manifest_hash='a'*64,deployment_hash=content_hash(manifest))
                plan_raw['request_template']['universe_hash']='c'*64
                (root/'config/engineering.json').write_text(json.dumps(plan_raw),encoding='utf-8')
                ledger=base/'synthetic-store'; registry=reg(ledger); task=EngineeringTaskBridge(registry,EngineeringTaskPlan.from_dict(plan_raw,discovered_project_ids=[6701]))
                def make_bad():
                    if failure=='source_size': qc['native_source_file_limit']['max_file_characters']=len(raw)-1
                    else: policy['max_history_pages']=4
                    files()
                make_bad()
                with patch.object(stage2,'ROOT',root),patch.object(stage2,'current_bridge',return_value=task),patch.object(stage2,'export_usage') as export,patch.object(stage2,'open_registry',side_effect=AssertionError('Must fail before registry open')):
                    self.reject_unchanged(ledger,lambda:stage2.freeze({'success':True,'projects':[{'projectId':6701}]},plan_file=root/'config/engineering.json'))
                    with patch.object(sys,'argv',['stage2.py','register']): self.reject_unchanged(ledger,stage2.main)
                    export.assert_not_called()
                note('CLI_'+failure+'_freeze_and_register_no_debit')
                qc['native_source_file_limit']['max_file_characters']=20; policy['max_history_pages']=3; files()
                with patch.object(stage2,'ROOT',root),patch.object(stage2,'current_bridge',return_value=task),patch.object(stage2,'export_usage'),patch.object(sys,'argv',['stage2.py','register']),patch('sys.stdout',new_callable=io.StringIO): stage2.main()
                self.assertEqual(registry.snapshot()['usage']['configurations']['total'],1)
                make_bad()
                with patch.object(stage2,'ROOT',root),patch.object(stage2,'current_bridge',return_value=task),patch.object(stage2,'export_usage') as export,patch.object(sys,'argv',['stage2.py','claim','--stage','research']):
                    self.reject_unchanged(ledger,stage2.main); export.assert_not_called()
                self.assertEqual(registry.snapshot()['usage']['research']['total'],0)
                note('CLI_'+failure+'_claim_no_debit_legal_registration_retained')

if __name__=='__main__':
    OUT.mkdir(parents=True,exist_ok=True)
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(IndependentCyclesAndRound))
    report={'source_commit':'975f676d62b561689909744f9e7236290e3f5fcb','methods':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),'named_scenarios':len(OBS),'observations':OBS,
            'failure_details':[{'test':str(test),'traceback':tb} for test,tb in result.failures+result.errors],'cloud_calls':0,'real_budget_writes':0,'original_source_writes':0}
    (OUT/'first_results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    sys.exit(0 if result.wasSuccessful() else 1)
