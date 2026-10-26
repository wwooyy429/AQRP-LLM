"""Independent WR-08 negative control, public API and synthetic constant IC."""
from pathlib import Path
import json,math,sys
sys.path.insert(0,str(Path(sys.argv[1]).resolve()/'cloud'))
import pandas as pd
from qresearch.evaluation import summarize_ic
observed=[];passed=True
for value in [.7,-.7]:
    result=summarize_ic(pd.DataFrame({'ic':[value]*6,'n':[5]*6}))
    ok=result['mean_ic']==value and result['sample_std_ic']==0. and math.isnan(result['icir'])
    observed.append({'constant_ic':value,'days':6,'expected':{'mean_ic':value,'sample_std_ic':0.,'icir':'NaN'},
        'actual':{k:None if isinstance(v,float) and math.isnan(v) else v for k,v in result.items()},'passed':ok})
    passed &= ok
print(json.dumps({'source':sys.argv[1],'observed':observed,'passed':passed},allow_nan=False))
raise SystemExit(0 if passed else 1)
