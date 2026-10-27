"""Then-unknown current mapping is not affirmative evidence of exclusion."""
from cert_fixture import *
import argparse,hashlib
p=argparse.ArgumentParser();p.add_argument('--output',type=Path);a=p.parse_args()
FLAGS=('vendor_provenance_authenticated','full_historical_US200_certified','actual_availability_certified','financial_vintage_certified','research_certified','row_values_exported','financial_evidence')
def case(mode,missing=True):
 def change(raw):
  old=raw['tables']['security_master'][0];old['effective_to']='2018-01-25T00:00:00-05:00'
  if mode!='no_current':
   new=deepcopy(old);new.update(ticker='RENAMED000',effective_from='2018-01-25T00:00:00-05:00',effective_to=None,available_at='2018-01-25T00:00:00-05:00')
   if mode=='late_current':new['available_at']='2018-02-02T09:00:00.000001-05:00'
   if mode=='known_unlisted':new['listed']=False
   raw['tables']['security_master'].append(new)
  if missing:
   raw['liquid']=[r for r in raw['liquid'] if r['sid']!='SID000']
   for r in raw['tables']['membership']:r['sids']=raw['sids'][1:201]
 return make(change)
controls={}
for label,mode,missing,expected in [('known_current_complete','known_current',False,'observations_passed'),('known_current_all_liquidity_missing','known_current',True,'insufficient_evidence'),('explicit_current_unlisted','known_unlisted',True,'observations_passed'),('late_current_but_liquidity_present','late_current',False,'insufficient_evidence')]:
 r=run(case(mode,missing));controls[label]=r['status'];assert r['status']==expected,(label,r['status'])
bad=[]
for mode in ('late_current','no_current'):
 f=case(mode);before=dict(f['store']._data);r=run(f)
 bad.append({'mode':mode,'last_old_master_was_listed':True,'old_ticker_interval_end':'2018-01-25T00:00:00-05:00','explicit_delisting_evidence':False,'current_classification_known_at_formation':False,'status':r['status'],'checks':r['checks'],'counts':r['counts'],'all_certification_flags_false':all(r[k] is False for k in FLAGS),'refs_preserved':r['evidence_refs']==f['refs'],'raw_bytes_preserved':all(f['store'].read_bytes(k)==v for k,v in before.items())})
out={'source_tree':str(SOURCE),'source_raw_sha256':hashlib.sha256((SOURCE/'cloud/qresearch/data_certification.py').read_bytes()).hexdigest(),'controls':controls,'invalid_cases':bad,'synthetic_memory_only':True,'new_QC_market_model_or_authoritative_budget_calls':0}
raw=(json.dumps(out,ensure_ascii=False,indent=2)+'\n').encode()
if a.output:a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_bytes(raw)
print(raw.decode(),end='');raise SystemExit(1 if any(x['status']=='observations_passed' for x in bad) else 0)
