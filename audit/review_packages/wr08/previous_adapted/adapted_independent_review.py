"""Independent, synthetic-only AQRP audit. No developer fixtures or remote calls.

Run: venv/Scripts/python.exe -B independent_review.py
Production code is loaded only from the fixed source snapshot beside this file.
Known-defect tests assert the required contract, so unresolved defects FAIL.
"""
from pathlib import Path
from copy import deepcopy
from decimal import Decimal, localcontext, Inexact, Rounded, FloatOperation
from fractions import Fraction
from concurrent.futures import ThreadPoolExecutor
import base64, hashlib, io, json, multiprocessing as mp, os, platform, socket
import sys, tempfile, threading, traceback, unittest

ROOT=Path(__file__).resolve().parent
SOURCE=ROOT/'source'
sys.path[:0]=[str(SOURCE/'cloud'),str(SOURCE/'tools')]
import numpy as np
import pandas as pd
from qresearch.artifacts import (MemoryArtifactStore,FilesystemArtifactStore,
    canonical_json,content_hash,ArtifactConflict,CorruptEventStream,decode_events,StoreBusy)
from qresearch.registry import Registry,BudgetExceeded,RegistryError
from qresearch.engineering_tasks import EngineeringTaskPlan,EngineeringTaskBridge,EngineeringTaskError
from qresearch.engineering_receipts import (research_observation,backtest_submission,
    backtest_observation,ReceiptParseError)
from qresearch.engineering_data import load_task_input,verify_deployment
from qresearch.contracts import DataRequest,RECORD_COLUMNS,PITWindow,NY
from qresearch.cache import SharedDataCache,CacheMiss
from qresearch.point_in_time import causal_window
from qresearch.factors import FactorSpec,FactorValidationError,evaluate_factors
from qresearch.labels import LabelProtocol,build_execution_labels,LabelValidationError
from qresearch.models import ModelSpec,create_model,restore_model
from qresearch.evaluation import (daily_rank_ic,paired_factor_correlation,six_rolling_folds,
    build_fold_splits,walk_forward_evaluate)
from qresearch.study import StudySpec
from qresearch.pipeline import evaluate_registered_study,PipelineValidationError
from qresearch.runtime import ResearchEngine
from qresearch.coverage import produce_engineering_coverage
from qresearch.ingestion import HistoricalBatchIngestor,MissingPITEvidence,IngestionError,resolve_historical_sid
from qresearch.workflow import SubmissionRejected
from qresearch.universe import select_liquid_universe
from stage2 import _limits

LIMITS={'configurations':{'total':12,'normal':8,'reserve':4},
        'research':{'total':20,'normal':12,'reserve':8},
        'lean':{'total':16,'normal':8,'reserve':8}}
OBSERVATIONS={}
def stamp(value): return pd.Timestamp(value,tz='America/New_York')
def raw_plan(name='audit-A',project=101):
    d=json.loads((SOURCE/'config/engineering.json').read_text(encoding='utf-8-sig'))
    d.update(plan_id=name,project_id=project,source_manifest_hash='1'*64,deployment_hash='2'*64)
    d['request_template']['universe_hash']='3'*64
    d['request_template']['data_version']='independent-synthetic-v1'
    return d
def bridge(registry,doc=None,adapter=None):
    plan=EngineeringTaskPlan.from_dict(doc or raw_plan(),discovered_project_ids=[101,102,103])
    return EngineeringTaskBridge(registry,plan,adapter=adapter)
def fresh():
    s=MemoryArtifactStore(); return s,Registry(s,LIMITS)
def resolution():
    refs={'resolved_registry_ref':{'key':'synthetic/sids.json','sha256':'4'*64},
          'resolved_request_ref':{'key':'synthetic/request.json','sha256':'5'*64}}
    return dict(refs,resolved_request_hash='5'*64,resolved_registry_hash='4'*64,
        resolution_artifact_hash=content_hash(refs),tickers=['AAPL','MSFT'],ticker_count=2,
        permanent_sid_count=2,method='QuantBook.add_equity/as-of fixed fixture')
def report_wrapper(payload):
    stage=payload['identity']['stage']
    stats=({'record_count':60,'history_calls_first':1,'history_calls_second':0,'expected_formation_count':6}
       if stage=='research' else {'data_event_count':12,'slice_count':6,'orders_submitted':0,
        'runtime_error_count':0,'dividend_event_count':1,'split_event_count':0,
        'delisting_event_count':0,'mapping_event_count':0})
    report={'schema_version':1,'identity':deepcopy(payload['identity']),'status':'completed','terminal':True,
        'checks':{name:True for name in payload['plan']['required_checks'][stage]},
        'statistics':stats,'resolution':resolution(),'market_values_exported':False,
        'economic_factor_tested':False,'final_data_accessed':False,'full_US200_coverage_certified':False,
        'actual_availability_verified':False}
    return {'cloud_report':report,'report_ref':{'key':payload['report_key'],'sha256':content_hash(report)}}
def deployment(payload):
    return {k:payload['identity'][k] for k in ('source_manifest_hash','deployment_hash')}|{'input_hash':'6'*64}
def native_research(payload,wrapper=None):
    wrap=wrapper or report_wrapper(payload)
    encoded=base64.b64encode(canonical_json(wrap)).decode()
    return {'tool_name':'mcp__quantconnect__jupyter_execute_cell',
        'arguments':{'projectId':payload['identity']['project_id'],'index':0},
        'result':{'success':True,'outputs':[{'output_type':'stream','name':'stdout','text':'AQRP_ENGINEERING_JSON '+encoded+'\n'}]}}
def complete_research(b):
    a=b.claim('research'); p=b.payload(a)
    obs=research_observation(p,deployment(p),native_research(p))
    b.record_submission(a,obs['submission'])
    return b.consume_completion(a,completion_source=lambda _:obs['completion'])
def native_submission(payload,external='synthetic-backtest'):
    return {'tool_name':'mcp__quantconnect__create_backtest',
        'arguments':{'projectId':payload['identity']['project_id'],'backtestName':'synthetic'},
        'result':{'success':True,'backtestId':external}}
def native_terminal(payload,external='synthetic-backtest',status='Completed.',completed=True):
    return {'tool_name':'mcp__quantconnect__read_backtest',
        'arguments':{'projectId':payload['identity']['project_id'],'backtestId':external},
        'result':{'success':True,'backtest':{'backtestId':external,'projectId':payload['identity']['project_id'],
        'completed':completed,'status':status,'progress':1 if completed else .5,
        'statistics':{'Total Orders':'0'},'error':None,'stacktrace':None,'hasInitializeError':False}}}
def native_logs(payload,external='synthetic-backtest',wrapper=None):
    encoded=base64.b64encode(canonical_json(wrapper or report_wrapper(payload))).decode()
    pieces=[encoded[i:i+500] for i in range(0,len(encoded),500)]
    logs=['AQRP_ENGINEERING '+payload['identity']['attempt_id']+' '+str(i)+'/'+str(len(pieces))+' '+p for i,p in enumerate(pieces)]
    return [{'tool_name':'mcp__quantconnect__search_backtest_logs',
        'arguments':{'projectId':payload['identity']['project_id'],'backtestId':external,
            'query':'AQRP_ENGINEERING '+payload['identity']['attempt_id'],'page':1},
        'result':{'success':True,'logs':logs,'totalPages':1}}]

class SyntheticAdapter:
    def __init__(self,error=None): self.calls=0; self.error=error
    def submit_research(self,payload,*,operation_key):
        self.calls+=1
        if self.error: raise self.error
        return research_observation(payload,deployment(payload),native_research(payload))['submission']
    def submit_backtest(self,payload,*,operation_key):
        self.calls+=1
        if self.error: raise self.error
        return backtest_submission(payload,deployment(payload),native_submission(payload))

def race_worker(root,doc,kind,retry,barrier,queue):
    try:
        r=Registry(FilesystemArtifactStore(root,lock_timeout=10),LIMITS)
        b=bridge(r,doc)
        _limits(b,kind)
        barrier.wait(15)
        if kind=='configurations': result={'registered':b.register()}
        else:
            a=b.claim(kind,retry_of=retry,reason='synthetic repair' if retry else None,
                      allocation='reserve' if retry else 'normal')
            result={'should_execute':a.should_execute,'attempt_id':a.attempt_id}
        queue.put({'ok':True,**result})
    except Exception as exc:
        queue.put({'ok':False,'type':type(exc).__name__,'message':str(exc)})

class AdmissionTests(unittest.TestCase):
    def race(self,kind,processes):
        with tempfile.TemporaryDirectory(prefix='aqrp-independent-') as directory:
            store=FilesystemArtifactStore(directory,lock_timeout=10) if processes else MemoryArtifactStore()
            r=Registry(store,LIMITS)
            if kind=='configurations':
                bridge(r,raw_plan('used',103)).register()
                docs=[raw_plan('contender-a',101),raw_plan('contender-b',102)]; retries=[None,None]
            else:
                docs=[raw_plan('contender-a',101),raw_plan('contender-b',102)]
                bs=[bridge(r,d) for d in docs]
                for b in bs: b.register()
                if kind=='lean':
                    for b in bs: complete_research(b)
                used=bs[0].claim(kind); r.fail(used,'synthetic failure; no refund')
                retries=[used.attempt_id,None]
            if processes:
                ctx=mp.get_context('spawn'); barrier=ctx.Barrier(2); queue=ctx.Queue()
                children=[ctx.Process(target=race_worker,args=(directory,d,kind,retry,barrier,queue)) for d,retry in zip(docs,retries)]
                for p in children: p.start()
                answers=[queue.get(timeout=35) for _ in children]
                for p in children:
                    p.join(5)
                    if p.is_alive(): p.terminate(); p.join(); self.fail('Worker did not finish')
                    self.assertEqual(p.exitcode,0)
            else:
                barrier=threading.Barrier(2)
                def work(pair):
                    doc,retry=pair; b=bridge(r,doc)
                    _limits(b,kind); barrier.wait(10)
                    try:
                        if kind=='configurations': return {'ok':True,'registered':b.register()}
                        a=b.claim(kind,retry_of=retry,reason='synthetic repair' if retry else None,
                                  allocation='reserve' if retry else 'normal')
                        return {'ok':True,'should_execute':a.should_execute}
                    except BudgetExceeded as exc:
                        return {'ok':False,'type':type(exc).__name__,'message':str(exc)}
                with ThreadPoolExecutor(max_workers=2) as ex: answers=list(ex.map(work,zip(docs,retries)))
            snap=r.snapshot(); count=snap['usage'][kind]['total']
            OBSERVATIONS[self.id()]={'kind':kind,'processes':processes,'usage':snap['usage'],'responses':answers}
            winners=[a for a in answers if a['ok']]
            rejected=[a for a in answers if not a['ok']]
            self.assertEqual(len(winners),1,answers)
            self.assertEqual(len(rejected),1,answers)
            self.assertEqual(rejected[0]['type'],'BudgetExceeded',answers)
            if kind!='configurations': self.assertTrue(winners[0]['should_execute'])
            self.assertEqual(count,2,answers)
            self.assertLessEqual(count,2,'WR-04: both contenders passed the stage-2 check and total became '+str(count))
    def test_WR04_configuration_thread_race(self): self.race('configurations',False)
    def test_WR04_configuration_process_race(self): self.race('configurations',True)
    def test_WR04_research_thread_race(self): self.race('research',False)
    def test_WR04_research_process_race(self): self.race('research',True)
    def test_WR04_lean_thread_race(self): self.race('lean',False)
    def test_WR04_lean_process_race(self): self.race('lean',True)
    def test_WR04_direct_register_enforces_stop(self):
        _,r=fresh(); bridges=[bridge(r,raw_plan('direct-'+str(i),101+i)) for i in range(3)]
        for b in bridges[:2]: b.register()
        with self.assertRaises((EngineeringTaskError,BudgetExceeded,ValueError)):
            bridges[2].register()
    def test_WR04_direct_claim_enforces_stop(self):
        _,r=fresh(); b=bridge(r); b.register(); a=b.claim('research'); r.fail(a,'first')
        a=b.claim('research',retry_of=a.attempt_id,reason='first repair'); r.fail(a,'second')
        other=bridge(r,raw_plan('renamed',102)); other.register()
        with self.assertRaises((EngineeringTaskError,BudgetExceeded,ValueError)):
            other.claim('research')
    def test_WR04_direct_submit_enforces_stop(self):
        _,r=fresh(); adapter=SyntheticAdapter(SubmissionRejected('synthetic rejection'))
        b=bridge(r,adapter=adapter); b.register(); first=b.submit('research')
        second=b.submit('research',retry_of=first.attempt_id,reason='repair')
        self.assertEqual(second.status,'failed')
        other=bridge(r,raw_plan('new-project',102),adapter=adapter); other.register()
        with self.assertRaises((EngineeringTaskError,BudgetExceeded,ValueError)):
            other.submit('research')
    def test_serial_cli_check_preserves_round_count_after_restart(self):
        store,r=fresh()
        for i in range(2):
            b=bridge(r,raw_plan('serial-'+str(i),101+i)); _limits(b,'configurations'); b.register()
        restarted=Registry(store,LIMITS); b=bridge(restarted,raw_plan('serial-third',103))
        with self.assertRaises(ValueError): _limits(b,'configurations')
        self.assertEqual(restarted.snapshot()['usage']['configurations']['total'],2)
    def test_global_budget_remains_atomic_across_allocations(self):
        _,r=fresh()
        for i in range(12):
            r.register_config({'synthetic':i},allocation='normal' if i<8 else 'reserve')
        with self.assertRaises(BudgetExceeded): r.register_config({'synthetic':13},allocation='reserve')
        self.assertEqual(r.snapshot()['usage']['configurations']['total'],12)
    def test_global_last_slot_is_single_winner_across_store_instances(self):
        with tempfile.TemporaryDirectory() as directory:
            usage={'configurations':{'total':11,'normal':8,'reserve':3},
                'research':{'total':0,'normal':0,'reserve':0},'lean':{'total':0,'normal':0,'reserve':0}}
            r=Registry(FilesystemArtifactStore(directory),LIMITS,usage=usage)
            gate=threading.Barrier(2)
            def contender(i):
                other=Registry(FilesystemArtifactStore(directory),LIMITS,usage=usage);gate.wait(5)
                try:other.register_config({'independent-contender':i},allocation='reserve');return True
                except BudgetExceeded:return False
            with ThreadPoolExecutor(max_workers=2) as executor:results=list(executor.map(contender,[1,2]))
            self.assertEqual(sum(results),1);self.assertEqual(r.snapshot()['usage']['configurations']['total'],12)

class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.store,self.r=fresh(); self.adapter=SyntheticAdapter(); self.b=bridge(self.r,adapter=self.adapter); self.b.register()
    def test_complete_research_restart_reuses_without_charge(self):
        a=complete_research(self.b); usage=deepcopy(self.r.snapshot()['usage'])
        restarted=bridge(Registry(self.store,LIMITS),adapter=self.adapter)
        _limits(restarted,'research'); got=restarted.submit('research')
        self.assertEqual(got.attempt_id,a.attempt_id); self.assertFalse(got.should_execute)
        self.assertEqual(self.adapter.calls,0); self.assertEqual(self.r.snapshot()['usage'],usage)
    def test_unknown_submission_blocks_automatic_resubmit_after_restart(self):
        self.adapter.error=TimeoutError('synthetic unknown acceptance'); a=self.b.submit('research')
        self.assertEqual(a.status,'ambiguous')
        restarted=bridge(Registry(self.store,LIMITS),adapter=self.adapter)
        again=restarted.submit('research'); self.assertEqual(again.attempt_id,a.attempt_id)
        self.assertEqual(self.adapter.calls,1); self.assertEqual(self.r.snapshot()['usage']['research']['total'],1)
    def test_failure_consumes_budget_and_requires_explicit_retry(self):
        self.adapter.error=SubmissionRejected('synthetic refusal'); a=self.b.submit('research')
        self.assertEqual(a.status,'failed'); self.assertEqual(self.b.submit('research').attempt_id,a.attempt_id)
        self.assertEqual(self.adapter.calls,1)
        b=self.b.submit('research',retry_of=a.attempt_id,reason='explicit synthetic repair',allocation='reserve')
        self.assertNotEqual(a.attempt_id,b.attempt_id)
        self.assertEqual(self.r.snapshot()['usage']['research'],{'total':2,'normal':1,'reserve':1})
    def test_unresolved_project_cannot_change_plan(self):
        self.b.submit('research'); other=bridge(self.r,raw_plan('changed',101)); other.register()
        with self.assertRaises(EngineeringTaskError): other.claim('research')
    def test_lean_needs_completed_research_and_exact_resolution(self):
        with self.assertRaises(EngineeringTaskError): self.b.claim('lean')
        complete_research(self.b); a=self.b.claim('lean'); p=self.b.payload(a)
        self.assertEqual(p['research_resolution'],resolution())
    def test_full_native_receipt_chain_completes_and_reuses(self):
        complete_research(self.b); a=self.b.submit('lean'); p=self.b.payload(a); d=deployment(p)
        observed=backtest_observation(p,d,'synthetic-backtest',native_terminal(p),native_logs(p))
        done=self.b.consume_completion(a,completion_source=lambda _:observed)
        self.assertEqual(done.status,'completed'); self.assertFalse(self.b.read_result(done)['financial_evidence'])
        repeat=self.b.submit('lean'); self.assertEqual(repeat.attempt_id,a.attempt_id)
        self.assertEqual(self.r.snapshot()['usage']['lean']['total'],1)
    def test_compile_receipt_is_not_submission(self):
        complete_research(self.b); a=self.b.claim('lean'); p=self.b.payload(a)
        native=native_submission(p); native['result']={'success':True,'compileId':'compile-only'}
        with self.assertRaises(ReceiptParseError): backtest_submission(p,deployment(p),native)
    def test_running_backtest_does_not_complete(self):
        complete_research(self.b); a=self.b.claim('lean'); p=self.b.payload(a)
        with self.assertRaises(ReceiptParseError):
            backtest_observation(p,deployment(p),'synthetic-backtest',native_terminal(p,status='In Progress...',completed=False),native_logs(p))
    def test_missing_or_duplicate_log_chunks_rejected(self):
        complete_research(self.b); a=self.b.claim('lean'); p=self.b.payload(a)
        for duplicate in (False,True):
            logs=native_logs(p)
            if duplicate: logs[0]['result']['logs'].append(logs[0]['result']['logs'][0])
            else: logs[0]['result']['logs'].pop()
            with self.subTest(duplicate=duplicate), self.assertRaises(ReceiptParseError):
                backtest_observation(p,deployment(p),'synthetic-backtest',native_terminal(p),logs)
    def test_receipt_identity_and_input_hash_mismatch_rejected(self):
        a=self.b.submit('research'); p=self.b.payload(a)
        observed=research_observation(p,deployment(p),native_research(p))['completion']
        for field in ('project_id','attempt_id','plan_hash','deployment_hash','input_hash'):
            bad=deepcopy(observed)
            if field=='input_hash': bad['platform']['deployment'][field]='9'*64
            else: bad['platform']['identity'][field]=102 if field=='project_id' else '9'*(32 if field=='attempt_id' else 64)
            with self.subTest(field=field),self.assertRaises(EngineeringTaskError):
                self.b.consume_completion(a,completion_source=lambda _:bad)
        self.assertEqual(self.b._record(a)['status'],'pending')
    def test_real_orders_rejected_even_with_success_marker(self):
        complete_research(self.b); a=self.b.claim('lean'); p=self.b.payload(a); native=native_terminal(p)
        native['result']['backtest']['statistics']['Total Orders']='1'
        with self.assertRaises(ReceiptParseError): backtest_observation(p,deployment(p),'synthetic-backtest',native,native_logs(p))
    def test_market_rows_do_not_enter_local_receipt(self):
        a=self.b.claim('research'); p=self.b.payload(a); wrapper=report_wrapper(p)
        wrapper['cloud_report']['rows']=[['synthetic-row',123]]
        with self.assertRaises(ReceiptParseError): research_observation(p,deployment(p),native_research(p,wrapper))
    def test_journal_torn_tail_fails_closed(self):
        data=self.store.read_bytes(self.r.JOURNAL)
        with self.assertRaises(CorruptEventStream): decode_events(data[:-1])
    def test_unreconciled_native_windows_lock_remains_occupied(self):
        with tempfile.TemporaryDirectory() as directory:
            store=FilesystemArtifactStore(directory,lock_timeout=.03)
            with store.locked('independent-owner'):
                with self.assertRaises(StoreBusy):
                    with store.locked('independent-owner'): pass
            with store.locked('independent-owner'): pass
    def test_input_file_is_inert_and_arbitrary_execution_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'input.py'; path.write_text('TASK_INPUT_JSON = \'{"x": 3}\'\n',encoding='utf-8')
            self.assertEqual(load_task_input(path),{'x':3})
            path.write_text('TASK_INPUT_JSON = \'{}\'\nraise RuntimeError("executed")\n',encoding='utf-8')
            with self.assertRaises(ValueError): load_task_input(path)
    def test_crash_after_result_publication_recovers_without_new_budget(self):
        class FaultStore(MemoryArtifactStore):
            armed=True
            def append_event(self,stream,event):
                if self.armed and event.get('kind')=='completed':
                    self.armed=False;raise OSError('injected crash after immutable result publication')
                return super().append_event(stream,event)
        store=FaultStore();r=Registry(store,LIMITS);b=bridge(r);b.register();a=b.claim('research');p=b.payload(a)
        obs=research_observation(p,deployment(p),native_research(p));b.record_submission(a,obs['submission'])
        with self.assertRaises(OSError):b.consume_completion(a,completion_source=lambda _:obs['completion'])
        self.assertTrue(store.exists(a.result_key));self.assertEqual(b._record(a)['status'],'pending')
        restarted=bridge(Registry(store,LIMITS));done=restarted.consume_completion(a,completion_source=lambda _:obs['completion'])
        self.assertEqual(done.status,'completed');self.assertEqual(r.snapshot()['usage']['research']['total'],1)

def factor(formula=None,ops=None,name='independent_factor'):
    return FactorSpec.from_dict({'schema_version':1,'factor_id':name,
        'economic_hypothesis':{'mechanism':'independent synthetic arithmetic oracle',
         'expected_direction':1,'prediction_horizon_sessions':1,'applicable_regimes':['synthetic'],
         'failure_conditions':['synthetic inputs only']},
        'allowed_fields':['close'],'allowed_operators':ops or [],'parameters':{},
        'formula':formula or {'op':'field','name':'close'}},field_catalog=['close'])
def protocol():
    return LabelProtocol.from_dict({'schema_version':1,'protocol_id':'independent-roundtrip',
        'target_kind':'net_return','price_basis':'actual_fill','currency':'USD','normalization':'raw',
        'corporate_action_policy':'reject_non_cash_actions','denominator':'entry_notional',
        'purpose':'engineering_fixture'})
def trade(year=2018,sid='X',entry=200,exit=180,quantity=1):
    identity=str(year)+'-'+sid
    return {'trade_id':identity,'sid':sid,'side':'long','currency':'USD','normalization':'raw',
        'execution_source':'independent-synthetic','entry_execution_id':identity+'-in','exit_execution_id':identity+'-out',
        'non_cash_corporate_action':False,'formation_at':stamp(str(year)+'-06-04 09:00'),
        'entry_at':stamp(str(year)+'-06-04 10:00'),'exit_at':stamp(str(year)+'-06-05 10:00'),
        'entry_available_at':stamp(str(year)+'-06-04 10:01'),'exit_available_at':stamp(str(year)+'-06-05 10:01'),
        'costs_available_at':stamp(str(year)+'-06-05 10:02'),'corporate_actions_available_at':stamp(str(year)+'-06-05 10:03'),
        'entry_quantity':quantity,'exit_quantity':quantity,'entry_price':entry,'exit_price':exit,
        'entry_fee':1,'exit_fee':2,'other_costs':0,'cash_distributions':0}
def model_spec(family='identity'):
    return ModelSpec.from_dict({'schema_version':1,'model_id':'independent-'+family,'model_family':family,
        'features':['score'],'target_kind':'net_return','preprocessing':{'standardize':family=='ridge','constant_feature_policy':'unit_scale'},
        'hyperparameters':{'coefficient':1} if family=='identity' else {'alpha':2,'fit_intercept':True},
        'trainable_parameters':[] if family=='identity' else ['coefficients','intercept','feature_mean','feature_scale'],
        'purpose':'engineering_fixture'})

class ArithmeticTests(unittest.TestCase):
    def test_WR01_unsigned_label_matches_hand_arithmetic(self):
        for dtype in ('uint8','uint64','int8','int64','float16','float32','float64'):
            t=trade(entry=100,exit=90); frame=pd.DataFrame([t])
            for name in ('entry_price','exit_price','entry_fee','exit_fee','other_costs','cash_distributions','entry_quantity','exit_quantity'):
                frame[name]=frame[name].astype(dtype)
            labels=build_execution_labels(frame,protocol())
            with self.subTest(dtype=dtype):
                self.assertAlmostEqual(labels.gross_return.iloc[0],-.1); self.assertAlmostEqual(labels.net_return.iloc[0],-.13)
    def test_WR03_original_precision_mismatch_is_rejected(self):
        for left,right in [(Decimal('1.00000000000000000001'),Decimal('1.00000000000000000002')),
             ('1.00000000000000000001','1.00000000000000000002'),(Fraction(2**60+1,2**60),Fraction(2**60+2,2**60))]:
            t=trade(); t.update(entry_quantity=left,exit_quantity=right)
            with self.subTest(left=str(left)), self.assertRaises(LabelValidationError):
                build_execution_labels(pd.DataFrame([t]),protocol())
    def test_exact_equal_quantities_remain_usable_under_low_decimal_context(self):
        with localcontext() as ctx:
            ctx.prec=2; ctx.traps[Inexact]=True;ctx.traps[Rounded]=True;ctx.traps[FloatOperation]=True
            labels=build_execution_labels(pd.DataFrame([trade(quantity=Decimal('1.00000000000000000001'))]),protocol())
            self.assertAlmostEqual(labels.net_return.iloc[0],-.115)
    def test_integer_precision_and_tiny_unequal_guards(self):
        for left,right in [(2**53+1,2**53+1),(1e-13,1e-12),(0,0)]:
            t=trade(); t.update(entry_quantity=left,exit_quantity=right)
            with self.subTest(left=left),self.assertRaises(LabelValidationError):build_execution_labels(pd.DataFrame([t]),protocol())
    def test_cost_distribution_and_delayed_maturity_are_hand_checked(self):
        t=trade(entry=40,exit=44,quantity=3);t.update(cash_distributions=6,other_costs=3)
        labels=build_execution_labels(pd.DataFrame([t]),protocol())
        self.assertAlmostEqual(labels.gross_return.iloc[0],18/120)
        self.assertAlmostEqual(labels.net_return.iloc[0],12/120)
        self.assertEqual(labels.label_available_at.iloc[0],t['corporate_actions_available_at'])
    def test_factor_rolling_and_historical_rank_known_answer(self):
        times=pd.DatetimeIndex([stamp('2018-06-04 09:00'),stamp('2018-06-05 09:00'),stamp('2018-06-06 09:00')])
        values=pd.DataFrame([[10.,20.,100.],[30.,20.,100.],[50.,20.,100.]],index=times,columns=['X','Y','Z'])
        member=pd.DataFrame([[True,True,False],[True,True,False],[True,True,False]],index=times,columns=values.columns)
        window=PITWindow(times[-1],{'close':values},tuple(values.columns),member)
        f=factor({'op':'rolling_mean','window':2,'arg':{'op':'rank','arg':{'op':'field','name':'close'}}},['rolling_mean','rank'])
        got=f.evaluate(window);np.testing.assert_allclose(got.loc[['X','Y']],[1.,.5])
    def test_factor_safe_divide_and_lag_missing_boundaries(self):
        times=pd.DatetimeIndex([stamp('2018-06-04 09:00'),stamp('2018-06-05 09:00')])
        values=pd.DataFrame([[2.,4.],[6.,8.]],index=times,columns=['X','Y'])
        window=PITWindow(times[-1],{'close':values},('X','Y'))
        lag=factor({'op':'lag','periods':1,'arg':{'op':'field','name':'close'}},['lag'])
        np.testing.assert_allclose(lag.evaluate(window),[2.,4.])
        zero=factor({'op':'safe_divide','args':[{'op':'field','name':'close'},0]},['safe_divide'])
        self.assertTrue(zero.evaluate(window).isna().all())
    def test_forbidden_formula_future_field_negative_lag_and_depth(self):
        for form,ops in [({'op':'eval','args':['os.system']},['eval']),
             ({'op':'lag','periods':-1,'arg':{'op':'field','name':'close'}},['lag']),
             ({'op':'field','name':'future_close'},[])]:
            with self.subTest(form=form),self.assertRaises(FactorValidationError):factor(form,ops)
    def test_ridge_solution_independent_linear_algebra(self):
        spec=model_spec('ridge'); model=create_model(spec)
        X=pd.DataFrame({'score':[1.,2.,4.,7.]});y=pd.Series([.1,.25,.3,.8],name='net_return')
        model.fit(X,y);x=X.score.to_numpy();z=(x-x.mean())/x.std(ddof=0)
        beta=float(z@(y-y.mean()))/float(z@z+2);expected=y.mean()+z*beta
        np.testing.assert_allclose(model.predict(X),expected,rtol=1e-13,atol=1e-14)
    def test_ridge_refit_discards_old_statistics(self):
        a=create_model(model_spec('ridge')); b=create_model(model_spec('ridge'))
        a.fit(pd.DataFrame({'score':[1.,1000.,3000.]}),pd.Series([.1,.2,.3],name='net_return'))
        newX=pd.DataFrame({'score':[2.,4.,8.]});newy=pd.Series([.3,.2,.1],name='net_return')
        a.fit(newX,newy);b.fit(newX,newy)
        np.testing.assert_array_equal(a.predict(newX),b.predict(newX))
    def test_rank_ic_ties_and_absolute_negative_correlation(self):
        frame=pd.DataFrame({'formation_at':[stamp('2018-06-04 09:00')]*4,'sid':['W','X','Y','Z'],
            'prediction':[1.,1.,2.,3.],'label':[1.,2.,3.,4.]})
        got=daily_rank_ic(frame).ic.iloc[0]
        left=np.array([1.5,1.5,3.,4.]);right=np.array([1.,2.,3.,4.])
        expected=((left-left.mean())@(right-right.mean()))/np.sqrt(((left-left.mean())**2).sum()*((right-right.mean())**2).sum())
        self.assertAlmostEqual(got,expected)
        result=paired_factor_correlation(pd.Series([1.,2.,3.]),pd.Series([-1.,-2.,-3.]))
        self.assertAlmostEqual(result['correlation'],-1);self.assertAlmostEqual(result['absolute_correlation'],1)
    def test_rank_ic_is_invariant_to_small_positive_scale(self):
        frame=pd.DataFrame({'formation_at':[stamp('2018-06-04 09:00')]*3,'sid':['X','Y','Z'],
            'prediction':[1e-200,2e-200,3e-200],'label':[.1,.2,.3]})
        got=daily_rank_ic(frame).ic.iloc[0]
        OBSERVATIONS[self.id()]={'actual_ic':None if pd.isna(got) else float(got),'expected_ic':1.,'prediction_scale':1e-200}
        self.assertAlmostEqual(got,1.,msg='Spearman must rank distinct finite values before testing variance')

class DataTests(unittest.TestCase):
    def test_dynamic_top200_uses_20_sessions_and_ignores_financial_missingness(self):
        sessions=pd.bdate_range('2018-05-01',periods=20,tz=NY)+pd.Timedelta(hours=16)
        rows=[]
        for number in range(201):
            for time in sessions:
                rows.append({'sid':'S'+str(number).zfill(3),'session':time,'available_at':time,
                    'dollar_volume':float(number+1),'instrument_type':'common_stock','listed':True,
                    'financial_value':np.nan if number==200 else 1.})
        data=pd.DataFrame(rows);formation=sessions[-1]+pd.Timedelta(days=1)
        got=select_liquid_universe(data,formation,sessions)
        self.assertEqual(got,tuple('S'+str(n).zfill(3) for n in range(200,0,-1)))
        data.loc[data.sid=='S000','dollar_volume']=1000.
        changed=select_liquid_universe(data,formation,sessions)
        self.assertEqual(changed[0],'S000');self.assertNotIn('S001',changed)
    def test_point_in_time_revisions_never_backfill(self):
        formation=[stamp('2018-06-04 09:00'),stamp('2018-06-05 09:00')]
        event=stamp('2018-05-31 16:00')
        rows=pd.DataFrame([['X','book',event,stamp('2018-06-01 12:00'),10.,'v1'],
            ['X','book',event,stamp('2018-06-04 12:00'),20.,'v2']],columns=RECORD_COLUMNS)
        expected={formation[0]:stamp('2018-06-01 16:00'),formation[1]:stamp('2018-06-04 16:00')}
        window=causal_window(rows,formation,['X'],{'book':'latest_available'},expected,{'book':pd.Timedelta('30d')})
        np.testing.assert_array_equal(window.matrices['book']['X'],[10.,20.])
    def test_missing_exact_session_is_not_forward_filled(self):
        times=[stamp('2018-06-04 09:00'),stamp('2018-06-05 09:00')]
        rows=pd.DataFrame([['X','close',stamp('2018-06-01 16:00'),stamp('2018-06-01 16:00'),10.,'v1']],columns=RECORD_COLUMNS)
        window=causal_window(rows,times,['X'],{'close':'exact_session'},dict(zip(times,[stamp('2018-06-01 16:00'),stamp('2018-06-04 16:00')])))
        self.assertEqual(window.matrices['close'].iloc[0,0],10.);self.assertTrue(pd.isna(window.matrices['close'].iloc[1,0]))
    def test_cache_union_once_field_reuse_and_reader_no_provider(self):
        class Provider:
            def __init__(self):self.calls=[];self.provenance={'data_version':'v1'}
            def fetch(self,request):
                self.calls.append(request.identity());t=stamp('2018-06-01 16:00')
                return pd.DataFrame([[sid,f,t,t,10.,'v1'] for sid in request.sids for f in request.fields],columns=RECORD_COLUMNS)
        p=Provider();store=MemoryArtifactStore();cache=SharedDataCache(store,p)
        req=DataRequest('US Equities',('close',),('X','Y'),stamp('2018-01-01'),stamp('2019-01-01'),'v1','1'*64)
        cache.prefetch(req);cache.prefetch(req);self.assertEqual(len(p.calls),1)
        reader=SharedDataCache(store);self.assertEqual(len(reader.read(req)),2)
        with self.assertRaises(CacheMiss):reader.read(DataRequest('US Equities',('volume',),('X','Y'),req.start,req.end,'v1','1'*64))
        self.assertEqual(len(p.calls),1)
    def test_cache_failure_does_not_silently_refetch(self):
        class Provider:
            calls=0
            def fetch(self,request):self.calls+=1;raise TimeoutError('synthetic')
        p=Provider();cache=SharedDataCache(MemoryArtifactStore(),p)
        req=DataRequest('US Equities',('close',),('X',),stamp('2018-01-01'),stamp('2019-01-01'),'v1','1'*64)
        with self.assertRaises(TimeoutError):cache.prefetch(req)
        with self.assertRaises(RuntimeError):cache.prefetch(req)
        self.assertEqual(p.calls,1)
    def test_final_request_and_naive_time_are_rejected(self):
        for start,end in [(stamp('2023-01-01'),stamp('2024-01-02')),('2018-01-01',stamp('2019-01-01'))]:
            with self.subTest(start=str(start)),self.assertRaises(ValueError):
                DataRequest('US Equities',('close',),('X',),start,end,'v1','1'*64)
    def test_unknown_financial_delivery_kept_and_cannot_be_used(self):
        ing=HistoricalBatchIngestor(MemoryArtifactStore(),source='synthetic',data_version='v1',origin='historical_declared_fixture',
            financial_catalog={'financial.book':{'unit':'USD','period_accessor':'quarter'}},synthetic=True)
        row={'sid':'X','source_revision':'v1','field_path':'financial.book','unit':'USD','period_accessor':'quarter',
            'report_period_end':'2018-03-31T00:00:00-04:00','value':10.,'public_at':'2018-05-01T10:00:00-04:00',
            'public_precision':'timestamp','availability_basis':'unknown'}
        receipt=ing.ingest('financial',[row],partition='2018/X')
        self.assertEqual(receipt['gaps']['vendor_available_at_missing'],1)
        with self.assertRaises(MissingPITEvidence):ing.financial_records_asof(receipt['batch_ref'],stamp('2018-06-04 09:00'))
    def test_date_only_publication_gate_and_null_value_preserved(self):
        ing=HistoricalBatchIngestor(MemoryArtifactStore(),source='synthetic',data_version='v1',origin='historical_declared_fixture',
            financial_catalog={'financial.book':{'unit':'USD','period_accessor':'quarter'}},synthetic=True)
        row={'sid':'X','source_revision':'v1','field_path':'financial.book','unit':'USD','period_accessor':'quarter',
            'report_period_end':'2018-03-31T00:00:00-04:00','value':None,'public_date':'2018-05-04',
            'public_precision':'date','availability_basis':'actual_historical_receipt',
            'vendor_available_at':'2018-05-04T18:00:00-04:00','historical_ingested_at':'2018-05-04T19:00:00-04:00'}
        receipt=ing.ingest('financial',[row],partition='2018/X')
        with self.assertRaises(MissingPITEvidence):ing.financial_records_asof(receipt['batch_ref'],stamp('2018-05-07 16:01'))
        gates={'2018-05-04':'2018-05-07T16:00:00-04:00'}
        before=ing.financial_records_asof(receipt['batch_ref'],stamp('2018-05-07 15:59'),date_release_gates=gates)
        after=ing.financial_records_asof(receipt['batch_ref'],stamp('2018-05-07 16:01'),date_release_gates=gates)
        self.assertTrue(before.empty);self.assertEqual(len(after),1);self.assertTrue(pd.isna(after.value.iloc[0]))
    def test_revision_change_without_new_identity_is_conflict(self):
        ing=HistoricalBatchIngestor(MemoryArtifactStore(),source='synthetic',data_version='v1',origin='historical_declared_fixture',
            financial_catalog={'financial.book':{'unit':'USD','period_accessor':'quarter'}},synthetic=True)
        row={'sid':'X','source_revision':'v1','field_path':'financial.book','unit':'USD','period_accessor':'quarter',
            'report_period_end':'2018-03-31T00:00:00-04:00','value':1.,'public_precision':'unknown'}
        ing.ingest('financial',[row],partition='2018/X');row['value']=2.
        with self.assertRaises(ArtifactConflict):ing.ingest('financial',[row],partition='2018/X')
    def test_historical_mapping_cannot_use_later_receipt(self):
        mapping=[{'ticker':'X','sid':'OLD','effective_from':'2010-01-01T00:00:00-05:00','effective_to':None,
            'available_at':'2018-06-05T12:00:00-04:00'}]
        with self.assertRaises(IngestionError):resolve_historical_sid('X',stamp('2018-06-04 09:00'),mapping)

def independent_study():
    model=model_spec(); f=factor()
    return StudySpec.from_dict({'schema_version':1,'study_id':'independent-sixfold','purpose':'engineering_fixture',
        'synthetic':True,'timezone':'America/New_York','research_phase':'factor','factor_specs':[f.to_dict()],
        'model_spec':model.to_dict(),'label_spec':protocol().to_dict(),'trading_spec':None,
        'fixed_model_hash':model.configuration_hash,'feature_bindings':{'score':f.factor_id},
        'data_binding':{'data_version':'independent-synthetic-v1','universe_hash':'7'*64,'code_hash':'8'*64},
        'development':{'start':'2010-01-01','end_exclusive':'2024-01-01'},
        'final_evaluation':{'execution_enabled':False,'whole_window_is_untouched_independent_holdout':False}},field_catalog=['close'])
def independent_panel():
    scores=[]; trades=[]
    for year in range(2010,2024):
        for i,sid in enumerate(['X','Y','Z']):
            t=trade(year,sid,entry=100,exit=105+10*i,quantity=2)
            trades.append(t);scores.append({'sid':sid,'formation_at':t['formation_at'],'independent_factor':float(i+1)})
    return pd.DataFrame(scores),pd.DataFrame(trades)

class FullChainTests(unittest.TestCase):
    def test_six_folds_features_realized_labels_model_restore_and_ic(self):
        study=independent_study();scores,trades=independent_panel();store=MemoryArtifactStore()
        result=evaluate_registered_study(study,scores,trades,audit_store=store)
        self.assertEqual(len(result.folds),6);self.assertEqual(len(result.predictions),18)
        np.testing.assert_allclose(result.predictions.label,[.035,.135,.235]*6,atol=1e-14)
        np.testing.assert_allclose(result.daily_ic.ic,[1.]*6)
        self.assertEqual(result.folds.train_n.tolist(),[24]*6)
        for i,artifact in enumerate(result.model_artifacts):
            self.assertEqual(artifact['train_start'],stamp(str(2010+i)+'-01-01').isoformat())
            restored=restore_model(artifact);np.testing.assert_array_equal(restored.predict(pd.DataFrame({'score':[1.,2.,3.]})),[1.,2.,3.])
    def test_missing_factor_label_population_is_rejected(self):
        scores,trades=independent_panel()
        with self.assertRaises(PipelineValidationError):evaluate_registered_study(independent_study(),scores.iloc[:-1],trades)
    def test_maturity_purges_label_crossing_fit_boundary(self):
        labels=build_execution_labels(pd.DataFrame([trade(2017)]),protocol())
        labels.loc[0,'label_available_at']=stamp('2018-01-01 00:00')
        split=build_fold_splits(labels,six_rolling_folds()[0]);self.assertTrue(split.train.empty);self.assertEqual(split.excluded_train,1)
    def test_rolling_window_removes_2010_from_second_fold(self):
        scores,trades=independent_panel();labels=build_execution_labels(trades,protocol())
        one=build_fold_splits(labels,six_rolling_folds()[0]);two=build_fold_splits(labels,six_rolling_folds()[1])
        self.assertEqual(set(one.train.formation_at.dt.year),set(range(2010,2018)))
        self.assertEqual(set(two.train.formation_at.dt.year),set(range(2011,2019)))
    def test_cache_pit_factor_pipeline_complete_synthetic_chain(self):
        scores,trades=independent_panel();rows=[]
        for row in scores.itertuples():
            event=row.formation_at-pd.Timedelta(days=3)+pd.Timedelta(hours=7)
            rows.append([row.sid,'close',event,event,row.independent_factor,'v1'])
        class Provider:
            def fetch(self,request):
                data=pd.DataFrame(rows,columns=RECORD_COLUMNS)
                return data[(data.event_time>=request.start)&(data.event_time<request.end)].copy()
        cache=SharedDataCache(MemoryArtifactStore(),Provider());engine=ResearchEngine(cache,synthetic=True)
        req=DataRequest('US Equities',('close',),('X','Y','Z'),stamp('2010-01-01'),stamp('2024-01-01'),'v1','7'*64)
        engine.prepare([req]);generated=[]
        for time in sorted(scores.formation_at.unique()):
            event=time-pd.Timedelta(days=3)+pd.Timedelta(hours=7)
            membership=pd.DataFrame(True,index=pd.DatetimeIndex([time]),columns=['X','Y','Z'])
            payload=engine.evaluate([factor()],req,[time],['X','Y','Z'],{'close':'exact_session'},{time:event},membership=membership)
            for sid,values in zip(payload['values']['index'],payload['values']['data']):
                generated.append({'sid':sid,'formation_at':time,'independent_factor':values[0]})
        result=evaluate_registered_study(independent_study(),pd.DataFrame(generated),trades)
        np.testing.assert_allclose(result.daily_ic.ic,[1.]*6)
    def test_cache_pit_factor_pipeline_with_explicit_zoneinfo_adapter(self):
        # Extra positive path only. The original equivalent-pytz test above is
        # preserved and must still fail if the production compatibility defect exists.
        scores,trades=independent_panel();rows=[]
        for row in scores.itertuples():
            event=row.formation_at-pd.Timedelta(days=3)+pd.Timedelta(hours=7)
            rows.append([row.sid,'close',event,event,row.independent_factor,'v1'])
        class Provider:
            def fetch(self,request):
                data=pd.DataFrame(rows,columns=RECORD_COLUMNS)
                return data[(data.event_time>=request.start)&(data.event_time<request.end)].copy()
        cache=SharedDataCache(MemoryArtifactStore(),Provider());engine=ResearchEngine(cache,synthetic=True)
        req=DataRequest('US Equities',('close',),('X','Y','Z'),stamp('2010-01-01'),stamp('2024-01-01'),'v1','7'*64)
        engine.prepare([req]);generated=[]
        for time in sorted(scores.formation_at.unique()):
            event=time-pd.Timedelta(days=3)+pd.Timedelta(hours=7)
            index=pd.DatetimeIndex([time]).tz_convert(NY)
            membership=pd.DataFrame(True,index=index,columns=['X','Y','Z'])
            payload=engine.evaluate([factor()],req,[time],['X','Y','Z'],{'close':'exact_session'},{time:event},membership=membership)
            for sid,values in zip(payload['values']['index'],payload['values']['data']):
                generated.append({'sid':sid,'formation_at':time,'independent_factor':values[0]})
        result=evaluate_registered_study(independent_study(),pd.DataFrame(generated),trades)
        np.testing.assert_allclose(result.daily_ic.ic,[1.]*6)

class JsonResult(unittest.TextTestResult):
    def __init__(self,*args,**kwargs):super().__init__(*args,**kwargs);self.subcase_count=0
    def addSubTest(self,test,subtest,err):
        self.subcase_count+=1;super().addSubTest(test,subtest,err)

def main():
    suite=unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    stream=io.StringIO();runner=unittest.TextTestRunner(stream=stream,verbosity=2,resultclass=JsonResult)
    # Explicit offline guarantee: an accidental network connection fails the audit.
    def denied(*args,**kwargs):raise AssertionError('Independent audit is offline; network connection forbidden')
    socket.socket.connect=denied
    result=runner.run(suite)
    text=stream.getvalue();(ROOT/'independent_test_output.txt').write_text(text,encoding='utf-8')
    report={'actually_executed':True,'test_methods':result.testsRun,
        'passed_methods':result.testsRun-len(result.failures)-len(result.errors)-len(result.skipped),
        'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),
        'subcases':result.subcase_count,'subcases_are_not_extra_methods':True,
        'failure_details':[{'test':str(test),'traceback':tb} for test,tb in result.failures],
        'error_details':[{'test':str(test),'traceback':tb} for test,tb in result.errors],
        'observations':OBSERVATIONS,'environment':{'os':platform.platform(),'python':sys.version,
        'numpy':np.__version__,'pandas':pd.__version__,'longdouble_nmant':int(np.finfo(np.longdouble).nmant)},
        'developer_test_fixtures_imported':False,'market_calls':0}
    (ROOT/'independent_test_results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(text);print(json.dumps({k:report[k] for k in ('test_methods','passed_methods','failures','errors','skipped','subcases')}))
    return 0 if result.wasSuccessful() else 1
if __name__=='__main__':raise SystemExit(main())
