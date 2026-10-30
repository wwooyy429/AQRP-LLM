"""WR16: standalone, synthetic Registry/Bridge admission comparison.

Usage: python -B minimal_joint_registry.py <source-dir>
No developer fixture or real ledger is used. A failing exit is the finding.
"""
from pathlib import Path
from copy import deepcopy
import json,sys
source=Path(sys.argv[1]).resolve();sys.dont_write_bytecode=True;sys.path.insert(0,str(source/'cloud'))
from qresearch.artifacts import MemoryArtifactStore
from qresearch.registry import Registry,RegistryError
from qresearch.engineering_tasks import EngineeringTaskPlan,EngineeringTaskBridge,EngineeringTaskError

catalog={n:{'kind':k,'role':'independent','unit':u,'period_accessor':None} for n,k,u in [
    ('dollar_volume','number','USD'),('has_fundamental_data','boolean','flag'),('time','text','clock'),('end_time','text','clock')]}
raw={'schema_version':2,'plan_id':'independent-registry-MRE','scope':'engineering','project_id':931001,
 'source_manifest_hash':'a'*64,'deployment_hash':'b'*64,'request_mode':'symbol_resolution',
 'request_template':{'dataset':'US Equities','fields':['close'],'start':'2018-01-01T00:00:00-05:00','end':'2019-01-01T00:00:00-05:00',
    'data_version':'independent-prices','universe_hash':'c'*64,'normalization':'raw','timezone':'America/New_York'},
 'symbol_resolution':{'tickers':['AAPL','MSFT'],'as_of':'2019-01-01T00:00:00-05:00','method':'QuantBook.add_equity/as-of fixed fixture'},
 'observation_window':{'start':'2018-01-03T00:00:00-05:00','end_exclusive':'2018-02-01T00:00:00-05:00'},
 'required_checks':{'research':['raw_data_received','collection_windows_completed','collection_cache_only_replay','collection_nonempty'],'lean':['no_orders']},
 'max_retries':{'research':0,'lean':0},'report_namespace':'independent/joint','orders_enabled':False,'financial_metrics_enabled':False,
 'economic_factor':None,'economic_model':None,'collection_probe':{'field_catalog':catalog,'collection_plan':{
 'schema_version':1,'plan_id':'independent-probe','scope':'engineering','source':'quantconnect_fundamental_universe',
 'data_version':'independent-observation','start':'2018-01-01T00:00:00-05:00','end_exclusive':'2018-02-10T00:00:00-05:00',
 'timezone':'America/New_York','fields':list(catalog),'calendar_days_per_request':1,'max_batch_records':1000,
 'max_records_per_window':50000,'source_manifest_hash':'a'*64}}}
limits={k:{'total':t,'normal':n,'reserve':t-n} for k,t,n in [('configurations',12,8),('research',20,12),('lean',16,8)]}
def pair():
    r=Registry(MemoryArtifactStore(),limits);p=EngineeringTaskPlan.from_dict(deepcopy(raw),discovered_project_ids=[931001],probe_field_catalog=catalog)
    b=EngineeringTaskBridge(r,p);b.register();return r,b
observations=[]
for case in ['wrong_operation','lean_before_research','retry_above_zero']:
    r,b=pair();control=None
    if case=='retry_above_zero':
        previous=b.claim('research');r.fail(previous,'independent known failure')
        try:b.claim('research',retry_of=previous.attempt_id,reason='known repair')
        except EngineeringTaskError as e:control=str(e)
    elif case=='lean_before_research':
        try:b.claim('lean')
        except EngineeringTaskError as e:control=str(e)
    before=r.snapshot()['usage'];attempt=None;refusal=None
    try:
        if case=='wrong_operation':attempt=r.begin_attempt(b.config_id,'research',operation_key='independent-free-operation')
        elif case=='lean_before_research':attempt=r.begin_attempt(b.config_id,'lean',operation_key=b._operation('lean'))
        else:attempt=r.begin_attempt(b.config_id,'research',operation_key=b._operation('research'),retry_of=previous.attempt_id,reason='known repair')
    except RegistryError as e:refusal=str(e)
    usable=False;later_refusal=None
    if attempt:
        try:b.payload(attempt);usable=True
        except EngineeringTaskError as e:later_refusal=str(e)
    observations.append({'case':case,'bridge_control_refusal':control,'registry_refusal':refusal,
      'attempt':None if attempt is None else vars(attempt),'before':before,'after':r.snapshot()['usage'],
      'bridge_payload_usable_after_charge':usable,'later_payload_refusal':later_refusal})
print(json.dumps({'executed_source':str(source),'observations':observations,'actual_remote_calls':0},indent=2))
assert all(x['registry_refusal'] for x in observations),'Joint policy is not atomically enforced at direct Registry admission'
