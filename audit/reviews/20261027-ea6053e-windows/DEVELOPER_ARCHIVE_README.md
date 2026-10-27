# 固定ea6053e独立审核的选择性归档

本目录原报告的审核源码为 `ea6053e3e9ef4be17db246daf18a4cf9b2e5be58`。独立结论：WR-20和WR-21原触发场景在此版本修复后通过；新增WR-23／P1、WR-22／P2仍阻断当前模块整体软件验收，WR-24／P3为非阻断元数据问题。阶段2整体未通过，不能将两个原反例通过扩大为模块、全系统、数据或金融有效性通过。

`formal_report.json`、`formal_report.txt`及选取的原审核脚本、首次/最终输出、修正记录、封包核对结果均保持原字节。`user_pasted_report.txt`是用户粘贴原件；`.gitattributes`、本说明、`developer_archive.py`、`developer_archive_initial.py`、`developer_archive_attempts.json`及`developer_archive_selection.json`属于开发归档元数据，不是独立审核者的新增结论，也不计入原审核文件数量。

完整原包位于 `B:/BaiduSyncdisk/学习/投资/量化/量化交易比赛/LLM审核/review-ea6053e-20261027.zip`，SHA-256为 `3eb0d548f2667c83c24e62f88495ae02fa2c8942440ce0c4aa665bb06b054753`。原目录为同名无.zip目录。清单登记14165个文件，包含清单自身时完整目录和ZIP共14166个文件。本仓库仅保留选取材料，**不是完整原包副本**。

原`archive_agent/first.stdout`及`dispatch_agent/legacy_original/crash_addendum/first.stdout`为非UTF-8字节，留在完整原包并按原路径/原字节哈希引用，未转码或冒充同字节文件。对应首次JSON、stderr及修正记录继续选取。开发归档器第一次因此停止的记录与初始脚本保留，属于归档读取器修正，不是新增产品缺陷。

`developer_archive_selection.json`精确列出本次保留的原件路径、字节数和SHA-256，列出省略类别与可重建的精确选择规则。完整`artifact_manifest.json`、`source_git_manifest.json`保留于已校验完整原包，Git内记录其原路径、原字节哈希及大小。重复固定source/baselines树、Git tar二进制输出、全量大patch、部分历史逐条重放输出均省略，可从原包或经过核对的固定Git提交重建对应内容。两份manifest的完整包含义不能用于宣称本目录包含所有清单成员。

归档程序只读核对完整包全部清单、ZIP成员及三个固定Git源码快照，再复制选定原字节；不会运行产品或独立测试脚本，不访问QC或模型，不改真实账本或预算，不提交Git。需要复现测试时，在新隔离目录重建固定源码并使用锁定依赖，保留原脚本与必要的显式路径/夹具适配。归档脚本里的旧来源路径是证据来源，不保证其他机器可直接运行。

当前真实账本仍为17事件，预算配置7/12、Research10/20、LEAN1/16，工程2／2／1停止门保持。实际云端执行仍按历史记录为7fc5ef2；本审核无当前平台读取，28相同／3不同仅为已存31文件参考的离线比较，不认证当前云端inventory或候选运行。真实成功联合链、旧worker差异、完整US200、财务版本及真实送达/摄入证据仍不足。正式研究、自动GPT、交易及最终测试继续关闭，2024–2025已暴露、2026独立性未知，`financial_evidence=false`。
