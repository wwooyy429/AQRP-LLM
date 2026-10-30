from pathlib import Path
import copy
import hashlib
import json
import shutil
import subprocess
import sys

root=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(root/'cloud'))
sys.path.insert(0,str(root/'tools'))
from qresearch.artifacts import content_hash
from collection_task_cli import execution_source_manifest

def read(p):return json.loads((root/p).read_text(encoding='utf-8-sig'))
def write(p,data):(root/p).write_bytes((json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
def sha(p):return hashlib.sha256((root/p).read_bytes()).hexdigest()

verified=read('audit/stage_verification.json')
assert verified['local_tests_passed'] and 'Ran 478 tests' in verified['test_output']
assert not subprocess.check_output(['git','diff','--name-only','--','config','audit/runtime','audit/task_inputs',
    'audit/engineering_current.json','audit/data_exposure.json'],cwd=root)
peer=read('.git/repair-work/native-rejection-peer/report.json')
for name,digest in peer['tested_runtime_raw_sha256'].items():assert sha(name)==digest,name
package=root/'audit/review_packages/native_rejection'
package.mkdir(exist_ok=False)
for prefix,folder in (('developer',root/'.git/repair-work/phase2-native-rejection'),
        ('peer',root/'.git/repair-work/native-rejection-peer')):
    for file in sorted(folder.iterdir()):
        if file.is_file() and file.suffix in {'.py','.json','.stdout','.stderr'}:
            shutil.copyfile(file,package/('original_'+prefix+'_'+file.name))
for name in ('compare_initial.py','initial.stdout','initial.stderr','initial_execution.json','compare.py'):
    shutil.copyfile(root/'.git/repair-work/phase2-preflight'/name,package/('original_preflight_'+name))
inventory=[]
for file in sorted(package.iterdir()):
    inventory.append({'path':file.name,'bytes':file.stat().st_size,
        'raw_sha256':hashlib.sha256(file.read_bytes()).hexdigest()})
write('audit/review_packages/native_rejection/original_files_manifest.json',{
    'byte_policy':'Original raw bytes; complete package -text','files':inventory,'file_count':len(inventory)})
deployment=read('audit/deployment.json')
replay=read('.git/repair-work/phase2-native-rejection/final_replay.json')
clarification=read('.git/repair-work/phase2-native-rejection/final_replay_count_clarification.json')
assert sha('tests/test_native_backtest_rejection.py')==replay['test_sha256']==clarification['same_final_test_sha256']
execution=execution_source_manifest()
report={'schema_version':1,'kind':'native_compile_rejection_development_candidate',
    'parent_commit':'268f420e9d066e7e7859566a65c0ce65523bec82',
    'independent_software_scope_retained_at':'81fbe5294055423e88ee5aeae48ca6223e7971da',
    'independent_WR19_metadata_scope_retained_at':'84414ab49c39e25cb50ece1c1debeefa3993c874',
    'current_candidate_independently_accepted':False,'source_manifest_hash':verified['source_hash'],
    'source_files':len(verified['source_files']),'execution_source_manifest_hash':execution['source_hash'],
    'configuration_hash':deployment['configuration_hash'],'implementation_hash':deployment['implementation_hash'],
    'deployment_hash':content_hash(deployment['source_files']),'deployment_files':len(deployment['source_files']),
    'generated_module_rebuilt':True,'registered_research_configuration_changed':False,
    'candidate_tests':{'repository_methods':478,'passed':True,'output':verified['test_output'],
        'dedicated_methods':25,'same_final_test_bytes_replayed':True,'baseline_commit':replay['baseline_commit'],
        'baseline_unique_unsuccessful_methods':24,'baseline_failure_outcomes':67,'baseline_error_outcomes':6,
        'error_outcomes_are_not_unique_methods_or_market_runtime_errors':True,
        'baseline_count_clarification':'original_developer_final_replay_count_clarification.json',
        'peer_methods':12,'peer_passed':True,'counts_overlap':True},
    'original_files':len(inventory),'original_files_manifest_raw_sha256':sha('audit/review_packages/native_rejection/original_files_manifest.json'),
    'initial_preflight_helper_failure':{'kind':'development_reader_assumption_error_not_product_WR',
        'reason':'The original task input was archived after source75; fixed comparison binds the input separately to268f Git.',
        'preserved':True},
    'source_preflight':'audit/stage2_next_preflight.json','source_writes_to_QC':0,
    'browser_terminal_reconciliation':'platform_page_requires_user_login; no_terminal_observed',
    'old_LEAN_terminal_confirmed':False,'backtest_status_results_logs_requested':False,
    'budget_usage':{'configurations':6,'research':9,'lean':1},'authoritative_events':12,
    'new_actual_charges':{'configurations':0,'research':0,'lean':0,'model_API':0},
    'authoritative_budget_original_inputs_pointer_and_exposure_unchanged':True,
    'cloud_deployed':False,'native_compile_rejection_verified':False,
    'research_native_execution_error_parser_implemented':False,'full_US200_and_financial_PIT_certified':False,
    'stage2':'pending','stage3_to7':'not_accepted','final_test_enabled':False,'financial_evidence':False,
    'review_handoff':'docs/stage2-next.md'}
write('audit/review_packages/native_rejection/developer_verification.json',report)

tracking=read('audit/review_tracking.json')
tracking['acceptance_scope']='保留既有固定范围；新增原生编译拒绝及原子结算候选待独立审核；阶段2整体待定'
tracking['current_handoff']='docs/stage2-next.md'
tracking['developer_fix_evidence']='audit/review_packages/native_rejection/developer_verification.json'
tracking['new_candidate_acceptance']='pending_fixed_commit_independent_review_of_native_compile_rejection_and_atomic_settlement'
tracking['current_candidate'].update(parent_commit=report['parent_commit'],kind=report['kind'],
    source_manifest_hash=verified['source_hash'],execution_source_manifest_hash=execution['source_hash'],
    implementation_hash=report['implementation_hash'],deployment_hash=report['deployment_hash'],
    independently_accepted=False,cloud_deployed=False,developer_repository_tests=478,
    metadata_and_documentation_only=False,runtime_engine_and_test_sources_unchanged=False,
    registry_changed=True,Engineering_CLI_changed=True,Engineering_completion_contract_changed=False,
    registry_or_WR12_CLI_changed_this_repair=True,Collection_WR12_CLI_changed=False,
    software_acceptance_bound_to='81fbe5294055423e88ee5aeae48ca6223e7971da')
tracking['current_candidate']['new_failure_feature_independently_accepted']=False
tracking['current_candidate']['prior_success_and_completion_scope_retained']=True
stage=next(x for x in tracking['stage_acceptance'] if x['stage']==2)
stage['implementation']='原有81f离线范围保留；新增原生编译拒绝与原子结算候选待审核'
stage['evidence']='WR19元数据844独立通过；新候选478仓库及12开发侧边界通过，不是新增独立验收'
stage['status']='pending_acceptance'
write('audit/review_tracking.json',tracking)

ready=read('audit/stage2_current_readiness.json')
comparison=copy.deepcopy(ready['platform_comparison_from_independent_review'])
ready.update(kind='native_compile_rejection_candidate_pending_review_and_platform_evidence',
    candidate_development_document='docs/stage2-next.md',candidate_source_manifest_hash=verified['source_hash'],
    candidate_execution_source_manifest_hash=execution['source_hash'],source_changed=True,
    source_changed_this_round=['cloud/qresearch/engineering_receipts.py','cloud/qresearch/engineering_tasks.py',
        'cloud/qresearch/registry.py','cloud/research_config.py','tools/stage2.py','tests/test_native_backtest_rejection.py'],
    new_candidate_independently_accepted=False,new_candidate_acceptance_scope='new_native_compile_rejection_and_atomic_settlement_pending_fixed_commit_independent_review',
    latest_read_only_preflight='audit/stage2_next_preflight.json',
    current_candidate_change_scope={'implementation_changed':True,'active_research_configuration_changed':False,'budget_usage_changed':False},
    developer_features_pending_independent_verification=['native_compile_rejection_and_atomic_settlement'],
    blockers=['existing_LEAN_delivered_terminal_and_reconciled_result','new_native_rejection_software_fixed_commit_independent_review',
        'new_implementation_cloud_deployment_and_completed_runtime_evidence','historical_US200_financial_PIT_and_corporate_action_certification'])
ready['source_configuration_budget_changed']=False
ready['source_configuration_budget_changed_scope']='No registered formal research configuration or budget admission changed; implementation changes are declared separately.'
assert ready['platform_comparison_from_independent_review']==comparison
write('audit/stage2_current_readiness.json',ready)
preflight=read('audit/stage2_next_preflight.json')
preflight['project_listing_before_read']={'called':True,'raw_record_persisted':False,'evidence':'native_tool_call_in_conversation'}
preflight['later_project_relisting_record']='audit/stage2_next_project_listing.json'
write('audit/stage2_next_preflight.json',preflight)
print(json.dumps({'repository_methods':478,'source_hash':verified['source_hash'],'execution_hash':execution['source_hash'],
    'implementation_hash':report['implementation_hash'],'deployment_hash':report['deployment_hash'],
    'original_files':len(inventory),'original_manifest_raw_sha256':report['original_files_manifest_raw_sha256']}))
