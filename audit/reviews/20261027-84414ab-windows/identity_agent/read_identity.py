"""Read-only identity functions; does not invoke build/verify/Registry/platform."""
from pathlib import Path
from hashlib import sha256
import json,sys
sys.dont_write_bytecode=True
root=Path(sys.argv[1]).resolve()
sys.path[:0]=[str(root/'tools'),str(root/'cloud')]
import stages,research,collection_task_cli
from qresearch.artifacts import canonical_json,content_hash
source=stages.source_manifest()
execution=collection_task_cli.execution_source_manifest()
deployment=json.loads((root/'audit/deployment.json').read_text(encoding='utf-8-sig'))
implementation={p.name:sha256(p.read_text(encoding='utf-8-sig').encode('utf-8')).hexdigest() for p in sorted((root/'cloud/qresearch').glob('*.py'))}
cloud={p.relative_to(root/'cloud').as_posix():sha256(p.read_text(encoding='utf-8-sig').encode('utf-8')).hexdigest() for p in sorted((root/'cloud').rglob('*.py')) if '__pycache__' not in p.parts}
print(json.dumps({'source_root':str(root),'source_manifest_hash':source['source_hash'],'source_files':source['source_files'],
'execution_manifest_hash':execution['source_hash'],'execution_files':execution['source_files'],
'implementation_hash':content_hash(implementation),'implementation_files':implementation,
'active_configuration_hash':content_hash(research.configuration()),'deployment_hash':content_hash(deployment['source_files']),
'cloud_computed_deployment_hash':content_hash(cloud),'cloud_files':cloud,
'deployment_manifest_matches_cloud':deployment['source_files']==cloud,
'archived_implementation_hash':deployment['implementation_hash'],'archived_configuration_hash':deployment['configuration_hash'],
'unit_methods':0,'build_invocations':0,'verify_invocations':0,'Registry_opens':0,'QC_calls':0},ensure_ascii=False,indent=2))
