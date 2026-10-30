"""Run candidate preview/preflight with provider sockets denied."""
from pathlib import Path
from types import SimpleNamespace
import argparse, copy, importlib, json, runpy, socket, sys

parser=argparse.ArgumentParser();parser.add_argument('mode',choices=('preview','preflight'));parser.add_argument('source');args=parser.parse_args()
source=Path(args.source).resolve();attempts=[]
def denied(*a,**kw):
    attempts.append('socket')
    raise AssertionError('Offline evidence probe cannot access a provider socket')
socket.socket.connect=denied;socket.create_connection=denied
sys.dont_write_bytecode=True;sys.path.insert(0,str(source/'tools'));sys.path.insert(0,str(source/'cloud'))
if args.mode=='preview':
    sys.argv=[str(source/'tools/stage2.py'),'preview','--plan-file',str(source/'config/engineering_joint_pilot.json'),'--projects-file',str(source/'audit/stage2_live_project_listing.json')]
    runpy.run_path(str(source/'tools/stage2.py'),run_name='__main__')
else:
    stage2=importlib.import_module('stage2');opens=[]
    def no_registry():
        opens.append('open_registry')
        raise AssertionError('Preflight must not open the authoritative Registry')
    stage2.open_registry=no_registry
    document=json.loads((source/'audit/stage2_joint_preview.json').read_text(encoding='utf-8-sig'))['plan']
    bridge=SimpleNamespace(plan=SimpleNamespace(to_dict=lambda:copy.deepcopy(document)))
    stage2.joint_preflight(bridge)
    stale=copy.deepcopy(document);stale['deployment_hash']='f'*64
    refused=False
    try:stage2.joint_preflight(SimpleNamespace(plan=SimpleNamespace(to_dict=lambda:copy.deepcopy(stale))))
    except ValueError:refused=True
    assert refused and not opens
    print(json.dumps({'valid_joint_preflight_passed':True,'stale_deployment_rejected':refused,'Registry_open_attempts':len(opens),'provider_socket_attempts':len(attempts),'registration_or_admission_performed':False,'unit_test_methods':0}))
assert not attempts
