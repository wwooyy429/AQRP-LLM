"""Read-only metadata/policy scope checks; no software test execution."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parent.parent
out=ROOT/'identity_agent';source=ROOT/'source';base=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-81fbe52-20261027\source')
d=json.loads((out/'identity_checks.json').read_text(encoding='utf-8'))
old=(base/'.gitattributes').read_text(encoding='utf-8-sig')
new=(source/'.gitattributes').read_text(encoding='utf-8-sig')
ready=json.loads((source/'audit/stage2_current_readiness.json').read_text(encoding='utf-8-sig'))
archive=json.loads((source/'audit/81fbe52_review_archive_check.json').read_text(encoding='utf-8-sig'))
readme=(source/'README.md').read_text(encoding='utf-8-sig')
wr18=(source/'docs/review/wr18.md').read_text(encoding='utf-8-sig')
wr19=(source/'docs/review/wr19.md').read_text(encoding='utf-8-sig')
scope=[
 {'name':'scope:gitattributes_only_adds_two_archive_preservation_rules','passed':new==old+'audit/reviews/20261027-81fbe52-windows/** -text\n'+'audit/review_packages/wr19/** -text\n'},
 {'name':'scope:source_manifest_change_only_docs_and_gitattributes','passed':d['source_manifest_changed_paths']==['.gitattributes','docs/review/wr18.md','docs/review/wr19.md']},
 {'name':'scope:execution_manifest_change_only_docs_and_gitattributes','passed':d['execution_manifest_changed_paths']==['.gitattributes','docs/review/wr18.md','docs/review/wr19.md']},
 {'name':'scope:latest_report_binds81','passed':ready['latest_independent_report']=='audit/reviews/20261027-81fbe52-windows/formal_report.json'},
 {'name':'scope:new_metadata_does_not_claim_new_software_acceptance','passed':ready['new_candidate_acceptance_scope']=='metadata_only; software_acceptance_bound_to81fbe52'},
 {'name':'scope:WR18_WR19_docs_keep_software_SHA81','passed':'81fbe5294055423e88ee5aeae48ca6223e7971da' in wr18 and '81fbe5294055423e88ee5aeae48ca6223e7971da' in wr19 and '本轮归档提交不冒充运行代码的新独立验收' in wr19},
 {'name':'scope:README_retains_stage2_pending','passed':'GPT Work固定81fbe52确认WR-18修复后通过' in readme and '整阶段仍待验收' in readme},
 {'name':'scope:archive_acceptance_retains81_and_system_not_accepted','passed':archive['reviewed_source_commit']=='81fbe5294055423e88ee5aeae48ca6223e7971da' and archive['acceptance_scope']['whole_stage2']=='pending' and archive['acceptance_scope']['whole_system']=='not_accepted'},
]
for x in scope:x['scope']='metadata_policy_scope'
(out/'scope_checks.json').write_text(json.dumps({'metadata_checks':len(scope),'passed':sum(x['passed'] for x in scope),'failed':sum(not x['passed'] for x in scope),'unit_methods':0,'checks':scope},indent=2)+'\n',encoding='utf-8')
d['checks']=[x for x in d['checks'] if not x['name'].startswith('scope:')]+scope
d['metadata_checks']=len(d['checks']);d['passed_checks']=sum(x['passed'] for x in d['checks']);d['failed_checks']=sum(not x['passed'] for x in d['checks'])
d['policy_impact_note']='Only archive byte-preservation attributes are extended; no production selection or execution-identity policy function changes. Because docs/attributes participate in execution_source_manifest, a new dispatch plan must bind the current execution identity; preserving software acceptance at81 does not authorize new dispatch. Existing frozen evidence/input bytes stay unchanged.'
d['production_or_runtime_semantic_changes_detected']=0
d['protected_unique_files']=115
(out/'identity_checks.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'metadata_checks':len(scope),'passed':sum(x['passed'] for x in scope),'failed':sum(not x['passed'] for x in scope),'total_metadata_checks':d['metadata_checks'],'unit_methods':0,'scope':scope},ensure_ascii=False,indent=2))
