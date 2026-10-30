"""Only add actual pre-dispatch prerequisites to old independent fixtures."""
import ast,difflib,hashlib,json,shutil
from pathlib import Path
OUT=Path(__file__).resolve().parent
old=OUT/'legacy_scripts';new=OUT/'legacy_adapted_scripts';shutil.copytree(old,new)
anchor="    admission=okay(invoke(case,['prepare','--attempt',attempt],label+'-prepare'))\n"
extra="""    from qresearch.engineering_receipts import research_cell_source
    fixed_source=research_cell_source(admission['payload'],admission['deployment'])
    fixed_read={'tool_name':'mcp__quantconnect__jupyter_read_cell',
        'arguments':{'projectId':admission['payload']['identity']['project_id'],'index':4},
        'result':{'cellType':'code','source':fixed_source.splitlines(keepends=True)}}
    fixed_path=case.parent/'independent-fixed-cell.json';dump(fixed_path,fixed_read)
    okay(invoke(case,['research-dispatch','--attempt',attempt,'--tool-file',fixed_path],label+'-fixed-dispatch'))
"""
records=[]
for relative in ('independent_recovery_support.py','compat_scripts/independent_recovery_support.py'):
    original=(old/relative).read_text(encoding='utf-8');assert original.count(anchor)==1
    changed=original.replace(anchor,anchor+extra);(new/relative).write_text(changed,encoding='utf-8')
    diff=''.join(difflib.unified_diff(original.splitlines(True),changed.splitlines(True),fromfile='original/'+relative,tofile='legal-fixture/'+relative))
    (OUT/(relative.replace('/','_')+'.diff')).write_text(diff,encoding='utf-8')
    records.append({'file':relative,'original_sha256':hashlib.sha256((old/relative).read_bytes()).hexdigest(),
        'adapted_sha256':hashlib.sha256((new/relative).read_bytes()).hexdigest(),'change':'only setup_case prerequisite pinning at the original emitted cell index4'})
recovery=OUT.parent/'recovery_agent';target=OUT/'recovery_adapted_scripts';target.mkdir()
original=(recovery/'independent_recovery.py').read_text(encoding='utf-8');assert original.count(anchor)==1
changed=original.replace(anchor,anchor+extra);(target/'independent_recovery.py').write_text(changed,encoding='utf-8')
shutil.copy2(recovery/'direct_freeze_entry.py',target/'direct_freeze_entry.py')
# Preserve unittest bodies exactly; all differences lie in fixture setup_case.
classes=lambda text:[ast.dump(item,include_attributes=False) for item in ast.parse(text).body if isinstance(item,ast.ClassDef)]
assert classes(original)==classes(changed)
(OUT/'recovery_fixture.diff').write_text(''.join(difflib.unified_diff(original.splitlines(True),changed.splitlines(True),fromfile='original/independent_recovery.py',tofile='legal-fixture/independent_recovery.py')),encoding='utf-8')
records.append({'file':'independent_recovery.py','original_sha256':hashlib.sha256((recovery/'independent_recovery.py').read_bytes()).hexdigest(),
    'adapted_sha256':hashlib.sha256((target/'independent_recovery.py').read_bytes()).hexdigest(),'all_class_AST_unchanged':True})
(OUT/'fixture_adapters.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
print(json.dumps(records))
