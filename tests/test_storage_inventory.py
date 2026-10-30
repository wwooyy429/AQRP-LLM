"""Synthetic read-only inventory known answers; never contact QuantConnect."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'cloud'))
from qresearch.storage_inventory import LIMITS, run_inventory, validate_policy, validate_report

PREFIX='aqrp/engineering/v2/'
PRIVATE='PRIVATE-LICENSED-ROW-MUST-NOT-LEAVE-8831'
IDENTITY={'project_id':77,'attempt_id':'a'*32,'config_id':'b'*64,'plan_hash':'c'*64,
          'stage':'research','worker_sha256':'d'*64}

def encode(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def digest(value):return sha256(encode(value)).hexdigest()
def policy(keys=(),**changes):return {'schema_version':1,'metadata_keys':list(keys),**LIMITS,**changes}


class Signal:
    def __init__(self):self.handlers=[];self.fail_remove=False
    def __iadd__(self,h):self.handlers.append(h);return self
    def __isub__(self,h):
        self.handlers.remove(h)
        if self.fail_remove:raise RuntimeError(PRIVATE)
        return self
    def emit(self):
        for h in self.handlers:h(self,object())


class Store:
    def __init__(self,root,objects,*,maximum=100000,max_files=1000):
        self.root=root;self.max_size=maximum;self.max_files=max_files;self.error_raised=Signal()
        self.paths={};self.read_calls=[];self.path_calls=[];self.contains_calls=[];self.write_calls=[]
        self.key_passes=0;self.key_hook=None;self.contains_hook=None;self.path_hook=None;self.read_hook=None
        for index,(key,raw) in enumerate(objects.items()):
            path=root/str(index);path.write_bytes(raw);self.paths[key]=path
    @property
    def keys(self):
        self.key_passes+=1
        return self.key_hook(self) if self.key_hook else list(self.paths)
    def __iter__(self):raise AssertionError('Must not iterate byte values')
    def contains_key(self,key):
        self.contains_calls.append(key)
        return self.contains_hook(self,key) if self.contains_hook else key in self.paths
    def get_file_path(self,key):
        self.path_calls.append(key)
        if self.path_hook:self.path_hook(self,key)
        assert key in self.paths,'Never register a nonexistent SDK key'
        return str(self.paths[key])
    def read_bytes(self,key):
        self.read_calls.append(key)
        if self.read_hook:return self.read_hook(self,key)
        return self.paths[key].read_bytes()
    def save_bytes(self,*args):self.write_calls.append('save');raise AssertionError('No write')
    def delete(self,*args):self.write_calls.append('delete');raise AssertionError('No delete')
    def clear(self,*args):self.write_calls.append('clear');raise AssertionError('No clear')


def historical(*,year=2018,version=1,batches=1,window_extra=None,payload_extra=None,end_exclusive=None):
    stamp=f'{year}-01-02T00:00:00-05:00';end=end_exclusive or f'{year}-01-03T00:00:00-05:00'
    window={'start':stamp,'end_exclusive':end}
    plan_identity={'plan':{'scope':'engineering','start':stamp,'end_exclusive':end},'field_catalog':{}}
    plan_hash=digest(plan_identity)
    identity={'plan_hash':plan_hash,'synthetic':True,'window':window}
    raw_objects={};refs=[]
    for index in range(batches):
        value={'schema_version':version,**identity,'batch_index':index,'records':[
            {'sid':'SYNTHETIC','snapshot_at':stamp,'values':{'private':PRIVATE,'number':12.5}}]}
        if payload_extra:value.update(payload_extra)
        raw=encode(value);token=sha256(raw).hexdigest();relative=f'historical-snapshots/v{version}/objects/{token}.json'
        raw_objects[PREFIX+relative]=raw;refs.append({'key':relative,'sha256':token})
    value={'schema_version':version,**identity,'status':'completed','plan_identity':plan_identity,
        'batches':refs,'record_count':batches,'snapshot_count':1,'unique_sid_count':1,'missing_values':{},'provider_calls':1,
        'full_historical_US200_certified':False,'actual_availability_certified':False,
        'research_certified':False,'row_values_exported':False}
    if version==2:value.update(observation_policy='retain_source_occurrences',duplicate_projection_records=0,conflicting_projection_records=0)
    if window_extra:value.update(window_extra)
    key=PREFIX+f'historical-snapshots/v{version}/windows/{digest(identity)}.json'
    raw_objects[key]=encode(value)
    intent=PREFIX+f'historical-snapshots/v{version}/intents/{digest(identity)}.json'
    raw_objects[intent]=encode({'schema_version':version,**identity})
    return raw_objects,key,intent,refs


def feature(*,year=2018):
    request={'dataset':'US Equities','fields':['close'],'sids':['SYNTHETIC'],'start':f'{year}-01-01T00:00:00-05:00',
        'end':f'{year+1}-01-01T00:00:00-05:00','data_version':'synthetic-v1','universe_hash':'a'*64,
        'normalization':'raw','timezone':'America/New_York'}
    value=[['SYNTHETIC','close',f'{year}-01-02T00:00:00-05:00',f'{year}-01-03T00:00:00-05:00',PRIVATE,'original']]
    raw=encode(value);token=sha256(raw).hexdigest();payload='feature-cache/v1/objects/'+token+'.json'
    key=PREFIX+'feature-cache/v1/manifests/'+digest(request)+'.json'
    manifest={'request':request,'payload':payload,'sha256':token,'rows':1,'provenance':{'synthetic':True},'status':'complete'}
    return {key:encode(manifest),PREFIX+payload:raw},key


class StorageInventoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
    def store(self,objects,**kwargs):return Store(self.root,objects,**kwargs)
    def run_audit(self,native,plan=None,**kwargs):
        result=run_inventory(native,policy() if plan is None else plan,IDENTITY,**kwargs)
        self.assertEqual(native.write_calls,[])
        self.assertNotIn(PRIVATE,json.dumps(result))
        self.assertFalse(result['retention']['global_reference_closure'])
        self.assertFalse(result['retention']['safe_deletion_authorized'])
        self.assertEqual(result['retention']['confirmed_reclaimable_bytes'],0)
        self.assertIsNone(result['retention']['potential_reclaimable_bytes'])
        self.assertTrue(all(o['deletion_authorized'] is False for o in result['objects']))
        return result
    def test_unknown_content_is_never_read_and_capacity_is_unique_sum(self):
        native=self.store({'unknown/private.bin':PRIVATE.encode(),'other/object':b'abc'})
        result=self.run_audit(native)
        self.assertEqual(result['status'],'completed')
        self.assertEqual(result['capacity_before']['used_size_bytes'],len(PRIVATE.encode())+3)
        self.assertEqual(result['capacity_before']['used_files'],2)
        self.assertEqual(result['read_summary']['metadata_passes'],2)
        self.assertEqual(native.read_calls,[])
        self.assertEqual(len(native.path_calls),4)
        self.assertEqual(native.error_raised.handlers,[])
    def test_exact_byte_envelope_boundary_has_no_implicit_write(self):
        for extra,expected in [(73727,False),(73728,True),(73729,True)]:
            native=self.store({'x':b'a'},maximum=1+extra)
            result=self.run_audit(native)
            self.assertIs(result['capacity_before']['lean_byte_envelope_sufficient'],expected)
            self.assertEqual(result['capacity_before']['lean_required_bytes'],73728)
    def test_empty_store_is_a_complete_zero_usage_observation(self):
        result=self.run_audit(self.store({}))
        self.assertEqual(result['capacity_before']['used_size_bytes'],0)
        self.assertEqual(result['capacity_before']['used_files'],0)
        self.assertEqual(result['objects'],[])
    def test_invalid_policy_fails_before_sdk_access(self):
        class Untouchable:
            @property
            def max_size(self):raise AssertionError('No SDK on invalid policy')
        for name,bad in [('max_keys',True),('max_keys',1001),('max_seconds',181),('max_report_bytes',100),
                         ('metadata_keys',['foreign/windows/'+'a'*64+'.json']),('metadata_keys',['aqrp/engineering/v2/historical-snapshots/v1/objects/'+'a'*64+'.json'])]:
            with self.subTest(name=name,bad=bad),self.assertRaises(ValueError):
                run_inventory(Untouchable(),policy(**{name:bad}),IDENTITY)
    def test_duplicate_or_malformed_keys_fail_closed(self):
        for keys in [['x','x'],['x','../unsafe'],['x',None]]:
            native=self.store({'x':b'a'});native.key_hook=lambda store,values=keys:values
            with self.subTest(keys=keys):
                result=self.run_audit(native)
                self.assertEqual(result['status'],'failed')
                self.assertIn('duplicate_or_invalid_key',result['failure_codes'])
    def test_missing_key_does_not_call_get_file_path(self):
        native=self.store({'x':b'a'});native.contains_hook=lambda store,key:False
        result=self.run_audit(native)
        self.assertEqual(result['status'],'failed');self.assertEqual(native.path_calls,[])
    def test_key_count_bound_stops_enumeration(self):
        native=self.store({'a':b'a','b':b'b'})
        result=self.run_audit(native,policy(max_keys=1))
        self.assertEqual(result['failure_codes'],['key_limit'])
        self.assertEqual(native.path_calls,['a'])
    def test_changed_size_between_passes_is_not_a_stable_snapshot(self):
        native=self.store({'a':b'a'})
        def change(store):
            if store.key_passes==2:store.paths['a'].write_bytes(b'changed')
            return list(store.paths)
        native.key_hook=change;result=self.run_audit(native)
        self.assertEqual(result['status'],'failed')
        self.assertIn('metadata_changed',result['failure_codes'])
        self.assertFalse(result['metadata_observation_stable'])
    def test_sdk_event_and_exception_are_sanitized(self):
        for event in (True,False):
            native=self.store({'a':b'a'})
            def bad(store,key):
                if event:store.error_raised.emit()
                else:raise RuntimeError(PRIVATE)
            native.path_hook=bad
            with self.subTest(event=event):
                result=self.run_audit(native)
                self.assertEqual(result['status'],'failed')
                self.assertFalse(result['metadata_observation_stable'])
    def test_event_unsubscribe_failure_invalidates_success(self):
        native=self.store({});native.error_raised.fail_remove=True
        result=self.run_audit(native)
        self.assertEqual(result['status'],'failed');self.assertEqual(result['failure_codes'],['sdk_error'])
        self.assertFalse(result['metadata_observation_stable'])
    def test_cooperative_time_bound_fails_without_native_exception(self):
        native=self.store({'a':b'a'});ticks=iter([0,181])
        result=self.run_audit(native,clock=lambda:next(ticks))
        self.assertEqual(result['failure_codes'],['time_limit']);self.assertEqual(native.path_calls,[])
    def test_known_historical_schema_links_and_hashes_payload_once(self):
        for version in (1,2):
            objects,key,intent,refs=historical(version=version)
            native=self.store(objects)
            with self.subTest(version=version):
                result=self.run_audit(native,policy([key,intent]))
                self.assertEqual(result['status'],'completed')
                self.assertEqual(len(result['references']),1)
                edge=result['references'][0]
                self.assertEqual(edge['kind'],'historical_window_batch')
                self.assertTrue(edge['content_hash_verified'])
                target=PREFIX+refs[0]['key']
                self.assertEqual(native.read_calls.count(target),1)
                self.assertEqual(len(native.read_calls),3)
                self.assertEqual(result['read_summary']['total_read_bytes'],sum(map(len,objects.values())))
                self.assertNotEqual(next(o for o in result['objects'] if o['key']==key)['content_sha256'],key.split('/')[-1][:-5])
    def test_reserved_window_metadata_never_authorizes_payload_read(self):
        objects,key,intent,refs=historical(year=2024)
        native=self.store(objects);result=self.run_audit(native,policy([key,intent]))
        self.assertEqual(result['status'],'completed')
        self.assertEqual(result['references'],[])
        self.assertNotIn(PREFIX+refs[0]['key'],native.read_calls)
        self.assertEqual({o['content_status'] for o in result['objects'] if o['key'] in (key,intent)}, {'retained_reserved_or_unknown_dates'})
    def test_new_york_development_cutoff_accepts_exact_boundary_only(self):
        for end,read_payload in [('2024-01-01T00:00:00-05:00',True),
                                 ('2024-01-01T05:00:00+00:00',True),
                                 ('2024-01-01T00:00:00.000001-05:00',False)]:
            objects,key,intent,refs=historical(year=2023,end_exclusive=end)
            native=self.store(objects)
            with self.subTest(end=end):
                result=self.run_audit(native,policy([key,intent]))
                self.assertEqual(result['status'],'completed')
                self.assertEqual(PREFIX+refs[0]['key'] in native.read_calls,read_payload)
    def test_unknown_schema_is_retained_without_guessing_edges(self):
        objects,key,intent,refs=historical(window_extra={'private_rows':[PRIVATE]})
        native=self.store(objects);result=self.run_audit(native,policy([key]))
        self.assertEqual(result['status'],'completed');self.assertEqual(result['references'],[])
        self.assertEqual(result['read_summary']['unrecognized_metadata_objects'],1)
        self.assertEqual(native.read_calls,[key])
    def test_missing_payload_reference_is_explicit_and_preserved(self):
        objects,key,intent,refs=historical();del objects[PREFIX+refs[0]['key']]
        result=self.run_audit(self.store(objects),policy([key]))
        self.assertEqual(result['status'],'completed')
        self.assertFalse(result['references'][0]['target_exists'])
        self.assertFalse(result['references'][0]['content_hash_verified'])
    def test_wrong_raw_content_hash_cannot_be_promoted_by_filename(self):
        objects,key,intent,refs=historical();target=PREFIX+refs[0]['key'];objects[target]=objects[target]+b' '
        result=self.run_audit(self.store(objects),policy([key]))
        self.assertEqual(result['failure_codes'],['reference_hash_mismatch'])
        self.assertFalse(result['references'][0]['content_hash_verified'])
    def test_cross_namespace_reference_is_not_followed(self):
        objects,key,intent,refs=historical();doc=json.loads(objects[key]);doc['batches'][0]['key']='historical-snapshots/v2/objects/'+refs[0]['sha256']+'.json';objects[key]=encode(doc)
        native=self.store(objects);result=self.run_audit(native,policy([key]))
        self.assertEqual(result['references'],[]);self.assertEqual(native.read_calls,[key])
    def test_feature_manifest_binds_payload_identity_and_dates(self):
        objects,key=feature();native=self.store(objects);result=self.run_audit(native,policy([key]))
        self.assertEqual(result['status'],'completed')
        self.assertEqual(result['references'][0]['kind'],'feature_manifest_payload')
        self.assertTrue(result['references'][0]['content_hash_verified'])
        self.assertEqual(len(native.read_calls),2)
    def test_read_and_edge_budgets_stop_before_disallowed_payload(self):
        objects,key,intent,refs=historical(batches=2)
        for changes,code in [({'max_total_read_bytes':len(objects[key])-1},'read_limit'),({'max_edges':1},'edge_limit')]:
            native=self.store(objects)
            with self.subTest(code=code):
                result=self.run_audit(native,policy([key],**changes))
                self.assertEqual(result['failure_codes'],[code])
                self.assertTrue(all(k==key for k in native.read_calls))
    def test_json_duplicate_keys_depth_and_nonfinite_values_are_not_exported(self):
        objects,key,intent,refs=historical()
        for raw in [b'{"schema_version":1,"schema_version":2}',b'{"secret":NaN}',encode({'private':[[[[PRIVATE]]]]})]:
            changed=dict(objects);changed[key]=raw;native=self.store(changed)
            with self.subTest(raw=raw[:24]):
                result=self.run_audit(native,policy([key],max_json_depth=2))
                self.assertEqual(result['status'],'completed')
                self.assertEqual(result['references'],[])
                self.assertEqual(native.read_calls,[key])
    def test_output_limit_omits_detail_but_preserves_actual_counters(self):
        objects={f'unknown/{i:03}/'+('x'*120):b'a' for i in range(30)}
        result=self.run_audit(self.store(objects),policy(max_report_bytes=4096))
        self.assertEqual(result['failure_codes'],['report_limit']);self.assertFalse(result['details_complete'])
        self.assertEqual(result['objects'],[]);self.assertIsNone(result['capacity_before'])
        self.assertEqual(result['read_summary']['unread_objects'],30)
    def test_report_validator_rejects_extra_rows_false_deletion_and_identity_types(self):
        native=self.store({'unknown':b'a'});plan=policy();result=self.run_audit(native,plan)
        bads=[]
        bad=deepcopy(result);bad['rows']=[PRIVATE];bads.append(bad)
        bad=deepcopy(result);bad['objects'][0]['deletion_authorized']=True;bads.append(bad)
        bad=deepcopy(result);bad['retention']['confirmed_reclaimable_bytes']=True;bads.append(bad)
        bad=deepcopy(result);bad['identity']['project_id']=True;bads.append(bad)
        bad=deepcopy(result);bad['capacity_before']['used_size_bytes']=999;bads.append(bad)
        for bad in bads:
            with self.subTest(bad=set(bad)),self.assertRaises(ValueError):validate_report(bad,plan,IDENTITY)
    def test_missing_allowlist_metadata_is_reported_without_materializing_it(self):
        objects,key,intent,refs=historical();native=self.store({})
        result=self.run_audit(native,policy([key]))
        self.assertEqual(result['read_summary']['missing_metadata_keys'],1)
        self.assertEqual(native.path_calls,[]);self.assertEqual(native.read_calls,[])
    def test_report_cannot_forge_unapproved_unknown_content_read_evidence(self):
        native=self.store({'unknown/object':b'a'});plan=policy();result=self.run_audit(native,plan)
        bad=deepcopy(result)
        bad['objects'][0]['content_sha256']=sha256(b'a').hexdigest()
        bad['objects'][0]['content_status']='retained_unknown_schema'
        bad['read_summary'].update(payload_read_calls=1,total_read_bytes=1,objects_hashed=1,unread_objects=0)
        with self.assertRaises(ValueError):validate_report(bad,plan,IDENTITY)


if __name__=='__main__':unittest.main()
