"""Bind the unmodified prior independent recovery suite to the current source."""
from pathlib import Path
from hashlib import sha256
import ast,json,os,subprocess,sys,time

ROOT=Path(__file__).resolve().parent
SOURCE=ROOT.parent/'source'
PREVIOUS=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-be94426-20261026')
ORIGINAL=PREVIOUS/'recovery_agent/independent_recovery.py'
SCRIPT=ROOT/'independent_recovery.py'
COMMIT='dc49f0f3037918f3ce4413665c59b164a8d6e2b7'
assert SOURCE.resolve()==Path(r'C:\Users\11638\.codex\tmp\aqrp-review-dc49f0f-20261027\source').resolve()
payload=ORIGINAL.read_bytes()
if SCRIPT.exists():assert SCRIPT.read_bytes()==payload,'Do not replace an altered replay script'
else:SCRIPT.write_bytes(payload)
assert SCRIPT.read_bytes()==payload
protected=['tools/collection_task_cli.py','tools/stage2_collection.py','cloud/qresearch/registry.py',
 'cloud/qresearch/collection_tasks.py','cloud/qresearch/engineering_tasks.py','cloud/qresearch/collection_execution.py',
 'cloud/qresearch/collection.py','cloud/qresearch/historical_source.py']
before={p.relative_to(SOURCE).as_posix():sha256(p.read_bytes()).hexdigest() for p in SOURCE.rglob('*') if p.is_file()}
comparison={rel:{'current_sha256':sha256((SOURCE/rel).read_bytes()).hexdigest(),
                 'previous_sha256':sha256((PREVIOUS/'source'/rel).read_bytes()).hexdigest(),
                 'raw_bytes_equal':(SOURCE/rel).read_bytes()==(PREVIOUS/'source'/rel).read_bytes()}
            for rel in protected}
locations={}
for rel in ['tools/collection_task_cli.py','tools/stage2_collection.py','cloud/qresearch/engineering_receipts.py']:
    for node in ast.walk(ast.parse((SOURCE/rel).read_text(encoding='utf-8-sig'))):
        if isinstance(node,ast.FunctionDef):locations[rel+':'+node.name]=[node.lineno,node.end_lineno]
command=[sys.executable,'-B',str(SCRIPT)]
started=time.monotonic()
result=subprocess.run(command,cwd=ROOT.parent,text=True,encoding='utf-8',capture_output=True,
 env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1'))
elapsed=time.monotonic()-started
(ROOT/'replay_stdout.txt').write_text(result.stdout,encoding='utf-8')
(ROOT/'replay_stderr.txt').write_text(result.stderr,encoding='utf-8')
actual=json.loads((ROOT/'first_results.json').read_text(encoding='utf-8'))
after={p.relative_to(SOURCE).as_posix():sha256(p.read_bytes()).hexdigest() for p in SOURCE.rglob('*') if p.is_file()}
record={'reviewed_source_commit':COMMIT,'actual_source_directory':str(SOURCE.resolve()),'source_files':len(before),
 'source_raw_bytes_before_after_equal':before==after,'previous_original_script':str(ORIGINAL),
 'copied_script':str(SCRIPT),'script_raw_bytes_equal_original':SCRIPT.read_bytes()==payload,
 'script_sha256':sha256(payload).hexdigest(),'historical_literal_commit_in_original_output':actual.get('commit'),
 'historical_literal_is_not_current_execution_identity':True,'command':command,'cwd':str(ROOT.parent),
 'exit_code':result.returncode,'elapsed_seconds':elapsed,'methods':actual['methods'],'passed_methods':actual['passed_methods'],
 'failed_methods':actual['failed_methods'],'error_methods':actual['error_methods'],'subcases':actual['subcases'],
 'skipped':actual['skipped'],'failure_records':actual['failure_records'],'error_records':actual['error_records'],
 'protected_module_comparison_with_be944':comparison,'source_function_locations':locations,
 'actual_external_calls':0,'author_test_fixture_imports':False,
 'scope':'Independent synthetic recovery replay through actual CLI/full copied source/Filesystem Registry; not platform or financial evidence.'}
(ROOT/'current_execution.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(record,ensure_ascii=False,indent=2))
raise SystemExit(result.returncode)
