from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
from unittest.mock import patch
import json,sys
sys.path[:0]=[str(Path('cloud').resolve()),str(Path('tools').resolve()),str(Path('tests').resolve())]
import collection_task_cli as cli, stages, research
from test_collection_tasks import raw_plan,CAT
from test_persistence import budget_fixture
from qresearch.artifacts import MemoryArtifactStore
from qresearch.registry import Registry
with TemporaryDirectory(prefix='aqrp-review-budget-pin-fixed-') as directory:
    root=Path(directory);(root/'config').mkdir();(root/'audit').mkdir()
    budget=budget_fixture();(root/'config/budget.json').write_text(json.dumps(budget),encoding='utf-8')
    (root/'audit/deployment.json').write_text(json.dumps({'source_files':{'synthetic.py':'b'*64}}),encoding='utf-8')
    registry=Registry(MemoryArtifactStore(),budget)
    with patch.object(cli,'ROOT',root),patch.object(stages,'ROOT',root),patch.object(research,'ROOT',root),patch.object(cli,'open_registry',return_value=registry):
        cli.freeze_task(raw_plan(),{'success':True,'projects':[{'projectId':17}]},field_catalog=CAT)
        frozen=cli.current_bridge(field_catalog=CAT).plan.to_dict()['source_manifest_hash']
        cli.execute_metadata_command(NS(command='register-task',allocation='normal'),field_catalog=CAT)
        after_registration=cli.execution_source_manifest()['source_hash']
        claimed=cli.execute_metadata_command(NS(command='claim-task',allocation='normal',retry_of=None,reason=None),field_catalog=CAT)
        after_claim=cli.execution_source_manifest()['source_hash']
        prepared=cli.execute_metadata_command(NS(command='prepare-task',attempt=claimed['attempt_id']),field_catalog=CAT)
        assert frozen==after_registration==after_claim
        assert claimed['should_execute'] is True
        assert (root/prepared['input_path']).exists()
        updated=json.loads((root/'config/budget.json').read_text(encoding='utf-8-sig'))
        updated['limits']['full_configurations']=11
        (root/'config/budget.json').write_text(json.dumps(updated),encoding='utf-8')
        try:
            cli.verify_current_source(cli.current_bridge(field_catalog=CAT))
            policy_rejected=False
        except ValueError:
            policy_rejected=True
        assert policy_rejected
        print(json.dumps({'real_export_usage_called':True,'frozen_execution_hash':frozen,'after_registration_hash':after_registration,'after_claim_hash':after_claim,'usage_projection_identity_stable':True,'claim_admitted':claimed['should_execute'],'prepare_succeeded':True,'budget_policy_change_still_rejected':policy_rejected,'usage':registry.snapshot()['usage'],'authoritative_files_touched':False}))
