"""Run with a fixed source directory argument; synthetic finite scores only."""
from pathlib import Path
import json,math,sys,warnings
sys.path.insert(0,str(Path(sys.argv[1]).resolve()/'cloud'))
import pandas as pd
from qresearch.evaluation import paired_factor_correlation,pairwise_factor_correlations
observations=[]
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter('always')
    for scale in [1e-200,1.,1e200]:
        x=pd.Series([scale,2*scale,3*scale]);y=pd.Series([1.,2.,3.])
        default=paired_factor_correlation(x,y)
        matrix=pairwise_factor_correlations(pd.DataFrame({'X':x,'Y':y}))
        values={'default_pearson':default['correlation'],
                'absolute_pearson_matrix':matrix['absolute_pearson'].loc['X','Y'],
                'spearman':paired_factor_correlation(x,y,method='spearman')['correlation']}
        observations.append({'scale':scale,'expected':1.,'actual':{k:None if math.isnan(v) else float(v) for k,v in values.items()},
            'NaN_paths':[k for k,v in values.items() if math.isnan(v)]})
print(json.dumps({'source':sys.argv[1],'observations':observations,
    'runtime_warnings':sorted(set(str(w.message) for w in caught))},allow_nan=False))
