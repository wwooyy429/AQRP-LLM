"""Independent exact-input Pearson audit; no developer tests/fixtures imported.

Oracle: exact rational raw moments n*sum(x*y)-sum(x)*sum(y), followed
by 160-significant-digit Decimal square root/division. This differs from the
candidate's scaled-offset/unit-vector algorithm. Every expected value describes
the actual binary64 inputs, not their ideal decimal construction.
"""
from pathlib import Path
from fractions import Fraction
from decimal import Decimal,localcontext
from copy import deepcopy
import hashlib,io,json,math,platform,random,socket,sys,unittest,warnings
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parent
SOURCE=ROOT.parent/'source'
sys.path.insert(0,str(SOURCE/'cloud'))
from qresearch.evaluation import paired_factor_correlation,pairwise_factor_correlations

TOL=128*sys.float_info.epsilon
OBS={'comparison_count':0,'max_absolute_error':0.,'worst_case':None,'first_failure':None}

def exact_pearson(left,right):
    n=len(left)
    if n<2:return math.nan
    x=[Fraction.from_float(float(v)) for v in left]
    y=[Fraction.from_float(float(v)) for v in right]
    sx,sy=sum(x),sum(y)
    covariance=n*sum((a*b for a,b in zip(x,y)),Fraction())-sx*sy
    variance_x=n*sum((a*a for a in x),Fraction())-sx*sx
    variance_y=n*sum((b*b for b in y),Fraction())-sy*sy
    if not variance_x or not variance_y:return math.nan
    def dec(q):return Decimal(q.numerator)/Decimal(q.denominator)
    with localcontext() as ctx:
        ctx.prec=160
        result=dec(covariance)/(dec(variance_x)*dec(variance_y)).sqrt()
        return float(result)

class ExactPearsonTests(unittest.TestCase):
    def check(self,left,right,label):
        left=[float(v) for v in left];right=[float(v) for v in right]
        self.assertTrue(all(math.isfinite(v) for v in left+right),label+' input must be finite')
        expected=exact_pearson(left,right)
        with np.errstate(over='raise',invalid='raise',divide='raise'):
            result=paired_factor_correlation(pd.Series(left,dtype=float),pd.Series(right,dtype=float))
        actual=result['correlation'];OBS['comparison_count']+=1
        self.assertEqual(result['n'],len(left));self.assertEqual(result['method'],'pearson')
        if math.isnan(expected):
            self.assertTrue(math.isnan(actual),label)
            self.assertTrue(math.isnan(result['absolute_correlation']),label)
            return
        if not math.isfinite(actual) or abs(actual-expected)>TOL:
            failure={'label':label,'left_hex':[v.hex() for v in left],'right_hex':[v.hex() for v in right],
                'expected':expected,'actual':None if math.isnan(actual) else actual}
            if OBS['first_failure'] is None:OBS['first_failure']=failure
        self.assertTrue(math.isfinite(actual),label+' lost valid finite nonconstant inputs')
        error=abs(actual-expected)
        if error>OBS['max_absolute_error']:
            OBS['max_absolute_error']=error
            OBS['worst_case']={'label':label,'left_hex':[v.hex() for v in left],
                'right_hex':[v.hex() for v in right],'expected':expected,'actual':actual,'error':error}
        self.assertLessEqual(error,TOL,label)
        self.assertLessEqual(abs(actual),1.,label)
        self.assertLessEqual(abs(result['absolute_correlation']-abs(expected)),TOL,label)

    def test_original_scale_reproducer_and_signs_against_exact_raw_moments(self):
        for sx in [1e-200,1.,1e200]:
            for sy in [1e-200,1.,1e200]:
                for sign in [-1,1]:
                    with self.subTest(sx=sx,sy=sy,sign=sign):
                        self.check([sx,2*sx,3*sx],[sign*sy,sign*2*sy,sign*3*sy],f'original-{sx}-{sy}-{sign}')

    def test_nonperfect_nonlinear_and_non_equally_spaced_offsets(self):
        patterns=[([0.,1.,4.,9.,16.],[7.,0.,4.,8.,1.]),
                  ([0.,1.,1.,5.,11.],[8.,3.,3.,1.,-4.]),
                  ([-7.,-1.,0.,2.,9.],[3.,1.,0.,-8.,4.])]
        scales=[math.ldexp(1.,-1000),1.,math.ldexp(1.,1000)]
        for i,(x,y) in enumerate(patterns):
            for sx in scales:
                for sy in scales:
                    with self.subTest(pattern=i,sx=sx,sy=sy):
                        self.check([v*sx for v in x],[v*sy for v in y],f'nonperfect-{i}-{sx}-{sy}')

    def test_smallest_subnormal_minimum_normal_and_maximum_finite(self):
        tiny=float(np.nextafter(0.,1.));maximum=sys.float_info.max;normal=sys.float_info.min
        vectors=[[-maximum,-maximum/2,0.,maximum/2,maximum],
            [tiny,2*tiny,3*tiny,7*tiny,11*tiny],
            [-normal,-normal/2,0.,normal/2,normal],
            [0.,tiny,normal,1.,maximum],
            [-maximum,-1.,-tiny,0.,tiny,1.,maximum],
            [maximum,maximum,maximum,np.nextafter(maximum,0.)],
            [-maximum,-maximum,np.nextafter(-maximum,0.),-maximum]]
        for i,x in enumerate(vectors):
            patterns=[list(range(len(x))),list(reversed(range(len(x)))),x[::-1]]
            for j,y in enumerate(patterns):
                with self.subTest(vector=i,other=j):self.check(x,y,f'limits-{i}-{j}')

    def test_ulp_variation_near_positive_and_negative_large_offsets(self):
        deltas=[[0,1,2,7,11,49,101],[0,0,1,3,3,17,1024]]
        bases=[1e-200,-1e-200,1.,-1.,1e200,-1e200,sys.float_info.max/2,-sys.float_info.max/2]
        for b in bases:
            for i,delta in enumerate(deltas):
                x=[b+math.ulp(b)*v for v in delta];y=[4.,-7.,1.,9.,0.,2.,-3.]
                for permutation in [[0,1,2,3,4,5,6],[6,1,4,0,3,2,5],[2,4,6,1,3,0,5]]:
                    with self.subTest(base=b,pattern=i,permutation=permutation):
                        self.check([x[k] for k in permutation],[y[k] for k in permutation],f'ULP-{b}-{i}-{permutation}')

    def test_two_point_near_offset_and_constant_boundaries(self):
        for value in [0.,float(np.nextafter(0.,1.)),sys.float_info.min,1.,1e200,sys.float_info.max]:
            for n in [0,1,2,3,17]:
                with self.subTest(constant=value,n=n):
                    self.check([value]*n,list(range(n)),f'constant-{value}-{n}')
        for b in [sys.float_info.min,1.,1e200,sys.float_info.max/2]:
            for direction in [-1,1]:
                x=[b,float(np.nextafter(b,math.inf))];y=[7.,7.+direction]
                with self.subTest(two_point=b,direction=direction):self.check(x,y,f'two-point-{b}-{direction}')

    def test_mixed_dynamic_range_cancellation_and_almost_orthogonal(self):
        tiny=float(np.nextafter(0.,1.));big=sys.float_info.max
        examples=[
            ([-big,-1.,0.,1.,big],[1.,-big,0.,big,-1.]),
            ([-big,-1.,0.,1.,big],[1.,big,0.,-big,-1.]),
            ([tiny,1e-200,0.,-1e-200,-tiny],[big,1.,0.,-1.,-big]),
            ([-big,0.,big,0.],[0.,-big,0.,big]),
            ([big,big,-big,-big],[big,-big,big,-big]),
            ([1.,1.+2**-52,1.,1.-2**-53],[1.,-1.,-1.,1.]),
            ([big]+[float(np.nextafter(big,0.))]*31,list(range(32))),
            ([0.]*31+[tiny],list(range(32)))
        ]
        for i,(x,y) in enumerate(examples):
            with self.subTest(case=i):self.check(x,y,f'mixed-{i}')

    def test_deterministic_random_finite_values_wide_exponent_range(self):
        rng=random.Random(73158023)
        for case in range(240):
            n=rng.randint(2,24)
            x=[math.ldexp(rng.uniform(-.99,.99),rng.randint(-1074,1024)) for _ in range(n)]
            y=[math.ldexp(rng.uniform(-.99,.99),rng.randint(-1074,1024)) for _ in range(n)]
            with self.subTest(case=case,n=n):self.check(x,y,f'random-wide-{case}')

    def test_deterministic_random_large_offsets_and_ulp_spreads(self):
        rng=random.Random(919117)
        for case in range(240):
            n=rng.randint(3,24);exponent=rng.randint(-1000,1000)
            base=math.ldexp(rng.choice([-1.,1.])*rng.uniform(.5,.9),exponent)
            dx=[rng.randrange(-2048,2049) for _ in range(n)]
            x=[base+math.ulp(base)*d for d in dx]
            y=[rng.uniform(-3.,3.) for _ in range(n)]
            with self.subTest(case=case,n=n,exponent=exponent):self.check(x,y,f'random-offset-{case}')

    def test_deterministic_random_independent_scales_and_near_perfect_pairs(self):
        rng=random.Random(317226)
        for case in range(240):
            n=rng.randint(3,24);sx=math.ldexp(1.,rng.randint(-1000,1000));sy=math.ldexp(1.,rng.randint(-1000,1000))
            raw=[rng.uniform(-2.,2.) for _ in range(n)];sign=rng.choice([-1,1]);noise=10.**(-rng.randrange(0,17))
            x=[v*sx for v in raw];y=[(v*sign+rng.uniform(-1,1)*noise)*sy for v in raw]
            with self.subTest(case=case,n=n,noise=noise):self.check(x,y,f'random-nearperfect-{case}')

    def test_public_matrix_on_pairwise_aligned_missing_values(self):
        data=pd.DataFrame({'small':[1e-200,4e-200,np.nan,-1e-200,7e-200],
            'large':[-3e200,np.nan,2e200,4e200,-1e200],
            'offset':np.array([0.,1.,7.,3.,11.])*math.ulp(1e200)+1e200,'constant':[2.]*5})
        result=pairwise_factor_correlations(data)
        for a in data:
            for b in data:
                pair=data[[a,b]].dropna() if a!=b else data[[a]].dropna()
                x=pair[a].tolist();y=pair[b].tolist()
                expected=exact_pearson(x,y);actual=result['absolute_pearson'].loc[a,b]
                with self.subTest(left=a,right=b):
                    self.assertEqual(result['n'].loc[a,b],len(pair))
                    if math.isnan(expected):self.assertTrue(math.isnan(actual))
                    else:self.assertLessEqual(abs(actual-abs(expected)),TOL)

class Result(unittest.TextTestResult):
    def __init__(self,*a,**k):super().__init__(*a,**k);self.subcase_count=0
    def addSubTest(self,test,subtest,error):self.subcase_count+=1;super().addSubTest(test,subtest,error)
def main():
    tracked=list((SOURCE/'cloud').rglob('*.py'));before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked}
    def denied(*a,**k):raise AssertionError('Offline independent Pearson audit; network prohibited')
    socket.socket.connect=denied
    stream=io.StringIO()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        result=unittest.TextTestRunner(stream=stream,verbosity=2,resultclass=Result).run(unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    def method_id(test):return getattr(test,'test_case',test).id()
    bad={method_id(t) for t,_ in result.failures};errors={method_id(t) for t,_ in result.errors}
    report={'source_commit':'7b0dccebef2d3582e1b07ada05211863c3cba0d8','actually_executed':True,
        'methods':result.testsRun,'passed_methods':result.testsRun-len(bad|errors)-len(result.skipped),
        'failed_methods':len(bad),'error_methods':len(errors),'failure_records':len(result.failures),'error_records':len(result.errors),
        'skipped':len(result.skipped),'subcases':result.subcase_count,'oracle':'Exact rational raw moments, 160-significant-digit Decimal square root/division',
        'absolute_tolerance':TOL,'tolerance_note':'128 binary64 eps; near-zero results assessed by absolute error, not a relative-error criterion.',
        'observations':OBS,'warnings':sorted(set(str(w.message) for w in caught)),
        'failures':[{'test':str(t),'traceback':tb} for t,tb in result.failures],
        'errors':[{'test':str(t),'traceback':tb} for t,tb in result.errors],
        'source_unchanged':all(hashlib.sha256(p.read_bytes()).hexdigest()==before[str(p)] for p in tracked),
        'developer_test_fixtures_imported':False,'environment':{'platform':platform.platform(),'python':sys.version,'numpy':np.__version__,'pandas':pd.__version__},
        'platform_calls':0,'financial_evidence':False,'exit_code':0 if result.wasSuccessful() else 1}
    (ROOT/'exact_test_results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    (ROOT/'exact_test_output.txt').write_text(stream.getvalue(),encoding='utf-8')
    if OBS['first_failure'] is not None:
        (ROOT/'first_failure.json').write_text(json.dumps(OBS['first_failure'],indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(stream.getvalue());print(json.dumps({k:report[k] for k in ['methods','passed_methods','failed_methods','error_methods','failure_records','skipped','subcases','absolute_tolerance','observations','source_unchanged','exit_code']}))
    return report['exit_code']
if __name__=='__main__':raise SystemExit(main())
