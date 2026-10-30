from pathlib import Path
import json
import sys

WORK=Path(__file__).resolve().parent
FIXED=WORK/'fixed81'
sys.path[:0]=[str(FIXED/'cloud'),str(FIXED/'tools')]
import stage2
from qresearch.engineering_receipts import backtest_observation, ReceiptParseError

attempt='bfd00f2611fd4496b9498d4597618a8e'
bridge=stage2.bridge_for_attempt(attempt)
admission=stage2.admitted_input(bridge,attempt)
before=bridge.registry.snapshot()
native=json.loads((WORK/'native_original.json').read_text(encoding='utf-8'))
try:
    backtest_observation(admission['payload'],admission['deployment'],
        '39cafa1e9b11f91b27e396b66d033a6d',native,[])
except ReceiptParseError as error:
    reason=str(error)
else:
    raise AssertionError('The accepted old parser must reject this unsupported native error carrier')
after=bridge.registry.snapshot()
assert before==after
print(json.dumps({'old_parser_rejected':True,'reason':reason,'mirror_registry_unchanged':True,
    'module_origins':{'stage2':stage2.__file__},'real_registry_access':False,'real_QC_calls':0}))
