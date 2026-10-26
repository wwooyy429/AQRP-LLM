"""Independent synthetic collection review; never imports developer test helpers."""
from pathlib import Path
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import io, json, math, multiprocessing as mp, os, sys, threading, time, traceback, unittest
from uuid import uuid4

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent / 'source'
STORE_RUN = ROOT / 'stores' / uuid4().hex
sys.path.insert(0, str(SOURCE/'cloud'))
import pandas as pd
from qresearch.artifacts import MemoryArtifactStore, FilesystemArtifactStore, canonical_json, content_hash
from qresearch.collection import (HistoricalCollectionPlan, HistoricalSnapshotCollector, CollectionError,
    CollectionInterrupted, CollectionIntegrityError, CollectionMiss)
from qresearch.quantconnect import ObjectStoreArtifactStore

CAT = {'measure':{'kind':'number','role':'independent_observation','unit':'USD','period_accessor':None},
       'covered':{'kind':'boolean','role':'coverage','unit':'boolean','period_accessor':None},
       'report_day':{'kind':'date','role':'metadata','unit':'date','period_accessor':None}}

def ts(value): return pd.Timestamp(value, tz='America/New_York')
def freeze(catalog=None, **overrides):
    raw = {'schema_version':1,'plan_id':'independent-collection','scope':'engineering',
           'source':'quantconnect_fundamental_universe','data_version':'independent-v1',
           'start':ts('2021-11-06').isoformat(),'end_exclusive':ts('2021-11-07').isoformat(),
           'timezone':'America/New_York','fields':['report_day','measure','covered'],
           'calendar_days_per_request':1,'max_batch_records':2,'max_records_per_window':5,
           'source_manifest_hash':'c'*64}
    raw.update(overrides)
    return HistoricalCollectionPlan.from_dict(raw, field_catalog=CAT if catalog is None else catalog)
def row(sid='independent-A', stamp='2021-11-06T09:17:00-04:00', number=0):
    return {'sid':sid,'snapshot_at':stamp,'values':{'measure':number,'covered':False,'report_day':None}}
def keys(store, fragment): return sorted(k for k in store._data if fragment in k)
def collector(store, source, plan=None):
    return HistoricalSnapshotCollector(store,source,freeze() if plan is None else plan,synthetic=True)

class GeneratedSource:
    def __init__(self, records=None, error_after=None, delay=0):
        self.records = [row()] if records is None else records
        self.calls=0; self.error_after=error_after; self.delay=delay; self.mutex=threading.Lock()
    def fetch(self,start,end,catalog):
        with self.mutex: self.calls += 1
        if self.delay: time.sleep(self.delay)
        for i, item in enumerate(self.records):
            if self.error_after is not None and i == self.error_after:
                raise RuntimeError('PRIVATE-SYNTHETIC-ROW-1234')
            yield deepcopy(item)
        if self.error_after == len(self.records): raise RuntimeError('PRIVATE-SYNTHETIC-ROW-1234')

class SyntheticBackend:
    """SDK-shaped byte store only, never a platform SDK."""
    def __init__(self): self.data={}; self.saves=0
    def contains_key(self,k): return k in self.data
    def read_bytes(self,k): return self.data[k]
    def save_bytes(self,k,value): self.data[k]=bytes(value); self.saves+=1; return True

class QueueSource:
    def __init__(self,q): self.q=q
    def fetch(self,start,end,catalog):
        self.q.put(('fetch',os.getpid())); time.sleep(.1); yield row()

def process_collect(store_root,q):
    try:
        result=collector(FilesystemArtifactStore(store_root,data_classification='synthetic'),QueueSource(q)).collect()
        q.put(('done',result['provider_calls'],result['window_refs']))
    except BaseException as e: q.put(('error',type(e).__name__,str(e),traceback.format_exc()))

OBS={}
class IndependentCollection(unittest.TestCase):
    def test_semantic_identity_is_immutable_and_selected_catalog_bound(self):
        base=freeze(); original=base.hash
        for key,new in [('unit','shares'),('kind','text'),('role','other'),('period_accessor','value')]:
            c=deepcopy(CAT); c['measure'][key]=new
            with self.subTest(catalog_key=key): self.assertNotEqual(original,freeze(catalog=c).hash)
        copied=base.identity(); copied['field_catalog']['measure']['unit']='mutated'; copied['plan']['fields'].clear()
        self.assertEqual(original,base.hash)
        unused=deepcopy(CAT); unused['unselected']={'kind':'text','role':'unused','unit':'code','period_accessor':None}
        self.assertEqual(original,freeze(catalog=unused,fields=['covered','report_day','measure']).hash)

    def test_calendar_partition_contiguous_through_fall_clock_change(self):
        p=freeze(start=ts('2021-11-06').isoformat(),end_exclusive=ts('2021-11-09').isoformat())
        windows=p.windows(); self.assertEqual([(b-a).total_seconds()/3600 for a,b in windows],[24,25,24])
        self.assertTrue(all(a.hour==b.hour==0 for a,b in windows))
        self.assertTrue(all(windows[i][1]==windows[i+1][0] for i in range(2)))
        for final in ['2024-01-02T00:00:00-05:00','2025-01-01T00:00:00-05:00']:
            with self.subTest(final=final),self.assertRaises(CollectionError):freeze(end_exclusive=final)

    def test_same_memory_store_six_collectors_get_one_source_dispatch(self):
        store,src=MemoryArtifactStore(),GeneratedSource(delay=.03)
        with ThreadPoolExecutor(max_workers=6) as pool:
            results=list(pool.map(lambda _:collector(store,src).collect(),range(6)))
        self.assertEqual(src.calls,1); self.assertEqual(sum(r['provider_calls'] for r in results),1)
        self.assertTrue(all(r['window_refs']==results[0]['window_refs'] for r in results))
        self.assertEqual(len(keys(store,'/windows/')),1)

    def test_separate_filesystem_instances_share_thread_lock_boundary(self):
        path=STORE_RUN/'thread-store'; src=GeneratedSource(delay=.03)
        def execute(_):return collector(FilesystemArtifactStore(path,data_classification='synthetic'),src).collect()
        with ThreadPoolExecutor(max_workers=6) as pool: results=list(pool.map(execute,range(6)))
        self.assertEqual(src.calls,1);self.assertEqual(sum(r['provider_calls'] for r in results),1)
        self.assertTrue(all(r['window_refs']==results[0]['window_refs'] for r in results))

    def test_separate_processes_share_filesystem_single_window_intent(self):
        ctx=mp.get_context('spawn');q=ctx.Queue(); path=str(STORE_RUN/'process-store')
        jobs=[ctx.Process(target=process_collect,args=(path,q)) for _ in range(4)]
        for p in jobs:p.start()
        messages=[q.get(timeout=20) for _ in range(5)]
        for p in jobs:p.join(20);self.assertEqual(p.exitcode,0)
        self.assertEqual(len([m for m in messages if m[0]=='fetch']),1)
        done=[m for m in messages if m[0]=='done'];self.assertEqual(len(done),4)
        self.assertEqual(sum(m[1] for m in done),1)
        self.assertTrue(all(m[2]==done[0][2] for m in done));OBS['process_messages']=messages

    def test_restart_readonly_consumption_reuses_bytes_and_never_needs_source(self):
        path=STORE_RUN/'restart-store';src=GeneratedSource([row('A'),row('B'),row('C',number=2.5)])
        first=collector(FilesystemArtifactStore(path,data_classification='synthetic'),src).collect()
        before={p.relative_to(path).as_posix():p.read_bytes() for p in path.rglob('*') if p.is_file()}
        restarted=collector(FilesystemArtifactStore(path,data_classification='synthetic'),None)
        receipt=restarted.collect(); records=restarted.read_window(first['window_refs'][0])
        after={p.relative_to(path).as_posix():p.read_bytes() for p in path.rglob('*') if p.is_file()}
        self.assertEqual(before,after);self.assertEqual(receipt['provider_calls'],0);self.assertEqual(len(records),3)
        self.assertEqual(src.calls,1)

    def test_stream_failure_after_persisted_batch_never_publishes_or_retries(self):
        store=MemoryArtifactStore();src=GeneratedSource([row('A'),row('B'),row('C')],error_after=2)
        with self.assertRaises(CollectionError) as caught:collector(store,src).collect()
        self.assertNotIn('PRIVATE-',str(caught.exception));self.assertEqual(src.calls,1)
        self.assertEqual(len(keys(store,'/objects/')),1);self.assertEqual(keys(store,'/windows/'),[])
        for source in [src,None,GeneratedSource()]:
            with self.subTest(source=type(source).__name__),self.assertRaises(CollectionInterrupted):
                collector(store,source).collect()
        self.assertEqual(src.calls,1)

    def test_batch_write_unknown_preserves_intent_and_does_not_retry_source(self):
        class Uncertain(MemoryArtifactStore):
            def write_once(self,key,data):
                result=super().write_once(key,data)
                if '/objects/' in key:raise IOError('PRIVATE-STORAGE-DETAIL')
                return result
        store=Uncertain();src=GeneratedSource([row('A'),row('B'),row('C')])
        with self.assertRaises(CollectionError) as caught:collector(store,src).collect()
        self.assertNotIn('PRIVATE-',str(caught.exception))
        with self.assertRaises(CollectionInterrupted):collector(store,src).collect()
        self.assertEqual(src.calls,1);self.assertEqual(len(keys(store,'/objects/')),1)

    def test_completed_manifest_unknown_write_can_be_verified_after_restart(self):
        class Uncertain(MemoryArtifactStore):
            raised=False
            def write_once(self,key,data):
                result=super().write_once(key,data)
                if '/windows/' in key and not self.raised:self.raised=True;raise IOError('PRIVATE-STORE')
                return result
        store=Uncertain();src=GeneratedSource()
        with self.assertRaises(CollectionError):collector(store,src).collect()
        recovered=collector(store,None).collect()
        self.assertEqual(recovered['provider_calls'],0);self.assertEqual(recovered['reused_windows'],1)
        self.assertEqual(src.calls,1);self.assertEqual(len(collector(store,None).read_window(recovered['window_refs'][0])),1)

    def test_cloud_readonly_store_rejects_missing_fetch_and_reuses_verified_cache(self):
        backend=SyntheticBackend(); src=GeneratedSource()
        readonly=ObjectStoreArtifactStore(backend,'independent-cloud-synthetic',read_only=True)
        with self.assertRaises(PermissionError):HistoricalSnapshotCollector(readonly,src,freeze(),synthetic=True).collect()
        self.assertEqual(src.calls,0);self.assertEqual(backend.saves,0)
        producer=ObjectStoreArtifactStore(backend,'independent-cloud-synthetic',read_only=False,single_producer=True)
        first=HistoricalSnapshotCollector(producer,src,freeze(),synthetic=True).collect();saves=backend.saves
        reader=HistoricalSnapshotCollector(readonly,None,freeze(),synthetic=True)
        self.assertEqual(reader.collect()['provider_calls'],0);self.assertEqual(len(reader.read_window(first['window_refs'][0])),1)
        self.assertEqual(backend.saves,saves);self.assertEqual(src.calls,1)

    def test_cloud_different_adapter_instances_serialize_same_namespace(self):
        backend=SyntheticBackend();src=GeneratedSource(delay=.03)
        def execute(_):
            adapter=ObjectStoreArtifactStore(backend,'parallel-synthetic',read_only=False,single_producer=True)
            return HistoricalSnapshotCollector(adapter,src,freeze(),synthetic=True).collect()
        with ThreadPoolExecutor(max_workers=5) as pool:results=list(pool.map(execute,range(5)))
        self.assertEqual(src.calls,1);self.assertEqual(sum(r['provider_calls'] for r in results),1)

    def test_cross_plan_and_cross_synthetic_refs_rejected_without_fetch(self):
        store=MemoryArtifactStore();src=GeneratedSource();reference=collector(store,src).collect()['window_refs'][0]
        variants=[freeze(plan_id='other'),freeze(data_version='other'),freeze(source_manifest_hash='d'*64),
                  freeze(max_batch_records=1),freeze(calendar_days_per_request=2),freeze(fields=['measure'])]
        changed=deepcopy(CAT);changed['measure']['unit']='shares';variants.append(freeze(catalog=changed))
        for p in variants:
            with self.subTest(plan=p.hash),self.assertRaises(CollectionIntegrityError):collector(store,None,p).read_window(reference)
        store.residency='quantconnect_cloud'
        with self.assertRaises(CollectionIntegrityError):HistoricalSnapshotCollector(store,None,freeze(),synthetic=False).read_window(reference)
        self.assertEqual(src.calls,1)

    def test_semantic_changes_get_new_namespaces_and_explicit_new_dispatches(self):
        store=MemoryArtifactStore();src=GeneratedSource();first=collector(store,src).collect()
        second=collector(store,src,freeze(data_version='new-frozen-version')).collect()
        self.assertNotEqual(first['window_refs'],second['window_refs']);self.assertEqual(src.calls,2)
        self.assertEqual(len(keys(store,'/windows/')),2)
        self.assertEqual(collector(store,None).collect()['provider_calls'],0)

    def test_missing_or_corrupt_batch_fails_entire_read_without_repair_fetch(self):
        for corruption in ['missing','byte','noncanonical']:
            with self.subTest(corruption=corruption):
                store=MemoryArtifactStore();src=GeneratedSource([row('A'),row('B'),row('C')]);r=collector(store,src).collect()
                ref=r['window_refs'][0];manifest=json.loads(store.read_bytes(ref['key']));key=manifest['batches'][1]['key']
                if corruption=='missing':del store._data[key]
                elif corruption=='byte':store._data[key]=b'broken!'
                else:store._data[key]=json.dumps(json.loads(store._data[key]),indent=2).encode()
                with self.assertRaises(CollectionIntegrityError):collector(store,None).read_window(ref)
                with self.assertRaises(CollectionIntegrityError):collector(store,src).collect()
                self.assertEqual(src.calls,1)

    def test_manifest_metadata_tamper_with_recomputed_digest_still_rejected(self):
        for key,wrong in [('record_count',True),('snapshot_count',8),('provider_calls',0),
                          ('missing_values',{'measure':0,'covered':0,'report_day':False}),
                          ('research_certified',True),('status','partial')]:
            with self.subTest(key=key):
                store=MemoryArtifactStore();r=collector(store,GeneratedSource()).collect()['window_refs'][0]
                doc=json.loads(store.read_bytes(r['key']));doc[key]=wrong;raw=canonical_json(doc);store._data[r['key']]=raw
                modified={'key':r['key'],'sha256':sha256(raw).hexdigest()}
                with self.assertRaises(CollectionIntegrityError):collector(store,None).read_window(modified)

    def test_equivalent_instants_duplicate_across_batches_leave_unfinished(self):
        records=[row('A'),row('B'),row('A',stamp='2021-11-06T13:17:00+00:00')]
        store=MemoryArtifactStore();src=GeneratedSource(records)
        with self.assertRaises(CollectionError):collector(store,src).collect()
        self.assertEqual(len(keys(store,'/objects/')),1);self.assertEqual(keys(store,'/windows/'),[])
        with self.assertRaises(CollectionInterrupted):collector(store,src).collect()
        self.assertEqual(src.calls,1)

    def test_exact_batch_window_capacity_and_excess_never_returns_partial_window(self):
        for count,expected in [(5,True),(6,False)]:
            with self.subTest(count=count):
                store=MemoryArtifactStore();src=GeneratedSource([row(str(i)) for i in range(count)])
                c=collector(store,src)
                if expected:
                    receipt=c.collect();manifest=json.loads(store.read_bytes(receipt['window_refs'][0]['key']))
                    self.assertEqual([len(json.loads(store.read_bytes(ref['key']))['records']) for ref in manifest['batches']],[2,2,1])
                    self.assertEqual(len(c.read_window(receipt['window_refs'][0])),5)
                else:
                    with self.assertRaises(CollectionError):c.collect()
                    self.assertEqual(keys(store,'/windows/'),[])
                    with self.assertRaises(CollectionInterrupted):c.collect()
                self.assertEqual(src.calls,1)

    def test_multiwindow_failure_retains_only_completed_prefix_and_blocks_resume(self):
        class SecondFails:
            calls=0
            def fetch(self,start,end,catalog):
                self.calls+=1
                if start.day==7:raise RuntimeError('PRIVATE-SECOND-DAY')
                yield row()
        store=MemoryArtifactStore();src=SecondFails();p=freeze(end_exclusive=ts('2021-11-08').isoformat())
        with self.assertRaises(CollectionError):collector(store,src,p).collect()
        self.assertEqual(len(keys(store,'/windows/')),1);self.assertEqual(len(keys(store,'/intents/')),2)
        with self.assertRaises(CollectionInterrupted):collector(store,src,p).collect()
        self.assertEqual(src.calls,2)
        key=keys(store,'/windows/')[0];ref={'key':key,'sha256':sha256(store._data[key]).hexdigest()}
        self.assertEqual(len(collector(store,None,p).read_window(ref)),1)

    def test_empty_cache_miss_and_empty_source_have_distinct_honest_receipts(self):
        store=MemoryArtifactStore()
        with self.assertRaises(CollectionMiss):collector(store,None).collect()
        self.assertEqual(store._data,{})
        src=GeneratedSource([]);r=collector(store,src).collect()
        self.assertEqual((r['provider_calls'],r['empty_windows'],r['record_count']),(1,1,0))
        self.assertEqual(collector(store,None).read_window(r['window_refs'][0]),[])
        for flag in ['full_historical_US200_certified','actual_availability_certified','research_certified','row_values_exported']:
            with self.subTest(flag=flag):self.assertIs(r[flag],False)

class CountedResult(unittest.TextTestResult):
    def __init__(self,*a,**kw):super().__init__(*a,**kw);self.subcases=0
    def addSubTest(self,test,subtest,error):self.subcases+=1;super().addSubTest(test,subtest,error)

def main():
    output=io.StringIO();r=unittest.TextTestRunner(stream=output,verbosity=2,resultclass=CountedResult).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(IndependentCollection))
    text=output.getvalue();(ROOT/'verification_output.txt').write_text(text,encoding='utf-8')
    def name(test):return getattr(test,'test_case',test).id()
    failed={name(test) for test,_ in r.failures};errored={name(test) for test,_ in r.errors}
    result={'source_commit':'fbe2454e6ea10aa59211c01f236c54bb251527be','methods':r.testsRun,
        'passed_methods':r.testsRun-len(failed|errored),'failed_methods':len(failed),'error_methods':len(errored),
        'subcases':r.subcases,'failure_records':len(r.failures),'error_records':len(r.errors),'skipped':len(r.skipped),
        'failures':[{'method':name(t),'traceback':v} for t,v in r.failures],
        'errors':[{'method':name(t),'traceback':v} for t,v in r.errors], 'observations':OBS,
        'python':sys.version,'pandas':pd.__version__,'actual_external_calls':0,'developer_helpers_imported':False,
        'command':str(Path(sys.executable))+' -B '+str(Path(__file__).resolve()),
        'scope':'independent synthetic collection behavior; no financial or actual platform evidence',
        'exit_code':0 if r.wasSuccessful() else 1}
    (ROOT/'verification_results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(text);print(json.dumps({k:result[k] for k in ['methods','passed_methods','failed_methods','error_methods','subcases','exit_code']}))
    return result['exit_code']

if __name__=='__main__':mp.freeze_support();raise SystemExit(main())
