"""Read-only final report QA; does not rerun any product test or platform call."""
from pathlib import Path
import hashlib,json
R=Path(__file__).resolve().parents[1];O=Path(__file__).resolve().parent
read=lambda p:json.loads((R/p).read_text(encoding='utf-8-sig'))
f=read('formal_report.json');findings=read('findings.json');cloud=read('cloud_comparison.json')
e=read('evidence_agent/evidence_verification.json');s=read('evidence_agent/supplemental_verification.json');b=read('evidence_agent/build_preview_verification.json')
checks={
 '364 metadata checks and zero unit methods': f['tests']['metadata_checks']=={'primary':350,'supplemental':14,'passed':364,'failed':0,'unit_methods':0},
 'fixed Git / review / execution identity': f['Git_archive_files']==1843 and f['source_manifest_files']==120 and f['source_manifest_hash']==e['source']['review_hash'] and f['execution_manifest_hash']==e['source']['execution_hash'],
 'local deployment / implementation / active config identity': f['deployment_hash']==e['deployment']['local_deployment_hash'] and f['implementation_hash']==e['deployment']['implementation_hash'] and f['active_configuration_hash']==e['deployment']['active_configuration_hash'],
 'two builds and previews no source writes': f['tests']['build_preview']=={'builds':2,'CLI_previews':2,'each_exit_code':0,'files_unchanged':1843,'valid_preflight':'accepted','stale_deployment':'rejected'} and b['candidate_source_unchanged'],
 'budget replay and pending identity': all(f['budget_replay'][k]==e['budget'][k] for k in ('events','usage','limits','pending_attempt')) and f['budget_replay']['new_real_charges']=={'configurations':0,'research':0,'lean':0,'model_API':0},
 'findings identical between formal and standalone': f['findings']==findings and [v['id'] for v in findings]==['WR-18'],
 'reported cloud file counts and inventory boundary': f['platform_evidence_level']['implementation_files']==25 and f['platform_evidence_level']['task_input_files']==1 and cloud['actual_python_files_read']==26 and cloud['raw_old_matches']==26 and f['platform_evidence_level']['listing_python_files']==cloud['listed_python_files']==18 and f['platform_evidence_level']['known_readable_files_missing_from_listing']==cloud['known_but_not_listed'] and len(cloud['known_but_not_listed'])==8 and f['platform_evidence_level']['full_inventory_certified'] is False,
 'no candidate deployment or runtime certification': f['platform_evidence_level']['candidate_deployment_verified'] is False and f['platform_evidence_level']['candidate_runtime_verified'] is False and f['backtest_terminal']['current_platform_status'] is None and f['backtest_terminal']['status_results_logs_read'] is False,
 'narrow WR16/17 closure and WR18 software blocking only': f['software_acceptance']=='failed_WR18; WR16_and_WR17_passed_in_retested_scope; prior_stage0_1_scope_preserved' and f['stage_results'][2]['blocking_findings']==['WR-18'] and all(x['acceptance']=='未验收' for x in f['stage_results'][3:]) and f['financial_evidence'] is False and f['data_certification'] is False,
}
input_row=next(v for v in cloud['files'] if v['path']=='_engineering_task_input.py')
failure=read('recovery_agent/failure_settlement_result.json');settlement=f['tests']['new_recovery_failure_settlement_probes']
checks['25 Git75 implementations and one admitted archive input separated']=input_row['baseline_kind']=='admitted_input_archive' and input_row['baseline_reference']==f['platform_evidence_level']['input_baseline']=='source/audit/task_inputs/bfd00f2611fd4496b9498d4597618a8e.py' and all(v['baseline_kind']=='git75_cloud_source' for v in cloud['files'] if v['path']!='_engineering_task_input.py')
checks['four manual failure probes recorded separately with synthetic limits']=settlement['manual_scenarios']==failure['subcases']==4 and settlement['passed']==failure['passed']==4 and settlement['unit_methods']==0 and settlement['process_counts']==failure['stats'] and settlement['scope']==failure['limits']
lines=['只读报告 QA：未运行新测试，未访问平台，未修改正式报告或生产文件。', '']
for name,ok in checks.items():lines.append(('OK: ' if ok else 'ERROR: ')+name)
lines.extend(['', '逐行核对问题位置：Registry 416–425 确实只核对来源/部署hash及报告/引用；Bridge 625–642 确实另要求submission、完整deployment及非空raw_receipt。WR18的三负一正原始结果与报告描述一致；全局cap仍有效及合成账本、未真实执行的范围声明适当。',
 '历史证据摘要与350+14检查结果一致：1398旧证据文件、208原件+11引用、65开发raw输出、最终3328项清单/ZIP，以及首包漏6历史源的失败/修正均有保留。', '', '初次QA提出的两处编辑项均已解决；初稿QA保留为qa_first.txt/qa_report_first.py：',
 '1. 正式文本和JSON明确25份实现等Git75/cloud，另1份独立输入等原已准入归档。cloud_comparison为每行新增baseline_kind/reference、历史基线hash；输入基线引用明确。目录18份/其余8份已知可读/未认证全集的表述准确；cloud_comparison_first.json保留初版。',
 '2. 失败结算摘要现已按1程序/4合成手工探针全过记录，与5方法46子例分列；实际追加CLI28、synthetic finish6，worker0。明确Research fixed-check false不是一次真实Research运行失败，LEAN Runtime Error envelope也为合成，未扩大为真实原生失败认证。',
 '', '最终未发现需要进一步修改的实质性错误。WR16/17关闭限原及本轮已测范围；WR18阻断当前候选软件，阶段2整体及全系统未验收、financial_evidence=false，无扩大。',
 '', '读取时的文档 raw SHA256：'])
for name in ('formal_report.json','formal_report.txt','findings.json','cloud_comparison.json'):
 lines.append(name+' '+hashlib.sha256((R/name).read_bytes()).hexdigest())
lines.append('')
(O/'qa.txt').write_text('\n'.join(lines),encoding='utf-8')
print('\n'.join(lines))
