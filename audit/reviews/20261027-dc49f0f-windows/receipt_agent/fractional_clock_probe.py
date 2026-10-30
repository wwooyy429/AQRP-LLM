"""Same public valid worker→nested marker chain on candidate and old baseline."""
import hashlib
import json
from pathlib import Path
import sys
import independent_fractional_harness as h

records=[]
for family in ('collection','old_research'):
    for fraction in ('','5','12','123','1234','12345','123456'):
        clock='2018-01-03T00:00:00'+('.'+fraction if fraction else '')+'Z'
        item=h.Harness(family)
        native=h.native_shape(h.marker(item.wrapper),{'lastModified':clock},'content')
        before=dict(item.local._data);usage=item.reg.snapshot()['usage']
        accepted=False;error=None
        try:
            # Empty outer annotation avoids the old be94426 rejection of all
            # nonempty MCP outer annotations. The same valid nested hint is the
            # only changed observation between the two source versions.
            parsed=item.parse(native,outer_annotation={})
            final=item.finish(parsed);accepted=final.status=='completed'
        except h.ReceiptParseError as exc:error=str(exc)
        item.assert_no_rows(__import__('unittest').TestCase())
        state=item.bridge._record(item.attempt)['status']
        rec={'family':family,'lastModified':clock,'fraction_digits':len(fraction),
            'expected_completed':True,'actual_completed':accepted,'final_status':state,'error':error,
            'source_fetch_calls':item.source.calls if family=='collection' else item.qb.history_calls,
            'research_usage_before':usage['research']['total'],'research_usage_after':item.reg.snapshot()['usage']['research']['total'],
            'registry_unchanged_on_reject':item.local._data==before if not accepted else None,
            'raw_row_persisted':h.SECRET.encode() in b''.join(item.local._data.values()),
            'worker_report_status':item.wrapper['cloud_report']['status'],
            'worker_report_sha256':h.content_hash(item.wrapper['cloud_report'])}
        records.append(rec)
label='candidate' if h.ROOT.parent.name.startswith('aqrp-review-dc49') else 'baseline_be94426'
result={'label':label,'source_root':str(h.ROOT),'command_argv':sys.argv,
    'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'helper_sha256':hashlib.sha256((Path(__file__).parent/'independent_fractional_harness.py').read_bytes()).hexdigest(),
    'receipt_source_sha256':hashlib.sha256((h.ROOT/'cloud/qresearch/engineering_receipts.py').read_bytes()).hexdigest(),
    'variants':len(records),'expected_completed':len(records),'actually_completed':sum(x['actual_completed'] for x in records),
    'incorrect_rejections':sum(not x['actual_completed'] for x in records),'cases':records,
    'scope':'1/2/3/4/5/6 digits within ordinary fractional-second ISO forms explicitly described by candidate; no arbitrary full-ISO requirement',
    'real_actions':{'SDK':0,'Research':0,'LEAN':0,'market':0,'models':0,'deployment':0,'budget_change':0,'source_edits':0}}
(h.OUT/(label+'_fractional_clock.json')).write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k!='cases'},ensure_ascii=False))
for rec in records:print(json.dumps(rec,ensure_ascii=False))
sys.exit(1 if result['incorrect_rejections'] else 0)
