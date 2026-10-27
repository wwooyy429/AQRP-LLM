"""Read-only report consistency QA; no product test or platform call."""
from pathlib import Path
import hashlib,json
R=Path(__file__).resolve().parents[1];O=Path(__file__).resolve().parent
read=lambda p:json.loads((R/p).read_text(encoding='utf-8-sig'))
f=read('formal_report.json');findings=read('findings.json');e=read('evidence_agent/evidence_verification.json');b=read('evidence_agent/build_preview_verification.json')
checks={
 '固定2374raw文件及122源码身份':f['Git_archive_files']==e['source']['files']==2374 and f['source_manifest_files']==e['source']['review_files']==122 and f['source_manifest_hash']==e['source']['review_hash'] and f['execution_manifest_hash']==e['source']['execution_hash'],
 '部署/实现/活跃配置hash':f['deployment_hash']==e['deployment']['local_deployment_hash'] and f['implementation_hash']==e['deployment']['implementation_hash'] and f['active_configuration_hash']==e['deployment']['active_configuration_hash'],
 '634=633通过+1非阻断WR19且0unit':f['tests']['metadata_checks']['checks']==634 and f['tests']['metadata_checks']['passed']==633 and f['tests']['metadata_checks']['failed']==1 and f['tests']['metadata_checks']['unit_methods']==0 and e['check_count']==634 and e['passed_checks']==633 and e['failed_checks']==1,
 '首634的6条CRLF测量错误与1条真实差异区分':e['first_run_measurement_correction']['measurement_errors']==6 and e['first_run_measurement_correction']['real_metadata_discrepancies']==1 and all((O/p).is_file() for p in ('verify_evidence_first.py','evidence_verification_first.json','evidence_first.stdout.txt','evidence_first.stderr.txt')),
 '两build两preview及2374不变':f['tests']['build_preview']=={'builds':2,'CLI_previews':2,'each_exit_code':0,'files_unchanged':2374,'valid_preflight':'accepted','stale_deployment':'rejected'} and b['candidate_source_unchanged'],
 '12事件及6/9/1原pending身份':all(f['budget_replay'][k]==e['budget'][k] for k in ('events','usage','limits','pending_attempt')) and f['budget_replay']['new_real_charges']=={'configurations':0,'research':0,'lean':0,'model_API':0},
 '独立/开发归档与引用计数':len(e['developer_originals'])==62 and len(e['prior_independent_archive']['originals'])==463 and len(e['prior_independent_archive']['reused'])==21 and e['prior_independent_archive']['full_artifact_entries_verified']==3902 and e['old_evidence_files_unchanged']==1674,
 '非阻断WR19正式finding一致':f['findings']==findings and len(findings)==1 and findings[0]['id']=='WR-19' and findings[0]['priority']=='P3' and findings[0]['blocking'] is False and findings[0]['location']=={'file':'audit/stage2_current_readiness.json','line':124},
 '本轮无QC与上轮历史平台证据区分':f['platform_evidence_level']['current_cloud_source_commit'] is None and f['platform_evidence_level']['current_cloud_deployment_hash'] is None and f['platform_evidence_level']['full_cloud_inventory_certified'] is False and f['platform_evidence_level']['candidate_runtime_verified'] is False and f['backtest_terminal']['current_platform_status'] is None and f['backtest_terminal']['status_results_logs_read'] is False,
 'WR18仅已测离线范围通过/阶段2整体仍待验收':f['software_acceptance']=='passed_retested_WR18_and_offline_regressions; nonblocking_WR19_open; full_stage2_pending' and f['stage_results'][2]['acceptance']=='已测离线软件通过；整体验收待定' and all(v['acceptance']=='未验收' for v in f['stage_results'][3:]) and f['data_certification'] is False and f['financial_evidence'] is False,
}
archive=R/'source/audit/reviews/20261027-ae2b898-windows'
manifest=json.loads((archive/'source_git_manifest.json').read_text(encoding='utf-8-sig'))['candidate'];comparison=json.loads((archive/'cloud_comparison.json').read_text(encoding='utf-8-sig'))
candidate={k[6:]:v for k,v in manifest['files'].items() if k.startswith('cloud/') and k.endswith('.py')};reference={v['path']:v['cloud_utf8_sha256'] for v in comparison['files'] if v['path']!='_engineering_task_input.py'}
different=[k for k in candidate.keys()&reference.keys() if candidate[k]!=reference[k]];outside=set(candidate)-set(reference)
mre=read('wr19_confirmation/execution_record.json')
checks['root最小MRE归档版本/29与25路径/9+4及exit1']=manifest['commit']==comparison['reviewed_source_commit']=='ae2b8985f3799c246e90341370f86d80483f63ed' and len(manifest['files'])==1843 and len(candidate)==29 and len(reference)==25 and len(different)==9 and len(outside)==4 and mre['exit_code']==1 and mre['script_sha256']==hashlib.sha256((R/'minimal_wr19.py').read_bytes()).hexdigest()
lines=['最终报告只读QA完成。未运行新软件测试、未访问QC/市场/模型、未修改正式报告或生产文件。','']
for name,passed in checks.items():lines.append(('OK: ' if passed else 'ERROR: ')+name)
lines.extend(['', 'WR19定位准确：固定source audit/stage2_current_readiness.json:124原声明12；nested candidate_commit=ae。独立Git raw/LF计算及root仅用归档source_git_manifest/cloud_comparison的最小脚本均为9条不同+4条不在旧25已知参考=13。正式报告明确不认证实际当前云端缺4或全集，顶层dc49历史12没有被判错或覆盖。',
 '主报告634检查、两build/preview、预算和历史归档表述与本代理原结果一致。首次6条CRLF解析测量错误及原件保留，最终1条声明差异仍明确显示，不扩大为产品测试失败。62份开发raw回归也未被称为本代理的独立软件结果。',
 'WR18软件结论以root/准入/恢复代理实际回归为依据；其关闭限定已测接口合同和合成环境。整体阶段2、真实原生成功/失败回执、数据覆盖、阶段3–7和金融有效性仍未认证。',
 '', '未发现需要修改的实质性错误。QA对现有文档的读取和算术复核不新增634软件检查或单元方法数。', '', '读取时文件raw SHA256：'])
for p in ('formal_report.json','formal_report.txt','findings.json','minimal_wr19.py'):lines.append(p+' '+hashlib.sha256((R/p).read_bytes()).hexdigest())
(O/'qa.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8');print('\n'.join(lines))
