"""Trusted operator assembly for one real round009 task; no read grant.

This sidecar is not an independently accepted production transport. It binds
the approved host implementation to one charged configuration and platform ID.
"""
from pathlib import Path

from followup_host import FollowupHost, TransportAuthority
from qresearch.task_followup import TaskFollowupController
from research import open_registry, read_json
from stage2 import admitted_input, bridge_for_attempt

ATTEMPT = "11147fc5a7ac4f6c951a86d021d069b2"
BACKTEST = "6347a33efc37e761f486f982e804dbac"
CONFIGURATION = "64e7ef0354b78b69d97bd97b5e2a0210c0545bf08c921b53fbde98f6a0f2810a"
SOURCE = "fe3df524e360fef6d74dc06559b553bd0005b9350c9f425855a4ec26ec4360c5"
DEPLOYMENT = "f89de8960ab68d1e18dc2003a7b4a9e3517100e4daf9c12a6eda2b95b378fdc6"


def create_host():
    root = Path(__file__).resolve().parents[3]
    registry = open_registry()
    bridge = bridge_for_attempt(ATTEMPT, registry=registry)
    record = bridge._record(ATTEMPT)
    admission = admitted_input(bridge, ATTEMPT)
    identity = admission["payload"]["identity"]
    if (record["config_id"] != CONFIGURATION or record["external_id"] != BACKTEST
            or record["stage"] != "lean" or identity["project_id"] != 38436695
            or identity["source_manifest_hash"] != SOURCE
            or identity["deployment_hash"] != DEPLOYMENT
            or admission["deployment"]["input_hash"] != "9cecf347f6955053adce330e866dc10301600285bc76fab598657e13e8733060"):
        raise ValueError("Operator factory identity differs from the admitted real task")
    controller = TaskFollowupController(registry, read_json(root / "config/task_followup.json"))
    authority = TransportAuthority(
        transport_name="quantconnect_mcp_trusted_stdio_operator_round009",
        discovery_attempts=frozenset({ATTEMPT}),
        history_attempts=frozenset({ATTEMPT}),
        read_mode="disabled",
    )
    return FollowupHost(controller, authority=authority, enabled=True)
