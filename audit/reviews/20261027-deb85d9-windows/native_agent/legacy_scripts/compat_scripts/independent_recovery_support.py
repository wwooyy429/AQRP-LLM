"""Independent WR17 actual-CLI and filesystem-ledger recovery tests."""
import argparse
import base64
from copy import deepcopy
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import unittest

ap=argparse.ArgumentParser();ap.add_argument('--source',required=True);ap.add_argument('--out',required=True)
arg=ap.parse_args();ROOT=Path(arg.source).resolve();OUT=Path(arg.out).resolve();OUT.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(ROOT/'cloud'))
from qresearch.artifacts import FilesystemArtifactStore,MemoryArtifactStore,canonical_json,content_hash
from qresearch.registry import Registry
from qresearch.engineering_tasks import EngineeringTaskPlan,EngineeringTaskBridge,JOINT_PROBE_CHECKS
from qresearch.engineering_data import _finish
from qresearch.collection import HistoricalCollectionPlan

LOG=[];INPUTS=[];STATS={'actual_CLI_processes':0,'direct_freeze_processes':0,'synthetic_metadata_finish_calls':0,'actual_worker_executions':0}
ENV=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
CHECK_FILES=['tools/stage2.py','cloud/qresearch/engineering_tasks.py','cloud/qresearch/registry.py','config/budget.json','audit/runtime/registry/events.jsonl']
BEFORE={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in CHECK_FILES}
def dump(path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(canonical_json(value))
def files(root):return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
def registry(case):
    store=FilesystemArtifactStore(case/'audit/runtime')
    return Registry(store,json.loads(store.read_bytes('registry/baseline.json')))
def invoke(case,args,label,*,direct=False):
    index=len(LOG);argv=[sys.executable,'-B',*(args if direct else [str(case/'tools/stage2.py'),*map(str,args)])]
    if direct:STATS['direct_freeze_processes']+=1
    else:STATS['actual_CLI_processes']+=1
    started=time.monotonic();r=subprocess.run(argv,cwd=case,env=ENV,capture_output=True,timeout=55)
    folder=OUT/'commands';folder.mkdir(exist_ok=True)
    stdout=folder/(str(index).zfill(3)+'-'+label+'.stdout');stderr=folder/(str(index).zfill(3)+'-'+label+'.stderr')
    stdout.write_bytes(r.stdout);stderr.write_bytes(r.stderr)
    LOG.append({'index':index,'label':label,'argv':argv,'cwd':str(case),'exit_code':r.returncode,'seconds':time.monotonic()-started,
        'stdout':str(stdout.relative_to(OUT)),'stderr':str(stderr.relative_to(OUT)),
        'stdout_sha256':hashlib.sha256(r.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(r.stderr).hexdigest()})
    return r
def okay(result):
    if result.returncode:raise AssertionError(result.stderr.decode('utf-8',errors='replace'))
    return json.loads(result.stdout)
def plan_input(version,tag):
    value={'schema_version':version,'plan_id':'INDEPENDENT-WR17-'+tag,'scope':'engineering','project_id':None,
        'source_manifest_hash':None,'deployment_hash':None,'request_mode':'symbol_resolution',
        'request_template':{'dataset':'US Equities','fields':['close'],'start':'2018-01-01T00:00:00-05:00','end':'2019-01-01T00:00:00-05:00',
            'data_version':'SYNTHETIC-WR17-'+tag,'universe_hash':None,'normalization':'raw','timezone':'America/New_York'},
        'symbol_resolution':{'tickers':['AAPL','MSFT'],'as_of':'2019-01-01T00:00:00-05:00','method':'QuantBook.add_equity/as-of fixed fixture'},
        'observation_window':{'start':'2018-01-03T00:00:00-05:00','end_exclusive':'2018-01-06T00:00:00-05:00'},
        'required_checks':{'research':['raw_data_received','second_prefetch_no_history'], 'lean':['raw_data_received','no_orders','corporate_action_received']},
        'max_retries':{'research':0,'lean':0},'report_namespace':'independent-wr17/'+tag,
        'orders_enabled':False,'financial_metrics_enabled':False,'economic_factor':None,'economic_model':None}
    if version==2:
        value['required_checks']['research']+=sorted(JOINT_PROBE_CHECKS)
        value['collection_probe']={'collection_plan':{'schema_version':1,'plan_id':'INDEPENDENT-WR17-child','scope':'engineering',
            'source':'quantconnect_fundamental_universe','data_version':'SYNTHETIC-child-'+tag,'start':'2018-01-01T00:00:00-05:00',
            'end_exclusive':'2018-02-10T00:00:00-05:00','timezone':'America/New_York',
            'fields':['dollar_volume','has_fundamental_data','time','end_time'],'calendar_days_per_request':1,
            'max_batch_records':1000,'max_records_per_window':50000,'source_manifest_hash':None},'field_catalog':None}
    return value
def fresh(label):
    case=OUT/'cases'/label/'source';case.parent.mkdir(parents=True,exist_ok=True)
    # Complete execution source/config tree; historical audit archives are not
    # runtime inputs. Start a separately identified synthetic ledger, retaining
    # the original budget document as its unchanged aggregate baseline.
    for item in ROOT.iterdir():
        if item.name=='audit':continue
        if item.is_dir():shutil.copytree(item,case/item.name,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        else:
            (case/item.name).parent.mkdir(parents=True,exist_ok=True);shutil.copy2(item,case/item.name)
    (case/'audit').mkdir(exist_ok=True);shutil.copy2(ROOT/'audit/deployment.json',case/'audit/deployment.json')
    for version in (1,2):dump(case/('config/independent-v'+str(version)+'.json'),plan_input(version,'v'+str(version)))
    active=json.loads((case/'config/quantconnect.json').read_text(encoding='utf-8'))['active_project_id']
    listing=case.parent/'synthetic-projects.json';dump(listing,{'success':True,'projects':[{'projectId':active}]})
    return case,listing
def setup_case(version,label):
    case,listing=fresh(label)
    okay(invoke(case,['freeze','--plan-file','config/independent-v'+str(version)+'.json','--projects-file',listing],label+'-freeze'))
    pointer=(case/'audit/engineering_current.json').read_bytes()
    okay(invoke(case,['register'],label+'-register'))
    attempt=okay(invoke(case,['claim','--stage','research'],label+'-claim'))['attempt_id']
    admission=okay(invoke(case,['prepare','--attempt',attempt],label+'-prepare'))
    return {'case':case,'listing':listing,'attempt':attempt,'admission':admission,'pointer':pointer,'version':version}
def admission_key(attempt):return 'engineering/admitted-inputs/'+attempt+'.json'
def synthetic_report(context,admission,stage):
    payload=admission['payload'];plan=EngineeringTaskPlan.from_dict(payload['plan'],discovered_project_ids=(payload['identity']['project_id'],))
    cloud=MemoryArtifactStore();refs={}
    if stage=='research':
        for key in ('resolved_registry_ref','resolved_request_ref'):
            data={'synthetic_fixture':True,'kind':key};name='independent-cloud/'+context['attempt']+'/'+key+'.json'
            cloud.write_once(name,canonical_json(data));refs[key]={'key':name,'sha256':content_hash(data)}
        resolution={'resolved_registry_hash':refs['resolved_registry_ref']['sha256'],'resolved_request_hash':refs['resolved_request_ref']['sha256'],
            'resolution_artifact_hash':content_hash(refs),'tickers':['AAPL','MSFT'],'ticker_count':2,'permanent_sid_count':2,
            'method':'QuantBook.add_equity/as-of fixed fixture',**refs}
    else:resolution=payload['research_resolution']
    evidence={}
    if plan.to_dict()['schema_version']==2 and stage=='research':
        child=plan.to_dict()['collection_probe'];cp=HistoricalCollectionPlan.from_dict(child['collection_plan'],field_catalog=child['field_catalog'])
        key=plan.to_dict()['report_namespace']+'/collection-probes/'+plan.hash+'/'+payload['identity']['attempt_id']+'.json'
        synthetic={'synthetic_fixture':True,'identity':payload['identity']};cloud.write_once(key,canonical_json(synthetic))
        evidence['collection_probe']={'schema_version':1,'plan_hash':cp.hash,'receipt_ref':{'key':key,'sha256':content_hash(synthetic)},
            'window_count':40,'record_count':40,'source_fetch_calls':40,'reused_windows':0,'empty_windows':0,'cache_only_source_fetch_calls':0,
            'missing_values':{field:0 for field in cp.field_catalog},'full_historical_US200_certified':False,
            'actual_availability_certified':False,'research_certified':False,'row_values_exported':False,'financial_vintage_certified':False}
    checks={name:True for name in plan.to_dict()['required_checks'][stage]}
    statistics={'record_count':6,'history_calls_first':1,'history_calls_second':0,'expected_formation_count':3} if stage=='research' else {
        'data_event_count':6,'slice_count':3,'orders_submitted':0,'runtime_error_count':0,'dividend_event_count':1}
    STATS['synthetic_metadata_finish_calls']+=1
    wrapper=_finish(cloud,payload,checks,statistics,resolution,evidence=evidence)
    return wrapper
def envelopes(context,admission,stage):
    wrapper=synthetic_report(context,admission,stage);payload=admission['payload'];project=payload['identity']['project_id']
    text=base64.b64encode(canonical_json(wrapper)).decode();folder=context['case'].parent/'native';folder.mkdir(exist_ok=True)
    if stage=='research':
        result={'outputs':[{'output_type':'stream','name':'stdout','text':'AQRP_ENGINEERING_JSON '+text}],'status':'ok','success':True}
        path=folder/'research.json';dump(path,{'tool_name':'mcp__quantconnect__jupyter_execute_cell','arguments':{'projectId':project,'index':4},
            'result':{'structuredContent':result,'content':[{'type':'text','text':json.dumps(result)}]}})
        return {'result':path}
    external='synthetic-wr17-'+payload['identity']['attempt_id'];sub=folder/'submission.json';read=folder/'read.json';logs=folder/'logs.json'
    dump(sub,{'tool_name':'mcp__quantconnect__create_backtest','arguments':{'projectId':project,'backtestName':'independent-offline'},
        'result':{'success':True,'errors':[],'backtestId':external}})
    dump(read,{'tool_name':'mcp__quantconnect__read_backtest','arguments':{'projectId':project,'backtestId':external},
        'result':{'success':True,'errors':[],'backtest':{'backtestId':external,'projectId':project,'completed':True,'progress':1,
            'status':'Completed.','hasInitializeError':False,'statistics':{'Total Orders':'0'}}}})
    parts=[text[i:i+500] for i in range(0,len(text),500)]
    lines=['AQRP_ENGINEERING '+payload['identity']['attempt_id']+' '+str(i)+'/'+str(len(parts))+' '+s for i,s in enumerate(parts)]
    dump(logs,[{'tool_name':'mcp__quantconnect__search_backtest_logs','arguments':{'projectId':project,'backtestId':external,
        'query':'AQRP_ENGINEERING '+payload['identity']['attempt_id'],'page':1},'result':{'success':True,'errors':[],'logs':lines,'totalPages':1}}])
    return {'submission':sub,'result':read,'logs':logs}
def restore_files(case,saved):
    for relative,content in saved.items():
        path=case/relative
        if content is None:
            if path.exists():path.unlink()
        else:path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(content)
def drift(context,attempt):
    case=context['case'];names=['audit/engineering_current.json','audit/deployment.json','config/source_catalog.json','cloud/research_config.py']
    saved={name:(case/name).read_bytes() if (case/name).exists() else None for name in names}
    for name in names[:3]:(case/name).unlink(missing_ok=True)
    with (case/names[3]).open('ab') as stream:stream.write(b'\n# INDEPENDENT historical settlement source drift\n')
    local=case/('audit/task_inputs/'+attempt+'.py');local.unlink(missing_ok=True)
    return saved

