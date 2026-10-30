"""WR-11 parser-boundary MRE; the full worker/CLI chain is separate."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(sys.argv[1])/'cloud'))
from qresearch.engineering_receipts import _native, ReceiptParseError
clean={'status':'completed','outputs':[]}
assert _native({'structuredContent':clean})==clean
conflict={'isError':False,'structuredContent':clean,'content':[{
    'type':'text','text':'{"status":"error","success":false,"outputs":[{"output_type":"error","evalue":"synthetic failure"}]}'}]}
rejected=False
try: print('accepted:',_native(conflict))
except ReceiptParseError: rejected=True
assert rejected, 'Conflicting native content must not be silently discarded'
