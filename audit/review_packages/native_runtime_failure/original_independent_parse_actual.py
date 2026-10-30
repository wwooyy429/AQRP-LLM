from pathlib import Path
import hashlib
import json
import sys

ROOT=Path(__file__).resolve().parents[3]
WORK=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'cloud'))
from qresearch.artifacts import canonical_json, content_hash
import qresearch.engineering_receipts as receipts

original=(WORK/'native_original.json').read_bytes()
assert hashlib.sha256(original).hexdigest()=='867148e882d39a024d12d68a01803ba80c282f05b872f16616dfded53c7eea27'
admitted=json.loads((WORK/'fixed81/audit/runtime/engineering/admitted-inputs/bfd00f2611fd4496b9498d4597618a8e.json').read_text(encoding='utf-8'))
packet=json.loads(original)
observed=receipts.backtest_runtime_failure(admitted['payload'],admitted['deployment'],
    '39cafa1e9b11f91b27e396b66d033a6d',packet)
assert observed==receipts.backtest_observation(admitted['payload'],admitted['deployment'],
    '39cafa1e9b11f91b27e396b66d033a6d',packet,[])
assert (WORK/'native_original.json').read_bytes()==original
encoded=canonical_json(observed)
assert b'Cloud implementation differs' not in encoded
assert not {'orders_count','progress','completed','status'} & set(observed['platform']['raw_receipt'])
(WORK/'parsed_observation.json').write_bytes(encoded)
report={'native_original_raw_sha256':hashlib.sha256(original).hexdigest(),
    'original_packet_unchanged':True,'parser_module':receipts.__file__,
    'parser_raw_sha256':hashlib.sha256(Path(receipts.__file__).read_bytes()).hexdigest(),
    'observation_sha256':content_hash(observed),'observation':observed,
    'raw_diagnostics_not_stored_in_observation':True,'orders_progress_completion_not_inferred':True,
    'real_registry_writes':0,'real_QC_calls':0,'adapter_independently_accepted':False}
(WORK/'actual_parser_report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report))
