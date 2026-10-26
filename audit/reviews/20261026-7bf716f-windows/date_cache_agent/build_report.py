from pathlib import Path
from hashlib import sha256
import json
root=Path(__file__).resolve().parent
result=json.loads((root/'first_results.json').read_text(encoding='utf-8'))
report={
 'source_commit':result['commit'],
 'task_scope':'WR09 minimum date missingness, existing cache rejection and legitimate cache compatibility',
 'verdict':'WR09 fix passes this independent synthetic source/cache scope; no newly confirmed defect.',
 'methods':result['methods'],'passed_methods':result['passed_methods'],'subcases':result['subcases'],
 'failed_methods':result['failed_methods'],'error_methods':result['error_methods'],'skipped':result['skipped'],
 'minimal_new_failing_reproduction':None,
 'first_execution_output':'first_output.txt','first_execution_result':'first_results.json',
 'command':result['command'],
 'evidence':[
  'Public QuantConnectSnapshotSource projection maps Python date.min, datetime.min, pandas Timestamp(datetime.min) and canonical minimum ISO date string to None; other missing variants stay None.',
  'Public resolved Value remains available without consulting default-period HasValue; test property raises if read. 0001-01-02, 1899-12-31, valid leap day and timezone-aware normal dates survive; numeric zero, negative zero and False survive.',
  'Fresh two-window source -> collector -> read chain stores five independent synthetic names with date gaps 1 and 4, and second collect performs zero new source calls.',
  'Unmodified fbe source and collector, run in an isolated subprocess against new synthetic inputs, actually write the wrong minimum-date cache. Current collector rejects both read_window and collect for that cache with source=None and a fetch-counting spy; all persisted bytes unchanged and spy calls zero.',
  'The old wrong date is deliberately in the second batch after an entirely legitimate first batch. Whole-window read rejects rather than yielding a partial list.',
  'An independently generated legitimate fbe cache containing nulls, zero, 0001-01-02 and 2000-02-29 still reads and reuses with no new calls or byte changes.',
  'Invalid strings and directly supplied serialized minimum-date rows fail without completed publication and leave an intent that blocks auto-retry.'
 ],
 'accurate_source_lines':{
  'sentinel_projection':'cloud/qresearch/historical_source.py:84-99',
  'stored_date_validation':'cloud/qresearch/collection.py:212-218',
  'whole_window_validation_and_row_revalidation':'cloud/qresearch/collection.py:248-299',
  'public_read':'cloud/qresearch/collection.py:301-303',
  'completed_cache_checked_before_intent_or_fetch':'cloud/qresearch/collection.py:320-333'},
 'baseline_comparison':result['static_review'],
 'observations':result['observations'],
 'limits':['Synthetic native shape only; no actual SDK or market response executed.',
           'WR10 endpoint correctness is separately assigned; these date fixtures intentionally place snapshots inside both old and new request intervals.',
           'Budget bridge remains the explicitly declared missing integration; this review changes no budgets, registry entries, production or developer files.',
           'No financial validity or stage2/full-system acceptance follows from this scoped software result.'],
 'artifact_sha256':{p.name:sha256(p.read_bytes()).hexdigest() for p in root.glob('*') if p.is_file() and p.name!='review_report.json'}
}
(root/'review_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'methods':report['methods'],'subcases':report['subcases'],'failed_methods':report['failed_methods'],'report':str(root/'review_report.json')}))
