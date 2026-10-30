from pathlib import Path
import ast,hashlib,json,subprocess
R=Path(__file__).resolve().parent;S=R/'source';G=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\repo')
def h(b):return hashlib.sha256(b).hexdigest()
def canon(v):return json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
def norm(b):return b.decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n').encode()
maps=json.loads((R/'source_git_manifest.json').read_bytes());out={}
for name,item in maps.items():
 root=R/item['directory'];raw={p.relative_to(root).as_posix():p.read_bytes()for p in root.rglob('*')if p.is_file()}
 assert {p:h(b)for p,b in raw.items()}==item['files'],name
 managed={p:h(norm(b))for p,b in raw.items()if p in{'requirements-test.txt','.gitattributes','.gitignore','AGENTS.md'}or(p.split('/')[0]in{'cloud','config','templates','tests','tools','docs','.github'}and Path(p).suffix in{'.py','.json','.md','.yml','.yaml'}and'__pycache__'not in Path(p).parts)}
 sources={p[6:]:b for p,b in raw.items()if p.startswith('cloud/')and p.endswith('.py')};strict={p:h(norm(b))for p,b in sources.items()}
 records={p:{'source_sha256':h(norm(b)),'canonical_sha256':h(norm(b).rstrip(b'\n')+b'\n'),'terminal_lf_count':len(norm(b))-len(norm(b).rstrip(b'\n'))}for p,b in sources.items()}
 policy={'schema_version':2,'source_identity_policy':'utf8_sig_universal_newlines_terminal_lf_v1','files':dict(sorted(records.items()))}
 d=json.loads(raw['audit/deployment.json']);generated={n.targets[0].id:ast.literal_eval(n.value)for n in ast.parse(raw['cloud/research_config.py'].decode('utf-8-sig')).body if isinstance(n,ast.Assign)}
 impl={Path(p).name:h(norm(b))for p,b in raw.items()if p.startswith('cloud/qresearch/')and p.endswith('.py')}
 assert generated['IMPLEMENTATION_SHA256']==h(canon(impl))
 assert generated['SOURCE_SHA256']==h(canon(generated['CONFIGURATION']))
 if name!='baseline':
  assert d['source_files']==strict and d['deployment_manifest']==policy
  deployment_hash=h(canon(policy))
 else:
  assert d['source_files']==strict
  deployment_hash=h(canon(strict))
 out[name]={'commit':item['commit'],'raw_files':len(raw),'managed_source_files':len(managed),'source_manifest_hash':h(canon(managed)),'cloud_files':len(sources),'deployment_hash':deployment_hash,'implementation_hash':generated['IMPLEMENTATION_SHA256'],'configuration_hash':generated['SOURCE_SHA256'],'manifest_schema_version':2 if name!='baseline'else1}
assert out['candidate']['source_manifest_hash']=='bf19f3027e5fa21ded361c4cbb1edc6264a06def00c306b72d62c52ce8af9b5a'
assert out['candidate']['source_manifest_hash']==out['archive']['source_manifest_hash']
assert out['candidate']['deployment_hash']=='8eb1e822e2b857356fb975d60cbfc0d37053600f777e21ee79fe96da5a020243'
assert out['candidate']['configuration_hash']=='3dd0b9832dff6ce1afdee616054f93dbdbdb3de5dbcb4f7c3545c560da0ab695'
args=['git','-C',str(G),'diff','--name-only','4a42c18f0b78bea2068d589bc12f1615712354c6','1cf26578da59eebd37e138ca5d6d076991386470','--','cloud','tools','config','tests'];p=subprocess.run(args,capture_output=True);assert p.returncode==0 and p.stdout==b''
result={'identities':out,'fixed_to_archive_cloud_tools_config_tests_diff':[],'all_raw_Git_trees_unchanged':True,'v2_hash_computed_from_independent_raw_file_oracles':True,'real_QC_or_budget_calls':0,'git_command':args,'git_exit_code':p.returncode}
(R/'static_identity.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result))
