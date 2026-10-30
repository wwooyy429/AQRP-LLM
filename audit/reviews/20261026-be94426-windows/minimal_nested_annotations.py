"""WR-13 extractor boundary; full valid-report chain is separately archived."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(sys.argv[1])/'cloud'))
from qresearch.engineering_receipts import _native,_research_stdout,ReceiptParseError
marker='AQRP_ENGINEERING_JSON e30='
clean={'type':'text','text':marker}
assert _research_stdout(_native({'structuredContent':{'content':[clean]}}))=='e30='
hidden=dict(clean,annotations={'rows':[{'sid':'SYNTHETIC-SID','close':123.45}]})
native={'content':[hidden],'status':'completed','success':True}
result={'structuredContent':native,'content':[{'type':'text','text':json.dumps(native)}]}
rejected=False
try: print('accepted marker:',_research_stdout(_native(result)))
except ReceiptParseError: rejected=True
assert rejected,'Nested unregistered row annotations must not be silently ignored'
