"""Offline comparison of root-obtained QC readback; no platform tool calls.

Builds only an independent copy under runs/evidence_build_source. The candidate
source and current delivery evidence report are never changed.
"""
from pathlib import Path
import ast,hashlib,io,json,os,subprocess,sys,tarfile

ROOT=Path(__file__).resolve().parents[1]
OUT=Path(__file__).resolve().parent
GIT=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\repo')
PYTHON=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\venv\Scripts\python.exe')
CANDIDATE='be9442603a31481a9a71e51ca794df77650c7411'
HISTORICAL='75f24629d3b7f94ff3aa906c3ce8a2b8b9a8d3c4'
def canon(obj):return json.dumps(obj,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def normalized(b):
    text=b.decode('utf-8-sig') if isinstance(b,bytes) else b.removeprefix('\ufeff')
    return text.replace('\r\n','\n').replace('\r','\n').encode()
def gitfiles(revision):
    data=subprocess.check_output(['git','-C',str(GIT),'archive',revision])
    with tarfile.open(fileobj=io.BytesIO(data)) as tf:return {m.name:tf.extractfile(m).read() for m in tf.getmembers() if m.isfile()}
candidate,historical=gitfiles(CANDIDATE),gitfiles(HISTORICAL)
def code_manifest(files):return {p[len('cloud/'):]:sha(normalized(b)) for p,b in files.items() if p.startswith('cloud/') and p.endswith('.py')}
new_manifest,old_manifest=code_manifest(candidate),code_manifest(historical)
delivery_report=OUT/'delivery_evidence_report.json'
delivery_report_before=sha(delivery_report.read_bytes())
readback_bytes=(ROOT/'qc_source_readback.json').read_bytes()
readback=json.loads(readback_bytes)
assert readback['success'] is True
project=readback['project'];assert project['projectId']==38436695
readback_files={f['filePath']:f['content'] for f in project['files']}
assert len(readback_files)==len(project['files']) and all(p.endswith('.py') for p in readback_files)
task=readback_files.pop('_engineering_task_input.py')
observed={p:sha(normalized(text)) for p,text in readback_files.items()}
historical_differences=[p for p in sorted(set(old_manifest)|set(observed)) if old_manifest.get(p)!=observed.get(p)]
candidate_differences=[p for p in sorted(set(new_manifest)|set(observed)) if new_manifest.get(p)!=observed.get(p)]
assert len(observed)==25 and not historical_differences
tree=ast.parse(task)
assert len(tree.body)==1 and isinstance(tree.body[0],ast.Assign)
assignment=tree.body[0]
assert len(assignment.targets)==1 and isinstance(assignment.targets[0],ast.Name) and assignment.targets[0].id=='TASK_INPUT_JSON'
literal=ast.literal_eval(assignment.value);assert isinstance(literal,str)
payload=json.loads(literal);task_hash=sha(normalized(task))
admissions={p:json.loads(b) for p,b in candidate.items() if p.startswith('audit/runtime/engineering/admitted-inputs/') and p.endswith('.json')}
matches=[p for p,d in admissions.items() if d['deployment']['input_hash']==task_hash and d['payload']==payload]
assert len(matches)==1
admitted=admissions[matches[0]];identity=payload['identity']
assert identity['stage']=='lean' and identity['attempt_id']=='bfd00f2611fd4496b9498d4597618a8e'
assert admitted['deployment']['deployment_hash']==sha(canon(observed))
submission_path='audit/runtime/engineering/submissions/'+identity['attempt_id']+'.json'
submission=json.loads(candidate[submission_path])
assert submission['deployment']==admitted['deployment'] and submission['identity']==identity
report={'actually_executed':'Offline comparison only; QC readback was independently obtained by root, not fetched by this script',
    'source_readback_file':'qc_source_readback.json','source_readback_raw_sha256':sha(readback_bytes),'project_id':project['projectId'],
    'deployment_source_file_count':len(observed),'separate_task_input_file_count':1,
    'historical_source_commit':HISTORICAL,'candidate_source_commit':CANDIDATE,
    'normalization':'UTF-8-sig decoded text; CRLF/CR normalized to LF',
    'current_readback_deployment_hash':sha(canon(observed)),
    'historical_deployment_hash':sha(canon(old_manifest)),
    'candidate_local_deployment_hash':sha(canon(new_manifest)),
    'historical_differences':historical_differences,'candidate_differences':candidate_differences,
    'candidate_difference_details':[{'path':p,'cloud_sha256':observed.get(p),'candidate_sha256':new_manifest.get(p)} for p in candidate_differences],
    'task_input':{'normalized_sha256':task_hash,'inert_single_JSON_assignment':True,
        'matching_admitted_input':matches[0],'payload_equal_admitted_input':True,
        'attempt_id':identity['attempt_id'],'stage':identity['stage'],
        'external_id_from_archived_submission':submission['external_id'],
        'deployment_observation_matches_archived_submission':True,
        'source_manifest_hash':identity['source_manifest_hash'],
        'deployment_hash':identity['deployment_hash'],'input_hash_matches':True},
    'interpretation':'Current readback matches the old 75 implementation and existing LEAN input. It does not show a be944 deployment or establish historical execution/terminal status.',
    'backtest_terminal_or_logs_read':False,'platform_calls_by_this_script':0,'financial_evidence':False}
(OUT/'qc_readback_comparison.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def filesystem_hashes(directory):
    return {p.relative_to(directory).as_posix():sha(p.read_bytes()) for p in directory.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
candidate_before=filesystem_hashes(ROOT/'source')
build=ROOT/'runs/evidence_build_source'
assert not build.exists(),'Use a new evidence build-copy directory rather than overwrite prior execution evidence'
build.mkdir(parents=True)
for name,data in candidate.items():
    path=build/name
    assert path.resolve().is_relative_to(build.resolve())
    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
before=filesystem_hashes(build);records=[]
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
for iteration in (1,2):
    completed=subprocess.run([str(PYTHON),'-B','tools/research.py','build'],cwd=build,env=env,capture_output=True,text=True,encoding='utf-8')
    stdout_path=OUT/('build_'+str(iteration)+'.stdout.txt');stderr_path=OUT/('build_'+str(iteration)+'.stderr.txt')
    stdout_path.write_text(completed.stdout,encoding='utf-8');stderr_path.write_text(completed.stderr,encoding='utf-8')
    after=filesystem_hashes(build)
    changes=[p for p in sorted(set(before)|set(after)) if before.get(p)!=after.get(p)]
    records.append({'iteration':iteration,'command':[str(PYTHON),'-B','tools/research.py','build'],
        'cwd':str(build),'exit_code':completed.returncode,'stdout':completed.stdout.strip(),
        'changed_paths':changes,'source_file_count':len(after),
        'research_config_raw_sha256':after['cloud/research_config.py'],
        'deployment_manifest_raw_sha256':after['audit/deployment.json']})
    assert completed.returncode==0 and not changes
    before=after
candidate_after=filesystem_hashes(ROOT/'source')
assert candidate_before==candidate_after
build_result={'actually_executed':True,'execution_kind':'Two local configuration rebuild commands, no test methods or external calls',
    'candidate_source_commit':CANDIDATE,'independent_build_copy':str(build),'commands':records,
    'both_builds_exit_zero':True,'all_build_copy_bytes_stable':True,
    'candidate_source_unchanged':True,'budget_or_platform_operations':False,
    'normalized_deployment_hash':sha(canon(new_manifest)),
    'delivery_report_unchanged':sha(delivery_report.read_bytes())==delivery_report_before,
    'delivery_report_sha256':delivery_report_before,'financial_evidence':False}
(OUT/'build_stability.json').write_text(json.dumps(build_result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for artifact in ('qc_readback_comparison.json','build_stability.json'):
    (OUT/(artifact+'.sha256')).write_text(sha((OUT/artifact).read_bytes())+'  '+artifact+'\n',encoding='utf-8')
print(json.dumps({'cloud_vs_75_differences':historical_differences,'cloud_vs_be944_differences':candidate_differences,
    'task_input_sha256':task_hash,'task_input_matches':matches[0],
    'builds':[{'iteration':r['iteration'],'exit_code':r['exit_code'],'changed_paths':r['changed_paths']} for r in records],
    'candidate_source_unchanged':True},ensure_ascii=False,indent=2))
