from pathlib import Path
from hashlib import sha256
from datetime import datetime
import json, sys, unittest, copy, math
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parent
S=R/'source'
sys.path.insert(0,str(S/'cloud'))
import pandas as pd
from qresearch.contracts import DataRequest, NY, RECORD_COLUMNS
from qresearch.received_manifest import build_received_manifest
from qresearch.storage_capacity import check_capacity, StorageCapacityError

scenarios=[]
def named(label): scenarios.append(label)
def canonical(obj):return json.dumps(obj,sort_keys=True,ensure_ascii=True,separators=(',',':'),allow_nan=False).encode()

class IndependentStorageIdentity(unittest.TestCase):
    def fixture(self):
        request=DataRequest('US Equities',('open','high','low','close','volume'),('SID-A','SID-B'),datetime(2018,1,1,tzinfo=NY),datetime(2019,1,1,tzinfo=NY),'independent-v1','a'*64)
        rows=[]
        for si,sid in enumerate(request.sids):
            for fi,field in enumerate(request.fields):
                rows.append([sid,field,'2018-07-03T13:00:00-04:00','2018-07-03T13:00:00-04:00',float(10+si*10+fi),'independent-v1'])
        cached=pd.DataFrame(rows,columns=RECORD_COLUMNS)
        for c in ('event_time','available_time'):cached[c]=pd.DatetimeIndex(cached[c])
        refs=[]
        for field in request.fields:
            encoded=json.dumps([r for r in rows if r[1]==field],separators=(',',':'),allow_nan=False).encode()
            digest=sha256(encoded).hexdigest()
            refs.append({'key':'feature-cache/v1/objects/'+digest+'.json','sha256':digest})
        return request,rows,cached,{'start':'2018-07-03T00:00:00-04:00','end_exclusive':'2018-07-04T00:00:00-04:00'},refs
    def test_received_known_answer_and_order(self):
        req,rows,cached,window,refs=self.fixture()
        for reversed_input in (False,True):
            with self.subTest(reversed_input=reversed_input):
                m,meta=build_received_manifest(list(reversed(rows)) if reversed_input else rows,cached,req,window,list(reversed(refs)))
                self.assertEqual(m['actual_rowset_sha256'],sha256(canonical(rows)).hexdigest())
                self.assertEqual(m['record_count'],10)
                self.assertEqual(meta['cache_reference_count'],5)
                self.assertFalse(m['row_values_stored']);self.assertFalse(meta['new_row_objects'])
                self.assertNotIn('rows',m);self.assertEqual(m['source_refs'],sorted(refs,key=lambda x:x['key']))
                named('known_answer_order_'+str(reversed_input))
    def test_received_mutations_refuse(self):
        changes={'value':lambda r:r[0].__setitem__(4,99.0),'sid':lambda r:r[0].__setitem__(0,'OTHER'),'revision':lambda r:r[0].__setitem__(5,'other'),'naive_time':lambda r:r[0].__setitem__(2,'2018-07-03T13:00:00'),'future_availability':lambda r:r[0].__setitem__(3,'2024-01-01T00:00:00-05:00'),'inexact_integer':lambda r:r[0].__setitem__(4,2**53+1),'nan':lambda r:r[0].__setitem__(4,float('nan')),'bool':lambda r:r[0].__setitem__(4,True),'duplicate':lambda r:r.append(copy.deepcopy(r[0]))}
        for label,change in changes.items():
            with self.subTest(case=label):
                req,rows,cached,window,refs=self.fixture();change(rows)
                with self.assertRaises(ValueError):build_received_manifest(rows,cached,req,window,refs)
                named('received_reject_'+label)
    def test_cache_reference_and_outside_window_ambiguity(self):
        for label in ('foreign_hash','missing_reference','duplicate_reference','extra_reference','outside_duplicate'):
            with self.subTest(case=label):
                req,rows,cached,window,refs=self.fixture()
                if label=='foreign_hash':refs[0]={'key':'feature-cache/v1/objects/'+'b'*64+'.json','sha256':'b'*64}
                elif label=='missing_reference':refs.pop()
                elif label=='duplicate_reference':refs[0]=refs[1]
                elif label=='extra_reference':refs.append(refs[0])
                else:
                    extra=cached.iloc[[0]].copy();extra['event_time']=pd.DatetimeIndex(['2018-07-02T13:00:00-04:00']);extra['available_time']=extra['event_time'];cached=pd.concat([cached,extra,extra],ignore_index=True)
                with self.assertRaises(ValueError):build_received_manifest(rows,cached,req,window,refs)
                named('cache_reference_reject_'+label)
    def test_capacity_exact_boundaries(self):
        snapshot={'max_size_bytes':100,'max_files':10,'used_size_bytes':70,'used_files':6}
        got=check_capacity(snapshot,20,3,reserve_bytes=10,reserve_files=1)
        self.assertEqual((got['remaining_bytes_after_reservation'],got['remaining_files_after_reservation']),(0,0));named('exact_capacity')
        for args,code in [((21,3),'byte_capacity_insufficient'),((20,4),'file_capacity_insufficient')]:
            with self.subTest(args=args):
                with self.assertRaises(StorageCapacityError) as caught:check_capacity(snapshot,*args,reserve_bytes=10,reserve_files=1)
                self.assertEqual(caught.exception.failure_code,code);named('capacity_'+code)
        for bad in (True,-1,1.5,float('inf')):
            with self.subTest(bad=bad):
                with self.assertRaises(StorageCapacityError):check_capacity(snapshot,bad,0)
                named('capacity_bad_'+repr(bad))
    def test_identity_independently_rebuilt(self):
        records={}
        for folder in ('cloud','config','templates','tests','tools','docs','.github'):
            for p in (S/folder).rglob('*'):
                if p.is_file() and p.suffix in {'.py','.json','.md','.yml','.yaml'} and '__pycache__' not in p.parts:
                    raw=p.read_bytes().decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n').encode('utf-8');records[p.relative_to(S).as_posix()]=sha256(raw).hexdigest()
        for name in ('requirements-test.txt','.gitattributes','.gitignore','AGENTS.md'):
            raw=(S/name).read_bytes().decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n').encode();records[name]=sha256(raw).hexdigest()
        self.assertEqual(len(records),213)
        self.assertEqual(sha256(canonical(records)).hexdigest(),'d5a5ca0b1426c4333061932e280de08976762c801e6e26ff9c33cdcc74f2ef01');named('source_identity_213')
        maps=json.loads((R/'source_git_manifest.json').read_text())
        self.assertTrue(all((R/'materials'/p).read_bytes()==(S/p).read_bytes() for p in records));named('source_materials_same_managed_raw_bytes')
        deployment=json.loads((S/'audit/deployment.json').read_text())
        for path,digest in deployment['source_files'].items():
            raw=(S/'cloud'/path).read_bytes().decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n').encode()
            self.assertEqual(sha256(raw).hexdigest(),digest,path)
        named('deployment_source_map')
        (R/'independent_identity.json').write_text(json.dumps({'source_manifest_hash':sha256(canonical(records)).hexdigest(),'source_files':len(records),'deployment_files':len(deployment['source_files']),'deployment_hash':sha256(canonical(deployment['deployment_manifest'])).hexdigest(),'implementation_hash':deployment['implementation_hash'],'configuration_hash':deployment['configuration_hash']},indent=2))

if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(IndependentStorageIdentity)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    report={'methods':result.testsRun,'named_scenarios':len(scenarios),'scenarios':scenarios,'failures':[(str(t),s) for t,s in result.failures],'errors':[(str(t),s) for t,s in result.errors],'skips':[(str(t),s) for t,s in result.skipped],'actually_executed':True,'financial_evidence':False}
    (R/'independent_storage_identity_result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    sys.exit(not result.wasSuccessful())
