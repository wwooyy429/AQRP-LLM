from pathlib import Path
import importlib.metadata as metadata,json,platform,sys
import numpy as np
R=Path(__file__).parent
def read(name):return json.loads((R/name).read_text(encoding='utf-8'))
def write(name,data):(R/name).write_bytes((json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
D=read('source/audit/reviews/20261027-dc49f0f-windows/formal_report.json')
ev=read('evidence_agent/delivery_evidence_report.json');rc=read('recovery_agent/current_execution.json');pr=read('recovery_agent/parser_first_results.json');ar=read('receipt_agent/report.json')
bindings=read('original_probes/full_chain_bindings.json');raw=read('evidence_agent/developer_outputs_raw_verification.json')
sha='4a94430144cd3d9e4b5469bd2b6e4a48d80d5fc7'
assert ev['check_count']==466 and ev['passed_checks']==465 and ev['failed_checks']==1
assert rc['methods']==rc['passed_methods']==12 and rc['subcases']==36
assert pr['methods']==pr['passed_methods']==2 and pr['subcases']==7
assert ar['first_run']['methods']==ar['first_run']['passed_methods']==10 and ar['first_run']['subcases']==803
assert bindings[0]['actually_completed']==14 and bindings[0]['incorrect_rejections']==0 and bindings[1]['actually_completed']==6
assert raw['file_count']==raw['passed_files']==48 and raw['normalization_applied'] is False
assert read('runs/dc_annotations_with_fixture/role_corrected_summary.json')['success']
D.update(review_id='AQRP-20261027-4A94430-WINDOWS-10',reviewed_source_commit=sha,baseline_commit='dc49f0f3037918f3ce4413665c59b164a8d6e2b7',source_manifest_hash=ev['source_manifest']['hash'],source_manifest_files=112,git_files_verified=1331,execution_source_manifest_hash=ev['execution_source_manifest']['hash'],deployment_hash=ev['deployment']['local_candidate_hash'])
D['evidence_commits']['current_delivery']=sha
D['environment']={'os':platform.platform(),'python':platform.python_version(),'python_executable':sys.executable,'dependencies':{x:metadata.version(x) for x in ['numpy','pandas','python-dateutil','pytz','six','tzdata']},'longdouble_nmant':int(np.finfo(np.longdouble).nmant),'blas_threads_for_main_replays':1,'real_AlgorithmImports_executed':False,'local_Python311_executed':False}
write('environment.json',D['environment'])
D['stage_results'][0].update(evidence='407仓库、原24/36共享准入及465/466审计检查',notes=['WR15/P3：开发输出清单raw哈希声明需更正，非阻断'])
D['stage_results'][2].update(evidence='原最小新版0/旧版1；同14完整worker链新版14完成、旧版6完成8误拒绝；新增10/803及恢复2/7通过',blockers=['新版真实部署/输入和原生成功/完整失败回执缺证据','旧LEAN无已交付终态','历史US200及财务时点未认证'],status='待验收',scope='已测试离线任务/回执/恢复范围修复后通过；整阶段仍待真实平台与数据证据')
rows=D['tests']['suites'];rows[0].update(methods=407,passed=407)
rows[16]['id']='dc_recovery_replay';rows[17].update(id='dc_annotations_with_fixture',passed=12,errors=0);rows[18].update(id='current_parser_recovery',subcases=7)
rows.append(dict(id='new_fractional_boundaries',methods=10,passed=10,failed=0,errors=0,skipped=0,subcases=803,actually_executed=True))
D['tests']={'actually_executed':True,'suites':rows,'counts_are_overlapping_not_unique':True,
 'original_public_reproductions':{'unchanged_scripts':True,'WR14_candidate_exit':0,'WR14_baseline_dc_exit':1,'WR11_WR12_WR13_candidate_exits':[0,0,0,0],'unit_methods':None},
 'original_worker_probe':{'same_script_and_helper':True,'variants':14,'candidate_completed':14,'candidate_incorrect_rejections':0,'baseline_dc_completed':6,'baseline_dc_incorrect_rejections':8,'historical_labels_not_current_identity':True,'outer_binding':'original_probes/full_chain_bindings.json','unit_methods':None},
 'independent_worker_branches':ar['worker_and_ledger_design'],
 'audit_checks':{'checks':466,'passed':465,'failed':1,'failed_finding':'WR-15','unit_methods':0},'isolated_builds':{'executed':2,'exit_codes':[0,0],'all_1331_raw_files_unchanged':True},
 'developer_raw_output_verification':{'files':48,'passed':48,'normalization_applied':False},
 'command_logs':['runs/execution_records.json','runs/dc_annotations_with_fixture/command.json','original_probes/command_log.json','receipt_agent/command_log.json','recovery_agent/current_execution.json','recovery_agent/command_log.json','recovery_agent/parser_command_log.json'],
 'reviewer_measurement_corrections':{'annotation_first_replay':{'methods':12,'passed':11,'failed':0,'errors':1,'subcases':156,'error_records':1,'skipped':0,'product_failure':False,'reason':'Original suite expects official schema in OUT; first replay omitted the unchanged fixture; rerun in new output directory with exact raw schema passed12/160, original script/assertions untouched'},'evidence_first':{'checks':465,'passed':461,'failed':4,'reviewer_ZIP_target_selection_errors':3,'genuine_manifest_discrepancies':1,'reason':'Three checks selected nested historical reports instead of exact ZIP root formal_report.txt; correction preserves first run and keeps real raw mismatch failed. One additional CRLF diagnostic yields final466 checks'}},
 'historical_harness_limits':'原样56历史50/3/3及认可适配差异保留；原脚本be/dc字面量和按路径推断label不作本轮源码身份，current_execution/实际路径与raw哈希绑定4a。',
 'portable_runner':{'help_and_syntax_checked':True,'full_aggregate_executed':False,'individual_acceptance_runs_actually_executed':True}}
D['findings']=[{'id':'WR-15','priority':'P3','blocking':False,'source_commit':sha,'file':'audit/review_packages/wr14/developer_verification.json','lines':[76],
 'title':'开发输出清单的raw哈希声明对应CRLF工作区字节，与固定Git中的LF原件不一致',
 'trigger':'按developer_outputs_manifest_raw_sha256校验同提交developer_outputs_manifest.json的原始文件字节',
 'expected':'明确固定Git原件的raw哈希；若同时记录工作区CRLF值，应分别说明字节表示和来源',
 'actual':{'declared_raw_sha256':'44e8ff2bc0ce87a76ef52b2c3d7f4d263166ca5bb14f0aaf5474e1516c869ddb','Git_raw_sha256':'b8170f1c123ef3eb3991cb519206f7db8a700f6673f406121b5535f4411c8df5','Git_raw_bytes':16556,'CRLF_bytes':16917,'LF_to_CRLF_matches_declared':True},
 'impact':'按声明值无法校验固定Git文件；仅换行表示解释差异。清单内48份输出原字节全过，源码/执行身份/预算不受影响，因此P3非阻断',
 'minimal_reproduction':'python -B minimal_manifest_hash.py source（当前exit1；不修改文件）',
 'fix':'更正固定Git原件的校验值，或明确区分Git LF与工作区CRLF两套原始字节身份；保留原输出和原声明记录',
 'regression':'固定Git归档下载后直接read_bytes重算，并继续逐项核验48个原始输出；不使用隐式换行归一化冒充raw一致',
 'evidence_level':['E1','E2'],'introduced_by_this_commit':True}]
D['budget_replay']=dict(ev['budget_replay'],new_real_configurations=0,new_real_Research=0,new_real_LEAN=0,new_model_calls=0,authoritative_files_unchanged=True)
D['platform_state'].update(CI_success_run_ids=[40367991545],unchanged_from_previous_readback=True)
D['platform_state']['CI_jobs']=[{'id':j['id'],'name':j['name'],'status':j['status'],'conclusion':j['conclusion']} for j in read('github_ci_jobs.json')['jobs']]
D['historical_findings']['WR-14']={'status':'修复后通过','scope':'固定Python3.10普通小数秒、原MRE和14例完整链、原12/160与新10/803通过；保留WR13拒绝和原attempt恢复边界'}
D['historical_findings']['WR-13']['scope']='原未知annotations行/错误旁路、非字符串text及非法偏移在各自测试范围通过；此前单列的普通fraction兼容问题WR14已在本轮修复后通过'
D['software_acceptance']={'overall':'passed_in_reviewed_offline_scope_with_nonblocking_finding','WR14':'passed_after_fix','blocking_findings':[],'nonblocking_findings':['WR-15'],'shared_budget_tested_scope':'passed','stage0_1_prior_scope':'retained','whole_system':'not_accepted'}
write('formal_report.json',D)
text=f'''AQRP-LLM 独立修复复审正式报告
审核编号：{D['review_id']}
固定源码：{sha}
比较基线：{D['baseline_commit']}
审核日期：2026-10-27，Asia/Shanghai。

总体结论：WR-14在本轮实际覆盖的离线范围修复后通过，未发现新的阻断性软件缺陷。新增WR-15/P3为归档raw哈希声明的换行表示不一致，非阻断；不能称466检查全通过。阶段0/1及既有修复原范围保持，已测离线任务/回执/恢复范围通过；阶段2整体验收待真实平台与数据证据，完整系统未验收，financial_evidence=false。
证据E1静态/哈希/AST/固定合同，E2审核者实际Windows合成执行，E3开发归档原生JSON离线重解析，E4只读QC源码与GitHub PR/CI任务元数据，E5无。未修改开发者源码/真实预算/配置或旧报告；未提交、推送、批准、合并PR，无真实Research/LEAN/模型/部署/购买/交易；未轮询或读取待终态LEAN日志，未打开最终数据。

全系统覆盖矩阵
'''
for s in D['stage_results']:text+=f"阶段{s['stage']} | {s['modules']} | {s['implementation']} | {s['evidence']} | 阻断{s['blockers']} | {s['status']}；范围{s['scope']}\n"
text+='''
WR14修复验收
engineering_receipts.py:73–79只构造年月日做日历校验，主行77；时分秒、偏移和非空ASCII小数仍由原regex检查，AST独立确认regex未变。小数部分没有浮点转换、截断、补零或改写，原hint字符串保持。原minimal_fractional_clock.py当前exit0，旧dc仍exit1；同原fractional_clock_probe.py和helper，新旧worker共14例当前14完成，旧dc仍6完成8误拒绝。所有原输入与完成预期不改。子脚本按路径猜出的label可能为baseline_be94426或candidate，不作版本证明；actual_source_commit、实际source目录和receipt raw哈希由full_chain_bindings.json明确绑定。
原WR11/WR12/WR13公开脚本当前均通过；原12/160注解、15/80载体、12/36恢复和2/7新恢复也通过。新10方法803子例首跑无失败，0–6位点/逗号、登记大小写/空格/偏移/naive提示、世纪闰年、长数字串、未知注解、非字符串text及非法offset边界覆盖。两次真正纯Python合成worker执行（新采集/旧Research各一次），其已预扣状态作独立MemoryRegistry克隆；234合法观察分支完成、36非法分支拒绝，不能把它们说成234次worker。拒绝后纠正同一attempt也能完成，源fetch不新增、预算不重扣、行哨兵不入账。原12/36实际生产CLI/Filesystem Registry重放完整保留，新2/7在A→B与源码/目录漂移后验证4种合法fraction及3种拒绝控制，拒绝后纠正完成不退款不重交。

新增问题 WR15 / P3，非阻断
位置audit/review_packages/wr14/developer_verification.json:76。
字段developer_outputs_manifest_raw_sha256声明44e8ff2bc0ce87a76ef52b2c3d7f4d263166ca5bb14f0aaf5474e1516c869ddb，固定Git developer_outputs_manifest.json原字节实际b8170f1c123ef3eb3991cb519206f7db8a700f6673f406121b5535f4411c8df5。Git原件16556字节、361个LF/0CRLF；仅LF→CRLF后16917字节恰得声明值，JSON语义相同。附近未限定工作区表示，而.gitattributes强制JSON LF。清单内48份输出的原字节hash及长度独立全过，没有把换行归一化当作原字节通过。
影响是按声明值不能校验固定Git文件，属于证据元数据表达问题；所有实际输出、源码身份和预算仍可独立核验，故P3非阻断。建议更正Git原件值，或分别标明Git LF与工作区CRLF的字节身份，保留原声明/输出。回归应在Git archive/download后直接read_bytes验证两层清单，不隐式改换行。最小复现minimal_manifest_hash.py当前exit1。

实际执行，方法/子例分开，重叠不累计为独有测试
'''
for t in rows:text+=f"{t['id']}: 方法{t['methods']}，通过{t['passed']}，失败{t['failed']}，错误{t['errors']}，跳过{t['skipped']}，子例{t['subcases']}。\n"
text+='''
407仓库和所有最终验收单元套件均通过，无skip/expectedFailure冒充通过。原14完整链是14个参数化变体，不是14个额外单元方法；旧dc负对照的8错误拒绝保留，未覆盖。原样56历史50/3/3及认可适配差异、数值精度限制均保留。
审计466检查465通过1不符（WR15），0单元方法；其中48开发输出原字节全过。首审计465检查461通过4不符：3项是ZIP根正式报告目标选取测量错误，另1项是真实raw不符。修正目标、另存脚本/首报告，再加CRLF事实诊断后最终466仍保留1不符，未吞掉。原注解首重放12方法/156子例有1个环境错误：OUT缺固定schema，非产品问题；另建OUT复制原字节schema后原脚本/断言不变12/160全过，首失败输出也保留。两次隔离build exit0，1331文件全稳定，不计测试方法。

实际命令与环境
python -B tools/stages.py verify（runs/repository_source独立副本）
python -B run_main_checks.py（首次最后一项schema夹具缺失如上保留）
python -B run_schema_fixture_replay.py（原字节fixture补齐后原12/160）
python -B run_original_probes.py（原最小/公开接口及新旧14链）
python -B receipt_agent/independent_fraction_boundaries.py --source source --out receipt_agent
python -B recovery_agent/independent_recovery.py
python -B recovery_agent/new_parser_recovery.py
python -B minimal_manifest_hash.py source
全部展开命令、cwd、解释器及退出码见JSON command_logs。实际查询环境：
'''
text+=json.dumps(D['environment'],ensure_ascii=False)+'\n'
text+=f'''
版本、平台、预算及数据
1331固定Git原文件字节一致，112审核hash {D['source_manifest_hash']}。
执行hash {D['execution_source_manifest_hash']}，仅排budget.usage；111源码变更、3usage稳定、45政策变更和新增政策键探针通过。
本地29py部署hash {D['deployment_hash']}；配置hash {ev['deployment']['configuration_hash']}；实现hash {ev['deployment']['implementation_hash']}。两次本地build不是云端部署或实际运行。
旧dc188原件+8引用全部匹配；完整旧3579 artifact及三版ZIP CRC/根正式报告核对通过，旧935份证据和20 SDK不变，原Role/措辞/格式修正与失败记录保留。12事件、37保护文件、Registry/WR12 CLI/config/flags均未改。
'''
text+='''
本轮先list_projects，再只读38436695项目；仅保存核对.py，未解析notebook内容。26个Python条目=25旧部署源+1独立工程输入，与dc轮逐路径无变化。源仍旧75，云部署hash dad57a0513899dc5ed89cef637d648229dd1c5c1b31bb70583ff95962c1c5bc6，距候选12路径；工程输入SHA95092b4de264c961895655f0853de639981143ad8cdb41e2c0d22b0adc7136b0绑定旧bfd00f2611fd4496b9498d4597618a8e，不能认证新版输入。
旧LEAN39cafa1e9b11f91b27e396b66d033a6d只归档pending，当前终态null，未轮询/读日志/重交。PR1/2仍open/draft/unmerged，PR2 base6a1edbf、head精确4a。独立只读CI40367991545，两任务synthetic-checks(3.10)/(3.11)均completed/success；这不是审核者在本地实际运行Python3.11或真实SDK的证据。
预算配置6/12（正常6预留0）、Research9/20（正常6预留3）、LEAN1/16（正常1预留0）。本轮实际新增三类和模型调用0，合成副本使用量不写真实账本；早期aggregate不冒称逐项独立重建。2024–2025暴露保持，2026独立性null；具体GPT模型/次数/费用限额null，正式研究/最终测试/交易关闭。

未验证与下一步
WR14可在本轮明确离线范围关闭。WR15是非阻断元数据更正任务，不需要新增真实执行。阶段2仍需新版真实部署/输入读回、原生成功与完整失败回执、旧LEAN已交付终态，以及完整历史US200、SID/分类/公司行动、财务版本/公开/实际送达/摄入证据；阶段3–7各自缺失交付仍需验收。不能由软件范围通过推断金融有效或无人值守真实研究已就绪。
聚合重现入口本轮仅检查语法/help，各底层命令已分别实际执行；不声称聚合整段重跑。重复生成源码case副本不入包，独立测试/合成生成器/命令/输出完整保留可重建，旧临时目录未删除。

可运行原WR14最小复验（当前exit0，旧dc exit1）
'''
text+=(R/'minimal_fractional_clock.py').read_text(encoding='utf-8')
text+='\nWR15非阻断最小复现（当前exit1）\n'+(R/'minimal_manifest_hash.py').read_text(encoding='utf-8')
text+='\n完整机器可读JSON\n'+json.dumps(D,ensure_ascii=False,indent=2)+'\n'
(R/'formal_report.txt').write_bytes(text.encode('utf-8'))
print(json.dumps({'review_id':D['review_id'],'WR14':'passed_after_fix','nonblocking':['WR-15'],'blocking':[],'suites':len(rows)},ensure_ascii=False))
