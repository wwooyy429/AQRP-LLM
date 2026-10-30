"""Explicit same-SID controls for the new mapping/history defect."""
from cert_fixture import *
import hashlib
O=Path(__file__).parent
def mapping(raw):
 old=raw['tables']['security_master'][0];old['effective_to']='2018-01-25T00:00:00-05:00'
 new=deepcopy(old);new.update(ticker='RENAMED000',effective_from='2018-01-25T00:00:00-05:00',effective_to=None,available_at='2018-01-25T00:00:00-05:00');raw['tables']['security_master'].append(new)
cases=[]
for variant in ('mapping_complete','same_old_SID_one_session_missing','same_old_SID_all_sessions_missing','genuine_young_IPO_without_prelisting_rows'):
 raw=raw_fixture()
 if variant!='genuine_young_IPO_without_prelisting_rows':mapping(raw)
 if variant=='same_old_SID_one_session_missing':
  raw['liquid']=[r for r in raw['liquid'] if not(r['sid']=='SID000' and r['session']==iso(raw['pairs'][0][1]))]
  raw['tables']['membership'][0]['sids']=raw['sids'][1:201]
 elif variant=='same_old_SID_all_sessions_missing':
  raw['liquid']=[r for r in raw['liquid'] if r['sid']!='SID000']
  for r in raw['tables']['membership']:r['sids']=raw['sids'][1:201]
 elif variant=='genuine_young_IPO_without_prelisting_rows':
  listing='2018-01-25T00:00:00-05:00'
  for r in raw['liquid']:
   if r['sid']=='SID200':r.update(dollar_volume=2000,listing_effective_at=listing,listing_available_at=listing,classification_effective_at=listing,classification_available_at=listing)
  raw['tables']['security_master'][-1].update(effective_from=listing,available_at=listing)
  raw['liquid']=[r for r in raw['liquid'] if r['sid']!='SID200' or pd.Timestamp(r['session'])>=pd.Timestamp(listing)]
 r=run(make(raw=raw));expected='insufficient_evidence' if variant in ('same_old_SID_one_session_missing','same_old_SID_all_sessions_missing') else 'observations_passed'
 cases.append({'variant':variant,'expected_status':expected,'actual_status':r['status'],'expectation_met':r['status']==expected,'known_candidate_expected_cells':r['counts']['known_eligible_candidate_expected_cells'],'missing_candidate_session_cells':r['counts']['missing_candidate_session_cells'],'membership_matches':r['checks']['ranked_membership_matches'],'certification_flags_false':all(r[k] is False for k in ('vendor_provenance_authenticated','full_historical_US200_certified','actual_availability_certified','financial_vintage_certified','research_certified','row_values_exported','financial_evidence'))})
out={'fixed_commit':'ea6053e3e9ef4be17db246daf18a4cf9b2e5be58','synthetic_memory_only':True,'scenarios':cases,'unit_methods':0,'new_market_QC_model_or_authoritative_budget_calls':0,'source_raw_sha256':hashlib.sha256((SOURCE/'cloud/qresearch/data_certification.py').read_bytes()).hexdigest()}
(O/'mapping_gap_controls_first_result.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(out,ensure_ascii=False,indent=2));raise SystemExit(0 if all(c['expectation_met'] for c in cases) else 1)
