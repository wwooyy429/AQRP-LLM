from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess, sys, os, json

sys.dont_write_bytecode=True
source=Path(sys.argv[1]).resolve()
factory='''from followup_host import FollowupHost, TransportAuthority
from qresearch.artifacts import MemoryArtifactStore
from qresearch.registry import Registry
from qresearch.task_followup import TaskFollowupController
def build():
    limits={k:dict(total=n,normal=n,reserve=0) for k,n in
            [('configurations',12),('research',20),('lean',16)]}
    controller=TaskFollowupController(Registry(MemoryArtifactStore(),limits),
        dict(schema_version=1,notification_grace_seconds=1800,max_history_pages=3))
    return FollowupHost(controller,authority=TransportAuthority('synthetic'),enabled=True)
'''
with TemporaryDirectory() as temporary:
    Path(temporary,'wr29_factory.py').write_text(factory,encoding='utf-8')
    env=dict(os.environ,PYTHONPATH=temporary+os.pathsep+str(source/'tools'),PYTHONDONTWRITEBYTECODE='1')
    args=['serve','--enable-dispatch','--host-factory','wr29_factory:build']
    commands={
        'canonical_import_control':[sys.executable,'-B','-c','import followup_host; raise SystemExit(followup_host.main())',*args],
        'documented_script':[sys.executable,'-B',str(source/'tools/followup_host.py'),*args],
        'documented_module':[sys.executable,'-B','-m','followup_host',*args]}
    observed={}
    for label,command in commands.items():
        completed=subprocess.run(command,cwd=source,env=env,input='',text=True,capture_output=True)
        observed[label]={'expected_exit':0,'actual_exit':completed.returncode,'stdout':completed.stdout,'stderr':completed.stderr}
    print(json.dumps(observed,ensure_ascii=False))
    assert all(item['actual_exit']==0 for item in observed.values()),'WR-29: valid factory rejected by executable entry'
