"""Parse saved native tool response with fixed current production parser; offline."""
from pathlib import Path
import copy,hashlib,json,socket,sys
R=Path(__file__).resolve().parents[1];O=Path(__file__).resolve().parent;S=R/'source';socket_attempts=[]
def denied(*a,**k):socket_attempts.append(True);raise AssertionError('No network in terminal evidence replay')
socket.socket.connect=denied;socket.create_connection=denied;sys.dont_write_bytecode=True;sys.path.insert(0,str(S/'cloud'))
import qresearch.engineering_receipts as receipts
from qresearch.artifacts import canonical_json,content_hash
attempt='bfd00f2611fd4496b9498d4597618a8e';external='39cafa1e9b11f91b27e396b66d033a6d'
p=S/'audit/tool_observations'/f'{attempt}-terminal-runtime-error.json';raw=p.read_bytes();packet=json.loads(raw)
admitted=json.loads((S/f'audit/runtime/engineering/admitted-inputs/{attempt}.json').read_bytes())
assert hashlib.sha256(raw).hexdigest()=='867148e882d39a024d12d68a01803ba80c282f05b872f16616dfded53c7eea27'
assert packet['tool_name']=='mcp__quantconnect__read_backtest' and packet['arguments']=={'projectId':38436695,'backtestId':external}
assert packet['result']['isError'] is True and packet['result']['structuredContent']==json.loads(packet['result']['content'][0]['text'])
assert packet['result']['structuredContent']['success'] is False and packet['result']['structuredContent']['errors'][0]=='The backtest ended with a runtime error.'
original=copy.deepcopy(packet)
observed=receipts.backtest_runtime_failure(admitted['payload'],admitted['deployment'],external,packet)
assert observed==receipts.backtest_observation(admitted['payload'],admitted['deployment'],external,packet,[])
encoded=canonical_json(observed);assert packet==original and p.read_bytes()==raw
assert content_hash(observed)=='ff5002cdf15423e9a7f45a0b5b5744d89c675506ef7331df49bdec9b4f5c3233'
assert b'Cloud implementation differs' not in encoded
assert not {'orders_count','progress','completed','status'}&set(observed['platform']['raw_receipt'])
assert observed['platform']['raw_receipt']['response_sha256']==content_hash(packet['result'])
assert observed['platform']['raw_receipt']['arguments']==packet['arguments']
(O/'parsed_observation.json').write_bytes(encoded)
report={'fixed_parser_commit':'66ff72ffaaff8c91c008898e6527c91131176c2a','native_original_raw_sha256':hashlib.sha256(raw).hexdigest(),'parser_module':receipts.__file__,'parser_raw_sha256':hashlib.sha256(Path(receipts.__file__).read_bytes()).hexdigest(),'observation_sha256':content_hash(observed),'observation':observed,
 'production_parser_calls':2,'direct_runtime_failure_calls':1,'generic_backtest_observation_calls':1,'software_unit_methods':0,'provider_socket_attempts':len(socket_attempts),'real_platform_calls':0,'raw_packet_changed':False,
 'boundary':'Archived native tool wrapper, not a new platform read. No success/zero-orders/progress/completed inference. Diagnostic text stays in the archived original, outside shared ledger.'}
assert not socket_attempts
(O/'parser_replay.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(report,ensure_ascii=False,indent=2))
