from pathlib import Path
import ast
import hashlib
import json
import subprocess
import sys
import traceback

ROOT=Path(__file__).resolve().parents[3]
WORK=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'cloud'))
from qresearch.artifacts import content_hash
from qresearch.engineering_data import verify_deployment
COMMIT='75f24629d3b7f94ff3aa906c3ce8a2b8b9a8d3c4'
def blob(p):return subprocess.check_output(['git','show',COMMIT+':'+p],cwd=ROOT)
def sha(raw):return hashlib.sha256(raw).hexdigest()
source_old=blob('cloud/qresearch/engineering_data.py').decode('utf-8-sig')
source_current=(ROOT/'cloud/qresearch/engineering_data.py').read_text(encoding='utf-8-sig')
def function(text):return ast.get_source_segment(text,next(x for x in ast.parse(text).body if isinstance(x,ast.FunctionDef) and x.name=='verify_deployment'))
assert function(source_old)==function(source_current),'Reproduction must use the identical frozen verifier'
admission=json.loads((ROOT/'audit/runtime/engineering/admitted-inputs/bfd00f2611fd4496b9498d4597618a8e.json').read_bytes())
manifest=admission['payload']['deployment_manifest']
original=WORK/'source75-original'
transformed=WORK/'source75-import-emulation'
assert not original.exists() and not transformed.exists(),'Preserve earlier runs'
changed=[]
for name,expected in sorted(manifest.items()):
    raw=blob('cloud/'+name)
    text=raw.decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n')
    assert sha(text.encode('utf-8'))==expected
    has_import=any((isinstance(n,ast.ImportFrom) and n.module=='AlgorithmImports')
        or (isinstance(n,ast.Import) and any(a.name=='AlgorithmImports' for a in n.names)) for n in ast.walk(ast.parse(text)))
    modified=text if has_import else 'from AlgorithmImports import *\n'+text
    for folder,data in ((original,text),(transformed,modified)):
        path=folder/name; path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(data.encode('utf-8'))
    if modified!=text:changed.append({'path':name,'expected_sha256':expected,'emulated_runtime_sha256':sha(modified.encode('utf-8'))})
baseline=verify_deployment(manifest,content_hash(manifest),source_root=original)
try:
    verify_deployment(manifest,content_hash(manifest),source_root=transformed)
except ValueError as exc:
    assert str(exc)=='Cloud implementation differs from the frozen deployment'
    error={'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()}
else:raise AssertionError('Documented import transformation did not reproduce failure')
report={'kind':'synthetic_offline_emulation_not_actual_worker_evidence',
    'source_commit':COMMIT,'verifier_function_matches_frozen75':True,
    'baseline_verified_manifest_hash':baseline,'changed_files':changed,'changed_file_count':len(changed),
    'first_sorted_mismatch':changed[0]['path'],'failure':error,
    'assumed_platform_rule':'Prefix exact from AlgorithmImports import * LF only if no AST import of that module anywhere',
    'assumption_not_confirmed_from_actual_backtest_files':True,'actual_QC_calls':0,'actual_Research_or_LEAN_executions':0,
    'tracked_files_modified':False,'financial_evidence':False}
(WORK/'documented_import_emulation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:report[k] for k in ('kind','verifier_function_matches_frozen75','changed_file_count','first_sorted_mismatch','assumption_not_confirmed_from_actual_backtest_files')}))
