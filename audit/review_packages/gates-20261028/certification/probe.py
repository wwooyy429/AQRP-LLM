from pathlib import Path
from copy import deepcopy
import json
import sys

ROOT=Path(__file__).resolve().parents[4]
sys.dont_write_bytecode=True
sys.path[:0]=[str(ROOT/'cloud'),str(ROOT/'tests')]
from qresearch.artifacts import MemoryArtifactStore
from qresearch.data_certification import DataCertificationPlan,audit_data_certification,store_certification_table
from qresearch.ingestion import HistoricalBatchIngestor
import test_data_certification as fixture

store=MemoryArtifactStore()
calendar=fixture.Calendar()
liquidity,_=fixture.source_data(calendar)
ingestor=HistoricalBatchIngestor(store,source='synthetic-empty-financial-gate',data_version='synthetic-v1',
    origin='historical_all_market',financial_catalog={},synthetic=True)
raw=fixture.plan(ingestor).to_dict();raw['financial_catalog']={}
plan=DataCertificationPlan.from_dict(raw)
refs={'liquidity_refs':[ingestor.ingest('liquidity',liquidity,partition='synthetic/2018')['batch_ref']],
    'financial_refs':[]}
tables=fixture.tables(calendar)
for name,arg in [('membership','membership_refs'),('prices','price_refs'),
    ('security_master','security_master_refs'),('corporate_actions','corporate_action_refs')]:
    refs[arg]=[store_certification_table(store,plan,name,tables[name],synthetic=True)]
result=audit_data_certification(store,plan,calendar=calendar,ingestor=ingestor,synthetic=True,**refs)
assert result['status']=='insufficient_evidence'
assert result['counts']['observed_member_cells']==400
assert result['counts']['price_observed_cells']==400
assert result['checks']['financial_fields_declared'] is False
assert result['checks']['financial_scope_coverage_complete'] is False
assert result['checks']['declared_actual_timing_complete'] is False
for name in ('full_historical_US200_certified','financial_vintage_certified','actual_availability_certified',
    'research_certified','financial_evidence','vendor_provenance_authenticated'):
    assert result[name] is False
(Path(__file__).parent/'synthetic_empty_financial_plan.json').write_text(json.dumps(plan.to_dict(),indent=2)+'\n',encoding='utf-8')
print(json.dumps({'probe':'empty_financial_catalog_with_other_components_present','status':result['status'],
    'synthetic':True,'member_cells':result['counts']['observed_member_cells'],
    'price_cells':result['counts']['price_observed_cells'],
    'failed_checks':[n for n,v in result['checks'].items() if not v],
    'certification_flags_remain_false':True,'market_calls':0,'licensed_rows_exported':False}))
