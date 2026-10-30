"""Independent public path counterexample; no provider/SDK/worker invocation."""
from pathlib import Path
from copy import deepcopy
from unittest.mock import patch
from hashlib import sha256
import base64,json,sys
sys.dont_write_bytecode=True
import independent_cli_gates as f
import independent_wr16_boundaries as reports
from qresearch.artifacts import FilesystemArtifactStore,canonical_json
from qresearch.registry import Registry
import stage2
ROOT=Path(__file__).resolve().parent
def setup(tag):
    case=f.case(2,tag);attempt=f.prefix(case,'prepare')
    admission=f.accepted(f.cli(case,'prepare','--attempt',attempt))
    registry=Registry(FilesystemArtifactStore(case/'audit/runtime'),json.loads((case/'audit/runtime/registry/baseline.json').read_bytes()))
    bridge=stage2.bridge_for_attempt(attempt,registry=registry)
    return case,attempt,admission,registry,bridge
def result_tool(bridge,attempt,index):
    a=bridge._attempt(bridge._record(attempt));_,obs=reports.observation(bridge,a)
    wrapper={'cloud_report':obs['cloud_report'],'report_ref':obs['report_ref']}
    marker='AQRP_ENGINEERING_JSON '+base64.b64encode(canonical_json(wrapper)).decode()+'\n'
    return {'tool_name':'mcp__quantconnect__jupyter_execute_cell','arguments':{'projectId':bridge.plan.to_dict()['project_id'],'index':index},
            'result':{'status':'ok','outputs':[{'output_type':'stream','name':'stdout','text':marker}]}}
def settle_cli(case,bridge,attempt,index):
    path=case/'synthetic-terminal.json';f.dump(path,result_tool(bridge,attempt,index))
    return f.cli(case,'research-result','--attempt',attempt,'--tool-file',path)
def main():
    positive,aid,admission,r,b=setup('bound-positive')
    cell=f.accepted(f.cli(positive,'research-cell','--attempt',aid))
    read={'tool_name':'mcp__quantconnect__jupyter_read_cell','arguments':{'projectId':b.plan.to_dict()['project_id'],'index':17},
          'result':{'cellType':'code','source':cell['source'].splitlines(keepends=True)}}
    path=positive/'read-cell.json';f.dump(path,read)
    permit=f.accepted(f.cli(positive,'research-dispatch','--attempt',aid,'--tool-file',path))
    assert permit['should_execute'] is True
    good=f.accepted(settle_cli(positive,b,aid,17))
    assert good['status']=='completed'
    legacy,oldid,oldadm,oldr,oldb=setup('modeled-legacy-no-marker')
    # Only this isolated fixture models an old admission that never promised entry semantics.
    (legacy/'audit/runtime/engineering/research-entry-protocol'/(oldid+'.json')).unlink()
    assert not oldr.store.exists('engineering/research-entry-protocol/'+oldid+'.json')
    old_good=f.accepted(settle_cli(legacy,oldb,oldid,23))
    assert old_good['status']=='completed'
    case,aid,admission,r,b=setup('new-no-dispatch')
    marker='engineering/research-entry-protocol/'+aid+'.json'
    dispatch='engineering/research-dispatch/'+aid+'.json'
    assert r.store.exists(marker) and not r.store.exists(dispatch)
    before=r.snapshot()
    response=settle_cli(case,b,aid,999)
    after=r.snapshot()
    completed=None
    if response.returncode==0:completed=json.loads(response.stdout)
    data={'source_commit':'deb85d9f27441b275ab8b108f0232ecd2707a1e8','positive_bound_result':good['status'],
      'legacy_without_marker_result':old_good['status'],'legacy_fixture':'Entry marker removed only from isolated synthetic fixture to model pre-protocol admission; no authority mutation.',
      'new_entry_protocol_exists':r.store.exists(marker),'dispatch_exists_before_and_after':r.store.exists(dispatch),
      'unbound_cell_index':999,'unbound_CLI_exit_code':response.returncode,'unbound_CLI_stderr':response.stderr,
      'unbound_result':None if completed is None else completed['status'],'before':before,'after':after,
      'actual_entry_CLI_processes':len(f.COMMANDS),'actual_worker_QC_market_calls':0,
      'script_sha256':sha256(Path(__file__).read_bytes()).hexdigest()}
    (ROOT/'new_success_without_dispatch_first.json').write_text(json.dumps(data,indent=2)+'\\n',encoding='utf-8')
    (ROOT/'new_success_without_dispatch_commands.json').write_text(json.dumps(f.COMMANDS,indent=2)+'\\n',encoding='utf-8')
    print(json.dumps(data,indent=2))
    assert response.returncode!=0,'A newly prepared entry accepted success with no dispatch binding'
    assert before==after,'Rejected unbound success changed ledger state'
if __name__=='__main__':main()
