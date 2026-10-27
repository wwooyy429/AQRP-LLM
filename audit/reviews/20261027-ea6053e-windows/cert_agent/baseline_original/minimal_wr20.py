"""WR20 repro with fresh memory stores and optional independent output path.

python -B cert_agent/minimal_wr20.py --output NEW_DIRECTORY/result.json
Imports only the adjacent independently written cert_fixture and product code.
"""
from cert_fixture import *
import argparse,hashlib
p=argparse.ArgumentParser();p.add_argument('--output',type=Path);args=p.parse_args()
def ipo(raw,listing,*,drop_pre=False,turnover=False):
 for row in raw['liquid']:
  if row['sid']=='SID200':row.update(dollar_volume=2000,listing_effective_at=listing,listing_available_at=listing,classification_effective_at=listing,classification_available_at=listing)
 for row in raw['tables']['security_master']:
  if row['sid']=='SID200':row.update(effective_from=listing,available_at=listing)
 if drop_pre:raw['liquid']=[row for row in raw['liquid'] if row['sid']!='SID200' or pd.Timestamp(row['session'])>=pd.Timestamp(listing)]
 for index,row in enumerate(raw['tables']['membership']):row['sids']=list(raw['members']) if drop_pre and (not turnover or index==0) else ['SID200']+raw['sids'][:199]
baseline=run(make());legal=run(make(lambda raw:ipo(raw,'2018-01-25T00:00:00-05:00',drop_pre=True)))
boundary=run(make(lambda raw:ipo(raw,'2018-01-04T00:00:00-05:00',drop_pre=True,turnover=True)))
assert all(v['status']=='observations_passed' for v in (baseline,legal,boundary)),'Independent legal controls failed'
bad=make(lambda raw:ipo(raw,'2018-01-25T00:00:00-05:00'));r=run(bad)
out={'fixed_commit':'deb85d9f27441b275ab8b108f0232ecd2707a1e8','controls':{'201_old_names':baseline['status'],'legal_young_IPO_excluded':legal['status'],'19_then20_post_IPO_sessions_turnover':boundary['status']},
 'invalid_case':{'listing_effective_at':'2018-01-25T00:00:00-05:00','claimed_pre_listing_rows':15,'first_scored_post_listing_sessions':5,'second_scored_post_listing_sessions':6,'SID200_ranked_first':True,'actual_report_status':r['status'],'checks':r['checks'],'known_candidate_expected_cells':r['counts']['known_eligible_candidate_expected_cells'],'observed_member_cells':r['counts']['observed_member_cells'],'certification_flags_remain_false':all(r[k] is False for k in ('vendor_provenance_authenticated','full_historical_US200_certified','research_certified','financial_evidence'))},
 'source_file':'cloud/qresearch/data_certification.py','source_raw_sha256':hashlib.sha256((SOURCE/'cloud/qresearch/data_certification.py').read_bytes()).hexdigest(),'new_market_QC_model_or_budget_calls':0,'synthetic_memory_only':True}
if args.output:args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(out,ensure_ascii=False,indent=2))
raise SystemExit(1 if r['status']!='insufficient_evidence' else 0)
