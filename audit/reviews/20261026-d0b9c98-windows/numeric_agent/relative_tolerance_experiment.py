"""Independent legal-domain IC moment audit; no developer fixtures imported."""
from pathlib import Path
from fractions import Fraction
from decimal import Decimal,localcontext
import hashlib,io,itertools,json,math,platform,random,socket,sys,unittest,warnings
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parent;SOURCE=ROOT.parent/'source'
sys.path.insert(0,str(SOURCE/'cloud'))
from qresearch.evaluation import summarize_ic,daily_rank_ic
EPS=sys.float_info.epsilon
OBS={'comparison_count':0,'max_normalized_mean_error':0.,'max_std_relative_error':0.,
     'max_normalized_icir_error':0.,'worst_mean':None,'first_failure':None}
def oracle(raw):
    values=[Fraction.from_float(float(x)) for x in raw if math.isfinite(float(x))]
    if not values:return math.nan,math.nan,math.nan
    n=len(values);mean=sum(values)/n
    if n==1:return float(mean),math.nan,math.nan
    # Exact raw moments; not the candidate's shifted two-pass algorithm.
    variance=(n*sum((x*x for x in values),Fraction())-sum(values)**2)/(n*(n-1))
    if variance==0:return float(mean),0.,math.nan
    with localcontext() as context:
        context.prec=180
        std=(Decimal(variance.numerator)/Decimal(variance.denominator)).sqrt()
        ratio=(Decimal(mean.numerator)/Decimal(mean.denominator))/std
        return float(mean),float(std),float(ratio)
def table(values):return pd.DataFrame({'ic':list(values),'n':[11]*len(values)})

class SummaryTests(unittest.TestCase):
    def check(self,values,label,counts=None):
        finite=[float(v) for v in values if math.isfinite(float(v))]
        self.assertTrue(all(-1<=v<=1 for v in finite),'Only legal IC domain is under review')
        expected=oracle(values);result=summarize_ic(table(values) if counts is None else pd.DataFrame({'ic':values,'n':counts}))
        OBS['comparison_count']+=1
        self.assertEqual(result['valid_days'],len(finite));self.assertEqual(result['total_days'],len(values))
        self.assertEqual(result['common_observations'],11*len(values) if counts is None else sum(counts))
        self.assertFalse(result['icir_annualized'])
        scale=max(map(abs,finite),default=0.)
        mean_tol=max(16*EPS*scale,2*math.ulp(expected[0]) if math.isfinite(expected[0]) else 0.)
        std_tol=max(32*EPS*expected[1],2*math.ulp(expected[1])) if math.isfinite(expected[1]) else 0.
        # Strong-cancellation near-zero ratios are assessed absolutely; ordinary
        # nonzero and near-constant large ratios retain a relative criterion.
        icir_tol=(32*EPS*max(1.,abs(expected[2])) if label=='cancellation' else 32*EPS*abs(expected[2])) if math.isfinite(expected[2]) else 0.
        fields=['mean_ic','sample_std_ic','icir'];tolerances=[mean_tol,std_tol,icir_tol]
        for field,want,tolerance in zip(fields,expected,tolerances):
            actual=result[field]
            if math.isnan(want):
                self.assertTrue(math.isnan(actual),f'{label}-{field}: undefined must remain NaN')
            else:
                if not math.isfinite(actual) or abs(actual-want)>tolerance:
                    failure={'label':label,'field':field,'values_hex':[v.hex() for v in finite],
                        'expected':want,'actual':actual if math.isfinite(actual) else None,'absolute_tolerance':tolerance}
                    if OBS['first_failure'] is None:OBS['first_failure']=failure
                self.assertTrue(math.isfinite(actual),label+'-'+field)
                self.assertLessEqual(abs(actual-want),tolerance,label+'-'+field)
        if math.isfinite(expected[1]) and expected[1]>0:
            self.assertGreater(result['sample_std_ic'],0.,label+' must not erase representable nonzero variance')
        if finite:
            # Divide in this order so the diagnostic's denominator itself does
            # not underflow for legitimate subnormal inputs.
            me=(abs(result['mean_ic']-expected[0])/scale)/EPS if scale else 0.
            if me>OBS['max_normalized_mean_error']:
                OBS['max_normalized_mean_error']=me;OBS['worst_mean']={'label':label,'values_hex':[v.hex() for v in finite],
                    'expected':expected[0],'actual':result['mean_ic'],'absolute_error':abs(result['mean_ic']-expected[0]),'error_in_eps_times_max_abs_input':me}
        if math.isfinite(expected[1]) and expected[1]>sys.float_info.min:
            OBS['max_std_relative_error']=max(OBS['max_std_relative_error'],abs(result['sample_std_ic']-expected[1])/expected[1])
        if math.isfinite(expected[2]):
            OBS['max_normalized_icir_error']=max(OBS['max_normalized_icir_error'],abs(result['icir']-expected[2])/(EPS*max(1.,abs(expected[2]))))
        return result

    def test_constants_nonperfect_positive_negative_and_signed_zero(self):
        for value in [.7,-.7,.1,-.3,.6571428571428571,-.3141592653589793,0.,-0.,1.,-1.]:
            for n in [2,3,6,9,17,31,252]:
                with self.subTest(value=value,n=n):
                    result=self.check([value]*n,f'constant-{value}-{n}')
                    self.assertEqual(result['mean_ic'],value);self.assertEqual(result['sample_std_ic'],0.)
                    self.assertTrue(math.isnan(result['icir']))
    def test_zero_one_valid_day_and_nan_inf_filter_counts(self):
        for values in [[],[math.nan,math.inf,-math.inf],[math.nan,.3,math.inf],[math.nan,-.8,-math.inf],[0.,math.nan]]:
            counts=list(range(1,len(values)+1))
            with self.subTest(values=values):self.check(values,'missing-single',counts)
        self.check([.3,math.nan,-.2,math.inf,.8,-math.inf],'common-finite',[2,3,5,7,11,13])
    def test_hand_sample_variance_and_nonannualized_ratio(self):
        result=self.check([-.5,0.,.5],'hand-centered')
        self.assertEqual(result['mean_ic'],0.);self.assertEqual(result['sample_std_ic'],.5);self.assertEqual(result['icir'],0.)
        self.check([-.3,.8,.2,-.6,.4],'nonperfect')
    def test_real_adjacent_ulp_variance_is_not_treated_as_constant(self):
        for base in [.7,-.7,.1,-.1,math.ldexp(1.,-1000),-math.ldexp(1.,-1000)]:
            ulp=math.ulp(base)
            for delta in [[0,1],[0,1,0,1,2,0],[0,0,0,1,7,2,2,0]]:
                values=[base+ulp*x for x in delta]
                with self.subTest(base=base,delta=delta):
                    result=self.check(values,f'ULP-{base}-{delta}')
                    self.assertGreater(result['sample_std_ic'],0.)
    def test_subnormal_and_small_scale_have_representable_ratio(self):
        tiny=float(np.nextafter(0.,1.))
        for scale in [tiny,sys.float_info.min,1e-300,1e-200]:
            for pattern in [[0,1],[0,1,2,7],[-1,0,1],[1,2,5,-2],([0]*63+[1])]:
                values=[v*scale for v in pattern]
                with self.subTest(scale=scale,pattern_size=len(pattern)):self.check(values,f'tiny-{scale}-{pattern}')
    def test_translations_and_reordering_use_actual_float_input_oracle(self):
        vectors=[[-.5,0.,.5],[-.125,.25,.375,-.25],[.7,float(np.nextafter(.7,1.)),.7,float(np.nextafter(.7,0.))]]
        for i,values in enumerate(vectors):
            for shift in [0.,.0625,-.0625]:
                data=[x+shift for x in values]
                for order in [data,list(reversed(data)),data[1:]+data[:1]]:
                    with self.subTest(vector=i,shift=shift,order=order):self.check(order,f'translation-{i}-{shift}')
    def test_cancellation_small_true_means_assessed_by_absolute_error(self):
        for first in [1.,.7,.125,1e-100]:
            for residual in [1e-200,2**-52,2**-50,-1e-200]:
                for values in itertools.permutations([first,-first,residual]):
                    with self.subTest(first=first,residual=residual,values=values):self.check(list(values),'cancellation')
    def test_deterministic_general_legal_ic_values(self):
        rng=random.Random(80821026)
        for case in range(180):
            values=[rng.uniform(-1.,1.) for _ in range(rng.randint(2,51))]
            with self.subTest(case=case):self.check(values,f'random-{case}')
    def test_deterministic_micro_variance_around_nonperfect_ic(self):
        rng=random.Random(808331)
        for case in range(180):
            base=rng.uniform(-.9,.9);n=rng.randint(2,51)
            values=[base+math.ulp(base)*rng.randint(-11,11) for _ in range(n)]
            with self.subTest(case=case):self.check(values,f'random-ULP-{case}')
    def test_deterministic_tiny_dynamic_ranges(self):
        rng=random.Random(808713)
        for case in range(120):
            scale=math.ldexp(1.,rng.randint(-1074,-50));n=rng.randint(2,31)
            values=[rng.randint(-7,7)*scale for _ in range(n)]
            with self.subTest(case=case):self.check(values,f'random-tiny-{case}')
    def test_independent_daily_rank_to_constant_nonperfect_ic_summary(self):
        rows=[]
        # d^2 sum=12 for n=6, so Spearman=1-6*12/(6*(36-1))=23/35.
        for day in range(1,10):
            for score,target in enumerate([2,3,1,5,6,4],1):
                rows.append({'formation_at':pd.Timestamp(f'2018-06-{day:02d} 09:00',tz='America/New_York'),
                    'sid':str(score),'prediction':float(score),'label':float(target)})
        daily=daily_rank_ic(pd.DataFrame(rows))
        self.assertTrue(np.all(np.abs(daily.ic.to_numpy()-float(Fraction(23,35)))<16*EPS))
        result=summarize_ic(daily)
        self.assertEqual(result['sample_std_ic'],0.);self.assertTrue(math.isnan(result['icir']))
        self.assertEqual(result['mean_ic'],daily.ic.iloc[0]);self.assertEqual(result['common_observations'],54)

class Result(unittest.TextTestResult):
    def __init__(self,*args,**kwargs):super().__init__(*args,**kwargs);self.subcase_count=0
    def addSubTest(self,test,subtest,error):self.subcase_count+=1;super().addSubTest(test,subtest,error)
def main():
    files=list((SOURCE/'cloud').rglob('*.py'));before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    def denied(*a,**k):raise AssertionError('Independent summary test is offline')
    socket.socket.connect=denied;stream=io.StringIO()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        result=unittest.TextTestRunner(stream=stream,verbosity=2,resultclass=Result).run(unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    def mid(test):return getattr(test,'test_case',test).id()
    bad={mid(t) for t,_ in result.failures};errors={mid(t) for t,_ in result.errors}
    report={'source_commit':'d0b9c98ae9490b977d62f3e9742d854146d298b4','actually_executed':True,
        'methods':result.testsRun,'passed_methods':result.testsRun-len(bad|errors)-len(result.skipped),
        'failed_methods':len(bad),'error_methods':len(errors),'failure_records':len(result.failures),'error_records':len(result.errors),
        'skipped':len(result.skipped),'subcases':result.subcase_count,'observations':OBS,
        'tolerance':{'mean':'max(16*eps*max(abs(valid_IC)),2*ulp(correctly_rounded_mean))',
            'sample_std':'max(32*eps*correctly_rounded_std,2*ulp(correctly_rounded_std))',
            'ICIR':'32*eps*abs(correctly_rounded_ICIR) except explicit strong cancellation, where 32*eps*max(1,abs(ICIR)) avoids relative-error false alarms near zero',
            'positive_std_guard':'Every representable positive oracle std must remain strictly positive; only subnormal std rounding uses 2 ULP allowance'},
        'oracle':'Exact Fraction raw moments with sample ddof1, 180-significant-digit Decimal square root and mean/std ratio',
        'warnings':sorted(set(str(w.message) for w in caught)),
        'failures':[{'test':str(t),'traceback':tb} for t,tb in result.failures],
        'errors':[{'test':str(t),'traceback':tb} for t,tb in result.errors],
        'source_unchanged':all(hashlib.sha256(p.read_bytes()).hexdigest()==before[str(p)] for p in files),
        'author_test_fixtures_imported':False,'environment':{'platform':platform.platform(),'python':sys.version,'numpy':np.__version__,'pandas':pd.__version__},
        'platform_calls':0,'financial_evidence':False,'exit_code':0 if result.wasSuccessful() else 1}
    output=stream.getvalue();(ROOT/'exact_summary_output.txt').write_text(output,encoding='utf-8')
    (ROOT/'exact_summary_results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    if OBS['first_failure'] is not None:(ROOT/'first_failure.json').write_text(json.dumps(OBS['first_failure'],indent=2)+'\n',encoding='utf-8')
    print(output);print(json.dumps({k:report[k] for k in ['methods','passed_methods','failed_methods','error_methods','failure_records','skipped','subcases','observations','warnings','exit_code']}))
    return report['exit_code']
if __name__=='__main__':raise SystemExit(main())
