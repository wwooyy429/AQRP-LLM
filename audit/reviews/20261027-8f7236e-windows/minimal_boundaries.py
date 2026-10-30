"""Offline WR-16/17 counterexamples. Candidate must exit 1 in either mode.
Usage: python -B minimal_boundaries.py SOURCE registry|freeze
Only memory or a new temporary copy is written. No remote execution occurs.
"""
from pathlib import Path
import json, os, shutil, subprocess, sys, tempfile
S = Path(sys.argv[1]).resolve()
mode = sys.argv[2]
sys.dont_write_bytecode = True
sys.path[:0] = [str(S/'cloud'), str(S/'tools')]
if mode == 'registry':
    from qresearch.artifacts import MemoryArtifactStore
    from qresearch.registry import Registry
    from qresearch.engineering_tasks import EngineeringTaskPlan, EngineeringTaskBridge, EngineeringTaskError
    raw = json.loads((S/'audit/stage2_joint_preview.json').read_text(encoding='utf-8'))['plan']
    assert raw['max_retries']['research'] == 0
    plan = EngineeringTaskPlan.from_dict(raw, discovered_project_ids=[raw['project_id']])
    limits = {k: dict(total=n, normal=n, reserve=0) for k,n in [('configurations',12),('research',20),('lean',16)]}
    reg = Registry(MemoryArtifactStore(), limits)
    bridge = EngineeringTaskBridge(reg, plan)
    bridge.register()
    first = bridge.claim('research')
    reg.fail(first, 'SYNTHETIC observed failure')
    try:
        bridge.claim('research', retry_of=first.attempt_id, reason='SYNTHETIC repair')
    except EngineeringTaskError:
        pass
    else:
        raise AssertionError('Bridge also failed to reject max_retries=0')
    retry = reg.begin_attempt(bridge.config_id, 'research', operation_key=first.operation_key,
                              retry_of=first.attempt_id, reason='SYNTHETIC repair')
    print('retry should_execute=', retry.should_execute, 'research used=', reg.snapshot()['usage']['research']['total'])
    print('payload stage=', bridge.payload(retry)['identity']['stage'])
    assert not retry.should_execute, 'WR-16: Registry admitted a forbidden retry'
elif mode == 'freeze':
    target = Path(tempfile.mkdtemp(prefix='aqrp-wr17-')).resolve()
    assert target.is_relative_to(Path(tempfile.gettempdir()).resolve())
    case = target/'source'
    shutil.copytree(S, case)
    pointer = case/'audit/engineering_current.json'
    before = pointer.read_bytes()
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONIOENCODING='utf-8')
    command = [sys.executable,'-B',str(case/'tools/stage2.py'),'freeze','--plan-file','config/engineering.json',
               '--projects-file','audit/stage2_live_project_listing.json']
    result = subprocess.run(command,cwd=case,env=env,capture_output=True)
    print('copy=',case,'freeze exit=',result.returncode,'pointer changed=',pointer.read_bytes()!=before)
    assert result.returncode != 0 and pointer.read_bytes() == before, 'WR-17: legacy freeze replaced pending settlement pointer'
else:
    raise ValueError('Expected registry or freeze')
