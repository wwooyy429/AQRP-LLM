from pathlib import Path
from hashlib import sha256
import ast,json
R=Path(__file__).resolve().parent;S=R.parent/'source'
locations={}
for rel in ['cloud/qresearch/collection.py','cloud/qresearch/quantconnect.py','tools/stage2_collection.py']:
    for node in ast.walk(ast.parse((S/rel).read_text(encoding='utf-8-sig'))):
        if isinstance(node,(ast.FunctionDef,ast.ClassDef)):
            locations[f'{rel}:{node.name}']=[node.lineno,node.end_lineno]
report={
 'reviewed_commit':'fbe2454e6ea10aa59211c01f236c54bb251527be',
 'verdict_in_tested_scope':'No newly confirmed defect in snapshot plan/cache/atomicity/failure/read-only handling.',
 'first_execution':json.loads((R/'first_results.json').read_text(encoding='utf-8')),
 'verification_execution':json.loads((R/'verification_results.json').read_text(encoding='utf-8')),
 'unique_methods':19,'subcases_per_execution':31,
 'reproducibility_note':'First suite passed. Its filesystem fixtures used fixed directories; before a repeat, the audit harness alone was changed to create a fresh UUID store subtree each run. Original first script and results are preserved. No test assertion or production source changed; final reproducible harness again passed 19 methods / 31 subcases. Do not add the two executions into 38 distinct methods.',
 'first_script_archive':'first_independent_collection.py',
 'source_locations':locations,
 'confirmed_findings':[],
 'minimal_failing_reproduction':None,
 'budget_and_scope_notes':[
   'collection.py imports no Registry/workflow dispatcher and calls no project/task submission interface; its source.fetch is an injected producer contract. Actual remote admission is explicitly deferred in module docs and docs/stage2-snapshot-collection.md. This declared missing integration is not reported as a new defect.',
   'Cloud read-only adapter rejects its first intent write before any injected source call. Existing completed caches read with zero writes and zero new source calls.',
   'Filesystem tests prove same-root cooperating process locking; in-process ObjectStore adapter tests prove same-namespace adapter locking. Cross-node cloud producers are explicitly unsupported, not certified by these synthetic tests.',
   'Window completion is atomic; a failed later window retains a readable completed prefix and a blocking failed intent. This is documented per-window progress, not an all-plan transaction.',
   'Catalog semantics, plan id, data version, projection and implementation-hash declarations are in cache identity. New frozen identities intentionally cause new source calls; arbitrary plans are not a cross-plan deduplication contract.',
   'Source-manifest matching to current implementation occurs in CLI preview, not in the injected collector API. The API depends on the declared trusted source/dispatcher boundary; no normal route into the old engineering budget bridge was found.',
   'No real market/platform/model calls, source edits, budget changes or financial conclusions.'
 ],
 'artifact_sha256':{p.name:sha256(p.read_bytes()).hexdigest() for p in R.glob('*') if p.is_file() and p.name!='review_report.json'}
}
(R/'review_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'unique_methods':19,'subcases':31,'confirmed_findings':0,'review_report':str(R/'review_report.json')}))
