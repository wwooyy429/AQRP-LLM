"""Offline WR-12 reproduction; all state changes stay in a temporary copy."""
import json, shutil, socket, sys, tempfile
from pathlib import Path
from types import SimpleNamespace as NS
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)/'source'; shutil.copytree(Path(sys.argv[1]), root)
    sys.path[:0] = [str(root/'cloud'), str(root/'tools')]
    import collection_task_cli as cli
    import stage2_collection as entry
    from qresearch.collection_execution import run_collection_task, stdout_marker, collection_research_observation
    from qresearch.artifacts import MemoryArtifactStore
    def deny(*args, **kwargs): raise AssertionError('offline only')
    socket.socket.connect = deny
    catalog = entry.catalog()
    def plan(name, project):
        return dict(schema_version=1, task_kind='historical_collection', scope='engineering',
            plan_id=name, project_id=project, source_manifest_hash=None, deployment_hash=None,
            field_catalog=None, report_namespace='independent/'+name, max_retries=1,
            collection_plan=dict(schema_version=1, plan_id=name, scope='engineering',
                source='quantconnect_fundamental_universe', data_version='synthetic-only',
                start='2018-01-03T00:00:00-05:00', end_exclusive='2018-01-04T00:00:00-05:00',
                timezone='America/New_York', fields=['dollar_volume'], calendar_days_per_request=1,
                max_batch_records=2, max_records_per_window=10, source_manifest_hash='0'*64))
    listing = {'success':True, 'projects':[{'projectId':38437839},{'projectId':38433336}]}
    def command(name, **kwargs):
        args = NS(command=name, attempt=None, tool_file=None, allocation='normal', retry_of=None, reason=None)
        vars(args).update(kwargs)
        return cli.execute_metadata_command(args, field_catalog=entry.catalog())
    cli.freeze_task(plan('A',38437839), listing, field_catalog=catalog)
    command('register-task'); attempt = command('claim-task')['attempt_id']
    admission = command('prepare-task', attempt=attempt); original = cli.current_bridge(field_catalog=catalog)
    class SyntheticSource:
        def fetch(self, start, end, fields):
            yield dict(sid='SYNTHETIC-SID', snapshot_at=start.isoformat(), values={'dollar_volume':0})
    payload = admission['payload']
    report = run_collection_task(payload, field_catalog=catalog, source=SyntheticSource(),
        store=MemoryArtifactStore(), synthetic=True, source_root=root/'cloud')
    tool = dict(tool_name='mcp__quantconnect__jupyter_execute_cell', arguments={'projectId':38437839,'index':2},
        result={'isError':False,'structuredContent':{'status':'completed','outputs':[
            {'output_type':'stream','name':'stdout','text':stdout_marker(report,payload=payload,field_catalog=catalog)+'\n'}]}})
    tool_file=root/'synthetic.json'; tool_file.write_text(json.dumps(tool),encoding='utf-8')
    if len(sys.argv)>2 and sys.argv[2]=='catalog':
        path=root/'config/source_catalog.json'; data=json.loads(path.read_text(encoding='utf-8'))
        data['fields']['dollar_volume']['unit']='changed-unit'; path.write_text(json.dumps(data),encoding='utf-8')
    else: cli.freeze_task(plan('B',38433336),listing,field_catalog=catalog)
    rejected=False
    try: command('research-result',attempt=attempt,tool_file=tool_file)
    except Exception as error: rejected=True; print(type(error).__name__,str(error))
    parsed=collection_research_observation(payload,admission['deployment'],tool,field_catalog=catalog)
    original.record_submission(attempt,parsed['submission'])
    control=original.consume_completion(attempt,completion_source=lambda _:parsed['completion'])
    print('original frozen context:',control.status)
    assert not rejected, 'CLI must settle the same valid old-attempt receipt after a local context change'
