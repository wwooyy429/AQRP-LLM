"""Independent WR08 public-interface and whole-chain compatibility checks.

All plans, factor rows and explicit executions below are independently created
synthetic fixtures. No developer test helpers or external service is used.
"""
from pathlib import Path
import ast,hashlib,io,json,math,os,platform,sys,unittest
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent
SOURCE=ROOT.parent/'source'
BASE=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-7b0dcce-20261026\source')
sys.path.insert(0,str(SOURCE/'cloud'))
from qresearch.evaluation import daily_rank_ic,summarize_ic,paired_factor_correlation,pairwise_factor_correlations
from qresearch.artifacts import MemoryArtifactStore
from qresearch.models import ModelSpec,restore_model
from qresearch.study import StudySpec
from qresearch.pipeline import evaluate_registered_study

OBS={}
def t(s):return pd.Timestamp(s,tz='America/New_York')
def make_study():
    model=ModelSpec.from_dict({'schema_version':1,'model_id':'independent-wr08-ridge','model_family':'ridge',
        'features':['score'],'target_kind':'net_return','preprocessing':{'standardize':True,'constant_feature_policy':'unit_scale'},
        'hyperparameters':{'alpha':.75,'fit_intercept':True},
        'trainable_parameters':['coefficients','intercept','feature_mean','feature_scale'],'purpose':'engineering_fixture'})
    label={'schema_version':1,'protocol_id':'independent-wr08-cash','target_kind':'net_return','price_basis':'actual_fill',
        'currency':'USD','normalization':'raw','corporate_action_policy':'reject_non_cash_actions',
        'denominator':'entry_notional','purpose':'engineering_fixture'}
    factor={'schema_version':1,'factor_id':'synthetic_measure','economic_hypothesis':{
        'mechanism':'synthetic oracle only','expected_direction':1,'prediction_horizon_sessions':1,
        'applicable_regimes':['synthetic'],'failure_conditions':['not financial evidence']},
        'allowed_fields':['close'],'allowed_operators':[],'parameters':{},'formula':{'op':'field','name':'close'}}
    return StudySpec.from_dict({'schema_version':1,'study_id':'independent-wr08-whole-chain','purpose':'engineering_fixture',
        'synthetic':True,'timezone':'America/New_York','research_phase':'factor','factor_specs':[factor],
        'model_spec':model.to_dict(),'label_spec':label,'trading_spec':None,'fixed_model_hash':model.configuration_hash,
        'feature_bindings':{'score':'synthetic_measure'},'data_binding':{
            'data_version':'independent-synthetic','universe_hash':'a'*64,'code_hash':'b'*64},
        'development':{'start':'2010-01-01','end_exclusive':'2024-01-01'},'final_evaluation':{
            'execution_enabled':False,'whole_window_is_untouched_independent_holdout':False}},field_catalog=['close'])

def executions_and_features():
    prices_order=[1,2,4,5,3];features=[];executions=[]
    for year in range(2010,2024):
        for month in ['05','10']:
            for score,sid,label_rank in zip(range(1,6),['J','K','L','M','N'],prices_order):
                day=f'{year}-{month}-06';form=t(day+' 09:00');entry=t(day+' 10:00');exit=entry+pd.Timedelta(days=1)
                identity=f'{year}-{month}-{sid}'
                features.append({'sid':sid,'formation_at':form,'synthetic_measure':score+(year-2010)*.01})
                executions.append({'trade_id':identity,'sid':sid,'side':'long','currency':'USD','normalization':'raw',
                    'execution_source':'independent-synthetic','entry_execution_id':identity+'-open','exit_execution_id':identity+'-close',
                    'non_cash_corporate_action':False,'formation_at':form,'entry_at':entry,'exit_at':exit,
                    'entry_available_at':entry+pd.Timedelta(minutes=1),'exit_available_at':exit+pd.Timedelta(minutes=1),
                    'costs_available_at':exit+pd.Timedelta(minutes=2),'corporate_actions_available_at':exit+pd.Timedelta(minutes=3),
                    'entry_quantity':1.,'exit_quantity':1.,'entry_price':100.,'exit_price':100.+3*label_rank,
                    'entry_fee':.05,'exit_fee':.05,'other_costs':0.,'cash_distributions':0.})
    return pd.DataFrame(features),pd.DataFrame(executions)

class Compatibility(unittest.TestCase):
    def test_public_pearson_spearman_and_matrix_contracts(self):
        left=pd.Series([1.,2.,4.,8.],index=['j','k','l','m'])
        right=pd.Series([1.,5.,3.,7.],index=['j','k','l','m'])
        a=paired_factor_correlation(left,right);b=paired_factor_correlation(left,right,'spearman')
        x=left.to_numpy();y=right.to_numpy();cx=x-x.mean();cy=y-y.mean()
        expected=float(cx@cy)/math.sqrt(float(cx@cx)*float(cy@cy))
        self.assertEqual(a['method'],'pearson');self.assertEqual(a['n'],4)
        self.assertAlmostEqual(a['correlation'],expected,places=14)
        self.assertAlmostEqual(b['correlation'],.8,places=14)
        matrix=pairwise_factor_correlations(pd.DataFrame({'left':left,'right':right}))
        self.assertEqual(set(matrix),{'absolute_pearson','absolute_spearman','n'})
        np.testing.assert_array_equal(matrix['n'],np.full((2,2),4.))
        self.assertAlmostEqual(matrix['absolute_pearson'].loc['left','right'],abs(expected),places=14)
        self.assertAlmostEqual(matrix['absolute_spearman'].loc['left','right'],.8,places=14)

    def test_finite_common_alignment_preserved(self):
        left=pd.Series([2.,4.,np.nan,np.inf,8.],index=list('jklmn'))
        right=pd.Series([8.,6.,-8.,-4.,-2.],index=list('zmlkj'))
        for method in ['pearson','spearman']:
            with self.subTest(method=method):
                result=paired_factor_correlation(left,right,method)
                self.assertEqual(result['n'],2)
                self.assertAlmostEqual(result['correlation'],-1.)
                self.assertAlmostEqual(result['absolute_correlation'],1.)

    def test_daily_missing_day_and_common_n_count_contract(self):
        rows=[]
        for day,predictions,labels in [
            (6,[1.,2.,3.,4.,5.],[1.,2.,4.,5.,np.nan]),
            (7,[1.,2.,np.nan,np.nan,np.nan],[1.,2.,3.,4.,5.]),
            (8,[np.nan]*5,[1.,2.,3.,4.,5.])]:
            for sid,score,label in zip('jklmn',predictions,labels):
                rows.append({'formation_at':t(f'2018-05-{day:02d} 09:00'),'sid':sid,'prediction':score,'label':label})
        frame=pd.DataFrame(rows);frame.index=[0]*15
        daily=daily_rank_ic(frame);summary=summarize_ic(daily)
        self.assertEqual(daily.n.tolist(),[4,2,0]);self.assertEqual(summary['common_observations'],6)
        self.assertEqual(summary['total_days'],3);self.assertEqual(summary['valid_days'],1)
        self.assertEqual(daily.ic.iloc[0],1.);self.assertTrue(daily.ic.iloc[1:].isna().all())
        self.assertEqual(summary['mean_ic'],1.);self.assertTrue(np.isnan(summary['sample_std_ic']))
        self.assertTrue(np.isnan(summary['icir']));self.assertFalse(summary['icir_annualized'])

    def test_zero_one_and_two_valid_day_rules(self):
        cases=[([],[],0),( [np.nan,np.inf,-np.inf],[3,4,5],0),([.37],[5],1),([.1,.3],[4,4],2)]
        for values,counts,valid in cases:
            with self.subTest(values=values):
                stats=summarize_ic(pd.DataFrame({'ic':values,'n':counts}))
                self.assertEqual(stats['valid_days'],valid);self.assertEqual(stats['total_days'],len(values))
                self.assertEqual(stats['common_observations'],sum(counts))
                if valid==0:self.assertTrue(np.isnan(stats['mean_ic']))
                if valid<2:
                    self.assertTrue(np.isnan(stats['sample_std_ic']));self.assertTrue(np.isnan(stats['icir']))
                else:
                    self.assertAlmostEqual(stats['mean_ic'],.2,places=15)
                    self.assertAlmostEqual(stats['sample_std_ic'],.2/math.sqrt(2),places=15)
                    self.assertAlmostEqual(stats['icir'],math.sqrt(2),places=14)

    def test_ddof_one_and_no_annualization(self):
        stats=summarize_ic(pd.DataFrame({'ic':[-.2,0.,.2,.4],'n':[5]*4}))
        self.assertAlmostEqual(stats['mean_ic'],.1,places=15)
        self.assertAlmostEqual(stats['sample_std_ic'],math.sqrt(.2/3),places=15)
        self.assertAlmostEqual(stats['icir'],.1/math.sqrt(.2/3),places=15)
        self.assertFalse(stats['icir_annualized'])

    def test_exact_constants_remain_undefined_without_tolerance(self):
        for constant,count in [(0.,7),(.37,9),(-.7,5),(.7,6)]:
            with self.subTest(constant=constant,count=count):
                stats=summarize_ic(pd.DataFrame({'ic':[constant]*count,'n':[5]*count}))
                self.assertEqual(stats['mean_ic'],constant);self.assertEqual(stats['sample_std_ic'],0.)
                self.assertTrue(np.isnan(stats['icir']))

    def test_adjacent_nonconstant_ic_keeps_real_variation(self):
        low=.7;high=float(np.nextafter(low,np.inf));delta=high-low
        stats=summarize_ic(pd.DataFrame({'ic':[low,high],'n':[5,5]}))
        expected_std=delta/math.sqrt(2.)
        expected_mean=low+delta/2.
        self.assertGreater(stats['sample_std_ic'],0.)
        self.assertTrue(math.isfinite(stats['icir']))
        self.assertTrue(math.isclose(stats['sample_std_ic'],expected_std,rel_tol=2e-15,abs_tol=0.))
        self.assertTrue(math.isclose(stats['icir'],expected_mean/expected_std,rel_tol=2e-15,abs_tol=0.))
        OBS['adjacent_ic']={'low':low,'high':high,'delta':delta,'summary':stats}

    def test_full_registered_ridge_chain_restores_nonperfect_constant_rank_statistics(self):
        features,trades=executions_and_features();result=evaluate_registered_study(make_study(),features,trades,audit_store=MemoryArtifactStore())
        self.assertEqual(len(result.predictions),60);self.assertEqual(len(result.model_artifacts),6)
        self.assertEqual(result.folds.train_n.tolist(),[80]*6);self.assertEqual(result.folds.validation_n.tolist(),[10]*6)
        self.assertEqual(result.daily_ic.n.tolist(),[5]*12)
        np.testing.assert_array_equal(result.daily_ic.ic,np.full(12,.7))
        self.assertEqual(result.ic_statistics['mean_ic'],.7);self.assertEqual(result.ic_statistics['sample_std_ic'],0.)
        self.assertTrue(np.isnan(result.ic_statistics['icir']));self.assertFalse(result.ic_statistics['icir_annualized'])
        for number,artifact in enumerate(result.model_artifacts,1):
            with self.subTest(fold=number):
                self.assertEqual(artifact['training_rows'],80)
                self.assertEqual(artifact['train_start'],t(f'{2009+number}-01-01').isoformat())
                self.assertEqual(artifact['fit_cutoff'],t(f'{2017+number}-01-01').isoformat())
                data=result.predictions[result.predictions.fold_id==number].merge(features,on=['sid','formation_at'])
                restored=restore_model(artifact)
                actual=restored.predict(data[['synthetic_measure']].rename(columns={'synthetic_measure':'score'}))
                np.testing.assert_allclose(actual,data.prediction,rtol=0,atol=1e-15)
        OBS['registered_chain']={'train_n':result.folds.train_n.tolist(),'validation_n':result.folds.validation_n.tolist(),
            'predictions':len(result.predictions),'artifacts':len(result.model_artifacts),
            'daily_ic':result.daily_ic.ic.tolist(),'sample_std_ic':result.ic_statistics['sample_std_ic'],
            'icir':None if np.isnan(result.ic_statistics['icir']) else result.ic_statistics['icir']}

def filehash(path):return hashlib.sha256(path.read_text(encoding='utf-8-sig').encode()).hexdigest()
def get_function(path,name):
    source=path.read_text(encoding='utf-8-sig');node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name==name)
    return ast.get_source_segment(source,node)
def statics():
    protected={}
    for folder in ['config','templates']:
        for p in (BASE/folder).rglob('*'):
            if p.is_file():
                rel=p.relative_to(BASE).as_posix();protected[rel]=(SOURCE/rel).is_file() and filehash(p)==filehash(SOURCE/rel)
    for rel in ['AGENTS.md','docs/research_charter.md','audit/data_exposure.json','audit/runtime/registry/baseline.json',
        'audit/runtime/registry/events.jsonl','tools/research.py','tools/stages.py','tools/stage2.py']:
        protected[rel]=filehash(BASE/rel)==filehash(SOURCE/rel)
    for p in (BASE/'cloud').rglob('*.py'):
        rel=p.relative_to(BASE).as_posix()
        if rel not in ['cloud/qresearch/evaluation.py','cloud/research_config.py']:
            protected[rel]=filehash(p)==filehash(SOURCE/rel)
    prod_changed=[]
    for folder in ['cloud','config','templates']:
        for p in (BASE/folder).rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts:
                rel=p.relative_to(BASE).as_posix()
                if not (SOURCE/rel).exists() or filehash(p)!=filehash(SOURCE/rel):prod_changed.append(rel)
    unchanged_functions={name:get_function(BASE/'cloud/qresearch/evaluation.py',name)==get_function(SOURCE/'cloud/qresearch/evaluation.py',name)
        for name in ['_centered_unit','_correlation','daily_rank_ic','paired_factor_correlation','pairwise_factor_correlations','walk_forward_evaluate']}
    def generated(path):
        return {n.targets[0].id:ast.literal_eval(n.value) for n in ast.parse(path.read_text(encoding='utf-8-sig')).body if isinstance(n,ast.Assign)}
    a,b=generated(BASE/'cloud/research_config.py'),generated(SOURCE/'cloud/research_config.py')
    return {'protected_hashes_equal':protected,'production_changed_paths':prod_changed,
        'public_and_upstream_functions_source_equal':unchanged_functions,
        'generated_configuration_equal':a['CONFIGURATION']==b['CONFIGURATION'],
        'generated_source_sha_equal':a['SOURCE_SHA256']==b['SOURCE_SHA256'],
        'generated_implementation_sha_changed':a['IMPLEMENTATION_SHA256']!=b['IMPLEMENTATION_SHA256'],
        'existing_test_files_unchanged':all(filehash(p)==filehash(SOURCE/'tests'/p.name) for p in (BASE/'tests').glob('*.py'))}

class Results(unittest.TextTestResult):
    def __init__(self,*a,**kw):super().__init__(*a,**kw);self.subcases=0
    def addSubTest(self,test,subtest,err):self.subcases+=1;super().addSubTest(test,subtest,err)

def main():
    output=io.StringIO();result=unittest.TextTestRunner(stream=output,verbosity=2,resultclass=Results).run(unittest.defaultTestLoader.loadTestsFromTestCase(Compatibility))
    text=output.getvalue();(ROOT/'output.txt').write_text(text,encoding='utf-8')
    def identity(test):return getattr(test,'test_case',test).id()
    failures={identity(x) for x,_ in result.failures};errors={identity(x) for x,_ in result.errors};skipped={identity(x) for x,_ in result.skipped}
    report={'reviewed_source_commit':'d0b9c98ae9490b977d62f3e9742d854146d298b4','actually_executed':True,
        'methods':result.testsRun,'passed_methods':result.testsRun-len(failures|errors|skipped),'failed_methods':len(failures),
        'error_methods':len(errors),'skipped_methods':len(skipped),'subcases':result.subcases,
        'failure_records_including_subcases':len(result.failures),'error_records_including_subcases':len(result.errors),
        'failure_details':[{'method':identity(test),'traceback':tb} for test,tb in result.failures],
        'error_details':[{'method':identity(test),'traceback':tb} for test,tb in result.errors],
        'observations':OBS,'static_checks':statics(),'developer_fixtures_imported':False,
        'environment':{'platform':platform.platform(),'python':sys.version,'numpy':np.__version__,'pandas':pd.__version__},
        'external_calls':0,'financial_evidence':False,'exit_code':0 if result.wasSuccessful() else 1}
    # NaN is explicitly represented as null in JSON observations, with source
    # assertions proving the undefined value rather than concealing a failure.
    def clean(x):
        if isinstance(x,float) and not math.isfinite(x):return None
        if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
        if isinstance(x,list):return [clean(v) for v in x]
        return x
    (ROOT/'results.json').write_text(json.dumps(clean(report),ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(text);print(json.dumps({k:report[k] for k in ['methods','passed_methods','failed_methods','error_methods','skipped_methods','subcases','exit_code']}))
    print(json.dumps(report['static_checks'],ensure_ascii=False))
    return report['exit_code']
if __name__=='__main__':raise SystemExit(main())
