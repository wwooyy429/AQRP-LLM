from pathlib import Path
import copy, io, json, sys, unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from datetime import timedelta
from unittest.mock import patch
sys.dont_write_bytecode=True
import independent_notifications as F
from qresearch.artifacts import MemoryArtifactStore, decode_events
from qresearch.task_followup import TaskFollowupController,TaskFollowupError
import stage2

CASES=[]
def note(s):CASES.append(s)
def reseal(store,key,events):
    replacement=MemoryArtifactStore()
    for event in events:replacement.append_event(key,event)
    store._data[key]=replacement.read_bytes(key)

class Supplement(unittest.TestCase):
    def test_01_watch_replay_identity_and_closed_events(self):
        edits=[('project',lambda e:e[0]['context']['identity'].update(project_id=F.PROJECT+1)),
          ('attempt',lambda e:e[0]['context']['identity'].update(attempt_id='f'*32)),
          ('source',lambda e:e[0]['context']['identity'].update(source_manifest_hash='f'*64)),
          ('config',lambda e:e[0]['context']['identity'].update(config_id='f'*64)),
          ('backtest',lambda e:e[0]['context'].update(backtest_id='foreign')),
          ('deadline',lambda e:e[0]['context'].update(deadline='2026-01-20T07:00:00+00:00')),
          ('policy',lambda e:e[0]['policy'].update(max_history_pages=99)),
          ('extra-registration-key',lambda e:e[0].update(secret='unknown')),
          ('unregistered-reservation',lambda e:e.pop(0)),
          ('wrong-page',lambda e:e[1].update(page=2)),
          ('boolean-page',lambda e:e[1].update(page=True)),
          ('unknown-kind',lambda e:e[1].update(kind='arbitrary')),
          ('duplicate-reservation',lambda e:e.append(copy.deepcopy(e[1]))),
          ('fabricated-registry-finished',lambda e:e.append({'kind':'registry_finished','registry_status':'completed'}))]
        for name,edit in edits:
            store,reg,bridge,a,c=F.fixture();F.request(c,a);journal=store.read_bytes(reg.JOURNAL)
            key=c._stream(a); events=[copy.deepcopy(x['event']) for x in decode_events(store.read_bytes(key))]
            edit(events);reseal(store,key,events)
            with self.assertRaises(TaskFollowupError):c.status(a)
            with self.assertRaises(TaskFollowupError):F.request(c,a)
            self.assertEqual(store.read_bytes(reg.JOURNAL),journal);note('watch-tamper-'+name)

    def test_02_reservation_clocks_canonical_and_monotonic(self):
        invalid=['2026-01-20T06:29:59.999999+00:00','2026-01-20T14:30:00+08:00',
          '2026-01-20T06:30:00','2026-01-20T06:30:00Z',None,True]
        for stamp in invalid:
            store,reg,bridge,a,c=F.fixture(); F.request(c,a)
            key=c._stream(a); events=[copy.deepcopy(x['event']) for x in decode_events(store.read_bytes(key))]
            events[1]['reserved_at']=stamp;reseal(store,key,events)
            with self.assertRaises(TaskFollowupError):c.status(a)
            note('reservation-clock-'+repr(stamp))
        store,reg,bridge,a,c=F.fixture();F.request(c,a,F.DEAD+timedelta(seconds=10));c.record_history(a,F.history(total=2,target=False))
        with self.assertRaises(TaskFollowupError):F.request(c,a,F.DEAD+timedelta(seconds=9))
        note('next-page-cannot-backdate')

    def test_03_concurrent_terminal_read_only_one_permission(self):
        store,reg,bridge,a,c=F.fixture();F.request(c,a);c.record_history(a,F.history());before=store.read_bytes(reg.JOURNAL)
        with ThreadPoolExecutor(max_workers=8) as pool:
            answers=list(pool.map(lambda _:F.request(c,a),range(24)))
        self.assertEqual(sum(x['should_execute'] for x in answers),1)
        self.assertEqual(store.read_bytes(reg.JOURNAL),before)
        self.assertEqual(sum(x['action']=='read_completed_backtest' for x in answers),1)
        note('24-completed-read-requests-only-one-permission')

    def test_04_watch_registration_failure_preserves_original_accepted(self):
        store,reg,bridge,a,c=F.fixture();before=store.read_bytes(reg.JOURNAL);orig=store.append_event
        def append(key,event):
            if key.startswith('engineering/followup/'):raise OSError('independent watcher-write failure')
            return orig(key,event)
        with patch.object(stage2,'read_json',return_value=F.POLICY),patch.object(store,'append_event',side_effect=append):
            answer=stage2._followup_after_receipt(bridge,a)
        self.assertFalse(answer['should_execute']);self.assertEqual(answer['action'],'attention_required')
        self.assertEqual(bridge._record(a)['status'],'pending');self.assertEqual(store.read_bytes(reg.JOURNAL),before)
        self.assertNotIn('failure',json.dumps(answer));note('watch-write-failure-keeps-accepted-pending')
        repaired=c.register(a);self.assertEqual(repaired['submitted_at'],F.START.isoformat())
        self.assertEqual(repaired['deadline'],F.DEAD.isoformat());self.assertFalse(repaired['should_execute'])
        note('register-recovery-keeps-original-deadline')

    def test_05_late_native_failure_closes_unknown_without_redispatch(self):
        store,reg,bridge,a,c=F.fixture();F.request(c,a);self.assertEqual(F.request(c,a)['action'],'attention_required')
        payload=bridge.payload(a)
        terminal=F.backtest_observation(payload,F.deployment(payload),F.BACKTEST,F.native_terminal(payload,status='Runtime Error',progress=.1,error='independent'),[])
        bridge.consume_completion(a,completion_source=lambda _:terminal)
        self.assertEqual(c.sync(a)['action'],'finished');self.assertFalse(F.request(c,a)['should_execute'])
        events=[x['event'] for x in decode_events(store.read_bytes(c._stream(a)))]
        self.assertEqual(events[-1],{'kind':'registry_finished','registry_status':'failed'})
        before=store.read_bytes(c._stream(a));c.sync(a);self.assertEqual(before,store.read_bytes(c._stream(a)))
        note('late-native-delivery-closes-unknown-watch-idempotently')

    def test_06_recorded_history_idempotence_and_conflict(self):
        store,reg,bridge,a,c=F.fixture();F.request(c,a);q=F.history(total=2,target=False);c.record_history(a,q)
        key=c._stream(a);before=store.read_bytes(key);c.record_history(a,copy.deepcopy(q));self.assertEqual(before,store.read_bytes(key))
        changed=F.history(total=2,target=True)
        with self.assertRaises(TaskFollowupError):c.record_history(a,changed)
        self.assertEqual(before,store.read_bytes(key));note('same-page-idempotent-conflicting-response-rejected')
        F.request(c,a);q=F.history(page=2,total=3,target=False)
        with self.assertRaises(TaskFollowupError):c.record_history(a,q)
        self.assertEqual(F.request(c,a)['action'],'attention_required');note('pagination-change-does-not-authorize-query')

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Supplement))
    (Path(__file__).parent/'supplement_results.json').write_text(json.dumps({'methods':result.testsRun,'failures':len(result.failures),
      'errors':len(result.errors),'skips':len(result.skipped),'named_scenarios':len(CASES),'scenarios':CASES,'cloud_calls':0},indent=2),encoding='utf-8')
    raise SystemExit(0 if result.wasSuccessful() else 1)
