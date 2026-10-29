"""Reviewer-owned synthetic factory; preserves exact public host type."""
import os, traceback
from pathlib import Path
from followup_host import FollowupHost, TransportAuthority
from qresearch.artifacts import FilesystemArtifactStore
from qresearch.registry import Registry
from qresearch.task_followup import TaskFollowupController

def build():
    attempt=os.environ['AQRP_REVIEW_ATTEMPT']
    limits={k:dict(total=8,normal=6,reserve=2) for k in ('configurations','research','lean')}
    registry=Registry(FilesystemArtifactStore(os.environ['AQRP_REVIEW_STORE'],lock_timeout=15),limits)
    controller=TaskFollowupController(registry,dict(schema_version=1,notification_grace_seconds=1800,max_history_pages=3))
    host=FollowupHost(controller,authority=TransportAuthority('reviewer-owned-io',frozenset([attempt]),frozenset([attempt])),enabled=True)
    original=host.command
    def traced(message):
        try:return original(message)
        except Exception:
            Path(os.environ['AQRP_REVIEW_TRACE']).write_text(traceback.format_exc(),encoding='utf-8')
            raise
    host.command=traced
    return host
