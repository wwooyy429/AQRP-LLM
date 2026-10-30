"""Expected failure on 7b0dcce: identical daily IC must have zero dispersion."""
from pathlib import Path
import json,math,sys
import pandas as pd
source=Path(sys.argv[1] if len(sys.argv)>1 else Path(__file__).parent/'source')
sys.path.insert(0,str(source.resolve()/'cloud'))
from qresearch.evaluation import summarize_ic
actual=summarize_ic(pd.DataFrame({'ic':[0.7]*6,'n':[5]*6}))
print(json.dumps(actual,allow_nan=True))
assert actual['sample_std_ic']==0.0 and math.isnan(actual['icir']), 'WR-08: identical IC values must have zero std and undefined ICIR'
