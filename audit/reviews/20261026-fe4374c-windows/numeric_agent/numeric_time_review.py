"""Independent synthetic audit of fe4374c rank/time fixes. No author fixtures."""
from pathlib import Path
from copy import deepcopy
from zoneinfo import ZoneInfo
import hashlib,io,json,math,platform,socket,sys,unittest
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parent
SOURCE=ROOT.parent/'source'
sys.path.insert(0,str(SOURCE/'cloud'))
from qresearch.contracts import NY,DataRequest,PITWindow,RECORD_COLUMNS,formation_index,canonical_membership
from qresearch.artifacts import MemoryArtifactStore
from qresearch.cache import SharedDataCache
from qresearch.point_in_time import causal_window
from qresearch.runtime import ResearchEngine,execution_plan_identity
from qresearch.factors import FactorSpec
from qresearch.models import ModelSpec,restore_model
from qresearch.labels import LabelProtocol
from qresearch.study import StudySpec
from qresearch.pipeline import evaluate_registered_study
from qresearch.evaluation import daily_rank_ic,paired_factor_correlation,pairwise_factor_correlations
OBS={}
def stamp(x,zone='America/New_York'):return pd.Timestamp(x,tz=zone)
def ranks(values):
    # Independent average-rank oracle, no pandas rank or production correlation.
    vals=list(values);sort=sorted(range(len(vals)),key=vals.__getitem__);result=[None]*len(vals);i=0
    while i<len(sort):
        j=i+1
        while j<len(sort) and vals[sort[j]]==vals[sort[i]]:j+=1
        for k in range(i,j):result[sort[k]]=(i+1+j)/2
        i=j
    return result
def corr_oracle(x,y):
    n=len(x)
    if n<2:return float('nan')
    mx=math.fsum(x)/n;my=math.fsum(y)/n
    a=[v-mx for v in x];b=[v-my for v in y]
    sa=math.fsum(v*v for v in a);sb=math.fsum(v*v for v in b)
    return math.fsum(u*v for u,v in zip(a,b))/math.sqrt(sa*sb) if sa and sb else float('nan')
def daily(x,y):
    n=len(x)
    return daily_rank_ic(pd.DataFrame({'sid':['S'+str(i) for i in range(n)],
        'formation_at':[stamp('2018-06-04 09:00')]*n,'prediction':x,'label':y})).iloc[0]
def spec():
    return FactorSpec.from_dict({'schema_version':1,'factor_id':'score_source',
      'economic_hypothesis':{'mechanism':'independent toy identity','expected_direction':1,
        'prediction_horizon_sessions':1,'applicable_regimes':['synthetic'],'failure_conditions':['not market evidence']},
      'allowed_fields':['close'],'allowed_operators':[],'parameters':{},'formula':{'op':'field','name':'close'}},field_catalog=['close'])
def fixture():
    times=pd.DatetimeIndex([stamp('2018-03-09 09:00'),stamp('2018-03-12 09:00')])
    events={times[0]:stamp('2018-03-08 16:00'),times[1]:stamp('2018-03-09 16:00')}
    records=pd.DataFrame([[sid,'close',event,event,value,'toy-v1'] for event in events.values()
        for sid,value in [('X',7.),('Y',9.)]],columns=RECORD_COLUMNS)
    members=pd.DataFrame([[True,False],[True,True]],index=times,columns=['X','Y'])
    request=DataRequest('US Equities',('close',),('X','Y'),stamp('2018-01-01'),stamp('2019-01-01'),'toy-v1','1'*64)
    return times,events,records,members,request
def window(records,times,events,members):
    return causal_window(records,times,['X','Y'],{'close':'exact_session'},events,membership=members)
def identity(request,times,events,members):
    return execution_plan_identity(request,times,['X','Y'],{'close':'exact_session'},events,membership=members)

class Numeric(unittest.TestCase):
    def test_original_WR05_reproduction_is_fixed(self):
        self.assertAlmostEqual(daily([1e-200,2e-200,3e-200],[.1,.2,.3]).ic,1.)
    def test_spearman_independent_rank_oracle_across_scales_sign_and_ties(self):
        base=np.array([-3.,-1.,-1.,2.,4.]);target=np.array([7.,3.,3.,5.,1.])
        expected=corr_oracle(ranks(base),ranks(target))
        for sx in [1e-320,1e-200,1.,1e200,1e306]:
            for sy in [1e-320,1e-200,1.,1e200,1e306]:
                for sign in [-1,1]:
                    x=base*sx;y=target*sy*sign
                    with self.subTest(sx=sx,sy=sy,sign=sign):
                        self.assertAlmostEqual(daily(x,y).ic,expected*sign)
                        self.assertAlmostEqual(paired_factor_correlation(pd.Series(x),pd.Series(y),method='spearman')['correlation'],expected*sign)
    def test_extreme_finite_scores_rank_without_overflow(self):
        x=[-1.7e308,-1e308,0.,1e308,1.7e308]
        self.assertAlmostEqual(daily(x,list(reversed(x))).ic,-1.)
    def test_spearman_constant_and_common_finite_sample(self):
        for x,y in [([1e-200]*3,[1.,2.,3.]),([1.,2.,3.],[1e200]*3)]:
            with self.subTest(side=x):self.assertTrue(math.isnan(daily(x,y).ic))
        a=pd.Series([4e-200,np.nan,2e-200,1e-200,np.inf],index=list('ABCDE'))
        b=pd.Series([4.,1.,2.,np.nan,9.],index=list('CADBF'))
        got=paired_factor_correlation(a,b,method='spearman')
        # Common finite A=(4e-200,1), C=(2e-200,4), D=(1e-200,2).
        self.assertEqual(got['n'],3);self.assertAlmostEqual(got['correlation'],-.5)
    def test_pearson_normal_scale_remains_distinct_from_spearman(self):
        a=[-2.,0.,1.,4.];b=[7.,2.,4.,-1.]
        got=paired_factor_correlation(pd.Series(a),pd.Series(b))
        self.assertAlmostEqual(got['correlation'],corr_oracle(a,b));self.assertEqual(got['method'],'pearson')
    def test_WR07_default_and_matrix_pearson_must_be_scale_invariant(self):
        # Expected mathematical answer is exact 1; all finite data are accepted.
        observations=[]
        for scale in [1e-200,1e200]:
            a=pd.Series(np.array([1.,2.,3.])*scale);b=pd.Series([1.,2.,3.])
            default=paired_factor_correlation(a,b)
            matrix=pairwise_factor_correlations(pd.DataFrame({'A':a,'B':b}))
            for name,value in [('default',default['correlation']),('absolute_matrix',matrix['absolute_pearson'].loc['A','B'])]:
                observations.append({'scale':scale,'path':name,'expected':1.,'actual':None if pd.isna(value) else float(value)})
                with self.subTest(scale=scale,path=name):self.assertAlmostEqual(value,1.)
        OBS['WR07']=observations

class Timezones(unittest.TestCase):
    def test_common_pandas_ny_input_no_adapter(self):
        t,e,r,m,q=fixture();got=window(r,t,e,m)
        np.testing.assert_array_equal(got.matrices['close'],[[7.,9.],[7.,9.]])
        self.assertIs(got.matrices['close'].index.tz,NY)
    def test_equivalent_ny_and_utc_inputs_have_same_plan_and_window(self):
        t,e,r,m,q=fixture();expected=identity(q,t,e,m)
        for time_zone in ['America/New_York',NY,'UTC']:
            for member_zone in ['America/New_York',NY,'UTC']:
                altered=m.copy();altered.index=m.index.tz_convert(member_zone)
                with self.subTest(time_zone=str(time_zone),member_zone=str(member_zone)):
                    self.assertEqual(identity(q,t.tz_convert(time_zone),e,altered),expected)
                    np.testing.assert_array_equal(window(r,t.tz_convert(time_zone),e,altered).matrices['close'],[[7.,9.],[7.,9.]])
    def test_timestamp_resolution_differences_preserve_exact_index(self):
        t,e,r,m,q=fixture()
        for unit in ['s','ms','us','ns']:
            shifted=m.copy();shifted.index=shifted.index.as_unit(unit)
            with self.subTest(unit=unit):self.assertEqual(identity(q,t,e,shifted),identity(q,t,e,m))
    def test_spring_dst_does_not_shift_actual_instants(self):
        t,e,r,m,q=fixture();idx=window(r,t,e,m).universe_membership.index
        self.assertEqual([x.utcoffset().total_seconds() for x in idx],[-18000.,-14400.])
        self.assertEqual(idx.tz_convert('UTC').hour.tolist(),[14,13])
    def test_fall_dst_repeated_wall_clock_stays_two_instants(self):
        times=pd.DatetimeIndex([pd.Timestamp('2018-11-04 05:30Z'),pd.Timestamp('2018-11-04 06:30Z')])
        event=stamp('2018-11-02 16:00');records=pd.DataFrame([['X','close',event,event,7.,'toy']],columns=RECORD_COLUMNS)
        members=pd.DataFrame(True,index=times.tz_convert('America/New_York'),columns=['X'])
        got=causal_window(records,times,['X'],{'close':'exact_session'},dict.fromkeys(times,event),membership=members)
        idx=got.matrices['close'].index
        self.assertEqual(idx.hour.tolist(),[1,1]);self.assertTrue(idx.is_unique)
        self.assertEqual(int((idx[1]-idx[0]).total_seconds()),3600)
    def test_direct_pit_normalizes_all_frames_without_mutating_input(self):
        t,e,r,m,q=fixture();a=pd.DataFrame([[1.,2.],[3.,4.]],index=t,columns=['X','Y']);b=a.copy();b.index=b.index.tz_convert('UTC')
        olda=a.copy(deep=True);oldb=b.copy(deep=True);oldm=m.copy(deep=True)
        got=PITWindow(t[-1],{'close':a,'volume':b},('X','Y'),m)
        self.assertTrue(got.matrices['close'].index.equals(got.matrices['volume'].index))
        pd.testing.assert_frame_equal(a,olda);pd.testing.assert_frame_equal(b,oldb);pd.testing.assert_frame_equal(m,oldm)
    def test_naive_missing_duplicate_reverse_and_misaligned_inputs_rejected(self):
        t,e,r,m,q=fixture();variants=[]
        for index in [t.tz_localize(None),pd.DatetimeIndex([t[0],t[0]]),t[::-1],t+pd.Timedelta(nanoseconds=1),pd.DatetimeIndex([t[0],pd.NaT])]:
            modified=m.copy();modified.index=index;variants.append(modified)
        for number,modified in enumerate(variants):
            for name,fn in [('causal',lambda:window(r,t,e,modified)),('plan',lambda:identity(q,t,e,modified))]:
                with self.subTest(variant=number,path=name),self.assertRaises((ValueError,TypeError)):fn()
    def test_nonboolean_missing_columns_and_future_members_rejected(self):
        t,e,r,m,q=fixture();variants=[m.astype(int),m.astype(float),m.assign(X=[True,None]),m.rename(columns={'X':'Z'}),pd.concat([m,m[['X']]],axis=1)]
        for number,modified in enumerate(variants):
            with self.subTest(variant=number),self.assertRaises(ValueError):window(r,t,e,modified)
        a=pd.DataFrame(1.,index=t,columns=['X','Y']);future=m.copy();future.index=future.index+pd.Timedelta(days=30)
        with self.assertRaises(ValueError):PITWindow(t[-1],{'close':a},('X','Y'),future)
        with self.assertRaises(ValueError):PITWindow(stamp('2024-01-01'),{'close':a},('X','Y'),m)
    def test_cache_identity_reused_for_timezone_equivalence(self):
        t,e,r,m,q=fixture()
        class Provider:
            calls=0
            def fetch(self,request):self.calls+=1;return r.copy()
        provider=Provider();store=MemoryArtifactStore();engine=ResearchEngine(SharedDataCache(store,provider),synthetic=True)
        engine.prepare([q]);first=engine.evaluate([spec()],q,t,['X','Y'],{'close':'exact_session'},e,membership=m)
        old_keys=set(store._data)
        changed=m.copy();changed.index=changed.index.tz_convert('UTC')
        second=engine.evaluate([spec()],q,t.tz_convert('UTC'),['X','Y'],{'close':'exact_session'},e,membership=changed)
        self.assertEqual(first,second);self.assertEqual(set(store._data),old_keys);self.assertEqual(provider.calls,1)
    def test_unadapted_full_cache_factor_label_sixfold_chain(self):
        f=spec()
        model=ModelSpec.from_dict({'schema_version':1,'model_id':'independent-scale-two','model_family':'identity','features':['signal'],
            'target_kind':'net_return','preprocessing':{'standardize':False,'constant_feature_policy':'unit_scale'},
            'hyperparameters':{'coefficient':2.},'trainable_parameters':[],'purpose':'engineering_fixture'})
        label=LabelProtocol.from_dict({'schema_version':1,'protocol_id':'independent-cash','target_kind':'net_return',
            'price_basis':'actual_fill','currency':'USD','normalization':'raw','corporate_action_policy':'reject_non_cash_actions',
            'denominator':'entry_notional','purpose':'engineering_fixture'})
        study=StudySpec.from_dict({'schema_version':1,'study_id':'independent-time-full-chain','purpose':'engineering_fixture','synthetic':True,
            'timezone':'America/New_York','research_phase':'factor','factor_specs':[f.to_dict()],'model_spec':model.to_dict(),
            'label_spec':label.to_dict(),'trading_spec':None,'fixed_model_hash':model.configuration_hash,'feature_bindings':{'signal':f.factor_id},
            'data_binding':{'data_version':'independent-chain','universe_hash':'1'*64,'code_hash':'2'*64},
            'development':{'start':'2010-01-01','end_exclusive':'2024-01-01'},'final_evaluation':{'execution_enabled':False}},field_catalog=['close'])
        rows=[];trades=[];times=[];events={}
        for year in range(2010,2024):
            time=stamp(str(year)+'-06-04 09:00');event=time-pd.Timedelta(days=1);times.append(time);events[time]=event
            for i,sid in enumerate(['X','Y','Z']):
                rows.append([sid,'close',event,event,float(1+2*i),'v1']);key=str(year)+sid
                trades.append({'trade_id':key,'sid':sid,'side':'long','currency':'USD','normalization':'raw','execution_source':'independent-toy',
                    'entry_execution_id':key+'-in','exit_execution_id':key+'-out','non_cash_corporate_action':False,'formation_at':time,
                    'entry_at':time+pd.Timedelta(hours=1),'exit_at':time+pd.Timedelta(days=1,hours=1),
                    'entry_available_at':time+pd.Timedelta(hours=1,minutes=1),'exit_available_at':time+pd.Timedelta(days=1,hours=1,minutes=1),
                    'costs_available_at':time+pd.Timedelta(days=1,hours=2),'corporate_actions_available_at':time+pd.Timedelta(days=1,hours=3),
                    'entry_quantity':2.,'exit_quantity':2.,'entry_price':100.,'exit_price':110.+10*i,'entry_fee':.5,'exit_fee':1.5,
                    'other_costs':0.,'cash_distributions':0.})
        class Provider:
            calls=0
            def fetch(self,request):
                self.calls+=1;data=pd.DataFrame(rows,columns=RECORD_COLUMNS)
                return data[(data.event_time>=request.start)&(data.event_time<request.end)].copy()
        provider=Provider();store=MemoryArtifactStore();engine=ResearchEngine(SharedDataCache(store,provider),synthetic=True)
        q=DataRequest('US Equities',('close',),('X','Y','Z'),stamp('2010-01-01'),stamp('2024-01-01'),'independent-chain','1'*64)
        engine.prepare([q]);calls=provider.calls;features=[]
        for time in times:
            m=pd.DataFrame(True,index=pd.DatetimeIndex([time]),columns=q.sids)
            got=engine.evaluate([f],q,[time],q.sids,{'close':'exact_session'},{time:events[time]},membership=m)
            for sid,values in zip(got['values']['index'],got['values']['data']):features.append({'sid':sid,'formation_at':time,f.factor_id:values[0]})
        got=evaluate_registered_study(study,pd.DataFrame(features),pd.DataFrame(trades),audit_store=store)
        self.assertEqual(len(got.model_artifacts),6);self.assertEqual(got.folds.train_n.tolist(),[24]*6)
        np.testing.assert_allclose(got.predictions.prediction,[2.,6.,10.]*6)
        np.testing.assert_allclose(got.predictions.label,[.09,.19,.29]*6)
        np.testing.assert_allclose(got.daily_ic.ic,[1.]*6)
        self.assertEqual(provider.calls,calls)
        for artifact in got.model_artifacts:
            restored=restore_model(artifact);np.testing.assert_allclose(restored.predict(pd.DataFrame({'signal':[1.,3.,5.]})),[2.,6.,10.])
        OBS['full_chain']={'folds':6,'predictions':18,'models_restored':6,'prefetch_calls':calls,'extra_history_calls':provider.calls-calls}

class DetailedResult(unittest.TextTestResult):
    def __init__(self,*a,**k):super().__init__(*a,**k);self.subcase_count=0
    def addSubTest(self,test,subtest,error):self.subcase_count+=1;super().addSubTest(test,subtest,error)
def main():
    files=list((SOURCE/'cloud').rglob('*.py'))
    hashes={str(p.relative_to(SOURCE)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    def denied(*a,**k):raise AssertionError('Network prohibited in independent numeric/time tests')
    socket.socket.connect=denied
    stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2,resultclass=DetailedResult).run(unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    def mid(test):return getattr(test,'test_case',test).id()
    failed={mid(t) for t,_ in result.failures};errors={mid(t) for t,_ in result.errors}
    report={'source_commit':'fe4374cee054fb8053706074be913ad7068c4484','actually_executed':True,
       'methods':result.testsRun,'passed_methods':result.testsRun-len(failed|errors)-len(result.skipped),
       'failed_methods':len(failed),'error_methods':len(errors),'failure_records':len(result.failures),'error_records':len(result.errors),
       'skipped':len(result.skipped),'subcases':result.subcase_count,'observations':OBS,
       'failures':[{'test':str(t),'traceback':tb} for t,tb in result.failures],
       'errors':[{'test':str(t),'traceback':tb} for t,tb in result.errors],
       'environment':{'platform':platform.platform(),'python':sys.version,'numpy':np.__version__,'pandas':pd.__version__},
       'author_test_fixtures_imported':False,'source_unchanged':all(hashlib.sha256(p.read_bytes()).hexdigest()==hashes[str(p.relative_to(SOURCE))] for p in files),
       'market_calls':0,'financial_evidence':False}
    (ROOT/'test_results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    (ROOT/'test_output.txt').write_text(stream.getvalue(),encoding='utf-8')
    print(stream.getvalue());print(json.dumps({k:report[k] for k in ('methods','passed_methods','failed_methods','error_methods','failure_records','skipped','subcases','source_unchanged')}))
    return 0 if result.wasSuccessful() else 1
if __name__=='__main__':raise SystemExit(main())
