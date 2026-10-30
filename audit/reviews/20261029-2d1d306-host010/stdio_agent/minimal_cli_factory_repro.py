from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess, os, sys, json
sys.dont_write_bytecode=True
source=Path(sys.argv[1]).resolve()
factory='''from followup_host import FollowupHost, TransportAuthority
from qresearch.artifacts import MemoryArtifactStore
from qresearch.registry import Registry
from qresearch.task_followup import TaskFollowupController

def create():
    limits={key:{'total':n,'normal':n,'reserve':0} for key,n in [('configurations',12),('research',20),('lean',16)]}
    registry=Registry(MemoryArtifactStore(),limits)
    policy={'schema_version':1,'notification_grace_seconds':1800,'max_history_pages':3}
    return FollowupHost(TaskFollowupController(registry,policy),authority=TransportAuthority('synthetic-no-network'),enabled=True)
'''
with TemporaryDirectory() as temporary:
    root=Path(temporary)
    (root/'valid_factory.py').write_text(factory,encoding='utf-8')
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8',PYTHONPATH=os.pathsep.join([str(root),str(source/'tools'),str(source/'cloud')]))
    controls=subprocess.run([sys.executable,'-B','-c','import valid_factory; h=valid_factory.create(); print(h.enabled, type(h).__module__)'],cwd=root,env=env,text=True,capture_output=True)
    records=[]
    for mode,command in [('script',[sys.executable,'-B',str(source/'tools/followup_host.py')]),('module',[sys.executable,'-B','-m','followup_host'])]:
        command+=['serve','--enable-dispatch','--host-factory','valid_factory:create']
        actual=subprocess.run(command,input='',cwd=root,env=env,text=True,capture_output=True)
        records.append({'mode':mode,'command':command,'expected_exit':0,'actual_exit':actual.returncode,'stdout':actual.stdout,'stderr':actual.stderr,'defect_reproduced':actual.returncode==2 and 'factory must return an explicitly enabled FollowupHost' in actual.stderr})
    report={'control_factory_exit':controls.returncode,'control_factory_stdout':controls.stdout,'control_factory_stderr':controls.stderr,'cases':records,'cloud_calls':0,'real_registry_writes':0}
    print(json.dumps(report,ensure_ascii=False,indent=2))
    assert controls.returncode==0 and controls.stdout.strip()=='True followup_host'
    assert all(item['actual_exit']==item['expected_exit'] for item in records),'Valid imported factory rejected in enabled CLI'
