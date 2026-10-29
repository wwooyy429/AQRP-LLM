from pathlib import Path
import hashlib
import json
import subprocess
import sys

root = Path.cwd()
sys.dont_write_bytecode = True
sys.path.insert(0, str(root / 'tools'))
from stages import source_manifest

manifest = source_manifest(root)
source = 'c2e63ac5f19901bd95e127069b5998452f7f9864'
mismatch = []
for name, digest in manifest['source_files'].items():
    raw = subprocess.check_output(['git', 'show', source + ':' + name], cwd=root)
    normal = raw.decode('utf-8-sig').replace('\r\n', '\n').replace('\r', '\n').encode()
    if hashlib.sha256(normal).hexdigest() != digest:
        mismatch.append(name)
paths = ['audit/current_review_status.json', 'audit/review_tracking.json',
         'audit/stage2_current_readiness.json', 'audit/current_review_package.json',
         'audit/review_handoffs/wr29.json', 'audit/review_results/host010.json']
formal_path = root.parent / 'LLM审核' / 'review-c2e63ac-20261029' / 'formal_report.json'
formal = json.loads(formal_path.read_text(encoding='utf-8-sig'))
result = {
    'kind': 'developer_auxiliary_readonly_initial_scope_snapshot',
    'new_independent_acceptance': False,
    'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
    'review_id': formal['review_id'],
    'reviewed_source_commit': source,
    'materials_commit': formal['evidence_commits']['materials'],
    'formal_report_raw_sha256': hashlib.sha256(formal_path.read_bytes()).hexdigest(),
    'source_manifest_hash': manifest['source_hash'],
    'source_files': len(manifest['source_files']),
    'source_identity_mismatch': mismatch,
    'pending_paths_raw_sha256': {
        name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in paths
    },
    'formal_findings': formal['findings'],
    'formal_WR29_status': formal['WR29_resolution']['status'],
    'stage2_accepted': False,
    'financial_evidence': False,
    'final_test_enabled': False,
    'scope': 'Only current closure metadata consistency; no production or Registry writes or cloud calls',
}
dest = root / '.git' / 'repair-work' / 'wr29-close-scope'
dest.mkdir(parents=True, exist_ok=True)
(dest / 'initial_scope_snapshot.json').write_text(
    json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8'
)
print(json.dumps(result, ensure_ascii=True))
