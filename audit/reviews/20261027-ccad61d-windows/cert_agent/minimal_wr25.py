"""Unmapped master classifications must not silently become known exclusions."""
from cert_fixture import *
import argparse,hashlib
p=argparse.ArgumentParser();p.add_argument('--output',type=Path);a=p.parse_args()
FLAGS=('vendor_provenance_authenticated','full_historical_US200_certified','actual_availability_certified','financial_vintage_certified','research_certified','row_values_exported','financial_evidence')
def fixture(code,missing):
 def change(raw):
  old=raw['tables']['security_master'][0];old['effective_to']='2018-01-25T00:00:00-05:00'
  new=deepcopy(old);new.update(ticker='RENAMED000',effective_from='2018-01-25T00:00:00-05:00',effective_to=None,available_at='2018-01-25T00:00:00-05:00',instrument_type=code);raw['tables']['security_master'].append(new)
  if missing:
   raw['liquid']=[x for x in raw['liquid'] if x['sid']!='SID000']
   for row in raw['tables']['membership']:row['sids']=raw['sids'][1:201]
 return make(change)
none=run(fixture(None,True));etf=run(fixture('etf',True));present=run(fixture('UNMAPPED_VENDOR_CODE',False))
assert none['status']=='insufficient_evidence','Unknown None is not an affirmative exclusion'
assert etf['status']=='observations_passed','An explicitly known ETF may be excluded'
assert present['status']=='insufficient_evidence','Present common-stock liquidity disagrees with unknown master code'
f=fixture('UNMAPPED_VENDOR_CODE',True);before=dict(f['store']._data);r=run(f)
from qresearch.ingestion import _CLASSIFICATIONS
assert 'UNMAPPED_VENDOR_CODE' not in _CLASSIFICATIONS
out={'source_tree':str(SOURCE),'source_raw_sha256':hashlib.sha256((SOURCE/'cloud/qresearch/data_certification.py').read_bytes()).hexdigest(),'controls':{'None_with_missing_liquidity':none['status'],'known_etf_with_missing_liquidity':etf['status'],'unmapped_master_with_present_liquidity':present['status']},'invalid_case':{'normal_path':'DataCertificationPlan -> ingest completed liquidity/financial -> store_certification_table(security_master) -> audit_data_certification','unmapped_master_type':'UNMAPPED_VENDOR_CODE','known_classifications':sorted(_CLASSIFICATIONS),'status':r['status'],'checks':r['checks'],'counts':r['counts'],'all_certification_flags_false':all(r[k] is False for k in FLAGS),'original_references_preserved':r['evidence_refs']==f['refs'],'original_bytes_preserved':all(f['store'].read_bytes(k)==v for k,v in before.items())},'synthetic_memory_only':True,'new_market_QC_model_or_authoritative_budget_calls':0}
raw=(json.dumps(out,ensure_ascii=False,indent=2)+'\n').encode()
if a.output:a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_bytes(raw)
print(raw.decode(),end='');raise SystemExit(1 if r['status']=='observations_passed' else 0)
