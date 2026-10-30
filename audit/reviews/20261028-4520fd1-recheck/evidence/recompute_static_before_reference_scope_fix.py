from pathlib import Path
import ast,hashlib,json,subprocess
R=Path(__file__).resolve().parent;S=R/'source';G=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\repo')
OLD=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-4520fd1-20261028')
def h(b):return hashlib.sha256(b).hexdigest()
def canonical(v):return json.dumps(v,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()
def normalized(b):return b.decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n').encode()
files={p.relative_to(S).as_posix():p.read_bytes()for p in S.rglob('*')if p.is_file()}
raw={n:h(b)for n,b in files.items()};assert raw==json.loads((R/'source_git_manifest.json').read_bytes())['files']
folders={'cloud','config','templates','tests','tools','docs','.github'}
special={'requirements-test.txt','.gitattributes','.gitignore','AGENTS.md'}
managed={n:h(normalized(b))for n,b in files.items()if n in special or(n.split('/')[0]in folders and Path(n).suffix in{'.py','.json','.md','.yml','.yaml'}and'__pycache__'not in Path(n).parts)}
deploy={n[len('cloud/'):]:h(normalized(b))for n,b in files.items()if n.startswith('cloud/')and n.endswith('.py')}
impl={Path(n).name:h(normalized(b))for n,b in files.items()if n.startswith('cloud/qresearch/')and n.endswith('.py')}
budget=json.loads(files['config/budget.json']);policy=dict(budget);policy.pop('usage');execution=dict(managed);execution['config/budget.json']=h(canonical(policy))
generated={n.targets[0].id:ast.literal_eval(n.value)for n in ast.parse(files['cloud/research_config.py'].decode()).body if isinstance(n,ast.Assign)}
identity={'source_manifest_hash':h(canonical(managed)),'execution_source_manifest_hash':h(canonical({'schema':'collection_execution_sources_v1','source_files':execution})),'deployment_hash':h(canonical(deploy)),'implementation_hash':h(canonical(impl)),'economic_configuration_hash':h(canonical(generated['CONFIGURATION']))}
previous=json.loads((OLD/'source_identity.json').read_bytes())['identity']['candidate']
for n,v in identity.items():assert previous[n]==v,n
assert len(managed)==169 and len(deploy)==32
assert generated['IMPLEMENTATION_SHA256']==identity['implementation_hash']
assert generated['SOURCE_SHA256']==identity['economic_configuration_hash']
assert json.loads(files['audit/deployment.json'])['source_files']==deploy
matrix=json.loads((OLD/'data_agent/system_matrix.json').read_bytes());refs=[]
for stage in matrix['stages']:
 for ref in stage['references']:
  p,line=ref.rsplit(':',1);assert files[p]==(OLD/'source'/p).read_bytes();assert len(files[p].decode('utf-8-sig').splitlines())>=int(line);refs.append(ref)
assert len(refs)==105 and len(matrix['stages'])==8
(R/'reused_stage_matrix.json').write_bytes((OLD/'data_agent/system_matrix.json').read_bytes())
git_records=[]
for args in [['rev-parse','4520fd1a4421a9b764d2bfd61e5fb5cf4b59a9c8^{tree}'],['merge-base','6a1edbf07fa8fc6cf774084094f4beacc28ff60b','4520fd1a4421a9b764d2bfd61e5fb5cf4b59a9c8'],['diff','--name-only','662ccd876b67ca0949f921a53c4c33df37cfbbf1','4520fd1a4421a9b764d2bfd61e5fb5cf4b59a9c8','--','cloud','tools','tests']]:
 argv=['git','-C',str(G),*args];p=subprocess.run(argv,capture_output=True);assert p.returncode==0;git_records.append({'command':argv,'exit_code':p.returncode,'stdout':p.stdout.decode(),'stderr':p.stderr.decode()})
assert git_records[0]['stdout'].strip()=='4719a951ddbb9f42f307478f718070b19cf941f1'
assert git_records[1]['stdout'].strip()=='6a1edbf07fa8fc6cf774084094f4beacc28ff60b'
assert git_records[2]['stdout']==''
dev=json.loads(files['config/development.json']);assert not any(dev['execution'][x]for x in ['market_research_enabled','llm_runtime_enabled','final_test_enabled','live_trading_enabled'])
exposure=json.loads(files['audit/data_exposure.json']);catalog=json.loads(files['config/source_catalog.json'])
assert not catalog['factor_fields_enabled'] and not catalog['vendor_revision_certified'] and not catalog['actual_availability_certified']
result={'reviewed_source_commit':'4520fd1a4421a9b764d2bfd61e5fb5cf4b59a9c8','raw_source_files':len(files),'managed_files':len(managed),'cloud_files':len(deploy),**identity,'generated_identity_matches':True,'all_raw_Git_bytes_unchanged':True,'runtime_cloud_tools_tests_diff':[],'reused_matrix_exact_refs_verified':105,'reused_matrix_stages':8,'reused_matrix_is_static_not_new_tests':True,'QC_calls_this_round':0,'previous_independent_live_QC_source_only_calls':35,'previous_live_readback_is_not_current_cloud_status':True,'declared_execution':dev['execution'],'source_catalog_fields':len(catalog['fields']),'data_exposure':exposure,'git_commands':git_records}
(R/'static_verification.json').write_text(json.dumps(result,ensure_ascii=True,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in result.items()if k not in ['data_exposure','git_commands']}))
