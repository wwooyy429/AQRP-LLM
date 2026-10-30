from pathlib import Path
from hashlib import sha256
import copy, json, sys, unittest
sys.dont_write_bytecode=True
import independent_host_api as B
from qresearch.artifacts import decode_events, canonical_json
from qresearch.engineering_receipts import backtest_observation
from unittest.mock import patch
H=B.H
SCENARIOS=[]
def scenario(x):SCENARIOS.append(x)

class Supplement(unittest.TestCase):
    def test_01_read_responses_fail_closed(self):
        edits={'wrong_project':lambda x:x['backtest'].update(projectId=B.PROJECT+1),'bool_project':lambda x:x['backtest'].update(projectId=True),'wrong_backtest':lambda x:x['backtest'].update(backtestId='other'),
          'not_completed':lambda x:x['backtest'].update(completed=False),'bad_progress':lambda x:x['backtest'].update(progress=.9),'running':lambda x:x['backtest'].update(status='In Progress...'),
          'top_unknown':lambda x:x.update(rows=['synthetic no provider']),'top_errors':lambda x:x.update(errors=['synthetic error'])}
        for name,edit in edits.items():
            store,reg,bridge,a,c=B.fixture();h=B.host(c,a);B.target_observed(h,a);q=h.prepare(a);value=B.terminal()['structuredContent'];edit(value)
            got=h.accept_response(B.message(q,B.native(value)));self.assertEqual(got['failure_code'],'invalid_native_response');self.assertEqual(h.prepare(a)['action'],'attention_required')
            self.assertEqual(reg.snapshot()['attempts'][-1]['status'],'pending');scenario(name)
    def test_02_conflicting_carriers_and_read_duplicate(self):
        store,reg,bridge,a,c=B.fixture();h=B.host(c,a);B.target_observed(h,a);q=h.prepare(a);bad=B.terminal();bad['content'][0]['text']='{"success":false,"errors":["synthetic contradictory"]}'
        self.assertEqual(h.accept_response(B.message(q,bad))['failure_code'],'invalid_native_response');scenario('read-conflicting-carriers')
        store,reg,bridge,a,c=B.fixture();h=B.host(c,a);B.target_observed(h,a);q=h.prepare(a);m=B.message(q,B.terminal());h.accept_response(m);raw=store.read_bytes(h._stream(a));self.assertEqual(h.accept_response(m)['action'],'awaiting_native_receipt');self.assertEqual(store.read_bytes(h._stream(a)),raw);scenario('read-duplicate-idempotent')
        changed=B.terminal()['structuredContent'];changed['backtest']['statistics']['Net Profit']='OTHER SYNTHETIC'
        self.assertEqual(h.accept_response(B.message(q,B.native(changed)))['failure_code'],'response_conflict');self.assertEqual(h.inspect(a)['action'],'attention_required');scenario('read-conflict-stops')
    def test_03_late_registry_completion_wins_over_unknown(self):
        store,reg,bridge,a,c=B.fixture();h=B.host(c,a);q=h.prepare(a)
        self.assertEqual(h.prepare(a)['action'],'attention_required');payload=bridge.payload(a)
        parsed=backtest_observation(payload,B.deployment(payload),B.BACKTEST,{'tool_name':H.READ,'arguments':{'projectId':B.PROJECT,'backtestId':B.BACKTEST},'result':B.terminal()},B.native_logs(payload))
        bridge.consume_completion(a,completion_source=lambda _:parsed);before=store.read_bytes(reg.JOURNAL)
        for call in (h.inspect,h.prepare):self.assertEqual(call(a)['action'],'finished');scenario('registry-terminal-dominates')
        self.assertEqual(h.command({'command':'sync','attempt_id':a})['action'],'finished')
        h.accept_response(B.message(q,B.projects()));self.assertEqual(h.prepare(a)['action'],'finished');self.assertEqual(before,store.read_bytes(reg.JOURNAL));scenario('late-original-discovery-does-not-reopen')
    def test_04_runtime_terminal_is_handoff_not_success(self):
        for form in ('native_backtest','native_error_envelope'):
            store,reg,bridge,a,c=B.fixture();h=B.host(c,a);B.discover(h,a);q=h.prepare(a);h.accept_response(B.message(q,B.history(status='Runtime Error',progress=.2)));q=h.prepare(a);before=store.read_bytes(reg.JOURNAL)
            if form=='native_backtest':
                value=B.terminal()['structuredContent'];value['backtest'].update(status='Runtime Error',completed=False,progress=.2);result=B.native(value)
            else:
                value={'success':False,'errors':['The backtest ended with a runtime error.','Independent synthetic runtime failure']};result=B.native(value);result['isError']=True
            self.assertEqual(h.accept_response(B.message(q,result))['action'],'awaiting_native_receipt');self.assertEqual(before,store.read_bytes(reg.JOURNAL));self.assertEqual(reg.snapshot()['attempts'][-1]['status'],'pending');scenario(form)
    def test_05_illegal_authority_shapes_and_foreign_grants(self):
        store,reg,bridge,a,c=B.fixture();identity={'attempt_id':a,'project_id':B.PROJECT,'backtest_id':B.BACKTEST}
        grants=[H.ReadGrant('f'*32,B.PROJECT,B.BACKTEST,'delivered_terminal_notification',B.digest('proof'))]
        auth=H.TransportAuthority('synthetic',frozenset([a]),frozenset([a]),'chat_connector',tuple(grants));self.assertFalse(auth.permits_read(identity));scenario('foreign-attempt-grant')
        values=[{'discovery_attempts':set([a])},{'history_attempts':(a,)},{'read_grants':[]},{'read_mode':'directory_completed'},{'transport_name':'bad\nname'}]
        for i,kw in enumerate(values):
            args={'transport_name':'synthetic','discovery_attempts':frozenset([a]),'history_attempts':frozenset([a]),'read_mode':'disabled','read_grants':()};args.update(kw)
            with self.assertRaises(ValueError):H.TransportAuthority(**args)
            scenario('bad-authority-shape-'+str(i))
    def test_06_binding_mutation_in_durable_events_is_rejected(self):
        store,reg,bridge,a,c=B.fixture();h=B.host(c,a);h.prepare(a);key=h._stream(a);original=decode_events(store.read_bytes(key));old=original[0]['event']
        for field,value in [('attempt_id','f'*32),('project_id',B.PROJECT+1),('backtest_id','other'),('deadline','2026-02-11T07:00:00+00:00')]:
            with self.subTest(field=field):
                events=copy.deepcopy(original);events[0]['event']['identity'][field]=value
                # API read only against independently rehashed stream; original
                # Memory store bytes are untouched and are restored by patch.
                encoded=b'';previous='0'*64
                for number,item in enumerate(events):
                    body={'sequence':number+1,'previous_hash':previous,'event':item['event']}
                    # Use actual stream serializer to produce a valid hash chain
                    # in a fresh private store, not a malformed-byte shortcut.
                extra=B.MemoryArtifactStore()
                for item in events:extra.append_event(key,item['event'])
                raw=extra.read_bytes(key);read=store.read_bytes
                with patch.object(store,'read_bytes',side_effect=lambda name:raw if name==key else read(name)):
                    with self.assertRaises(ValueError):h.prepare(a)
                scenario('bound-'+field)

if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Supplement);result=unittest.TextTestRunner(verbosity=2).run(suite)
    value={'methods':result.testsRun,'named_scenarios':len(SCENARIOS),'scenarios':SCENARIOS,'failures':[(str(t),s) for t,s in result.failures],'errors':[(str(t),s) for t,s in result.errors],'skips':[(str(t),s) for t,s in result.skipped],'actually_executed':True,'financial_evidence':False}
    (B.OUT/'supplement_results.json').write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8');raise SystemExit(not result.wasSuccessful())
