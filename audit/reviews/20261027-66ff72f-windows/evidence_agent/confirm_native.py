"""Parse root's new native readback offline once; never reapply settlement."""
from pathlib import Path
import hashlib,json,socket,sys
R=Path(__file__).resolve().parents[1];O=Path(__file__).resolve().parent;S=R/'source';calls=[]
def denied(*a,**k):calls.append(True);raise AssertionError('Offline native confirmation only')
socket.socket.connect=denied;socket.create_connection=denied;sys.dont_write_bytecode=True;sys.path.insert(0,str(S/'cloud'))
from qresearch.engineering_receipts import backtest_observation
from qresearch.artifacts import content_hash
attempt='bfd00f2611fd4496b9498d4597618a8e';external='39cafa1e9b11f91b27e396b66d033a6d'
path=R/'qc_terminal_native.json';raw=path.read_bytes();packet=json.loads(raw)
original=json.loads((S/f'audit/tool_observations/{attempt}-terminal-runtime-error.json').read_bytes())
admitted=json.loads((S/f'audit/runtime/engineering/admitted-inputs/{attempt}.json').read_bytes())
obs=backtest_observation(admitted['payload'],admitted['deployment'],external,packet,[])
saved=json.loads((O/'parsed_observation.json').read_bytes());assert obs==saved and content_hash(obs)=='ff5002cdf15423e9a7f45a0b5b5744d89c675506ef7331df49bdec9b4f5c3233'
report={'new_root_native_wrapper':'qc_terminal_native.json','raw_sha256':hashlib.sha256(raw).hexdigest(),'root_native_readback_semantically_equals_original_saved_packet':packet==original,'observation_sha256':content_hash(obs),'observation_equals_original_saved_parse':True,
 'production_parser_calls':1,'old_Bridge_or_Registry_calls':0,'actual_registry_writes':0,'network_calls_by_this_agent':0,'software_unit_methods':0,
 'boundary':'Root independently obtained this wrapper by one bounded terminal read after project listing. This child only parsed its saved bytes offline, did not read logs or query the platform, and did not repeat settlement. No worker file/stats/order-count inference.'}
assert not calls
(O/'native_confirmation_parser.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(report,ensure_ascii=False,indent=2))
