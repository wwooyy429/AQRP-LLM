"""Independent raw-hash/Git/archive/ledger audit; no product test approval."""
from pathlib import Path
import ast,hashlib,json,subprocess,sys,zipfile
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parent;ROOT=R.parent;S=ROOT/'source';BASE=ROOT/'baselines/1cf2657/source';ARCH=ROOT/'archive_source'
G=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\repo')
ZIP=Path('B:/BaiduSyncdisk/学习/投资/量化/量化交易比赛/LLM审核/review-4a42c18-20261028.zip')
checks=[];commands=[]
def h(raw):return hashlib.sha256(raw).hexdigest()
def canonical(value):return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
def require(name,condition,detail=None):
 row={'name':name,'passed':bool(condition)}
 if detail is not None:row['detail']=detail
 checks.append(row)
 if not condition:raise AssertionError(name)
def git(*args,input=None):
 argv=['git','-C',str(G),*args];p=subprocess.run(argv,input=input,capture_output=True)
 commands.append({'command':argv,'exit_code':p.returncode,'stdout_bytes':len(p.stdout),'stdout_sha256':h(p.stdout),'stderr_sha256':h(p.stderr)})
 if p.returncode:raise AssertionError(('Git readonly command failed',args,p.stderr.decode(errors='replace')))
 return p.stdout
def tree_bytes(root):return{p.relative_to(root).as_posix():p.read_bytes()for p in root.rglob('*')if p.is_file()}
maps=json.loads((ROOT/'source_git_manifest.json').read_bytes())
trees={label:tree_bytes(ROOT/item['directory'])for label,item in maps.items()}
for label,item in maps.items():require('complete_raw_source_'+label,{n:h(b)for n,b in trees[label].items()}==item['files'],{'files':len(trees[label])})
prod=lambda n:n=='README.md'or n.split('/')[0]in{'cloud','config','tools','tests','docs'}
production_names={n for n in set(trees['candidate'])|set(trees['baseline'])|set(trees['archive'])if prod(n)}
require('all_production_docs_README_byte_identical',all(trees['candidate'].get(n)==trees['baseline'].get(n)==trees['archive'].get(n)for n in production_names),{'files':len(production_names)})
for label,left,right in [('baseline_to_fixed',maps['baseline']['commit'],maps['candidate']['commit']),('fixed_to_archive',maps['candidate']['commit'],maps['archive']['commit'])]:
 delta=git('diff','--name-only',left,right).decode().splitlines()
 require(label+'_audit_only',all(n.startswith('audit/')for n in delta),{'changed_paths':delta})
roots={'cloud','config','templates','tests','tools','docs','.github'};special={'requirements-test.txt','.gitattributes','.gitignore','AGENTS.md'}
managed={}
for name,raw in trees['candidate'].items():
 if name in special or(name.split('/')[0]in roots and Path(name).suffix in{'.py','.json','.md','.yml','.yaml'}and'__pycache__'not in Path(name).parts):
  managed[name]=h(raw.decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n').encode())
require('unchanged_source_manifest_bf19',h(canonical(managed))=='bf19f3027e5fa21ded361c4cbb1edc6264a06def00c306b72d62c52ce8af9b5a',{'managed_files':len(managed)})
pack='audit/review_packages/deployment-eof-v2/'
for name in ['protected_before.json','reconciliation_result.json']:
 require('original_in_place_'+name,trees['candidate'][pack+name]==trees['baseline'][pack+name]==trees['archive'][pack+name])
old=json.loads(trees['candidate'][pack+'protected_before.json']);require('original_bad_list_retained_122',len(old)==122)
wrong=[name for name,d in old.items()if h(trees['candidate'][name])!=d]
require('old_wrong_three_remain_truthfully_archived',wrong==['audit/data_exposure.json','config/research.json','config/workflow.json'],{'old_declared_match_count':122-len(wrong),'mismatches':wrong})
require('all122_actual_original_bytes_unchanged',all(trees['candidate'][n]==trees['baseline'][n]==trees['archive'][n]for n in old))
watched=set(old)|production_names|{'audit/deployment.json'}
require('main_287_actual_bytes_unchanged',len(watched)==287 and all(trees['candidate'][n]==trees['baseline'][n]==trees['archive'][n]for n in watched),{'files':len(watched)})
originals=S/'audit/review_packages/wr28/originals';origins=json.loads((originals/'origins.json').read_bytes())
for item in origins['files']:
 raw=git('show',item['origin_commit']+':'+item['origin_path'])
 require('original_Git_copy_'+item['archive_path'],raw==(originals/item['archive_path']).read_bytes()and h(raw)==item['raw_sha256'])
old_failure=json.loads((originals/'old_failure_result.json').read_bytes())
require('old_failure_result_still_failed',old_failure['old_checker_clean_export_exit_code']==1 and old_failure['raw_git_match_count']==119 and len(old_failure['raw_git_mismatches'])==3)
require('old_failure_stderr_retained',b'AssertionError: audit/data_exposure.json'in(originals/'old_checker_export.stderr').read_bytes())
compact=S/'audit/reviews/20261028-4a42c18-eofv2';idx=json.loads((compact/'import_index.json').read_bytes());seal=json.loads((compact/'archive_manifest.json').read_bytes())
compact_actual={p.relative_to(compact).as_posix()for p in compact.rglob('*')if p.is_file()}
require('compact_exact_sealed_file_set',compact_actual==set(seal)|{'archive_manifest.json'},{'sealed_files':len(seal),'actual_files':len(compact_actual)})
require('all_compact_raw_hashes',all(h((compact/n).read_bytes())==d for n,d in seal.items()))
zip_raw=ZIP.read_bytes();require('original_ZIP_hash_bytes',h(zip_raw)=='e7f32eba7ccebcd6f833a9954b5ca13f50ec1a762497c59ae5f8a7a93fcc1910'==idx['original_zip_sha256']and len(zip_raw)==idx['original_zip_bytes'])
with zipfile.ZipFile(ZIP)as z:
 require('original_ZIP_CRC',z.testzip()is None)
 prefix=idx['original_bundle_name']+'/';names=[i.filename for i in z.infolist()if not i.is_dir()]
 require('original_ZIP_exact_member_population',len(names)==len(set(names))==idx['original_total_files']==18686 and all(n.startswith(prefix)for n in names))
 raw_manifest=z.read(prefix+'artifact_manifest.json');manifest=json.loads(raw_manifest)
 require('original_ZIP_raw_manifest_hash',h(raw_manifest)==idx['original_artifact_manifest_sha256'])
 require('original_ZIP_exact_manifest_set',{n[len(prefix):]for n in names}==set(manifest)|{'artifact_manifest.json'})
 require('all18685_original_ZIP_raw_hashes',len(manifest)==18685 and all(h(z.read(prefix+n))==d for n,d in manifest.items()))
 source_raw=z.read(prefix+'source_git_manifest.json');old_sources=json.loads(source_raw)
 require('original_three_source_maps_hash',h(source_raw)==idx['original_source_manifest_sha256'])
 omitted_sources=set()
 for label,item in old_sources.items():
  d=item['directory']+'/';copied={n[len(d):]:v for n,v in manifest.items()if n.startswith(d)}
  require('original_source_map_'+label,copied==item['files']and len(copied)==item['count']==idx['source_trees'][label]['count'])
  omitted_sources.update(d+n for n in item['files'])
 copied_original={n[len('evidence/'):]:digest for n,digest in idx['copied_files'].items()if n.startswith('evidence/')}
 supplementary={n:d for n,d in idx['copied_files'].items()if not n.startswith('evidence/')}
 require('supplemental_user_delivery_separately_preserved',set(supplementary)=={'user_delivery.txt'}and all(h((compact/n).read_bytes())==d for n,d in supplementary.items()))
 expected_copied=set(manifest)-omitted_sources
 expected_copied.discard('source_git_manifest.json')
 require('all_original_non_source_evidence_copied',set(copied_original)==expected_copied and len(copied_original)==167)
 total_bytes=0
 for original_name,digest in copied_original.items():
  raw=z.read(prefix+original_name);total_bytes+=len(raw)
  if h(raw)!=digest or raw!=(compact/'evidence'/original_name).read_bytes():raise AssertionError(('Original copy changed',original_name))
 require('all167_compact_evidence_exact_original_bytes',total_bytes==idx['copied_original_evidence_bytes']==700596)
 require('omissions_only_three_source_trees_and_two_maps',len(omitted_sources)==idx['original_source_files_omitted']==18517 and set(idx['original_large_manifests_omitted'])=={'artifact_manifest.json','source_git_manifest.json'})
 require('entire_old_independent_report_preserved',h((compact/'evidence/formal_report.json').read_bytes())=='78a615a11c7478eed98d98a278405be9e834ab194f0a84485da30256ae064f49')
 must_keep=['developer_candidate_checker.stderr','minimal_wr28.stderr','root_confirmed_protected_hash_mismatch.json','policy_agent/supplement_first.stderr','policy_agent/supplement_first/results.json','policy_agent/supplement_corrected/results.json','policy_agent/supplement_fixture_correction.diff','bridge_agent/first/results.json','bridge_agent/corrected/results.json','bridge_agent/reviewer_helper_correction.diff','evidence_agent/first.stderr','evidence_agent/continued.stderr','evidence_agent/final/results.json','evidence_agent/native_hash_oracle_correction.diff','static_identity_first_tool_output.txt','verify_static_identity_first.py']
 require('all_first_failure_correction_rerun_evidence_retained',all(n in copied_original and (compact/'evidence'/n).is_file()for n in must_keep),{'named_critical_files':len(must_keep)})
 old_report=json.loads((compact/'evidence/formal_report.json').read_bytes())
 require('old_review_open_failure_not_rewritten',old_report['findings'][0]['id']=='WR-28'and old_report['findings'][0]['status']=='confirmed_open'and old_report['software_acceptance']['candidate_delivery_validation']=='failed_WR28'and old_report['financial_evidence']is False)
 # Independently compare all original sealed source maps to immutable Git blobs.
 old_tree_oids={};all_oids=set()
 for label,item in old_sources.items():
  listing=git('ls-tree','-rz',item['commit']);mapping={}
  for row in listing.split(b'\0'):
   if not row:continue
   meta,path=row.split(b'\t',1);mode,kind,oid=meta.split();assert kind==b'blob'and mode in{b'100644',b'100755'}
   p=path.decode();o=oid.decode();assert p not in mapping;mapping[p]=o;all_oids.add(o)
  require('original_git_tree_paths_'+label,set(mapping)==set(item['files']))
  old_tree_oids[label]=mapping
 ordered=sorted(all_oids);response=git('cat-file','--batch',input=('\n'.join(ordered)+'\n').encode());cursor=0;digests={}
 for expected_oid in ordered:
  end=response.index(b'\n',cursor);oid,kind,size=response[cursor:end].split();assert oid.decode()==expected_oid and kind==b'blob';size=int(size);start=end+1;raw=response[start:start+size];assert len(raw)==size and response[start+size:start+size+1]==b'\n';cursor=start+size+1
  assert hashlib.sha1(b'blob '+str(size).encode()+b'\0'+raw).hexdigest()==expected_oid;digests[expected_oid]=h(raw)
 require('Git_batch_fully_consumed',cursor==len(response),{'unique_blobs':len(ordered)})
 for label,item in old_sources.items():require('all_original_Git_blob_hashes_'+label,all(digests[old_tree_oids[label][n]]==d for n,d in item['files'].items()),{'files':item['count']})
 journal=trees['candidate']['audit/runtime/registry/events.jsonl'];rows=journal.splitlines(keepends=True)
 require('current48_journal_identity',len(rows)==48 and h(journal)=='ff0440eb196fc5e79be54ab0d6113630510a058313251be667fae6d064a4c71d')
 require('old46_raw_prefix_preserved',h(b''.join(rows[:46]))=='f50d4cd8195428966484230adf0fd54ccf77f796159af61df748f37a7d1101b1')
 previous=None
 for i,row in enumerate(rows,1):
  obj=json.loads(row);assert obj['sequence']==i and obj['previous_hash']==previous;unsigned={k:v for k,v in obj.items()if k!='hash'};assert obj['hash']==h(canonical(unsigned));previous=obj['hash']
 require('independent48_event_hash_chain',True)
 events=[json.loads(row)['event']for row in rows]
 require('last_events_failure_then_closed',events[-2]['kind']=='failed'and events[-2]['attempt_id']=='37dc855045e14ca49c88fd9d75f40cf7'and events[-1]['kind']=='engineering_round_closed')
 sys.path.insert(0,str(S/'cloud'))
 from qresearch.artifacts import MemoryArtifactStore
 from qresearch.registry import Registry
 store=MemoryArtifactStore();store._data.update({p.relative_to(S/'audit/runtime').as_posix():p.read_bytes()for p in (S/'audit/runtime').rglob('*')if p.is_file()});before=dict(store._data);reg=Registry(store,json.loads(store.read_bytes('registry/baseline.json')));snap=reg.snapshot();rounds=reg.engineering_rounds_snapshot()
 require('read_only_Memory_Registry_replay',store._data==before)
 usage={n:v['total']for n,v in snap['usage'].items()};require('actual_usage12_15_2',usage==dict(configurations=12,research=15,lean=2))
 require('actual_round_closed',rounds['stage2-normal-repair-round-004']['status']=='closed')
 attempt=next(a for a in snap['attempts']if a['attempt_id']=='37dc855045e14ca49c88fd9d75f40cf7');require('old_attempt_failed_not_rebound',attempt['status']=='failed')
 require('candidate3dd_configuration_not_registered','3dd0b9832dff6ce1afdee616054f93dbdbdb3de5dbcb4f7c3545c560da0ab695'not in snap['config_ids'])
 dev=json.loads(trees['candidate']['config/development.json']);cfg=json.loads(trees['candidate']['config/research.json']);ready=json.loads(trees['candidate']['audit/stage2_current_readiness.json'])
 require('all_four_declared_gates_closed',all(dev['execution'][k]is False for k in ['market_research_enabled','llm_runtime_enabled','final_test_enabled','live_trading_enabled']))
 require('stage0_7_plan_preserved',[x['id']for x in dev['stages']]==list(range(8))and trees['candidate']['config/development.json']==trees['baseline']['config/development.json'])
 require('old_LEAN_checks_orders_null',ready['current_LEAN_ledger_status']=='failed'and old_report['platform_evidence_level']['original_LEAN']['actual_orders']is None and old_report['platform_evidence_level']['original_LEAN']['actual_seven_success_checks']is None)
 require('new_policy_not_deployed_current_activity',ready['current_activity']['unchanged_source_commit']=='4a42c18f0b78bea2068d589bc12f1615712354c6'and ready['current_activity']['new_configuration_registrations']==0 and ready['new_candidate_independently_accepted']is False)
 require('full_data_and_financial_gates_not_promoted',ready['financial_numeric_catalog_count']==0 and ready['charged_certification_native_dispatch_bridge']=='not_implemented'and ready['stage2_status'].startswith('not_accepted')and ready['prior_2024_2025_exposure_preserved']is True and ready['year2026_independence']=='not_certified')
 for label,item in maps.items():require('final_raw_source_'+label,{n:h(b)for n,b in tree_bytes(ROOT/item['directory']).items()}==item['files'])
 dynamic_names={'read_only_Memory_Registry_replay','actual_usage12_15_2','actual_round_closed','old_attempt_failed_not_rebound','candidate3dd_configuration_not_registered'}
 dynamic_count=sum(x['name']in dynamic_names for x in checks)
 result={'fixed_commit':maps['candidate']['commit'],'baseline_commit':maps['baseline']['commit'],'archive_commit':maps['archive']['commit'],'checks':checks,'static_logical_checks':len(checks)-dynamic_count,'metadata_replay_checks':dynamic_count,'unit_methods':0,'new_platform_calls':0,'findings':[],'all_passed':all(x['passed']for x in checks),'production_files_compared':len(production_names),'main_protected_files':len(watched),'compact_copied_original_files':167,'compact_copied_original_bytes':total_bytes,'compact_seal_files':len(seal),'supplemental_user_delivery_files':1,'original_ZIP_manifest_entries':len(manifest),'original_total_files':len(names),'omitted_source_files':len(omitted_sources),'omitted_large_manifests':['artifact_manifest.json','source_git_manifest.json'],'original_Git_source_maps':{k:v['count']for k,v in old_sources.items()},'original_ZIP_sha256':h(zip_raw),'budget':{'events':48,'usage':usage,'round_status':'closed','journal_sha256':h(journal),'old46_sha256':h(b''.join(rows[:46])),'source_unchanged':True,'no_new_configuration_registered':True},'commands':commands,'source_guards':{k:len(trees[k])for k in trees}}
 (R/'results.json').write_text(json.dumps(result,ensure_ascii=True,indent=2)+'\n',encoding='utf-8');print(json.dumps({k:v for k,v in result.items()if k not in{'checks','commands'}},ensure_ascii=True))
