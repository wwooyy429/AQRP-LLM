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
with TemporaryDirectory(prefix='aqrp-review-budget-pin-') as directory:
    root=Path(directory);(root/'config').mkdir();(root/'audit').mkdir()
    budget=budget_fixture();(root/'config/budget.json').write_text(json.dumps(budget),encoding='utf-8')
    (root/'audit/deployment.json').write_text(json.dumps({'source_files':{'synthetic.py':'b'*64}}),encoding='utf-8')
    registry=Registry(MemoryArtifactStore(),budget)
    with patch.object(cli,'ROOT',root),patch.object(stages,'ROOT',root),patch.object(research,'ROOT',root),patch.object(cli,'open_registry',return_value=registry):
        cli.freeze_task(raw_plan(),{'success':True,'projects':[{'projectId':17}]},field_catalog=CAT)
        frozen=cli.current_bridge(field_catalog=CAT).plan.to_dict()['source_manifest_hash']
        cli.execute_metadata_command(NS(command='register-task',allocation='normal'),field_catalog=CAT)
        changed=cli.source_manifest()['source_hash']
        try:
            cli.execute_metadata_command(NS(command='claim-task',allocation='normal',retry_of=None,reason=None),field_catalog=CAT)
            outcome='UNEXPECTED_ALLOWED'
        except Exception as error:
            outcome=type(error).__name__+':'+str(error)
        print(json.dumps({'real_export_usage_called':True,'frozen_source_hash':frozen,'source_hash_after_own_config_charge':changed,'identity_changed_by_usage_export':frozen!=changed,'next_claim':outcome,'usage':registry.snapshot()['usage']}))
