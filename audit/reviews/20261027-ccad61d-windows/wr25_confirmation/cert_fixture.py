"""Independent synthetic 201-name, 21-session data fixture. No author test imports."""
from copy import deepcopy
from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1];SOURCE=ROOT/'source';sys.dont_write_bytecode=True;sys.path.insert(0,str(SOURCE/'cloud'))
import pandas as pd
from qresearch.artifacts import MemoryArtifactStore,canonical_json,content_hash
from qresearch.ingestion import HistoricalBatchIngestor
from qresearch.data_certification import DataCertificationPlan,store_certification_table,audit_data_certification,summarize_certification_scope,DataCertificationError

NY='America/New_York'
def ts(value):return pd.Timestamp(value,tz=NY)
def iso(value):return value.isoformat()
class Calendar:
 def __init__(self,pairs):self.pairs=list(pairs)
 def decisions(self,start,end):
  return pd.DataFrame([{'formation_at':a,'session_close':b} for a,b in self.pairs if start<=a<end],columns=['formation_at','session_close'])

def raw_fixture():
 days=[d for d in pd.bdate_range('2018-01-03','2018-02-02',tz=NY) if str(d.date())!='2018-01-15']
 pairs=[(day+pd.Timedelta(hours=9),previous+pd.Timedelta(hours=16)) for previous,day in zip(days[:-1],days[1:])]
 sessions=[close for _,close in pairs];formations=[a for a,_ in pairs if a>=ts('2018-02-01')]
 assert len(sessions)==21 and len(formations)==2
 sids=['SID'+str(i).zfill(3) for i in range(201)];members=sids[:200];old=ts('2017-12-01')
 liquid=[]
 for sid_index,sid in enumerate(sids):
  for session in sessions:
   liquid.append({'sid':sid,'source_revision':'liquid_v1','session':iso(session),'dollar_volume':1000-sid_index,'dollar_volume_field':'dollar_volume','instrument_type':'common_stock','listed':True,
    'classification_effective_at':iso(old),'classification_available_at':iso(old),'listing_effective_at':iso(old),'listing_available_at':iso(old),
    'vendor_available_at':iso(session+pd.Timedelta(minutes=5)),'historical_ingested_at':iso(session+pd.Timedelta(minutes=10)),'availability_basis':'actual_historical_receipt'})
 financial=[{'sid':sid,'source_revision':'financial_v1','field_path':'fundamental.assets','unit':'USD','period_accessor':'value','report_period_end':'2017-12-31T00:00:00-05:00','value':10+i,'public_at':'2018-01-02T12:00:00-05:00','public_date':None,'public_precision':'timestamp','vendor_available_at':'2018-01-02T12:01:00-05:00','historical_ingested_at':'2018-01-02T12:02:00-05:00','availability_basis':'actual_historical_receipt'} for i,sid in enumerate(sids)]
 masters=[{'sid':sid,'ticker':'T'+str(i).zfill(3),'effective_from':iso(old),'effective_to':None,'available_at':iso(old),'instrument_type':'common_stock','listed':True,'exchange':'NYSE'} for i,sid in enumerate(sids)]
 prices=[{'sid':sid,'session':iso(close),'available_at':iso(close+pd.Timedelta(minutes=5)),'open':10,'high':12,'low':9,'close':11,'volume':10,'normalization':'raw','source_revision':'price_v1'} for sid in sids for close in sessions[-2:]]
 tables={'membership':[{'formation_at':iso(a),'sids':list(members)} for a in formations],'prices':prices,'security_master':masters,'corporate_actions':[]}
 return {'pairs':pairs,'liquid':liquid,'financial':financial,'tables':tables,'sids':sids,'members':members}

def make(mutator=None,*,raw=None,plan_change=None):
 raw=deepcopy(raw if raw is not None else raw_fixture())
 if mutator:mutator(raw)
 store=MemoryArtifactStore();catalog={'fundamental.assets':{'unit':'USD','period_accessor':'value'}}
 ing=HistoricalBatchIngestor(store,source='independent_synthetic_source',data_version='independent_v1',origin='historical_all_market',financial_catalog=catalog,synthetic=True)
 source_hash=json.loads((SOURCE/'audit/stage_verification.json').read_text(encoding='utf-8-sig'))['source_hash']
 pv={'schema_version':1,'plan_id':'independent_A','start':'2018-02-01T00:00:00-05:00','end_exclusive':'2018-02-03T00:00:00-05:00','warmup_start':'2018-01-03T00:00:00-05:00','timezone':NY,'source_manifest_hash':source_hash,'data_version':'independent_v1','ingestion_namespace':ing.namespace,'financial_catalog':catalog,'universe_size':200,'liquidity_lookback_sessions':20}
 if plan_change:pv.update(plan_change)
 plan=DataCertificationPlan.from_dict(pv)
 refs={}
 for kind in ('liquidity','financial'):
  refs[kind]=[ing.ingest(kind,raw['liquid' if kind=='liquidity' else 'financial'],partition='independent/'+kind)['batch_ref']]
 for kind,rows in raw['tables'].items():refs[kind]=[store_certification_table(store,plan,kind,rows,synthetic=True)]
 kwargs={'calendar':Calendar(raw['pairs']),'ingestor':ing,'synthetic':True,**{k+'_refs':v for k,v in refs.items()}}
 kwargs['membership_refs']=kwargs.pop('membership_refs');kwargs['price_refs']=kwargs.pop('prices_refs');kwargs['corporate_action_refs']=kwargs.pop('corporate_actions_refs')
 return {'store':store,'plan':plan,'raw':raw,'ingestor':ing,'refs':refs,'kwargs':kwargs}
def run(fixture):return audit_data_certification(fixture['store'],fixture['plan'],**fixture['kwargs'])
def scope(fixture,report):
 p=fixture['plan'].to_dict()
 return {'schema_version':1,'start':p['start'],'end_exclusive':p['end_exclusive'],'source_manifest_hash':p['source_manifest_hash'],'ingestion_namespace':p['ingestion_namespace'],'data_version_hash':content_hash(p['data_version']),'financial_catalog_hash':content_hash(p['financial_catalog']),
  'partitions':[{'plan_hash':fixture['plan'].hash,'start':p['start'],'end_exclusive':p['end_exclusive'],'report_ref':report['report_ref']}]}
