"""Execute the exact generated cell with a synthetic SDK, never QC or Registry."""
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from hashlib import sha256
import json,sys,types
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'cloud'))
from qresearch.artifacts import content_hash
from qresearch.storage_inventory_tasks import cell_source,_decode,MARKER

class Event:
    def __iadd__(self,callback):return self
    def __isub__(self,callback):return self
class EmptyStore:
    max_size=50000000
    max_files=1000
    keys=()
    def __init__(self):self.error_raised=Event()
    def contains_key(self,key):raise AssertionError('No synthetic keys may be read')
    def get_file_path(self,key):raise AssertionError('No synthetic paths may be materialized')
    def read_bytes(self,key):raise AssertionError('No synthetic values may be read')
    def save(self,*args):raise AssertionError('Writes prohibited')
    save_bytes=save
    delete=save
    clear=save
class FakeQuantBook:
    def __init__(self):self.object_store=EmptyStore()
    def history(self,*args):raise AssertionError('Market history prohibited')

def main():
    packet=Path(__file__).resolve().parent
    preview=json.loads((packet/'plan_preview.stdout.txt').read_bytes())
    payload={'schema_version':1,'plan':preview['plan'],'identity':{
        'project_id':preview['plan']['project_id'],'attempt_id':'f'*32,
        'config_id':preview['configuration_hash'],'plan_hash':preview['plan_hash'],
        'stage':'research','worker_sha256':preview['plan']['worker_sha256']}}
    qc=types.ModuleType('QuantConnect');qc.__path__=[]
    research=types.ModuleType('QuantConnect.Research');research.QuantBook=FakeQuantBook
    qc.Research=research;sys.modules['QuantConnect']=qc;sys.modules['QuantConnect.Research']=research
    source=cell_source(payload);capture=StringIO()
    with redirect_stdout(capture):exec(compile(source,'<synthetic-exact-generated-cell>','exec'),{})
    actual=capture.getvalue()
    assert actual.startswith(MARKER) and len(actual.splitlines())==1
    report=_decode(actual.strip()[len(MARKER):],payload)
    assert report['status']=='completed' and report['capacity_before']['used_files']==0
    assert report['read_summary']['payload_read_calls']==report['read_summary']['metadata_read_calls']==0
    assert report['read_summary']['missing_metadata_keys']==len(preview['plan']['inventory_policy']['metadata_keys'])
    assert report['retention']['confirmed_reclaimable_bytes']==0 and report['retention']['global_reference_closure'] is False
    print(json.dumps({'kind':'synthetic_exact_cell_to_bounded_parser_roundtrip_not_cloud_execution',
        'scenarios':1,'cell_characters':len(source),'cell_source_sha256':sha256(source.encode()).hexdigest(),
        'synthetic_stdout_sha256':sha256(actual.encode()).hexdigest(),'report_hash':content_hash(report),
        'metadata_allowlist_keys':len(preview['plan']['inventory_policy']['metadata_keys']),
        'real_Research_executions':0,'real_Registry_changes':0,'independent_acceptance':False,'final_test_enabled':False}))
if __name__=='__main__':main()
