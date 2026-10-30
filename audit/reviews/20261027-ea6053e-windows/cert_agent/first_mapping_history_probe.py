from cert_fixture import *
def mutation(raw):
 old=raw['tables']['security_master'][0]
 old['effective_to']='2018-01-25T00:00:00-05:00'
 new=deepcopy(old);new.update(ticker='RENAMED000',effective_from='2018-01-25T00:00:00-05:00',effective_to=None,available_at='2018-01-25T00:00:00-05:00')
 raw['tables']['security_master'].append(new)
 raw['liquid']=[r for r in raw['liquid'] if r['sid']!='SID000']
 for row in raw['tables']['membership']:row['sids']=raw['sids'][1:201]
f=make(mutation);r=run(f)
out={'fixed_source':'ea6053e3e9ef4be17db246daf18a4cf9b2e5be58','trigger':'Old listed SID has original interval from Dec1 to Jan25 and a new mapping from Jan25; all its liquidity is missing, declared membership fills with rank201.','status':r['status'],'counts':r['counts'],'checks':r['checks'],'certification_flags_false':all(r[x] is False for x in ('vendor_provenance_authenticated','full_historical_US200_certified','actual_availability_certified','financial_vintage_certified','research_certified','row_values_exported','financial_evidence')),'source_refs':f['refs'],'synthetic_memory_only':True}
(Path(__file__).parent/'first_mapping_history_result.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(out,ensure_ascii=False,indent=2));raise SystemExit(1 if r['status']=='observations_passed' else 0)
