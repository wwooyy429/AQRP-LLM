"""Read-only final metadata report QA; no suite/build or identity recomputation."""
from pathlib import Path
import hashlib,json
R=Path(__file__).resolve().parents[1];O=Path(__file__).resolve().parent
read=lambda p:json.loads((R/p).read_text(encoding='utf-8-sig'))
f=read('formal_report.json');e=read('evidence_agent/metadata_verification.json');first=read('evidence_agent/metadata_verification_first.json')
identity=read('identity_agent/candidate844.stdout.json');ic=read('identity_agent/identity_checks.json');comparison=read('comparison_agent/results.json')
group={x['name']:x for x in f['tests']['metadata_check_groups']}
checks={
 '591/591归档组与0软件方法/套件/构建':group['archive_provenance_budget']=={'name':'archive_provenance_budget','checks':591,'passed':591,'failed':0} and e['check_count']==e['passed_checks']==591 and e['failed_checks']==0 and all(f['tests'][k]==0 for k in ('software_unit_methods','software_subcases','software_suite_runs','builds')),
 '首590/589加1条过严阅读断言及新增d0细表核对':first['check_count']==590 and first['passed_checks']==589 and first['failed_checks']==1 and e['reviewer_first_measurement']['product_or_metadata_defects']==0 and f['tests']['reviewer_first_measurement']['checks']==590 and f['tests']['reviewer_first_measurement']['passed']==589 and f['tests']['reviewer_first_measurement']['overstrict_reader_assertions']==1 and f['tests']['reviewer_first_measurement']['product_failure'] is False,
 '首脚本报告及raw记录真实保留':all((O/p).is_file() for p in ('verify_metadata_first.py','metadata_verification_first.json','first.stdout.txt','first.stderr.txt','execution_record.json','corrected.stdout.txt','corrected.stderr.txt','corrected_execution_record.json')),
 '2890raw固定Git及源不变':f['Git_archive_files']==e['source']['raw_files']==2890 and e['source']['equal_fixed_Git'] and e['source']['unchanged_after_checks'],
 '22开发/487原件/27引用/4754旧artifact/2202旧证据':len(e['developer_originals'])==22 and len(e['prior_independent_archive']['originals'])==487 and len(e['prior_independent_archive']['reused'])==27 and e['prior_independent_archive']['full_artifact_entries_verified']==4754 and e['old_evidence_files_unchanged']==2202,
 '预算12事件6/9/1与原pending引用':all(f['budget_replay'][k]==e['budget'][k] for k in ('events','usage','limits','pending_attempt')) and f['budget_replay']['new_real_charges']=={'configurations':0,'research':0,'lean':0,'model_API':0},
 '123源码和新两身份/原部署实现配置hash引用正确':f['source_manifest_files']==len(identity['source_files'])==123 and all(f[k]==identity[k] for k in ('source_manifest_hash','execution_manifest_hash','deployment_hash','implementation_hash','active_configuration_hash')),
 '148身份/37比较组分列且115原字节保护文件':group['identity_and_runtime_scope']['checks']==ic['metadata_checks']==ic['passed_checks']==148 and group['comparison_and_negative_variants']['checks']==comparison['metadata_checks']==comparison['passed_checks']==37 and f['runtime_identity_check']['protected_unique_files']==ic['protected_unique_files']==115 and f['runtime_identity_check']['runtime_semantic_changes_detected']==0,
 'WR19现13与原12/历史dc49保留':f['WR19_acceptance']['total_different_or_outside']==e['WR19']['computed']==13 and f['WR19_acceptance']['same_hash']==len(e['WR19']['same'])==16 and f['WR19_acceptance']['different_hash']==len(e['WR19']['different'])==9 and f['WR19_acceptance']['not_in_reference']==len(e['WR19']['outside_known_reference'])==4 and f['WR19_acceptance']['original_claim12_preserved'] and e['WR19']['historical_dc49_files_unchanged']==189,
 '无新软件批准且阶段2及金融边界准确':f['software_acceptance_bound_to_commit']=='81fbe5294055423e88ee5aeae48ca6223e7971da' and f['software_acceptance']=='retained_81fbe52_scope; no_new_software_test_or_approval_at84414ab' and f['metadata_acceptance']=='WR19_passed_at84414ab' and f['findings']==[] and f['data_certification'] is False and f['financial_evidence'] is False and all(x['acceptance']=='未验收' for x in f['stage_results'][3:]),
 '本轮无平台读取/部署与当前终态未知':f['platform_evidence_level']['current_cloud_source_commit'] is None and f['platform_evidence_level']['current_cloud_deployment_hash'] is None and f['platform_evidence_level']['full_cloud_inventory_certified'] is False and f['platform_evidence_level']['candidate_runtime_verified'] is False and f['backtest_terminal']['current_platform_status'] is None and f['backtest_terminal']['status_results_logs_read'] is False,
}
lines=['只读最终报告QA完成；未重跑软件、构建、平台调用或身份函数，未改源和正式报告。','']
for n,p in checks.items():lines.append(('OK: ' if p else 'ERROR: ')+n)
lines.extend(['', '首590项中589通过/1条过严阅读断言的分类准确：当前说明合理澄清ae9+4=13，原错误readiness、dc49归档和d0历史细表均保留。修正阅读方法并增加历史表核对后591/591，原记录及raw没有被替换为全通过假象。',
 '22份开发原件及Git-export/453输出被限定为开发归档。487份旧独立原件、27引用、4754项旧最终封包及2202旧证据的表述与本代理逐字节核对结果一致。引用完整性没有被当作原生回执或远程来源认证。',
 '新2890源码等Git；123源码清单及新source/execution身份引用与身份代理结果一致，部署/实现/活跃配置保持。QA只读取身份代理结果，不重新计算身份。',
 'WR19关闭仅限元数据更正；报告明确4个参考外路径不证明当前云端缺4或全集，本轮无新QC。软件通过仍绑定81固定范围，完整阶段2、阶段3–7、真实原生终态/运行、数据与金融认证未扩大。',
 '', '未发现待改实质错误。QA文档一致性读取不增加报告元数据组或软件方法计数。', '', '读取时raw SHA256：'])
for p in ('formal_report.json','formal_report.txt'):lines.append(p+' '+hashlib.sha256((R/p).read_bytes()).hexdigest())
(O/'qa.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8');print('\n'.join(lines))
