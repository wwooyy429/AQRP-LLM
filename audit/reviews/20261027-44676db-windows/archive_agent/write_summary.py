from pathlib import Path
import hashlib,json
R=Path(__file__).resolve().parent
def read(p):return json.loads((R/p).read_bytes())
def write(p,v):p.write_bytes((json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode())
s=read('report.json');m=read('wr27_report.json');hashes=lambda p:hashlib.sha256((R/p).read_bytes()).hexdigest()
summary=f'''本子审查固定 {s['reviewed_source_commit']}，基线 {s['baseline_commit']}。来源／预算／归档范围67/67静态检查通过；WR27修复专项9/9检查组通过，未发现本子审查范围新增问题。静态检查及元数据CLI不计产品unit方法，WR25/26生产数据审计由其他子审和主审判定；不能扩展为模块或阶段2整体通过。

5433份候选原文件逐一等于固定Git原字节。review清单145文件，source {s['source_manifest_hash']}；稳定execution {s['execution_source_manifest_hash']}，仅排除budget.usage。31文件deployment {s['deployment_hash']}；implementation {s['implementation_hash']}；使用UTF8/BOM兼容、LF规范化并保留EOF。生成配置按权威config独立重算；经济配置272e2461117c36aec1c4470d13d2e47ee47fccdaab86b92f31fd11f922701f94及全部config原字节不变。开发tested141=review145减4个额外根文件，并非漏审；6个cloud/tests/tools Python实际变化与当前列表吻合。

真实17事件原字节等于ccad，SHA {s['budget']['journal_raw_sha256']}；旧13前缀及事件链完整。独立重放和内存Registry快照一致：配置7/12（normal6 reserve1），Research10/20（normal6 reserve4），LEAN1/16（normal1 reserve0）；工程2/2/1，cap2/2/2，已触发停止。保护39项runtime/input/tool-observation/budget/exposure原件及4745份旧review/review_packages原件字节不变；此39包含data_exposure，定义不同于开发38项。

原f5d原生packet14ae4a…、response6a537…保持；项目38436695/index1、attempt/config/plan/input/deployment/dispatch绑定和submission/completion内容地址均一致。仍是1次真实失败的2个相同载体、9条traceback项目/43物理行；底层来源迭代原因未知，无成功产物。实际云端执行仍7fc5ef2e9d2379d29f48d05a1f3cc760000884d6；前轮独立只读32源码记录在本轮仅离线重解析，当前31实现与该旧参考28同3异，不是当前云端读回或worker认证。

上一轮完整ZIP39319686字节，SHA 2ffc9089ad19a5675d18cafb5379262db7c99a431e518ae4f52cb2dd094b313c；15119份清单登记项加清单自身=15120完整文件，目录和ZIP逐文件重核。新选择性归档381份原件共1581651字节、省略14739份，原Git快照4977/4541/4204与完整原清单一致。选择规则、387项本地inventory加自身=388文件、三份外部清单、用户粘贴原件全部准确；未将选择目录称完整包。

新开发证据61项manifest原字节均真，668方法最终日志/source身份一致，开发重放不等于独立验收。所称省略binary Git index未被转码成源码、也未冒称审核者原日志：原件实际可读于B开发项目.git/repair-work/wr25_wr27/wr27/fixed_prepare.index，740565 bytes，raw SHA2ff2e0dab64f5a800a5ea8d56029f93e36f0de4be9b8970ac99686aa30e3843f，与省略记录完全相同；首次UnicodeDecodeError与仅打包修正说明保留且为真。

WR27：原始MRE字节SHA915a642e63991ebe0971bdbb120721605ff334c9309c204dc60b73eb18d97d23，在ccad负控退出1，默认0／错误S hash0／正确T hash1。原字节直接对新版首次退出1，是脚本固定旧ea基线断言在任何产品CLI前失败，不能当新版产品失败；原输出完整保留。仅修改C/B两个固定版本常量（ccad→446、ea→ccad），断言与预期不变，新版MRE退出0，默认S0／错误S hash1／正确T hash0，原源码及真实Git index保持。两常量diff和hash见wr27_scope_adapter.*。

独立补充：从S工具对真正不同的T目录，绝对路径和相对路径均接受正确T；随机hash、缺diff路径、错误历史原文、缺Git对象、错Git基线／diff、T预算原字节改变、T账本原字节改变7个CLI拒绝均正确。stages.source_manifest的默认S、绝对T、相对T与独立145文件清单逐项一致；S→T→S默认结果及globalROOT不被污染。当前6文件清单及带ccad/7fc身份的旧历史描述原文保持。

专项统计：3次MRE运行（旧负控、原字节新版范围不适配、仅版本常量适配新版正控），其中范围不适配0产品CLI；两条完整MRE内6次元数据CLI，追加相对路径及7负向共8次，总14次。另有9个检查组，含7个负向CLI场景，所有计数有包含关系，不作独有方法总数；独立产品unit方法0。旧MRE字段名称含false_accept/false_reject为保留的历史标签，新结论仅按实际退出状态，不将标签当当前缺陷。

本子审查真实QC／Research／LEAN／模型／部署／交易／真实账本写入及生产源码／真实Git索引写入均0；仅隔离index和合成副本写入。真实成功联合链、旧worker具体源码差异、完整US200／财务版本／真实可用时点和金融有效性仍未认证，financial_evidence=false。
'''
(R/'report.txt').write_bytes(summary.encode())
execution={'reviewed_source_commit':s['reviewed_source_commit'],'source_archive':{'static_checks':67,'passed':67,'unit_methods':0},'WR27':{'check_groups':9,'passed':9,'negative_target_CLI_scenarios':7,'MRE_runs':3,'original_byte_ccad_negative_exit':1,'original_byte_new_scope_exit':1,'original_byte_new_scope_product_CLI':0,'adapted_MRE_positive_exit':0,'metadata_CLI':14,'unit_methods':0,'scope_adapter_only_two_version_constants':True},'counts_are_overlapping':True,'new_findings':[],'financial_evidence':False,'real_platform_budget_source_Git_index_writes':0}
write(R/'execution_summary.json',execution)
write(R/'findings.json',[])
write(R/'reviewer_exploration_notes.json',{'read_only_exploration_note':'A guessed DEVELOPER_ARCHIVE_README.md filename did not exist; rg --files located ARCHIVE_SCOPE.md and developer_archive_helper.py. No product command/test was executed by the failed filename read.','new_MRE_scope_error':'Preserved separately from true old-negative and new-positive; original old-baseline assertion rejected before metadata CLI.','all_original_outputs_preserved':True})
names=['report.json','report.txt','wr27_report.json','execution_summary.json','first_execution.json','wr27_first_execution.json','wr27_scope_adapter.json','wr27_scope_adapter.diff','original_minimal_wr27.py','adapted_minimal_wr27.py','omitted_developer_artifact_verification.json']
write(R/'deliverable_hashes.json',{p:hashes(p) for p in names})
print(json.dumps(execution,ensure_ascii=True))
