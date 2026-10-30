"""Fingerprint-only wrapper for the independent synthetic developer probes."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
FILES=('cloud/qresearch/engineering_data.py','tools/stage2.py','tools/deployment_preflight.py',
       'tests/test_deployment_integrity_diagnostics.py','tests/test_deployment_preflight.py',
       'tests/test_wr17_engineering_recovery.py','tests/test_phase2_joint_boundaries.py')
def hashes():return {name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in FILES}
before=hashes()
result=subprocess.run([sys.executable,'-B',str(HERE/'probe.py')],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
(HERE/'final-replay.stdout.txt').write_bytes(result.stdout)
(HERE/'final-replay.stderr.txt').write_bytes(result.stderr)
after=hashes()
report={'kind':'independent_developer_synthetic_boundary_probe',
        'git_head_before_repair_commit':subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,stdout=subprocess.PIPE,check=True).stdout.decode().strip(),
        'reviewed_file_raw_sha256_before':before,'reviewed_file_raw_sha256_after':after,
        'source_bytes_stable_during_replay':before==after,'python':sys.version,
        'probe_raw_sha256':hashlib.sha256((HERE/'probe.py').read_bytes()).hexdigest(),
        'probe_method_count':16,'exit_code':result.returncode,
        'developer_probe_passed':result.returncode==0 and before==after,
        'real_provider_or_quantconnect_calls':0,'real_registry_or_budget_mutations':0,
        'tracked_files_written_by_peer':0,'gpt_work_software_acceptance':False,
        'worker_source_root_cause_confirmed':False,'phase2_acceptance':False,
        'financial_evidence':False,
        'scope':['EOF and arbitrary content/import changes strictly rejected',
          'UTF-8 BOM and universal newlines preserve the original normalization contract',
          'invalid/device/control source paths cause no source reads',
          'same single-read content determines observed diagnostic hash and no source disclosure',
          'original75 Git 25-file materialization verifies original dad57 frozen deployment',
          'v1/v2 freeze-preview, freeze, register, claim, first prepare check physical source and exact set before mutations',
          'new self-consistent local manifest cannot retarget frozen plan deployment hash',
          'v1/v2 old LEAN admission recovery ignores absent current source/deployment and foreign mutable pointer, with no protocol backfill',
          'native source listing validates both MCP mirrors, boolean IDs, duplicate identities and paths, unsafe paths',
          'input uses separate raw UTF-8 hash; source-only result does not certify worker or cloud inventory',
          'CLI success/mismatch/invalid exitcodes 0/1/2 are read-only and omit synthetic notebook output'],
        'preserved_attempts':[{'file':'probe-initial.txt','outcome':'4 fixture errors before LEAN claim because synthetic Research prerequisite was not completed; product correctly refused',
          'correction':'complete synthetic Research via original receipt parser before LEAN claim; no product change'},
         {'file':'probe-DEL-before.txt','outcome':'2 failure outcomes in one probe method; pure readback validator accepted DEL paths in returned entries and manifest',
          'correction':'controller developer aligned DEL rejection; final unchanged boundary probes pass'}]}
(HERE/'final-report.json').write_text(json.dumps(report,ensure_ascii=True,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'developer_probe_passed':report['developer_probe_passed'],'methods':16,'source_bytes_stable':before==after,'exit_code':result.returncode}))
raise SystemExit(0 if report['developer_probe_passed'] else 1)
