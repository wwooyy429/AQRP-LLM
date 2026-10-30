from pathlib import Path
from hashlib import sha256
from datetime import datetime,timezone
import base64,json,sys
root=Path.cwd().resolve();p=root/'audit/review_packages/storage_inventory015';sys.path[:0]=[str(root/'cloud'),str(root/'tools')]
from stages import source_manifest
from collection_task_cli import execution_source_manifest
from research import open_registry
def load(path):return json.loads((root/path).read_bytes())
def write(path,v):(root/path).write_bytes((json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode())
result=load('audit/review_packages/storage_inventory015/settled_result.json');analysis=load('audit/review_packages/storage_inventory015/actual_analysis.stdout.txt')
software=load('audit/review_packages/storage_inventory015/software_report.json');prereg=load('audit/review_packages/storage_inventory015/preregistration.json')
test=load('audit/stage_verification.json');current=source_manifest();stable=execution_source_manifest()
assert stable['source_hash']==software['stable_execution_source_manifest_hash']
changed=[name for name in current['source_files'] if current['source_files'][name]!=test['source_files'][name]]
assert changed==['config/budget.json'],changed
registry=open_registry();snapshot=registry.snapshot();cycle=registry.configuration_cycle_snapshot();rounds=registry.engineering_rounds_snapshot()
attempt='d22d36298ece423da53ed13817dd9b2e';record=[v for v in snapshot['attempts'] if v['attempt_id']==attempt][0]
assert record['status']=='completed' and rounds['stage2-object-store-inventory015']['status']=='closed'
journal=(root/'audit/runtime/registry/events.jsonl').read_bytes();prefix=b''.join(journal.splitlines(keepends=True)[:80])
assert sha256(prefix).hexdigest()==prereg['original_registry_sha256'] and len(journal.splitlines())==86
events=[json.loads(line) for line in journal.splitlines()][80:]
assert len(events)==6
cap=result['report']['capacity_after'];reads=result['report']['read_summary'];pool=analysis['payload_review_pool_summary']
assert cap['free_size_bytes']==53895 and cap['lean_required_bytes']-cap['free_size_bytes']==19833
report={'schema_version':1,'kind':'actual_native_readonly_inventory015_completed_storage_gate_blocked',
    'created_UTC':datetime.now(timezone.utc).isoformat(),'software_source_commit':'df48fbbe1f403913501c6bad16474fd7d4e2e25e',
    'software_test_full_source_hash':software['full_source_manifest_hash'],'current_full_source_hash':current['source_hash'],
    'stable_execution_source_hash':stable['source_hash'],'source_files':len(current['source_files']),
    'only_source_manifest_difference_after_execution':changed,'difference_is_authorized_budget_usage_projection':True,
    'full_product_synthetic_tests_at_software_freeze':1135,'product_tests_repeated_after_usage_only_change':False,
    'project_id':38436695,'round_id':'stage2-object-store-inventory015','attempt_id':attempt,
    'configuration_hash':prereg['configuration_hash'],'plan_hash':prereg['plan_hash'],
    'native_status':'completed','Registry_status':'completed','round_status':'closed','actual_Research_execute_calls':1,
    'actual_LEAN_submissions':0,'automatic_retries':0,'refunds':0,'budget_resets':0,'extra_purchases':0,
    'worker_sha256':prereg['worker_source']['worker_sha256'],'worker_PROJECT_exact_readback':True,
    'worker_runtime_exact_source_guard_passed':True,'isolated_worker_file_count':1,'full49_production_candidate_deployed':False,
    'capacity_method':'QC SDK keys/get_file_path stat; unique-key byte sum; native max_size/max_files; two matching metadata observations',
    'capacity_observed':cap,'frozen_LEAN_byte_envelope_deficit':19833,'capacity_is_not_platform_billing_evidence':True,
    'atomic_snapshot_or_exclusive_reservation':False,'objects_observed':488,'actual_object_hashes':438,
    'typed_references':analysis['typed_reference_summary'],'read_summary':reads,
    'bounded_graph_payload_review_pool':pool,'pool_is_not_a_safe_deletion_manifest':True,
    'all_objects_and_historical_receipts_retained':True,'explicit_Object_Store_save_delete_clear_calls':0,
    'SDK_may_flush_existing_dirty_cache_during_get_file_path':True,'global_reference_closure_complete':False,
    'confirmed_reclaimable_bytes':0,'potential_reclaimable_total_bytes':None,
    'independent_safe_deletion_acceptance':False,'source_static_cross_project_check':'main35 matches complete; four other project checks returned A1 busy, not treated as no consumers',
    'evidence_gaps':analysis['evidence_gaps'],'native_tool_response':'audit/review_packages/storage_inventory015/execute_cell_native.json',
    'native_result':'audit/review_packages/storage_inventory015/settled_result.json','fixed_analysis':'audit/review_packages/storage_inventory015/actual_analysis.stdout.txt',
    'registry_events_before':80,'registry_events_after':86,'original80_raw_prefix_preserved':True,
    'new_registry_event_kinds':[v['kind'] for v in events],'usage_after':snapshot['usage'],'configuration_cycle_after':cycle,
    'budget_limits_unchanged':True,'additional_Research_remaining':1,'LEAN_used':4,
    'ordered_work':[{'step':1,'status':'completed','fixed_commit':'d63a92975744b588def319c632d0cfe90f3841d6'},
        {'step':2,'status':'bounded_cloud_diagnostic_completed_full_closure_and_disposition_insufficient'},
        {'step':3,'status':'blocked_frozen_storage_gate_no_production_candidate_execution'},
        {'step':4,'status':'inventory_own_native_receipt_complete_production_collector_chain_still_unverified'},
        {'step':5,'status':'full_US200_financial_vintage_availability_currency_evidence_missing'},
        {'step':6,'status':'platform_billing_evidence_missing_whole_phase2_not_accepted'}],
    'new_software_independent_review':'pending_exact_version_review','WR31_scoped_closure_preserved':True,
    'stage2_accepted':False,'financial_evidence':False,'final_test_enabled':False,
    '2024_2025_exposure_preserved':True,'2026_independence':'not_certified'}
write('audit/stage2_storage_inventory015_report.json',report)
write('audit/review_packages/storage_inventory015/runtime_protection.json',{
    'software_source_commit':report['software_source_commit'],'software_test_source_hash':software['full_source_manifest_hash'],
    'current_full_source_hash':current['source_hash'],'stable_execution_source_hash':stable['source_hash'],
    'source_hash_changes_only_authorized_usage_projection':changed,
    'registry_sha256':sha256(journal).hexdigest(),'registry_events':86,'original80_prefix_sha256':sha256(prefix).hexdigest(),
    'budget_sha256':sha256((root/'config/budget.json').read_bytes()).hexdigest(),'no_reset_or_refund':True,
    'usage':snapshot['usage'],'configuration_cycle':cycle,
    'closed_round':rounds['stage2-object-store-inventory015']})
for name in ('audit/stage2_current_readiness.json','audit/current_review_status.json','audit/current_review_package.json'):
    v=load(name)
    v['current_storage_inventory']={'report':'audit/stage2_storage_inventory015_report.json','software_source_commit':report['software_source_commit'],
        'attempt_id':attempt,'status':'completed','round_status':'closed','objects':488,'free_bytes':53895,
        'LEAN_byte_envelope_deficit':19833,'all_objects_retained':True,'safe_deletion_accepted':False,
        'global_reference_closure_complete':False,'independent_review_status':'pending_new_exact_version',
        'Research_used':19,'LEAN_used':4,'configuration_cycle_used':5,'configuration_lifetime':18,'Registry_events':86}
    if name.endswith('stage2_current_readiness.json'):
        v['schema_version']+=1;v['stage2_status']='inventory015_completed_closed_storage_and_full_certification_blocked'
        v['historical_previous_candidate_identity']={k:v[k] for k in ('candidate_runtime_source_commit','candidate_execution_source_manifest_hash')}
        v['candidate_runtime_source_commit']=report['software_source_commit'];v['candidate_execution_source_manifest_hash']=stable['source_hash']
        v['candidate_local_cloud_source_files']=49;v['candidate_cloud_deployed']=False;v['candidate_independent_acceptance']=False
        v['current_activity']={'kind':'readonly_native_storage_inventory_completed_closed','new_configurations':1,'new_Research_executions':1,
            'new_LEAN_submissions':0,'new_registry_events':6,'journal_events':86,'Object_Store_deletions':0,
            'independent_acceptance':False,'report':'audit/stage2_storage_inventory015_report.json'}
        v['current_activity_evidence']='audit/stage2_storage_inventory015_report.json'
        v['global_usage']={'configurations':18,'research':19,'lean':4}
        v['configuration_cycle_usage']={'used':5,'limit':13,'remaining':8};v['journal_events']=86
        v['new_submit_allowed_scope']='Full production Research/LEAN remains closed; the separately granted single readonly inventory is completed and its1/1/0 round is closed'
        v['blockers']=['Frozen LEAN byte envelope needs73728B; observed free53895B, deficit19833B; no safe disposition authorized',
            'Unknown receipt schemas/unread candidates/cross-project consumers prevent complete reference and deletion certification',
            'Full49 production deployment/run and production collector native chain remain unverified',
            'Full historical US200 and financial versions/publication/actual delivery/ingestion/currency/unit evidence missing',
            'Actual platform billing evidence unavailable','Exact-version independent review of new inventory software and runtime metadata pending']
        if 'audit/stage2_storage_inventory015_report.json' not in v['reports']:v['reports'].append('audit/stage2_storage_inventory015_report.json')
    if name.endswith('current_review_status.json'):
        v['pending_review']={'source_commit':report['software_source_commit'],'full_source_manifest_hash':software['full_source_manifest_hash'],
            'stable_execution_source_hash':stable['source_hash'],'review_entry':'audit/review_packages/storage_inventory015/GPT_WORK_REVIEW.txt',
            'status':'new_inventory_software_and_native_runtime_pending_independent_review','independent_acceptance':False}
    if name.endswith('current_review_package.json'):
        v['historical_status014_review_entry']=v['review_entry'];v['review_entry']='audit/review_packages/storage_inventory015/GPT_WORK_REVIEW.txt'
        v['kind']='inventory015_software_and_actual_readonly_runtime_review'
        v['source_commit']=report['software_source_commit'];v['source_manifest_hash']=stable['source_hash']
        v['software_full_source_manifest_hash']=software['full_source_manifest_hash'];v['current_state_report']='audit/stage2_storage_inventory015_report.json'
        v['independent_review_status']='pending_new_inventory_exact_version_review'
        v['independent_review_status_scope']='New inventory015 software/runtime only; WR31 fixed-d177 remains independently closed'
    v['stage2_accepted']=False;v['financial_evidence']=False;v['final_test_enabled']=False
    write(name,v)
ledger=root/'audit/experiments.jsonl';raw=ledger.read_bytes();event={'experiment_id':'STAGE2-READONLY-OBJECT-STORE-INVENTORY-015',
    'type':'engineering_storage_diagnostic_not_factor_research','source_commit':report['software_source_commit'],
    'attempt_id':attempt,'native_status':'completed','round_closed':True,'configuration_debits':1,'Research_executions':1,'LEAN_submissions':0,
    'objects':488,'free_bytes':53895,'frozen_LEAN_shortfall_bytes':19833,'typed_references_verified':229,
    'confirmed_reclaimable_bytes':0,'potential_reclaimable_total_bytes':None,'cloud_deletions':0,'Registry_events':86,
    'report':'audit/stage2_storage_inventory015_report.json','independent_acceptance':False,'financial_evidence':False,'final_test_enabled':False}
assert event['experiment_id'].encode() not in raw and raw.endswith(b'\n');ledger.write_bytes(raw+(json.dumps(event)+'\n').encode())
text='''Object Store真实只读诊断015：完成并关轮，空间门槛仍未满足

固定软件df48fbbe1f403913501c6bad16474fd7d4e2e25e通过1135项完整合成测试和固定Git检出核验；新软件未独立验收。按用户“请按顺序处理”，先完成状态统一014，再登记normal1配置/1Research/0LEAN工程额度，源码精确上传/回读、cell绑定、先扣Research后实际执行一次。任务d22d36298ece423da53ed13817dd9b2e已原生completed并按同attempt结算，round已closed；没有第二次执行。

实际SDK原生上限52428800 B，488个唯一键对应文件总52374905 B，空闲53895 B；两遍键/文件字节观测相同，不是原子快照或平台账单。冻结LEAN写入包73728 B，仍短缺19833 B。没有降低旧门槛，没有提交LEAN或整套49文件生产候选。

在QC云内读取并哈希438对象，核验229条typed引用，未导出真实行情/财务/行级派生值。原13对象仍保留；新增3个v2对象仅在本次有界typed图未见入边，物理大小671114 B；16个待审对象合计2772902 B，都未读取内容/实际hash，不是孤儿或可删除证明。438份hash中两组相等是历史resolution元数据，各5份，继续保留。

20个未知schema、50个未读对象、11个本地/UI候选键未找到、其他4项目A1资源导致消费者查询不足，完整传递闭包仍未认证。确认可回收0 B表示证明不足，潜在可释放量未知；全部对象/intent/历史回执保留。SDK get_file_path可能flush已有dirty cache的限制已披露，代码显式save/delete/clear调用0，前后键/字节无变化。

预算上限不变：配置周期5/13（累计18）、Research19/20（余1）、LEAN4/16，80旧事件原字节前缀保留并追加6事件至86。无退款、重置、购买。完整生产回执链、US200/财务实际时点及平台计费仍缺；阶段2整体不通过，正式研究、自动GPT、交易及最终测试关闭，2024–2025暴露和2026独立性未认证保留。

步骤3/4依赖的空间门槛未满足，保持未派发。后续先补16池相关header/hash/所有历史及动态消费者和保留责任、独立核对形成具体安全处置清单，再由用户明确决定处置。当前没有可批准删除的清单，不以文件名、mtime、旧版本或failed/closed代替引用证据。
'''
(p/'REPORT.txt').write_bytes(text.encode())
readme=root/'README.md';s=readme.read_text(encoding='utf-8');first,rest=s.split('\n',1)
intro='''## 当前顺序推进015：只读云端诊断完成，生产联调仍受空间门槛阻挡

步骤1已统一当前/历史入口；步骤2真实Research仅执行一次并原生completed/关轮，488个对象精确总52374905 B、空闲53895 B，较冻结LEAN73728 B门槛短缺19833 B。核验229条typed引用、438份对象hash，完整闭包仍缺证据；原13加新3对象仅为16个待审池，全部保留，确认可回收仍0 B、潜在量未知。没有删除、降低门槛或提交新LEAN。新软件固定df48fbb通过1135项合成回归，只有单worker真实运行，完整49文件生产候选仍未验证且新软件独立复审待定。[实际报告](audit/review_packages/storage_inventory015/REPORT.txt)与[复审入口](audit/review_packages/storage_inventory015/GPT_WORK_REVIEW.txt)给出范围。

上限不变，配置周期5/13（累计18）、Research19/20（余1）、LEAN4/16，Registry86事件，旧80原字节前缀保留。正式研究、自动GPT、交易及最终测试继续关闭，2024–2025暴露与2026独立性未认证保留。以下为各自历史快照。

'''
assert '当前顺序推进015' not in s;readme.write_bytes((first+'\n\n'+intro+rest.lstrip('\n')).encode())
print(json.dumps({'native_status':'completed','round_closed':True,'objects':488,'free_bytes':53895,'LEAN_shortfall':19833,
    'typed_refs':229,'review_pool_objects':16,'confirmed_reclaimable':0,'Registry_events':86,'configuration_cycle':5,'Research':19,'LEAN':4,'independent_acceptance':False,'final_test_enabled':False}))
