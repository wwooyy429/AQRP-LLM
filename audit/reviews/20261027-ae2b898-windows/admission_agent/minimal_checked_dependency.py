"""Standalone public-API MRE: checked Research dependency is weaker than Bridge completion.
All plans, reports, ledgers and receipts are synthetic. No external calls.
Run: python -B minimal_checked_dependency.py <fixed source>
Expected safety assertions fail on ae2b898; exits 1 if any malformed dependency is admitted.
"""
from pathlib import Path
from copy import deepcopy
from types import SimpleNamespace
from hashlib import sha256
import json,sys
sys.dont_write_bytecode=True
SOURCE=Path(sys.argv[1]).resolve()
sys.path.insert(0,str(SOURCE/'cloud'))
from qresearch.artifacts import MemoryArtifactStore,canonical_json,content_hash
from qresearch.registry import Registry,RegistryError
from qresearch.engineering_tasks import EngineeringTaskBridge,EngineeringTaskPlan,EngineeringTaskError
from qresearch.collection import HistoricalCollectionPlan
CAT={name:{'kind':kind,'role':'independent_observation','unit':unit,'period_accessor':None}
     for name,kind,unit in [('dollar_volume','number','USD'),('has_fundamental_data','boolean','flag'),
                            ('time','text','clock'),('end_time','text','clock')]}

def budget():
    return {'limits':{'full_configurations':12,'research_execution_attempts':20,'lean_submission_attempts':16},
      'allocations':{'full_configurations':{'total':12,'normal':8,'reserve':4},'research_execution_attempts':{'total':20,'normal':12,'reserve':8},
                     'lean_submission_attempts':{'total':16,'normal':8,'reserve':8}},'usage':{}}

def joint(project=931001,name='independent-joint',retries=0):
    raw={'schema_version':2,'plan_id':name,'scope':'engineering','project_id':project,'source_manifest_hash':'a'*64,'deployment_hash':'b'*64,
      'request_mode':'symbol_resolution','request_template':{'dataset':'US Equities','fields':['close','volume'],'start':'2018-01-01T00:00:00-05:00',
        'end':'2019-01-01T00:00:00-05:00','data_version':'independent-parent-v1','universe_hash':'c'*64,'normalization':'raw','timezone':'America/New_York'},
      'symbol_resolution':{'tickers':['AAPL','MSFT'],'as_of':'2019-01-01T00:00:00-05:00','method':'QuantBook.add_equity/as-of fixed fixture'},
      'observation_window':{'start':'2018-01-03T00:00:00-05:00','end_exclusive':'2018-02-01T00:00:00-05:00'},
      'required_checks':{'research':['raw_data_received','collection_windows_completed','collection_cache_only_replay','collection_nonempty'],
                         'lean':['no_orders']},'max_retries':{'research':retries,'lean':retries},
      'report_namespace':'independent/joint','orders_enabled':False,'financial_metrics_enabled':False,'economic_factor':None,'economic_model':None,
      'collection_probe':{'field_catalog':deepcopy(CAT),'collection_plan':{'schema_version':1,'plan_id':'independent-child','scope':'engineering',
          'source':'quantconnect_fundamental_universe','data_version':'independent-child-v1','start':'2018-01-01T00:00:00-05:00',
          'end_exclusive':'2018-02-10T00:00:00-05:00','timezone':'America/New_York','fields':list(CAT),'calendar_days_per_request':1,
          'max_batch_records':1000,'max_records_per_window':50000,'source_manifest_hash':'a'*64}}}
    return EngineeringTaskPlan.from_dict(raw,discovered_project_ids=[project],probe_field_catalog=CAT)

h=SimpleNamespace(CAT=CAT,budget=budget,joint=joint)

def setup(store=None,retries=0):
    r=Registry(MemoryArtifactStore() if store is None else store,h.budget())
    b=EngineeringTaskBridge(r,h.joint(retries=retries));b.register();return r,b

def observation(b,a):
    payload=b.payload(a);identity=payload['identity'];document=b.plan.to_dict();external='qc-research:'+str(document['project_id'])+':'+a.attempt_id
    deployment={'source_manifest_hash':document['source_manifest_hash'],'deployment_hash':document['deployment_hash'],'input_hash':'d'*64}
    refs={'resolved_registry_ref':{'key':'independent/resolution/registry.json','sha256':'1'*64},
          'resolved_request_ref':{'key':'independent/resolution/request.json','sha256':'2'*64}}
    resolution={'resolved_request_hash':'2'*64,'resolved_registry_hash':'1'*64,'resolution_artifact_hash':content_hash(refs),
                'tickers':['AAPL','MSFT'],'ticker_count':2,'permanent_sid_count':2,'method':document['symbol_resolution']['method'],**refs}
    child=document['collection_probe'];cp=HistoricalCollectionPlan.from_dict(child['collection_plan'],field_catalog=child['field_catalog'])
    probe={'schema_version':1,'plan_hash':cp.hash,'receipt_ref':{'key':document['report_namespace']+'/collection-probes/'+b.plan.hash+'/'+a.attempt_id+'.json','sha256':'3'*64},
       'window_count':40,'record_count':40,'source_fetch_calls':40,'reused_windows':0,'empty_windows':0,'cache_only_source_fetch_calls':0,
       'missing_values':{field:0 for field in h.CAT},
       **{f:False for f in ['full_historical_US200_certified','actual_availability_certified','research_certified','row_values_exported','financial_vintage_certified']}}
    report={'schema_version':1,'identity':identity,'status':'completed','terminal':True,
       'checks':{name:True for name in document['required_checks']['research']},
       'statistics':{'record_count':2,'history_calls_first':1,'history_calls_second':0,'expected_formation_count':1},
       'resolution':resolution,'evidence':{'collection_probe':probe},
       **{f:False for f in ['market_values_exported','economic_factor_tested','final_data_accessed','full_US200_coverage_certified','actual_availability_verified']}}
    raw={'synthetic_observation':'independent-only','response_sha256':'f'*64}
    submitted={'identity':identity,'identity_kind':payload['external_identity_kind'],'external_id':external,'accepted':True,'status':'submitted','deployment':deployment,'raw_receipt':raw}
    observed={'platform':{'identity':dict(identity,external_id=external),'terminal':True,'status':'completed','deployment':deployment,'raw_receipt':raw},
              'cloud_report':report,'report_ref':{'key':payload['report_key'],'sha256':content_hash(report)}}
    return submitted,observed


def main():
    rows=[]
    for mutation in ["input_hash_conflict","empty_raw","missing_submission"]:
        r,b=setup()
        a=b.claim("research")
        submission,observed=observation(b,a)
        if mutation!="missing_submission":
            b.record_submission(a,submission)
        if mutation=="input_hash_conflict":
            observed["platform"]["deployment"]["input_hash"]="e"*64
        if mutation=="empty_raw":
            observed["platform"]["raw_receipt"]={}
        bridge_error=None
        try:
            b.consume_completion(a,completion_source=lambda _:deepcopy(observed))
        except EngineeringTaskError as exc:
            bridge_error=str(exc)
        assert bridge_error is not None,"Negative control: Bridge unexpectedly accepted the same observation"
        encoded=canonical_json(observed)
        digest=sha256(encoded).hexdigest()
        key="engineering/evidence/"+a.attempt_id+"/completion/"+digest+".json"
        r.store.write_once(key,encoded)
        result={"scope":"engineering","identity":b.payload(a)["identity"],"external_id":submission["external_id"],
                "cloud_report":observed["cloud_report"],"report_ref":observed["report_ref"],
                "platform_evidence_ref":{"key":key,"sha256":digest},"financial_evidence":False}
        r.complete(a,result,external_id=submission["external_id"])
        before=r.snapshot()["usage"]
        error=None;lean=None
        try:
            lean=r.begin_attempt(b.config_id,"lean",operation_key=b._operation("lean"))
        except RegistryError as exc:
            error=str(exc)
        rows.append({"mutation":mutation,"bridge_refusal":bridge_error,
                     "recorded_submission":None if mutation=="missing_submission" else json.loads(r.store.read_bytes(b._submission_key(a.attempt_id))),
                     "completion_platform":observed["platform"],"before":before,"after":r.snapshot()["usage"],
                     "registry_refusal":error,"lean_granted":lean is not None and lean.should_execute,
                     "lean_attempt_id":None if lean is None else lean.attempt_id})
    # A truly checked completion must still permit LEAN; this is not an all-refuse test.
    r,b=setup();a=b.claim("research");submission,observed=observation(b,a)
    b.record_submission(a,submission)
    assert b.consume_completion(a,completion_source=lambda _:deepcopy(observed)).status=="completed"
    good=r.begin_attempt(b.config_id,"lean",operation_key=b._operation("lean"))
    assert good.should_execute
    data={"source_root":str(SOURCE),"reviewed_source_commit":"ae2b8985f3799c246e90341370f86d80483f63ed",
          "script_sha256":sha256(Path(__file__).read_bytes()).hexdigest(),
          "new_unit_methods":0,"scenario_cases":4,"positive_checked_research_permits_lean":True,"observations":rows,
          "all_three_bridge_refusals":all(row["bridge_refusal"] for row in rows),
          "malformed_dependency_lean_permits":sum(row["lean_granted"] for row in rows),"external_calls":0}
    out=Path(__file__).with_name("minimal_checked_dependency_first.json")
    out.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(data,ensure_ascii=False,indent=2))
    assert not any(row["lean_granted"] for row in rows),"Registry admitted a dependency that Bridge explicitly rejected"
    return 0
if __name__=="__main__":raise SystemExit(main())
