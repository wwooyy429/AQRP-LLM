"""Pure synthetic WR22: an existing listed SID's mapping update hides missing history.

python -B cert_agent/minimal_wr22.py --output NEW_PATH.json
Uses only the adjacent original independent cert_fixture, never developer tests.
"""
from cert_fixture import *
import argparse,hashlib
p=argparse.ArgumentParser();p.add_argument('--output',type=Path);a=p.parse_args()
FLAGS=('vendor_provenance_authenticated','full_historical_US200_certified','actual_availability_certified','financial_vintage_certified','research_certified','row_values_exported','financial_evidence')
def mapping(raw):
 old=raw['tables']['security_master'][0]
 old['effective_to']='2018-01-25T00:00:00-05:00'
 new=deepcopy(old);new.update(ticker='RENAMED000',effective_from='2018-01-25T00:00:00-05:00',effective_to=None,available_at='2018-01-25T00:00:00-05:00')
 raw['tables']['security_master'].append(new)
def missing(raw):
 raw['liquid']=[r for r in raw['liquid'] if r['sid']!='SID000']
 for row in raw['tables']['membership']:row['sids']=raw['sids'][1:201]
baseline=run(make());recent=run(make(mapping));absent=run(make(missing))
assert baseline['status']=='observations_passed'
assert recent['status']=='observations_passed','A genuine mapping update with complete old history is valid'
assert absent['status']=='insufficient_evidence','Old eligible whole-history absence must be caught'
def bad(raw):mapping(raw);missing(raw)
f=make(bad);r=run(f)
out={'fixed_source':str(SOURCE),'controls':{'old_listed_complete':baseline['status'],'mapping_update_complete_history':recent['status'],'missing_old_history_without_mapping_update':absent['status']},
 'invalid_case':{'SID000_known_listed_from':'2017-12-01T00:00:00-05:00','old_interval_ends':'2018-01-25T00:00:00-05:00','same_SID_new_mapping_starts':'2018-01-25T00:00:00-05:00','missing_liquidity_rows':21,'rank201_substituted':True,'status':r['status'],'checks':r['checks'],'counts':r['counts'],'all_certification_flags_false':all(r[k] is False for k in FLAGS)},
 'source_raw_sha256':hashlib.sha256((SOURCE/'cloud/qresearch/data_certification.py').read_bytes()).hexdigest(),'synthetic_memory_only':True,'real_market_model_QC_or_budget_calls':0}
raw=json.dumps(out,ensure_ascii=False,indent=2)+'\n'
if a.output:a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(raw,encoding='utf-8')
print(raw,end='');raise SystemExit(1 if r['status']=='observations_passed' else 0)
