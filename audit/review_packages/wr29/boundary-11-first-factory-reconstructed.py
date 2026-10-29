from pathlib import Path
from datetime import datetime, timezone
import json, os, sys
import followup_host as public
from followup_host import FollowupHost, TransportAuthority, ReadGrant
from qresearch.artifacts import FilesystemArtifactStore
from qresearch.registry import Registry
from qresearch.task_followup import TaskFollowupController
LIMITS = {kind:dict(total=10,normal=8,reserve=2) for kind in ("configurations","research","lean")}
def controller():
    return TaskFollowupController(Registry(FilesystemArtifactStore(os.environ["WR29_STORE"],data_classification="synthetic"),LIMITS),dict(schema_version=1,notification_grace_seconds=1800,max_history_pages=3))
def forbidden_clock():
    Path(os.environ["WR29_CLOCK_USED"]).write_text("factory clock executed",encoding="utf-8")
    raise AssertionError("factory clock must be replaced by CLI real UTC")
def build(discovery=True,history=True):
    attempt=os.environ["WR29_ATTEMPT"]
    host=FollowupHost(controller(),authority=TransportAuthority("independent-synthetic",frozenset({attempt}) if discovery else frozenset(),frozenset({attempt}) if history else frozenset()),enabled=True,clock=forbidden_clock)
    meta={"host_module":type(host).__module__,"authority_module":type(host.authority).__module__,"grant_module":ReadGrant.__module__,"host_is_public":type(host) is public.FollowupHost,"file":str(Path(public.__file__).resolve()),"main_module":public.main.__module__,"serve_module":public.serve.__module__,"main_has_host_type":hasattr(sys.modules["__main__"],"FollowupHost")}
    Path(os.environ["WR29_METADATA"]).write_text(json.dumps(meta),encoding="utf-8")
    return host
def no_discovery(): return build(discovery=False)
def no_history(): return build(history=False)
def disabled(): return FollowupHost()
def bad(): return None
class Duck:
    enabled=True
    def command(self,message): return {"unsafe":True}
def duck(): return Duck()
class Child(FollowupHost): pass
def subclass(): return Child()
def bad_authority(): return FollowupHost(controller(),authority=Duck(),enabled=True)
def bad_controller(): return FollowupHost(Duck(),authority=TransportAuthority("synthetic"),enabled=True)
