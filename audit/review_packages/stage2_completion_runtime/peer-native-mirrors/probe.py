"""Independent developer probes of one real duplicate native Research error."""
from pathlib import Path
from copy import deepcopy
from hashlib import sha256
import inspect,json,sys,unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'cloud'),str(ROOT/'tools'),str(ROOT/'tests')]
from qresearch.artifacts import content_hash
from qresearch.engineering_tasks import EngineeringTaskError
from qresearch import engineering_receipts as receipts
import stage2
from test_engineering_receipts import context,envelope,research_tool
from test_wr17_engineering_recovery import SyntheticFixture

PRIVATE='PEER_NATIVE_ERROR_PRIVATE_SENTINEL_641.25'
ATTEMPT='f5d05f5b964b4a1d924e4b70cd207386'
def node():return {'output_type':'error','ename':'CollectionError','evalue':PRIVATE,'traceback':['Traceback sentinel '+PRIVATE,'CollectionError sentinel '+PRIVATE]}
def read(payload,deployment):return envelope('jupyter_read_cell',{'projectId':17,'index':4},{'cellType':'code','source':receipts.research_cell_source(payload,deployment).splitlines(keepends=True)})
def mirror(native=None):
 native=node() if native is None else native
 tool=envelope('jupyter_execute_cell',{'projectId':17,'index':4},native);del tool['result']['structuredContent'];tool['result']['content']*=2;tool['result']['content']=[deepcopy(b) for b in tool['result']['content']];tool['result']['isError']=False;return tool

def bind(payload,deployment):return receipts.research_dispatch_binding(payload,deployment,read(payload,deployment))

class NativeMirrorsPeer(unittest.TestCase):
 def parse(self,tool):
  p,d=context('research');return receipts.research_observation(p,d,tool,dispatch_binding=bind(p,d))
 def test_real_packet_readonly_parse_is_one_error_and_keeps_full_original_hash(self):
  paths=[ROOT/'audit/tool_observations'/(ATTEMPT+'-research.json'),ROOT/'audit/runtime/engineering/admitted-inputs'/(ATTEMPT+'.json'),ROOT/'audit/runtime/engineering/research-dispatch'/(ATTEMPT+'.json')]
  before={str(p):sha256(p.read_bytes()).hexdigest() for p in paths};tool,admission,binding=[json.loads(p.read_bytes()) for p in paths]
  self.assertEqual(before[str(paths[0])],'14ae4a18636496737862a1ce314d90ae7fcf1abaf35f8a0f27145e0e839af8f3')
  actual_source=receipts.research_cell_source(admission['payload'],admission['deployment']);self.assertEqual(sha256(actual_source.encode()).hexdigest(),'33c34e9fbbf958f6518966cee185e947d96a4c610b7c0a942d206dec252e3340')
  result=receipts.research_observation(admission['payload'],admission['deployment'],tool,dispatch_binding=binding);raw=result['completion']['platform']['raw_receipt']
  self.assertEqual(raw['error_output_count'],1);self.assertEqual(raw['native_error_representation_count'],2);self.assertEqual(raw['traceback_line_count'],9);self.assertEqual(raw['response_sha256'],content_hash(tool['result']))
  error=json.loads(tool['result']['content'][0]['text']);self.assertNotIn(error['evalue'],json.dumps(result));self.assertNotIn(error['ename'],json.dumps(result));self.assertEqual(before,{str(p):sha256(p.read_bytes()).hexdigest() for p in paths})
 def test_equal_json_representations_hash_raw_packet_not_projection_or_error_node(self):
  t=mirror();t['result']['content'][1]['text']=json.dumps(node(),sort_keys=True,indent=3)
  raw=self.parse(t)['completion']['platform']['raw_receipt'];self.assertEqual(raw['native_error_representation_count'],2);self.assertEqual(raw['error_output_count'],1);self.assertEqual(raw['response_sha256'],content_hash(t['result']))
  projected=deepcopy(t['result']);projected['content']=projected['content'][:1];self.assertNotEqual(raw['response_sha256'],content_hash(projected));self.assertNotEqual(raw['response_sha256'],content_hash(node()));self.assertNotIn(PRIVATE,json.dumps(raw))
 def test_every_carrier_content_hint_and_hidden_value_is_checked(self):
  variants=[]
  for pos in (0,1):
   for hint in ({'audience':['assistant','reviewer']},{'priority':True},{'lastModified':'2026-02-30'},{'rows':[PRIVATE]}):
    t=mirror();t['result']['content'][pos]['annotations']=hint;variants.append(t)
   t=mirror();t['result']['content'][pos]['hidden']=PRIVATE;variants.append(t)
   t=mirror();t['result']['content'][pos]['text']=json.dumps(node()|{'evalue':'different'});variants.append(t)
  t=mirror();t['result']['_meta']={'rows':[PRIVATE]};variants.append(t)
  t=mirror();t['result']['status']='error';variants.append(t)
  for t in variants:
   with self.subTest(top=list(t['result'])),self.assertRaises(ValueError):self.parse(t)
 def test_consistent_structured_mirror_is_third_representation_and_unknown_is_not_hidden(self):
  t=mirror();t['result']['structuredContent']=node();self.assertEqual(self.parse(t)['completion']['platform']['raw_receipt']['native_error_representation_count'],3)
  for value in (node()|{'traceback':['different']},[node()],False,{},node()|{'rows':[1]}):
   bad=deepcopy(t);bad['result']['structuredContent']=value
   with self.subTest(value_type=type(value).__name__),self.assertRaises(ValueError):self.parse(bad)
 def test_two_actual_nodes_single_json_and_nested_wrappers_do_not_become_one_error(self):
  for value in ([node(),node()],{'status':'error','outputs':[node(),node()]},[node()],{'status':'error','outputs':[node()]}):
   with self.subTest(value_type=type(value).__name__),self.assertRaises(ValueError):self.parse(mirror(value))
  p,d=context('research');t=envelope('jupyter_execute_cell',{'projectId':17,'index':4},[node(),node()]);t['result']['isError']=False
  with self.assertRaises(ValueError):receipts.research_observation(p,d,t,dispatch_binding=bind(p,d))
 def test_global_native_and_success_path_semantics_never_deduplicate(self):
  self.assertEqual(sha256(inspect.getsource(receipts._native).encode()).hexdigest(),'94e3b597ca229606942fd43e05dc58db867520603517d0a7528b82436e169812')
  t=mirror();self.assertEqual(receipts._native(t['result']),[b['text'] for b in t['result']['content']])
  p,d=context('research');success=research_tool(p);success['arguments']['index']=4;self.assertEqual(self.parse(success)['completion']['platform']['status'],'completed')
  success['result']['content']*=2
  with self.assertRaises(ValueError):self.parse(success)
 def test_transport_error_printed_json_unbound_or_bool_arguments_stay_unsettled(self):
  for value in ({'success':False,'errors':['Request timed out']},{'output_type':'stream','name':'stdout','text':json.dumps(node())},{'status':'ok','outputs':[node()]}):
   with self.subTest(value=list(value)),self.assertRaises(ValueError):self.parse(mirror(value))
  p,d=context('research')
  with self.assertRaises(ValueError):receipts.research_observation(p,d,mirror())
  for change in ({'projectId':True},{'index':True},{'index':4.0},{'index':3},{'projectId':18},{'extra':PRIVATE}):
   t=mirror();t['arguments'].update(change)
   with self.subTest(change=change),self.assertRaises(ValueError):self.parse(t)
  for flag in (0,1,'false',None):
   t=mirror();t['result']['isError']=flag
   with self.subTest(flag=flag),self.assertRaises(ValueError):self.parse(t)
 def test_isolated_failure_settlement_is_once_redacted_and_unknown_packet_cannot_replace(self):
  for version in (1,2):
   with self.subTest(version=version),SyntheticFixture(version) as f:
    p,d=f.admission['payload'],f.admission['deployment'];stage2.research_dispatch(f.bridge,f.attempt,read(p,d));before=f.registry.snapshot();raw=mirror()
    result=stage2.settle_research_result(f.bridge,f.attempt,raw);self.assertEqual(result.status,'failed');after=f.registry.snapshot();saved=dict(f.store._data);self.assertEqual(after['usage'],before['usage']);self.assertNotIn(PRIVATE,str(saved))
    self.assertEqual(stage2.settle_research_result(f.bridge,f.attempt,deepcopy(raw)).status,'failed');self.assertEqual(f.registry.snapshot(),after);self.assertEqual(f.store._data,saved)
    different=deepcopy(raw);different['result']['content'][1]['text']=json.dumps(node(),indent=2)
    with self.assertRaises(EngineeringTaskError):stage2.settle_research_result(f.bridge,f.attempt,different)
    self.assertEqual(f.registry.snapshot(),after);self.assertEqual(f.store._data,saved)
    with self.assertRaises(EngineeringTaskError):f.bridge.claim('lean')

if __name__=='__main__':unittest.main(verbosity=2)
