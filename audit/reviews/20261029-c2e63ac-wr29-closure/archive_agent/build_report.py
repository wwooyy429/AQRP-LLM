from pathlib import Path
from hashlib import sha256
import json,sys,platform
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parents[1];A=Path(__file__).resolve().parent
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
static=read(A/'static_results.json');replays=read(A/'replay_execution.json');maps=read(R/'source_git_manifest.json')
assert all(row['exit_code']==0 and row['script_changed'] is False for row in replays)
for row,methods,scenarios in zip(replays,(18,12,6,7),(37,79,27,28)):
    result=read(A/(row['name']+'_result.json'))
    assert result['methods']==methods and result['named_scenarios']==scenarios
    assert result['failures']==0 and result['errors']==0
    assert not result.get('skips') and not result.get('skipped')
source_guard={}
for folder,item in list(maps.items())+[('archive_agent/replay_context/source',maps['source'])]:
    base=R/folder
    actual={p.relative_to(base).as_posix() for p in base.rglob('*') if p.is_file()}
    assert actual==set(item['files']),(folder,actual-set(item['files']),set(item['files'])-actual)
    changed=[name for name,old in item['files'].items() if sha256((base/name).read_bytes()).hexdigest()!=old['sha256']]
    assert not changed,(folder,changed)
    source_guard[folder]={'files':len(actual),'changed':changed,'extra_or_missing':[]}
proof=read(R/'materials/audit/review_packages/wr29/protected_history.json')
supp=[]
for name,item in proof['files'].items():
    raw=(R/'source'/name).read_bytes()
    represented=raw if item['worktree_raw_matches_git'] else raw.decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n').replace('\n','\r\n').encode()
    assert sha256(represented).hexdigest()==item['worktree_raw_sha256'],name
    supp.append({'name':name,'recorded_worktree_hash_verified':True,'Git_equal':item['worktree_raw_matches_git']})
(A/'source_guard.json').write_text(json.dumps(source_guard,ensure_ascii=False,indent=2),encoding='utf-8')
(A/'additional_representation_checks.json').write_text(json.dumps(supp,ensure_ascii=False,indent=2),encoding='utf-8')
tests=[{'name':row['name'],'methods':m,'named_scenarios':s,'passed_methods':m,'failures':0,'errors':0,'skips':0,'first_execution_passed':True,'actually_executed':True,'source_commit':'c2e63ac5f19901bd95e127069b5998452f7f9864','script_changed':False}for row,m,s in zip(replays,(18,12,6,7),(37,79,27,28))]
report={
 'review_kind':'independent_WR29_archive_history_budget_and_raw_identity_recheck',
 'source_commit':'c2e63ac5f19901bd95e127069b5998452f7f9864','materials_commit':'f698a38a99c3ed8388c9403f2eda723b579c5eaf',
 'environment':{'platform':platform.platform(),'python':sys.version,'executable':sys.executable},
 'findings':[],'tests':tests,'counting':'43方法/171命名场景为原975独立脚本在当前source的实际重放，与根端1012及其他套件重叠；静态/文件/blob/元数据核验不是unit；开发辅助79/84、89/90、恢复8/8及克隆10/10这里只核对归档，没有独立运行它们的历史store。',
 'static_logical_checks':static['static_logical_checks'],'additional_representation_checks':len(supp),'static_are_not_unit_methods':True,
 'old_complete_ZIP':static['old_complete_ZIP'],'selected_archive':static['selected_archive'],'current_identity':static['identity'],'developer_guard':static['developer_guard'],
 'budget':static['budget'],'developer_auxiliary_metadata':static['developer_auxiliary'],
 'developer_auxiliary_replays_executed_this_round':False,
 'source_guard':source_guard,
 'preserved_history':{'old_formal_SHA256':'224a7b8a0e7667b6759e685f71dae0fd54ba0eb6c914ced1c9c1332deb009e14','old_WR29_failure':'open_at2d1d306','old_API_limited_pass':True,'prior975_limited_pass':True,'candidate_independent_status':'pending_in_materials','new_WR29_independent_verdict':'not_determined_by_archive_checks','first_failures_fixtures_QA_originals_restored':True},
 'reviewer_corrections':[read(A/'lookup_first_execution.json'),read(A/'static_correction.json')],
 'software_acceptance':{'historical_windows_notification_cycles_replayed':'passed_in_actually_executed_scope','new_WR29_CLI_verdict':'parent_and_entry_agent_determine','stage2_overall':'not_accepted','stages3_to7':'not_accepted'},
 'platform_evidence_level':'Immutable Git/local ZIP/raw restored original review evidence; old b1a archived platform claims retained only in their historical scope. No fresh QC retrieval or native-provider execution.',
 'unverified':static['limitations']+['New real factory/transport/notifications/cloud engineering chain and complete receipt collection have not been exercised here.','Full historical US200/SID/financial value/vintage/publication/actual vendor delivery/ingestion and charged certification dispatch remain unaccepted.','Financial efficacy,2026 independence and independent final executor remain uncertified.'],
 'external_calls':static['external_calls'],'authoritative_budget_or_production_writes':0,'financial_evidence':False,
 'artifacts':{'static':'audit_archive.py; static_results.json; git_execution.json','first_error':'audit_archive_first.py; static_first.stdout; static_first.stderr; static_correction.json','replays':'run_replays.py; replay_execution.json; *_result.json; *.stdout; *.stderr','source_guard':'source_guard.json; additional_representation_checks.json'}
}
(A/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
record={'static_first':{'command':[sys.executable,'-B',str(A/'audit_archive_first.py')],'exit_code':1,'stdout':'static_first.stdout','stderr':'static_first.stderr','classification':'reviewer summary-shape error'},'static_second':{'command':[sys.executable,'-B',str(A/'audit_archive.py')],'exit_code':0,'stdout':'static_second.stdout','stderr':'static_second.stderr'},'report_build':{'command':[sys.executable,'-B',str(A/'build_report.py')],'exit_code':0},'cloud_calls':0,'production_budget_writes':0}
(A/'execution_records.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'report':str(A/'report.json'),'sha256':sha256((A/'report.json').read_bytes()).hexdigest(),'static':static['static_logical_checks'],'supplementary_raw_proofs':len(supp),'replayed_methods':43,'named_scenarios':171,'findings':[],'source_guard':source_guard},ensure_ascii=False),flush=True)
