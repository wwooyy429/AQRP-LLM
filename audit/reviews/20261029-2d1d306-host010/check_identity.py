from pathlib import Path
import json,hashlib,sys
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parent;S=R/'source';M=R/'materials'
old=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-975f676-20261029\source')
def h(raw):return hashlib.sha256(raw).hexdigest()
def canon(value):return json.dumps(value,sort_keys=True,ensure_ascii=True,separators=(',',':'),allow_nan=False).encode()
def identity(root):
    files={}
    for folder in ('cloud','config','templates','tests','tools','docs','.github'):
        for p in (root/folder).rglob('*'):
            if p.is_file() and p.suffix in {'.py','.json','.md','.yml','.yaml'} and '__pycache__' not in p.parts:
                files[p.relative_to(root).as_posix()]=h(p.read_bytes().decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n').encode())
    for name in ('requirements-test.txt','.gitattributes','.gitignore','AGENTS.md'):
        files[name]=h((root/name).read_bytes().decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n').encode())
    return files
current=identity(S);prior=identity(old);material=identity(M)
assert len(current)==216 and len(prior)==213
assert h(canon(current))=='74bbefc270a6bd0d1385db9624eaa2bd600e38503f5932a88267a02a11c76a07'
assert current==material
changed=[p for p in prior if prior[p]!=current.get(p)]
assert changed==[],changed
added=sorted(set(current)-set(prior))
assert added==['docs/followup_host.md','tests/test_followup_host.py','tools/followup_host.py'],added
deployment=json.loads((S/'audit/deployment.json').read_text())
assert (S/'audit/deployment.json').read_bytes()==(old/'audit/deployment.json').read_bytes()
assert len(deployment['source_files'])==44
for p,digest in deployment['source_files'].items():assert h((S/'cloud'/p).read_bytes().decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n').encode())==digest,p
result={'source_hash':h(canon(current)),'source_files':216,'baseline_managed_files':213,'baseline_managed_changes':changed,'new_managed_files':added,'source_materials_managed_equal':True,'deployment_files':44,'deployment_manifest_hash':h(canon(deployment['deployment_manifest'])),'implementation_hash':deployment['implementation_hash'],'configuration_hash':deployment['configuration_hash'],'deployment_raw_unchanged_from975f676':True,'kind':'independent_static_raw_and_normalized_identity_recomputation_not_unit_tests'}
(R/'identity_verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False))
