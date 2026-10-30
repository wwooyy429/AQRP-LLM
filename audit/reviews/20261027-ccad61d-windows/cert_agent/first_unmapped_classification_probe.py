from cert_fixture import *
import hashlib
O=Path(__file__).parent
def change(raw):
 old=raw['tables']['security_master'][0];old['effective_to']='2018-01-25T00:00:00-05:00'
 new=deepcopy(old);new.update(ticker='RENAMED000',effective_from='2018-01-25T00:00:00-05:00',effective_to=None,available_at='2018-01-25T00:00:00-05:00',instrument_type='UNMAPPED_VENDOR_CODE')
 raw['tables']['security_master'].append(new);raw['liquid']=[x for x in raw['liquid'] if x['sid']!='SID000']
 for row in raw['tables']['membership']:row['sids']=raw['sids'][1:201]
f=make(change);r=run(f);out={'fixed_commit':'ccad61d03ccf17bf2bdc2d7ffc88dfd11b6d3ca6','current_master_instrument_type':'UNMAPPED_VENDOR_CODE','instrument_type_not_in_declared_ingestion_taxonomy':True,'status':r['status'],'checks':r['checks'],'counts':r['counts'],'all_certification_flags_false':all(r[k] is False for k in ('vendor_provenance_authenticated','full_historical_US200_certified','actual_availability_certified','financial_vintage_certified','research_certified','row_values_exported','financial_evidence')),'source_raw_sha256':hashlib.sha256((SOURCE/'cloud/qresearch/data_certification.py').read_bytes()).hexdigest(),'synthetic_memory_only':True}
raw=(json.dumps(out,ensure_ascii=False,indent=2)+'\n').encode();(O/'first_unmapped_classification_result.json').write_bytes(raw);print(raw.decode(),end='');raise SystemExit(1 if r['status']=='observations_passed' else 0)
