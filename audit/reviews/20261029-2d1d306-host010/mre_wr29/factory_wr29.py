from followup_host import FollowupHost, TransportAuthority
from qresearch.artifacts import MemoryArtifactStore
from qresearch.registry import Registry
from qresearch.task_followup import TaskFollowupController

def build():
    limits={name:{'total':n,'normal':n,'reserve':0}
            for name,n in [('configurations',12),('research',20),('lean',16)]}
    controller=TaskFollowupController(Registry(MemoryArtifactStore(),limits),
        {'schema_version':1,'notification_grace_seconds':1800,'max_history_pages':3})
    return FollowupHost(controller,authority=TransportAuthority('independent-synthetic'),enabled=True)
