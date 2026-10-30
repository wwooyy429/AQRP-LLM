from pathlib import Path
import ast,hashlib,json,subprocess
R=Path(__file__).resolve().parent;G=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\repo')
def h(b):return hashlib.sha256(b).hexdigest()
def c(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def n(b):return b.decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n').encode()
maps=json.loads((R/'source_git_manifest.json').read_bytes());identities={}
for label,item in maps.items():
 root=R/item['directory'];files={p.relative_to(root).as_posix():p.read_bytes()for p in root.rglob('*')if p.is_file()};assert {p:h(b)for p,b in files.items()}==item['files'],label
 managed={p:h(n(b))for p,b in files.items()if p in{'requirements-test.txt','.gitattributes','.gitignore','AGENTS.md'}or(p.split('/')[0]in{'cloud','config','templates','tests','tools','docs','.github'}and Path(p).suffix in{'.py','.json','.md','.yml','.yaml'}and'__pycache__'not in Path(p).parts)}
 dep=json.loads(files['audit/deployment.json']);sources={p[6:]:b for p,b in files.items()if p.startswith('cloud/')and p.endswith('.py')};strict={p:h(n(b))for p,b in sources.items()};records={p:{'source_sha256':h(n(b)),'canonical_sha256':h(n(b).rstrip(b'\n')+b'\n'),'terminal_lf_count':len(n(b))-len(n(b).rstrip(b'\n'))}for p,b in sources.items()}
 assert dep['source_files']==strict and dep['deployment_manifest']['files']==records
 generated={node.targets[0].id:ast.literal_eval(node.value)for node in ast.parse(files['cloud/research_config.py'].decode()).body if isinstance(node,ast.Assign)}
 assert generated['SOURCE_SHA256']==h(c(generated['CONFIGURATION']))
 impl={Path(p).name:h(n(b))for p,b in files.items()if p.startswith('cloud/qresearch/')and p.endswith('.py')};assert generated['IMPLEMENTATION_SHA256']==h(c(impl))
 info={'commit':item['commit'],'raw_files':len(files),'managed_source_files':len(managed),'source_manifest_hash':h(c(managed)),'cloud_files':len(sources),'deployment_hash':h(c(dep['deployment_manifest'])),'implementation_hash':generated['IMPLEMENTATION_SHA256'],'configuration_hash':generated['SOURCE_SHA256']}
 assert info['source_manifest_hash']=='bf19f3027e5fa21ded361c4cbb1edc6264a06def00c306b72d62c52ce8af9b5a'
 assert info['deployment_hash']=='8eb1e822e2b857356fb975d60cbfc0d37053600f777e21ee79fe96da5a020243'
 assert info['configuration_hash']=='3dd0b9832dff6ce1afdee616054f93dbdbdb3de5dbcb4f7c3545c560da0ab695'
 identities[label]=info
commands=[]
for left,right in [('1cf26578da59eebd37e138ca5d6d076991386470','2f5591e28c0748ac42caeae7bbf3977141d031cb'),('2f5591e28c0748ac42caeae7bbf3977141d031cb','fc0ba0ae36167a74c3e6c0c2e3c0cf33c3ba220f')]:
 argv=['git','-C',str(G),'diff','--name-only',left,right,'--','cloud','config','tools','tests','docs','README.md'];p=subprocess.run(argv,capture_output=True);assert p.returncode==0 and not p.stdout;commands.append({'command':argv,'exit_code':p.returncode,'stdout':p.stdout.decode(),'stderr':p.stderr.decode()})
result={'identities':identities,'production_changes':[],'all_original_raw_Git_bytes_unchanged':True,'all_manifest_values_recomputed':True,'Git_commands':commands}
(R/'identity_verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result))
