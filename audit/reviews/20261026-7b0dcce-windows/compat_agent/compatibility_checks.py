"""Independent public evaluation-contract checks; no author fixtures or APIs."""
from pathlib import Path
from copy import deepcopy
import ast,hashlib,io,json,math,os,platform,shutil,subprocess,sys,unittest
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent
SOURCE=ROOT.parent/'source'
BASE=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-fe4374c-20261026\source')
sys.path.insert(0,str(SOURCE/'cloud'))
from qresearch.evaluation import daily_rank_ic,summarize_ic,paired_factor_correlation,pairwise_factor_correlations,EvaluationError
from qresearch.artifacts import MemoryArtifactStore
from qresearch.models import ModelSpec,restore_model
from qresearch.labels import LabelProtocol
from qresearch.factors import FactorSpec
from qresearch.study import StudySpec
from qresearch.pipeline import evaluate_registered_study,PipelineValidationError

def t(text):return pd.Timestamp(text,tz='America/New_York')
def model_spec():
    return ModelSpec.from_dict({'schema_version':1,'model_id':'independent-compat-ridge','model_family':'ridge',
        'features':['score'],'target_kind':'net_return','preprocessing':{'standardize':True,'constant_feature_policy':'unit_scale'},
        'hyperparameters':{'alpha':2.,'fit_intercept':True},
        'trainable_parameters':['coefficients','intercept','feature_mean','feature_scale'],'purpose':'engineering_fixture'})
def study():
    model=model_spec()
    label={'schema_version':1,'protocol_id':'independent-compat-label','target_kind':'net_return',
        'price_basis':'actual_fill','currency':'USD','normalization':'raw','corporate_action_policy':'reject_non_cash_actions',
        'denominator':'entry_notional','purpose':'engineering_fixture'}
    factor={'schema_version':1,'factor_id':'compat_factor','economic_hypothesis':{
        'mechanism':'independent synthetic fixture','expected_direction':1,'prediction_horizon_sessions':1,
        'applicable_regimes':['synthetic only'],'failure_conditions':['not market evidence']},
        'allowed_fields':['close'],'allowed_operators':[],'parameters':{},'formula':{'op':'field','name':'close'}}
    return StudySpec.from_dict({'schema_version':1,'study_id':'independent-compat-sixfold','purpose':'engineering_fixture',
        'synthetic':True,'timezone':'America/New_York','research_phase':'factor','factor_specs':[factor],
        'model_spec':model.to_dict(),'label_spec':label,'trading_spec':None,
        'fixed_model_hash':model.configuration_hash,'feature_bindings':{'score':'compat_factor'},
        'data_binding':{'data_version':'independent-synthetic-compat','universe_hash':'a'*64,'code_hash':'b'*64},
        'development':{'start':'2010-01-01','end_exclusive':'2024-01-01'},'final_evaluation':{
            'execution_enabled':False,'whole_window_is_untouched_independent_holdout':False}},field_catalog=['close'])

def panel():
    features=[];trades=[]
    for year in range(2010,2024):
        for month in ('06','09'):
            for k,sid in enumerate(['Q','R','S'],1):
                day=f'{year}-{month}-04';formation=t(day+' 09:00');entry=t(day+' 10:00')
                exit=entry+pd.Timedelta(days=1);identity=f'{year}-{month}-{sid}'
                features.append({'sid':sid,'formation_at':formation,'compat_factor':k+(year-2010)*.01})
                trades.append({'trade_id':identity,'sid':sid,'side':'long','currency':'USD','normalization':'raw',
                    'execution_source':'independent-synthetic','entry_execution_id':identity+'-buy','exit_execution_id':identity+'-sell',
                    'non_cash_corporate_action':False,'formation_at':formation,'entry_at':entry,'exit_at':exit,
                    'entry_available_at':entry+pd.Timedelta(minutes=1),'exit_available_at':exit+pd.Timedelta(minutes=1),
                    'costs_available_at':exit+pd.Timedelta(minutes=2),'corporate_actions_available_at':exit+pd.Timedelta(minutes=3),
                    'entry_quantity':2.,'exit_quantity':2.,'entry_price':100.,
                    'exit_price':100.+3*k+(year-2010)*.01,'entry_fee':.2,'exit_fee':.2,'other_costs':0.,'cash_distributions':0.})
    return pd.DataFrame(features),pd.DataFrame(trades)

class PublicContracts(unittest.TestCase):
    def test_default_pearson_stays_distinct_from_spearman(self):
        x=pd.Series([1.,2.,3.]);y=pd.Series([1.,2.,9.])
        default=paired_factor_correlation(x,y);rank=paired_factor_correlation(x,y,'spearman')
        self.assertEqual(default['method'],'pearson');self.assertEqual(default['n'],3)
        self.assertEqual(set(default),{'method','n','correlation','absolute_correlation'})
        self.assertAlmostEqual(default['correlation'],8/math.sqrt(76),places=14)
        self.assertAlmostEqual(default['absolute_correlation'],8/math.sqrt(76),places=14)
        self.assertEqual(rank['correlation'],1.)

    def test_alignment_and_shared_finite_filtering(self):
        x=pd.Series([1.,2.,np.nan,np.inf,5.],index=list('abcde'))
        y=pd.Series([-5.,8.,7.,-2.,100.],index=list('edcbz'))
        for method in ['pearson','spearman']:
            with self.subTest(method=method):
                got=paired_factor_correlation(x,y,method)
                self.assertEqual(got['n'],2);self.assertAlmostEqual(got['correlation'],-1.)
                self.assertAlmostEqual(got['absolute_correlation'],1.)

    def test_reordering_index_does_not_change_result(self):
        x=pd.Series([1.,2.,3.],index=['a','b','c']);y=pd.Series([1.,2.,9.],index=['a','b','c'])
        for method in ['pearson','spearman']:
            with self.subTest(method=method):
                a=paired_factor_correlation(x,y,method);b=paired_factor_correlation(x,y.reindex(['c','a','b']),method)
                self.assertEqual(a,b)

    def test_zero_one_two_common_observations(self):
        for method in ['pearson','spearman']:
            for count in [0,1,2]:
                with self.subTest(method=method,count=count):
                    x=pd.Series([1.,2.][:count],dtype=float);y=pd.Series([3.,1.][:count],dtype=float)
                    result=paired_factor_correlation(x,y,method);self.assertEqual(result['n'],count)
                    if count<2:self.assertTrue(np.isnan(result['correlation']))
                    else:self.assertAlmostEqual(result['correlation'],-1.)

    def test_constant_zero_and_missing_stay_nan(self):
        for method in ['pearson','spearman']:
            for values in ([0.,0.,0.],[7.,7.,7.],[np.nan,np.nan,np.nan]):
                with self.subTest(method=method,values=values):
                    result=paired_factor_correlation(pd.Series(values),pd.Series([1.,2.,3.]),method)
                    self.assertTrue(np.isnan(result['correlation']));self.assertTrue(np.isnan(result['absolute_correlation']))
                    self.assertEqual(result['n'],0 if np.isnan(values[0]) else 3)

    def test_duplicate_indices_and_unknown_method_rejected(self):
        with self.assertRaises(EvaluationError):paired_factor_correlation(pd.Series([1.,2.],index=['a','a']),pd.Series([1.,2.]))
        with self.assertRaises(EvaluationError):paired_factor_correlation(pd.Series([1.,2.]),pd.Series([1.,2.],index=['a','a']))
        with self.assertRaises(EvaluationError):paired_factor_correlation(pd.Series([],dtype=float),pd.Series([],dtype=float),'kendall')

    def test_pairwise_matrix_preserves_common_sample_counts_and_sign_absolute(self):
        features=pd.DataFrame({'candidate':[1.,2.,3.,np.nan],
            'negative':[-1.,-2.,-3.,4.],'partial':[10.,np.nan,30.,40.]},index=list('abcd'))
        matrix=pairwise_factor_correlations(features)
        self.assertEqual(set(matrix),{'absolute_pearson','absolute_spearman','n'})
        np.testing.assert_array_equal(matrix['n'],[[3,3,2],[3,4,3],[2,3,3]])
        for name in ['absolute_pearson','absolute_spearman']:
            self.assertAlmostEqual(matrix[name].loc['candidate','negative'],1.)
            self.assertAlmostEqual(matrix[name].loc['candidate','partial'],1.)
            np.testing.assert_allclose(matrix[name],matrix[name].T,atol=1e-14)

    def test_daily_common_samples_with_duplicate_dataframe_labels(self):
        frame=pd.DataFrame({'formation_at':[t('2018-01-04 09:00')]*4+[t('2018-01-05 09:00')]*3,
            'sid':['a','b','c','d','a','b','c'],'prediction':[1.,2.,3.,4.,1.,2.,3.],
            'label':[1.,2.,3.,np.nan,3.,2.,1.]})
        frame.index=[0]*len(frame)
        result=daily_rank_ic(frame);self.assertEqual(result.n.tolist(),[3,3]);np.testing.assert_array_equal(result.ic,[1.,-1.])

    def test_same_rank_daily_ic_keeps_constant_icir_nan(self):
        rows=[]
        for day in range(4,10):
            for sid,score in zip(['a','b','c'],[1.,2.,3.]):
                rows.append({'formation_at':t(f'2018-06-{day:02d} 09:00'),'sid':sid,'prediction':score,'label':score*2+1})
        daily=daily_rank_ic(pd.DataFrame(rows));stats=summarize_ic(daily)
        np.testing.assert_array_equal(daily.ic,np.ones(6));self.assertEqual(stats['sample_std_ic'],0.)
        self.assertEqual(stats['mean_ic'],1.);self.assertTrue(np.isnan(stats['icir']))

    def test_same_nonperfect_rank_daily_ic_keeps_constant_icir_nan(self):
        rows=[]
        labels=[1.,2.,4.,5.,3.]
        for day in range(4,10):
            for sid,score,label in zip(['a','b','c','d','e'],[1.,2.,3.,4.,5.],labels):
                rows.append({'formation_at':t(f'2018-06-{day:02d} 09:00'),'sid':sid,'prediction':score,'label':label})
        daily=daily_rank_ic(pd.DataFrame(rows));stats=summarize_ic(daily)
        # The hand Spearman answer is 1-6*(1+1+4)/(5*(25-1)) = 0.7.
        np.testing.assert_array_equal(daily.ic,np.full(6,.7))
        self.assertTrue(stats['sample_std_ic']==0. and np.isnan(stats['icir']),stats)

    def test_sample_icir_and_observation_count_contract(self):
        daily=pd.DataFrame({'ic':[1.,-1.,np.nan],'n':[3,3,1]})
        stats=summarize_ic(daily)
        self.assertEqual(stats['valid_days'],2);self.assertEqual(stats['total_days'],3)
        self.assertEqual(stats['mean_ic'],0.);self.assertAlmostEqual(stats['sample_std_ic'],math.sqrt(2))
        self.assertEqual(stats['icir'],0.);self.assertFalse(stats['icir_annualized']);self.assertEqual(stats['common_observations'],7)

    def test_independent_ridge_sixfold_pipeline_and_model_restore(self):
        features,trades=panel();result=evaluate_registered_study(study(),features,trades,audit_store=MemoryArtifactStore())
        self.assertEqual(len(result.predictions),36);self.assertEqual(len(result.model_artifacts),6)
        self.assertEqual(result.folds.train_n.tolist(),[48]*6);self.assertEqual(result.folds.validation_n.tolist(),[6]*6)
        self.assertEqual(result.daily_ic.n.tolist(),[3]*12);np.testing.assert_array_equal(result.daily_ic.ic,np.ones(12))
        self.assertTrue(np.isnan(result.ic_statistics['icir']));self.assertEqual(result.ic_statistics['sample_std_ic'],0.)
        for fold,artifact in enumerate(result.model_artifacts,1):
            with self.subTest(fold=fold):
                self.assertEqual(artifact['training_rows'],48)
                self.assertEqual(artifact['train_start'],t(f'{2009+fold}-01-01').isoformat())
                self.assertEqual(artifact['fit_cutoff'],t(f'{2017+fold}-01-01').isoformat())
                restored=restore_model(artifact)
                predictions=result.predictions[result.predictions.fold_id==fold].merge(features,on=['sid','formation_at'])
                actual=restored.predict(predictions[['compat_factor']].rename(columns={'compat_factor':'score'}))
                np.testing.assert_allclose(actual,predictions.prediction,rtol=0,atol=1e-15)
        wrong=features.iloc[:-1]
        with self.assertRaises(PipelineValidationError):evaluate_registered_study(study(),wrong,trades)

class Result(unittest.TextTestResult):
    def __init__(self,*a,**kw):super().__init__(*a,**kw);self.subcases=0
    def addSubTest(self,test,subtest,err):self.subcases+=1;super().addSubTest(test,subtest,err)

def hashtext(path):return hashlib.sha256(path.read_text(encoding='utf-8-sig').encode()).hexdigest()
def function_text(path,name):
    text=path.read_text(encoding='utf-8-sig');tree=ast.parse(text)
    node=next(n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==name)
    return ast.get_source_segment(text,node)
def static_checks():
    protected=['cloud/qresearch/registry.py','cloud/qresearch/engineering_tasks.py','tools/stage2.py',
        'cloud/qresearch/workflow.py','cloud/qresearch/runtime.py','cloud/qresearch/point_in_time.py',
        'cloud/qresearch/contracts.py','cloud/qresearch/study.py','cloud/qresearch/factors.py',
        'cloud/qresearch/models.py','cloud/qresearch/labels.py','cloud/qresearch/pipeline.py',
        'tools/research.py','tools/stages.py','config/budget.json','config/research.json','config/data.json',
        'config/development.json','config/engineering.json','config/universe.json','config/workflow.json','config/quantconnect.json',
        'tests/test_factors.py','tests/test_pipeline.py','docs/research_charter.md']
    unchanged={name:hashtext(SOURCE/name)==hashtext(BASE/name) for name in protected}
    same_statistics=function_text(SOURCE/'cloud/qresearch/evaluation.py','summarize_ic')==function_text(BASE/'cloud/qresearch/evaluation.py','summarize_ic')
    same_wr05=function_text(SOURCE/'cloud/qresearch/evaluation.py','daily_rank_ic')==function_text(BASE/'cloud/qresearch/evaluation.py','daily_rank_ic')
    def generated(path):
        tree=ast.parse(path.read_text(encoding='utf-8-sig'))
        return {node.targets[0].id:ast.literal_eval(node.value) for node in tree.body if isinstance(node,ast.Assign)}
    old,new=generated(BASE/'cloud/research_config.py'),generated(SOURCE/'cloud/research_config.py')
    generation={'configuration_equal':old['CONFIGURATION']==new['CONFIGURATION'],
        'source_sha_equal':old['SOURCE_SHA256']==new['SOURCE_SHA256'],
        'implementation_sha_changed':old['IMPLEMENTATION_SHA256']!=new['IMPLEMENTATION_SHA256']}
    return {'protected_file_hash_equal':unchanged,'summarize_ic_source_unchanged':same_statistics,
        'daily_rank_ic_source_unchanged':same_wr05,'generated_configuration':generation}

def selected_historical_failure():
    first=ROOT/'first_attempt';first.mkdir(exist_ok=True)
    for name in ['cloud','tests']:
        shutil.copytree(SOURCE/name,first/name,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__'))
    archive=SOURCE/'audit/review_packages/wr07/first_shared_core_evaluation.py'
    shutil.copy2(archive,first/'cloud/qresearch/evaluation.py')
    method='test_factors.EvaluationTests.test_each_fold_gets_fresh_fit_and_exact_predictions'
    records=[]
    for label,source in [('archived_uncommitted_first_attempt',first),('current_fixed_commit',SOURCE)]:
        env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=os.pathsep.join([str(source/'cloud'),str(source/'tests')]))
        cmd=[sys.executable,'-B','-m','unittest',method,'-v']
        done=subprocess.run(cmd,cwd=source,env=env,capture_output=True,text=True,encoding='utf-8')
        (ROOT/(label+'_output.txt')).write_text(done.stdout+done.stderr,encoding='utf-8')
        records.append({'label':label,'command':cmd,'exit_code':done.returncode,'method':method,
            'source_commit':'7b0dccebef2d3582e1b07ada05211863c3cba0d8' if label=='current_fixed_commit' else None,
            'evaluation_file_sha256':hashtext(source/'cloud/qresearch/evaluation.py'),'output':done.stdout+done.stderr})
    return records

def main():
    buffer=io.StringIO();suite=unittest.defaultTestLoader.loadTestsFromTestCase(PublicContracts)
    result=unittest.TextTestRunner(stream=buffer,verbosity=2,resultclass=Result).run(suite)
    def test_id(test):return getattr(test,'test_case',test).id()
    fail={test_id(t) for t,_ in result.failures};errors={test_id(t) for t,_ in result.errors};skip={test_id(t) for t,_ in result.skipped}
    output=buffer.getvalue();(ROOT/'independent_output.txt').write_text(output,encoding='utf-8')
    report={'source_commit':'7b0dccebef2d3582e1b07ada05211863c3cba0d8','actually_executed':True,
        'independent_methods':result.testsRun,'passed_methods':result.testsRun-len(fail|errors|skip),
        'failed_methods':len(fail),'error_methods':len(errors),'skipped_methods':len(skip),'subcases':result.subcases,
        'failure_records_including_subcases':len(result.failures),'error_records_including_subcases':len(result.errors),
        'failure_details':[{'method':test_id(test),'traceback':tb} for test,tb in result.failures],
        'error_details':[{'method':test_id(test),'traceback':tb} for test,tb in result.errors],
        'static_checks':static_checks(),'selected_historical_reproduction':selected_historical_failure(),
        'environment':{'platform':platform.platform(),'python':sys.version,'numpy':np.__version__,'pandas':pd.__version__},
        'developer_fixtures_imported':False,'historical_original_method_run_separately':True,
        'market_or_model_calls':0,'financial_evidence':False}
    (ROOT/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(output);print(json.dumps({k:report[k] for k in ['independent_methods','passed_methods','failed_methods','error_methods','skipped_methods','subcases']}))
    print(json.dumps({'static_checks':report['static_checks'],'selected_historical_reproduction':report['selected_historical_reproduction']},ensure_ascii=False))
    return 0 if result.wasSuccessful() else 1
if __name__=='__main__':raise SystemExit(main())
