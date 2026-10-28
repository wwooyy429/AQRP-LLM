"""Read-only reproducer: fail when frozen protected hashes differ from Git bytes."""
import argparse,hashlib,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);a=p.parse_args()
root=a.source.resolve()
expected=json.loads((root/'audit/review_packages/deployment-eof-v2/protected_before.json').read_bytes())
failures=[]
for name,wanted in expected.items():
 raw=(root/name).read_bytes();actual=hashlib.sha256(raw).hexdigest()
 if actual!=wanted:
  failures.append({'path':name,'expected':wanted,'actual_Git_bytes':actual,
    'matches_hypothetical_CRLF_bytes':hashlib.sha256(raw.replace(b'\n',b'\r\n')).hexdigest()==wanted})
print(json.dumps({'protected':len(expected),'matching':len(expected)-len(failures),'failures':failures}))
raise SystemExit(1 if failures else 0)
