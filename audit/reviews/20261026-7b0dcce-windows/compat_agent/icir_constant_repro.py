"""Synthetic daily RankIC example: identical 0.7 observations need zero variance."""
from pathlib import Path
import json,math,sys
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'source/cloud'))
from qresearch.evaluation import daily_rank_ic,summarize_ic

rows=[]
for day in range(4,10):
    for sid,prediction,label in zip('abcde',[1,2,3,4,5],[1,2,4,5,3]):
        rows.append({'formation_at':pd.Timestamp(f'2018-06-{day:02d} 09:00',tz='America/New_York'),
                     'sid':sid,'prediction':prediction,'label':label})
daily=daily_rank_ic(pd.DataFrame(rows))
stats=summarize_ic(daily)
print(json.dumps({'daily_ic':daily.ic.tolist(),'actual':stats,'expected':{
    'mean_ic':.7,'sample_std_ic':0.,'icir':None,'icir_representation':'NaN'}},allow_nan=True))
assert daily.ic.tolist()==[.7]*6
assert stats['sample_std_ic']==0. and math.isnan(stats['icir']), 'Identical daily IC values must not produce a finite ICIR'
