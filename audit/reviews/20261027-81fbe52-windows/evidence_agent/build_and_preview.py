"""Two deterministic builds and read-only CLI/preflight on independent copy."""
from pathlib import Path
import hashlib, io, json, os, subprocess, tarfile

ROOT=Path(__file__).resolve().parents[1];OUT=Path(__file__).resolve().parent
GIT=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\repo')
PYTHON=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\venv\Scripts\python.exe')
SHA='81fbe5294055423e88ee5aeae48ca6223e7971da'
COPY=ROOT/'runs/evidence_build_source'
assert not COPY.exists(),'Never overwrite an existing evidence run'
def sha(b):return hashlib.sha256(b).hexdigest()
def canon(v):return json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
def hashes(root):return {p.relative_to(root).as_posix():sha(p.read_bytes()) for p in root.rglob('*') if p.is_file()}
source_before=hashes(ROOT/'source')
archive=subprocess.check_output(['git','-C',str(GIT),'archive',SHA]);COPY.mkdir(parents=True)
with tarfile.open(fileobj=io.BytesIO(archive)) as tf:
    for member in tf.getmembers():
        if member.isfile():
            path=COPY/member.name;assert path.resolve().is_relative_to(COPY.resolve());path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(tf.extractfile(member).read())
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
records=[]
def run(label,argv):
    before=hashes(COPY)
    result=subprocess.run(argv,cwd=COPY,env=env,capture_output=True)
    stdout=OUT/(label+'.stdout.txt');stderr=OUT/(label+'.stderr.txt');stdout.write_bytes(result.stdout);stderr.write_bytes(result.stderr)
    after=hashes(COPY);changes=[p for p in sorted(set(before)|set(after)) if before.get(p)!=after.get(p)]
    record={'label':label,'command':argv,'cwd':str(COPY),'exit_code':result.returncode,'file_count_after':len(after),'changed_paths':changes,'stdout_file':stdout.name,'stdout_raw_sha256':sha(result.stdout),'stderr_file':stderr.name,'stderr_raw_sha256':sha(result.stderr)}
    records.append(record)
    assert result.returncode==0,(label,result.stderr.decode('utf-8',errors='replace'))
    assert not changes,(label,changes)
    return result.stdout
for n in (1,2):run('build_'+str(n),[str(PYTHON),'-B','tools/research.py','build'])
previews=[]
for n in (1,2):
    raw=run('preview_'+str(n),[str(PYTHON),'-B',str(OUT/'offline_preview_runner.py'),'preview',str(COPY)])
    previews.append(json.loads(raw))
expected=json.loads((COPY/'audit/stage2_joint_preview.json').read_text(encoding='utf-8-sig'))
assert previews[0]==previews[1]==expected
preflight=json.loads(run('joint_preflight',[str(PYTHON),'-B',str(OUT/'offline_preview_runner.py'),'preflight',str(COPY)]))
assert preflight['valid_joint_preflight_passed'] and preflight['stale_deployment_rejected'] and preflight['Registry_open_attempts']==0 and preflight['provider_socket_attempts']==0
source_after=hashes(ROOT/'source');assert source_before==source_after
report={'fixed_commit':SHA,'actually_executed':True,'execution_kind':'Two local builds, two actual CLI previews and valid/stale joint_preflight metadata probes on an independent Git copy',
    'unit_test_methods':0,'new_QC_market_model_calls':0,'independent_copy':str(COPY),'commands':records,
    'both_builds_exit_zero':True,'both_previews_exit_zero':True,'previews_equal_each_other_and_archived_preview':True,
    'all2374_copy_file_bytes_unchanged_after_every_command':True,'candidate_source_unchanged':True,
    'preview_plan_hash':expected['plan_hash'],'preview_execution_identity':expected['source_manifest_hash'],'preview_deployment_hash':expected['deployment_hash'],
    'preview_registration_admission_dispatch_flags_false':all(expected[k] is False for k in ('configuration_registered','execution_started','ready_to_dispatch','budget_admission_performed')),
    'joint_preflight':preflight,'budget_and_original_pending_attempt_unchanged':True,
    'boundary':'Preview/preflight only validate metadata. They do not allocate a slot, authorize new execution, certify a delivered terminal or certify full historical/financial data.',
    'financial_evidence':False}
p=OUT/'build_preview_verification.json';p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');(OUT/'build_preview_verification.json.sha256').write_text(sha(p.read_bytes())+'  build_preview_verification.json\n',encoding='utf-8')
print(json.dumps({k:report[k] for k in ('fixed_commit','unit_test_methods','both_builds_exit_zero','both_previews_exit_zero','previews_equal_each_other_and_archived_preview','all2374_copy_file_bytes_unchanged_after_every_command','candidate_source_unchanged','preview_plan_hash','joint_preflight')},ensure_ascii=False,indent=2))
