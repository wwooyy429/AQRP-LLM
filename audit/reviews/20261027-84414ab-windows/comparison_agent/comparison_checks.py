"""Independent WR19 metadata checks; zero unittest methods, no provider calls."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ap=argparse.ArgumentParser();ap.add_argument('--source',required=True);ap.add_argument('--baseline',required=True)
args=ap.parse_args();ROOT=Path(args.source).resolve();BASE=Path(args.baseline).resolve();OUT=Path(__file__).resolve().parent
CHECKS=[];COMMANDS=[]
ENV=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8')
AE='ae2b8985f3799c246e90341370f86d80483f63ed';DC='dc49f0f3037918f3ce4413665c59b164a8d6e2b7'
CURRENT='84414ab49c39e25cb50ece1c1debeefa3993c874';PREVIOUS='81fbe5294055423e88ee5aeae48ca6223e7971da'
READY='audit/stage2_current_readiness.json';ARCHIVE='audit/reviews/20261027-ae2b898-windows/'
MANIFEST=ARCHIVE+'source_git_manifest.json';COMPARISON=ARCHIVE+'cloud_comparison.json'
DEVELOPER=ROOT/'audit/review_packages/wr19/verify_archived_comparison.py'
GUARD_FILES=[READY,'audit/review_packages/wr19/verify_archived_comparison.py','config/budget.json','audit/runtime/registry/events.jsonl']

def sha(data):return hashlib.sha256(data).hexdigest()
def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def write(path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
BEFORE={name:sha((ROOT/name).read_bytes()) for name in GUARD_FILES}

def check(name,passed,details=None):
    row={'name':name,'passed':bool(passed),'details':details};CHECKS.append(row)
    print(json.dumps(row,ensure_ascii=False))
    return passed

def invoke(label,script,source,expected_exit):
    folder=OUT/'commands';folder.mkdir(exist_ok=True)
    argv=[sys.executable,'-B',str(script),str(source)]
    result=subprocess.run(argv,cwd=OUT,env=ENV,capture_output=True,timeout=20)
    stdout=folder/(label+'.stdout');stderr=folder/(label+'.stderr');stdout.write_bytes(result.stdout);stderr.write_bytes(result.stderr)
    record={'label':label,'argv':argv,'cwd':str(OUT),'exit_code':result.returncode,'expected_exit':expected_exit,
        'stdout':str(stdout.relative_to(OUT)),'stderr':str(stderr.relative_to(OUT)),
        'stdout_sha256':sha(result.stdout),'stderr_sha256':sha(result.stderr)}
    COMMANDS.append(record);check('command:'+label,result.returncode==expected_exit,record)
    return result

def comparison(manifest,reference):
    candidate={name[len('cloud/'):]:digest for name,digest in manifest['files'].items() if name.startswith('cloud/') and name.endswith('.py')}
    known={item['path']:item['cloud_utf8_sha256'] for item in reference['files'] if item['path']!='_engineering_task_input.py'}
    same=sorted(name for name in candidate.keys()&known.keys() if candidate[name]==known[name])
    changed=sorted(name for name in candidate.keys()&known.keys() if candidate[name]!=known[name])
    outside=sorted(candidate.keys()-known.keys())
    return {'candidate_paths':len(candidate),'known_reference_paths':len(known),'same':same,'different':changed,'not_in_reference':outside,
        'same_count':len(same),'different_count':len(changed),'not_in_reference_count':len(outside),'difference_total':len(changed)+len(outside),
        'per_path':{name:{'candidate_sha256':candidate[name],'old_known_reference_sha256':known.get(name),
            'category':'outside_reference' if name not in known else 'same' if candidate[name]==known[name] else 'different'} for name in sorted(candidate)}}

ready=read(ROOT/READY);summary=ready['platform_comparison_from_independent_review'];old_ready=read(BASE/READY)
old_record=ROOT/'audit/review_packages/wr19/original_readiness_Git_81fbe52.json'
old_manifest=read(ROOT/'audit/reviews/20261027-81fbe52-windows/source_git_manifest.json')['candidate']
check('original_entire_81f_Git_readiness_raw_preserved',old_record.read_bytes()==(BASE/READY).read_bytes()
    and sha(old_record.read_bytes())==old_manifest['files'][READY] and old_manifest['commit']==PREVIOUS,
    {'raw_sha256':sha(old_record.read_bytes()),'bytes':len(old_record.read_bytes()),'manifest_commit':old_manifest['commit']})
check('original_erroneous_claim_preserved_exactly',ready['WR19_comparison_correction']['original_claim']==old_ready['platform_comparison_from_independent_review']
    and old_ready['platform_comparison_from_independent_review']['candidate_different_or_missing_paths']==12)
original=OUT/'original_minimal_wr19.py'
check('original_MRE_raw_bytes_preserved',original.read_bytes()==(BASE.parent/'minimal_wr19.py').read_bytes()
    ==(ROOT/'audit/review_packages/wr19/original_minimal_wr19.py').read_bytes(),{'raw_sha256':sha(original.read_bytes())})

archived_dc='audit/reviews/20261027-dc49f0f-windows'
baseline_files={path.relative_to(BASE/archived_dc).as_posix():sha(path.read_bytes()) for path in (BASE/archived_dc).rglob('*') if path.is_file()}
current_files={path.relative_to(ROOT/archived_dc).as_posix():sha(path.read_bytes()) for path in (ROOT/archived_dc).rglob('*') if path.is_file()}
check('historical_dc49_archive_raw_files_preserved',baseline_files==current_files,{'file_count':len(current_files)})
reference=read(ROOT/COMPARISON);manifest=read(ROOT/MANIFEST)['candidate'];computed=comparison(manifest,reference)
dc_manifest=read(ROOT/archived_dc/'source_git_manifest.json')['candidate'];dc=comparison(dc_manifest,reference)
dc_report=read(ROOT/archived_dc/'formal_report.json');dc_evidence=read(ROOT/archived_dc/'evidence_agent/qc_readback_comparison.json')
check('historical_dc49_8_plus_4_equals_12_retained',dc_manifest['commit']==DC and dc['different_count']==8
    and dc['not_in_reference_count']==4 and dc['difference_total']==12 and dc_report['platform_state']['candidate_differing_paths']==12
    and set(dc_evidence['candidate_differences'])==set(dc['different']+dc['not_in_reference']),dc)
check('ae_identity_and_29_25_16_9_4_13',manifest['commit']==reference['reviewed_source_commit']==summary['candidate_commit']==AE
    and [computed[k] for k in ('candidate_paths','known_reference_paths','same_count','different_count','not_in_reference_count','difference_total')]==[29,25,16,9,4,13],computed)
check('summary_exact_path_lists_and_counts',summary['differing_known_reference_paths']==computed['different']
    and summary['paths_not_in_known_reference']==computed['not_in_reference']
    and [summary[name] for name in ('candidate_different_or_missing_paths','candidate_known_reference_different_paths','candidate_paths_not_in_reference','candidate_manifest_files','known_reference_files')]==[13,9,4,29,25])
check('raw_reference_paths_and_hashes_bound',summary['candidate_manifest_ref']=={'path':MANIFEST,'raw_sha256':sha((ROOT/MANIFEST).read_bytes())}
    and summary['archived_platform_comparison_ref']=={'path':COMPARISON,'raw_sha256':sha((ROOT/COMPARISON).read_bytes())},
    {'candidate_manifest_raw_sha256':sha((ROOT/MANIFEST).read_bytes()),'comparison_raw_sha256':sha((ROOT/COMPARISON).read_bytes())})
check('same_and_different_hashes_match_archived_per_path_metadata',all(
    item.get('candidate_raw_sha256')==computed['per_path'][item['path']]['candidate_sha256']
    and item['cloud_utf8_sha256']==computed['per_path'][item['path']]['old_known_reference_sha256']
    for item in reference['files'] if item['path']!='_engineering_task_input.py'))
check('archived_scope_not_current_cloud_certification',summary['runtime_source_commit']==reference['old_cloud_source_commit']
    and summary['this_archival_turn_new_QC_read'] is False and summary['cloud_inventory_certified'] is False
    and ready['cloud_inventory_certified'] is False and ready['current_platform_lean_status'] is None
    and ready['WR19_comparison_correction']['outside_reference_does_not_mean_current_cloud_missing'] is True
    and ready['new_candidate_acceptance_scope']=='metadata_only; software_acceptance_bound_to81fbe52'
    and ready['stage2_status']=='pending_platform_runtime_receipts_terminal_and_data_certification')

invoke('original_MRE_candidate',original,ROOT,0)
baseline_result=invoke('original_MRE_baseline_negative',original,BASE,1)
check('baseline_negative_is_original_12_versus_13',b'declared 12, archived comparison computes 13' in baseline_result.stderr)
positive=invoke('developer_verifier_candidate',DEVELOPER,ROOT,0)
positive_value=json.loads(positive.stdout)
check('developer_output_preserves_archive_scope',positive_value['scope']=='Archived references only; no current cloud missing-file or inventory assertion'
    and positive_value['financial_evidence'] is False and positive_value['actual_provider_or_model_calls']==0)

for mutation in ('scope_escape','candidate_commit','reference_hash','count_12','tampered_raw','wrong_path_list','duplicate_known_reference'):
    case=OUT/'cases'/mutation/'source'
    for name in (READY,MANIFEST,COMPARISON):
        destination=case/name;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,destination)
    value=read(case/READY);s=value['platform_comparison_from_independent_review']
    if mutation=='scope_escape':
        outside=case.parent/'outside_manifest.json';shutil.copy2(case/MANIFEST,outside)
        s['candidate_manifest_ref']['path']='../outside_manifest.json'
    elif mutation=='candidate_commit':s['candidate_commit']='f'*40
    elif mutation=='reference_hash':s['candidate_manifest_ref']['raw_sha256']='f'*64
    elif mutation=='count_12':s['candidate_different_or_missing_paths']=12
    elif mutation=='tampered_raw':
        path=case/MANIFEST;path.write_bytes(path.read_bytes()+b'\n')
    elif mutation=='wrong_path_list':s['differing_known_reference_paths'][-1]='SYNTHETIC_UNKNOWN.py'
    elif mutation=='duplicate_known_reference':
        duplicate=read(case/COMPARISON);duplicate['files'].append(copy.deepcopy(duplicate['files'][1]));write(case/COMPARISON,duplicate)
        s['archived_platform_comparison_ref']['raw_sha256']=sha((case/COMPARISON).read_bytes())
    write(case/READY,value)
    before={name:sha((case/name).read_bytes()) for name in (READY,MANIFEST,COMPARISON)}
    result=invoke('negative_'+mutation,DEVELOPER,case,1)
    check('negative_no_write:'+mutation,before=={name:sha((case/name).read_bytes()) for name in before})
    expected_error={'scope_escape':b'Comparison reference escapes','candidate_commit':b'Comparison source identities differ',
        'reference_hash':b'Archived reference raw bytes differ','count_12':b'declared archived comparison differs',
        'tampered_raw':b'Archived reference raw bytes differ','wrong_path_list':b'declared archived comparison differs',
        'duplicate_known_reference':b'known-reference paths are duplicated'}[mutation]
    check('negative_exact_error:'+mutation,expected_error in result.stderr)

AFTER={name:sha((ROOT/name).read_bytes()) for name in GUARD_FILES}
check('candidate_source_and_authoritative_budget_journal_unchanged',BEFORE==AFTER,{'before':BEFORE,'after':AFTER})
summary_result={'commit':CURRENT,'reviewer':'comparison_agent','unit_methods':0,'metadata_checks':len(CHECKS),
    'passed_checks':sum(row['passed'] for row in CHECKS),'failed_checks':sum(not row['passed'] for row in CHECKS),
    'first_failure':next((row for row in CHECKS if not row['passed']),None),'checks':CHECKS,'commands':COMMANDS,
    'original_MRE_programs':1,'original_MRE_invocations':2,'developer_verifier_programs':1,'developer_verifier_invocations':8,
    'independent_negative_variants':7,'actual_provider_or_model_calls':0,'actual_worker_executions':0,
    'computed_ae':computed,'computed_dc49':dc,'actions':{'QC':0,'network':0,'SDK':0,'Research':0,'LEAN':0,'models':0,
        'market':0,'production_source_edits':0,'authoritative_budget_changes':0},
    'scope':'Metadata-only archival comparison. Referenced old-known paths absent from reference do not prove present cloud absence or inventory completeness. No software-runtime or stage2 acceptance.'}
write(OUT/'results.json',summary_result);write(OUT/'command_log.json',COMMANDS)
print(json.dumps({k:v for k,v in summary_result.items() if k not in ('checks','commands','computed_ae','computed_dc49')},ensure_ascii=False,indent=2))
sys.exit(1 if summary_result['failed_checks'] else 0)
