"""Read-only independent archive identity/counter inspection; no live platform I/O."""
import argparse,base64,hashlib,io,json,subprocess,sys,tarfile
from pathlib import Path
P=argparse.ArgumentParser();P.add_argument('--source',required=True);P.add_argument('--git',required=True);P.add_argument('--out',required=True);a=P.parse_args()
S=Path(a.source).resolve();O=Path(a.out).resolve();O.mkdir(parents=True,exist_ok=True);G=Path(a.git)
sys.dont_write_bytecode=True;sys.path[:0]=[str(S/'cloud'),str(S/'tools')]
from qresearch.artifacts import MemoryArtifactStore,canonical_json,content_hash
from qresearch.registry import Registry
from qresearch.engineering_receipts import research_cell_source,research_dispatch_binding,backtest_submission
import stage2
CHECKS=[];READ={}
def ck(name,condition):
 CHECKS.append({'name':name,'passed':bool(condition)});assert condition,name
def read(p):
 b=p.read_bytes();READ[p.relative_to(S).as_posix()]=hashlib.sha256(b).hexdigest();return b
def J(p):return json.loads(read(p))
def native(p):
 v=[];r=p['result']
 if r.get('structuredContent')is not None:v.append(r['structuredContent'])
 for b in r.get('content',[]):assert b['type']=='text';v.append(json.loads(b['text']))
 ck('all_native_mirrors_equal',bool(v)and all(canonical_json(x)==canonical_json(v[0])for x in v));return v[0]
m=MemoryArtifactStore()
for p in (S/'audit/runtime').rglob('*'):
 if p.is_file()and p.suffix in {'.py','.json','.jsonl'}:m.write_once(p.relative_to(S/'audit/runtime').as_posix(),read(p))
reg=Registry(m,J(S/'audit/runtime/registry/baseline.json'));snapshot=reg.snapshot();before=dict(m._data)
versions={'diagnostic':('b9f952c1de3a44f9b06e5c552f7d1af3','42b45c830aac691fe0763bfc6363997947625bc1'),'repaired':('2d1095df62dc4222bffd8000c0737d38','662ccd876b67ca0949f921a53c4c33df37cfbbf1'),'LEAN':('37dc855045e14ca49c88fd9d75f40cf7','662ccd876b67ca0949f921a53c4c33df37cfbbf1')}
trees={};records=[]
for label,(attempt,commit)in versions.items():
 b=stage2.bridge_for_attempt(attempt,registry=reg);ad=stage2.admitted_input(b,attempt);p=ad['payload'];dep=ad['deployment'];record=next(x for x in snapshot['attempts']if x['attempt_id']==attempt)
 ck(label+'_config_id',content_hash({'engineering_task_schema_version':1,'plan':p['plan']})==p['identity']['config_id'])
 ck(label+'_plan_hash',content_hash(p['plan'])==p['identity']['plan_hash'])
 encoded=('TASK_INPUT_JSON = '+repr(canonical_json(p).decode())+'\n').encode();ck(label+'_physical_input',read(S/ad['input_path'])==encoded);ck(label+'_input_hash',hashlib.sha256(encoded).hexdigest()==dep['input_hash'])
 if commit not in trees:
  raw=subprocess.check_output(['git','-C',str(G),'archive',commit,'cloud'])
  with tarfile.open(fileobj=io.BytesIO(raw))as t:trees[commit]={x.name.removeprefix('cloud/'):t.extractfile(x).read()for x in t.getmembers()if x.isfile()}
 normalized={n:hashlib.sha256(trees[commit][n].decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n').encode()).hexdigest()for n in p['deployment_manifest']}
 ck(label+'_frozen_Git32_source_hashes',len(normalized)==32 and normalized==p['deployment_manifest']);ck(label+'_deployment_hash',content_hash(normalized)==dep['deployment_hash'])
 row={'kind':label,'attempt_id':attempt,'runtime_source_commit':commit,'ledger_status':record['status'],'plan_hash':p['identity']['plan_hash'],'config_id':p['identity']['config_id'],'deployment':dep,'frozen_Git_source_files':32}
 if label!='LEAN':
  packet=J(S/'audit/tool_observations'/(attempt+'-research.json'));n=native(packet);cell=J(S/'audit/tool_observations'/(attempt+'-read-cell.json'));binding=stage2._read_research_dispatch(b,p,dep,require_dispatch=True)
  ck(label+'_native_source_dispatch_binding',research_dispatch_binding(p,dep,cell)==binding)
  row.update(native_packet_sha256=READ['audit/tool_observations/'+attempt+'-research.json'],cell_source_sha256=hashlib.sha256(research_cell_source(p,dep).encode()).hexdigest(),dispatch_binding_sha256=content_hash(binding))
  if label=='diagnostic':
   d=json.loads(n['evalue'].split('; diagnostic=',1)[1]);ck('diagnostic_owned_code_and_partial_counter',d['failure_code']=='native_sid_duplicate'and d['rows_emitted']==5124 and record['status']=='failed');row['diagnostic']=d
  else:
   marker=n['text'].strip();ck('repaired_one_marker',marker.startswith('AQRP_ENGINEERING_JSON ')and len(marker.splitlines())==1);w=json.loads(base64.b64decode(marker.split(' ',1)[1],validate=True));report=w['cloud_report'];ck('repaired_13_exact_true_checks',set(report['checks'])==set(p['plan']['required_checks']['research'])and len(report['checks'])==13 and all(v is True for v in report['checks'].values()))
   ck('repaired_report_identity_hash',report['identity']==p['identity']and w['report_ref']['key']==p['report_key']and w['report_ref']['sha256']==content_hash(report))
   ck('repaired_price_cached_counts',report['statistics']=={'expected_formation_count':250,'history_calls_first':0,'history_calls_second':0,'record_count':2510})
   probe=report['evidence']['collection_probe'];expected={'window_count':40,'record_count':208223,'source_fetch_calls':40,'reused_windows':0,'empty_windows':13,'cache_only_source_fetch_calls':0,'duplicate_projection_records':27,'conflicting_projection_records':0}
   ck('repaired_probe_exact_aggregate_counts',all(probe[k]==v and type(probe[k])is int for k,v in expected.items()))
   ck('repaired_probe_certification_flags_false',all(probe[k]is False for k in ['full_historical_US200_certified','actual_availability_certified','research_certified','row_values_exported','financial_vintage_certified']))
   row.update(checks=report['checks'],price_statistics=report['statistics'],collection_probe=probe)
 else:
  packet=J(S/'audit/tool_observations'/(attempt+'-submission.json'));native(packet);submitted=backtest_submission(p,dep,packet);original=b._recorded_submission(p)
  ck('LEAN_submission_receipt_matches_original',content_hash(submitted)==original['receipt_ref']['sha256']and m.read_bytes(original['receipt_ref']['key'])==canonical_json(submitted))
  ck('LEAN_actual_external_id_pending',submitted['external_id']=='3e68866a46ca88ff16481c31b3c2c822'and record['status']=='pending')
  files=sorted(x.name for x in (S/'audit/tool_observations').glob(attempt+'*'));ck('LEAN_no_delivered_terminal_or_logs_in_fixed_source',files==[attempt+'-submission.json'])
  ck('LEAN_required_seven_distinct_from_Research13',len(p['plan']['required_checks']['lean'])==7 and len(p['plan']['required_checks']['research'])==13)
  row.update(external_id=submitted['external_id'],required_checks=p['plan']['required_checks'],archived_task_packets=files,terminal_status=None,order_count=None,financial_evidence=False)
 records.append(row)
ck('all_readonly_Memory_bytes_unchanged',before==m._data)
out={'fixed_review_commit':'4520fd1a4421a9b764d2bfd61e5fb5cf4b59a9c8','checks':CHECKS,'static_checks':len(CHECKS),'software_methods':0,'archived_native_records':records,'source_input_raw_sha256':READ,'QC_calls':0,'LEAN_terminal_log_reads':0,'compile_calls':0,'live_cloud_readback_this_recheck':False,'evidence_level':'Developer-archived native packets independently decoded and identity-bound; frozen source32 perattempt verified against local fixed Git. Not a live platform fetch or remote signature.','limits':['Research aggregate counters were decoded, not fresh row-level208223 recount.','Normal004 compile has only developer summary; original native compile packet not certified.','Prior audit35 QC source-only calls are historical independent readback, not this recheck calls.','Native error response has no intrinsic attempt/source; trusted dispatcher original response provenance remains an operational boundary.']}
(O/'archive_inspection.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8');print(json.dumps({'static_checks':len(CHECKS),'all_passed':True,'records':3,'software_methods':0,'QC_calls':0}))
