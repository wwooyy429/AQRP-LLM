from cert_fixture import *
base=make();positive=run(base)
assert positive['status']=='observations_passed',(positive['checks'],positive['counts'])
def young_ipo(raw):
 sid='SID200';listing='2018-01-25T00:00:00-05:00'
 for row in raw['liquid']:
  if row['sid']==sid:
   row.update(dollar_volume=2000,listing_effective_at=listing,listing_available_at=listing,classification_effective_at=listing,classification_available_at=listing)
 for row in raw['tables']['security_master']:
  if row['sid']==sid:row.update(effective_from=listing,available_at=listing)
 for row in raw['tables']['membership']:row['sids']=[sid]+raw['sids'][:199]
bad=make(young_ipo);report=run(bad)
out={'baseline_status':positive['status'],'young_IPO_listing':'2018-01-25','first_scored_formation':'2018-02-01','pre_listing_liquidity_rows':sum(x['sid']=='SID200' and pd.Timestamp(x['session'])<ts('2018-01-25') for x in bad['raw']['liquid']),
 'report_status':report['status'],'checks':report['checks'],'counts':report['counts'],'all_certification_flags_still_false':all(report[k] is False for k in ('vendor_provenance_authenticated','full_historical_US200_certified','research_certified','financial_evidence'))}
(ROOT/'cert_agent/first_ipo_result.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(out,ensure_ascii=False,indent=2))
assert report['status']=='insufficient_evidence','Young IPO is wrongly ranked with claimed pre-listing history'
