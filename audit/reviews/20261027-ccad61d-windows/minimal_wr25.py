"""Offline known-answer probe; uses the review fixture archived in fixed Git."""
import argparse,importlib.util,json,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
source=a.source.resolve();sys.dont_write_bytecode=True
sys.path.insert(0,str(source/'cloud'))
fixture=source/'audit/reviews/20261027-ea6053e-windows/cert_agent/cert_fixture.py'
spec=importlib.util.spec_from_file_location('independent_fixture',fixture)
h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h);h.SOURCE=source
def change(raw,kind):
 old=raw['tables']['security_master'][0]
 old['effective_to']='2018-01-25T00:00:00-05:00'
 new=h.deepcopy(old)
 new.update(ticker='RENAMED000',effective_from=old['effective_to'],effective_to=None,available_at=old['effective_to'],instrument_type=kind)
 raw['tables']['security_master'].append(new)
 raw['liquid']=[r for r in raw['liquid'] if r['sid']!='SID000']
 for row in raw['tables']['membership']:row['sids']=raw['sids'][1:201]
results={}
for label,kind in [('unknown','UNMAPPED_VENDOR_CODE'),('null',None),('etf','etf'),('stock','common_stock')]:
 r=h.run(h.make(lambda raw:change(raw,kind)))
 results[label]={'status':r['status'],'checks':r['checks'],'counts':r['counts'],
  'financial_evidence':r['financial_evidence'],'research_certified':r['research_certified']}
a.output.write_bytes((json.dumps(results,indent=2)+'\n').encode())
print(json.dumps({k:v['status'] for k,v in results.items()}))
assert results['null']['status']==results['stock']['status']=='insufficient_evidence'
assert results['etf']['status']=='observations_passed'
assert results['unknown']['status']=='insufficient_evidence','WR-25: unknown classification was accepted as a known exclusion'
