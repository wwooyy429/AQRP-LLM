from pathlib import Path
import json,hashlib,ast,sys
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parent;S=R/'source';M=R/'materials'
OLD=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-2d1d306-20261029\source')
def h(raw):return hashlib.sha256(raw).hexdigest()
def canon(value):return json.dumps(value,sort_keys=True,ensure_ascii=True,separators=(',',':'),allow_nan=False).encode()
def files(root):
    result={}
    for folder in ('cloud','config','templates','tests','tools','docs','.github'):
        for p in (root/folder).rglob('*'):
            if p.is_file() and p.suffix in {'.py','.json','.md','.yml','.yaml'} and '__pycache__' not in p.parts:
                result[p.relative_to(root).as_posix()]=h(p.read_bytes().decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n').encode())
    for name in ('requirements-test.txt','.gitattributes','.gitignore','AGENTS.md'):
        result[name]=h((root/name).read_bytes().decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n').encode())
    return result
current,old,material=files(S),files(OLD),files(M)
assert len(current)==218 and len(old)==216
assert h(canon(current))=='9d0d6da95815ee77d993d823df616d575a3ec4f00f5e40e859a7858de02dad5f'
assert current==material
changed=sorted(p for p in old if old[p]!=current.get(p));added=sorted(set(current)-set(old))
assert changed==['docs/followup_host.md','tools/followup_host.py'],changed
assert added==['docs/review/wr29.md','tests/test_followup_host_entrypoints.py'],added
trees=[ast.parse((root/'tools/followup_host.py').read_text(encoding='utf-8-sig')) for root in (OLD,S)]
definitions=[{n.name:ast.dump(n,include_attributes=False) for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))} for tree in trees]
assert definitions[0]==definitions[1],'API/type/authority/defaultoff/UTC logic changed'
entry=trees[1].body[1]
assert isinstance(entry,ast.If) and ast.unparse(entry.test)=="__name__ == '__main__'"
assert isinstance(entry.body[0],ast.ImportFrom) and entry.body[0].module=='followup_host'
assert ast.unparse(entry.body[-1])=='raise SystemExit(_canonical_main())'
deployment=json.loads((S/'audit/deployment.json').read_text())
assert (S/'audit/deployment.json').read_bytes()==(OLD/'audit/deployment.json').read_bytes()
assert len(deployment['source_files'])==44
for p,digest in deployment['source_files'].items():assert h((S/'cloud'/p).read_bytes().decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n').encode())==digest,p
result={'source_hash':h(canon(current)),'managed_files':218,'baseline_managed_files':216,'changed_managed':changed,'added_managed':added,'source_materials_managed_equal':True,'all_public_function_and_class_ASTs_unchanged':True,'canonical_delegation_precedes_type_definitions':True,'AST_definitions_compared':len(definitions[0]),'deployment_files':44,'deployment_manifest_hash':h(canon(deployment['deployment_manifest'])),'configuration_hash':deployment['configuration_hash'],'implementation_hash':deployment['implementation_hash'],'deployment_raw_unchanged_from2d':True,'kind':'independent_static_identity_AST_checks_not_unit_methods'}
(R/'identity_verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False))
