import argparse,importlib.util,json,sys
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('--source',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args();source=a.source.resolve();sys.dont_write_bytecode=True
sys.path.insert(0,str(source/'cloud'))
fixture=source/'audit/reviews/20261027-ea6053e-windows/cert_agent/cert_fixture.py'
spec=importlib.util.spec_from_file_location('fixture',fixture)
h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h);h.SOURCE=source
def change(raw,mode):
 old=raw['tables']['security_master'][0]
 old['effective_to']='2018-01-25T00:00:00-05:00'
 new=h.deepcopy(old)
 new.update(ticker='RENAMED000',effective_from=old['effective_to'],effective_to=None,available_at=old['effective_to'])
 if mode=='unmapped':new['instrument_type']='UNMAPPED_VENDOR_CODE'
 if mode=='null':new['instrument_type']=None
 if mode=='etf':new['instrument_type']='etf'
 if mode=='delisted':new['listed']=False
 if mode=='future':new['available_at']='2018-02-02T09:00:00.000001-05:00'
 if mode!='missing':raw['tables']['security_master'].append(new)
 raw['liquid']=[r for r in raw['liquid'] if r['sid']!='SID000']
 for row in raw['tables']['membership']:row['sids']=raw['sids'][1:201]
expected={k:'insufficient_evidence'for k in ['stock','null','unmapped','future','missing']}
expected.update(etf='observations_passed',delisted='observations_passed')
actual={};details={}
for mode in expected:
 r=h.run(h.make(lambda raw:change(raw,mode)))
 actual[mode]=r['status'];details[mode]=r
a.output.write_bytes((json.dumps({'expected':expected,'actual':actual,'reports':details},indent=2)+'\n').encode())
print(json.dumps(actual));bad=[k for k in expected if actual[k]!=expected[k]]
assert not bad,'Unexpected acceptance: '+repr(bad)
