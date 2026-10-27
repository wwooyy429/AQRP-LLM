# deb85d9 独立审核的选择性归档

本目录保存外部独立审核的原字节报告、复现脚本、首次结果、测试日志和证据清单。它是开发者的归档工作，不是新一轮独立审核，也未重新执行产品或审核软件测试。

原审核结论：WR-21/P1、WR-20/P2 阻断本轮软件验收；阶段2整体未通过。原生失败恢复、受控worker诊断及历史回归仅保留报告所列局部范围通过。G1真实成功链缺失，G2旧worker差异证据不足，G4完整历史US200和财务来源认证不足。原账本17事件、预算7/10/1和本轮2/2/1停止条件保持，最终测试关闭。

原完整审核包为 `B:/BaiduSyncdisk/学习/投资/量化/量化交易比赛/LLM审核/review-deb85d9-20261027.zip`；SHA-256为 `19d2614008caf209c18b79e16220826de0394ee9a86f585f32ccce5a9bfd6b49`。目录及ZIP逐文件哈希、完整清单和Git源码原字节由 `developer_archive.py` 只读核对。详细结果见仓库 `audit/deb85d9_review_archive_check.json`。

为避免重复归档，未复制原包 `source/`、`baselines/` 下的固定Git源码树，也未复制 `change.diff` 和 `PR_complete_patch.stdout` 两份全量补丁。两份大型完整清单 `artifact_manifest.json`、`source_git_manifest.json` 保留在外部原包，Git记录原路径、原字节SHA-256、大小及实际核对结果。新问题的 `cert_agent`、`entry_agent`、`entry_additional`、`wr20_confirmation`、`wr21_confirmation` 子树完整保留；`native_agent` 保留脚本、汇总、首次结果和命令清单，省略逐条commands输出；其他历史重放子树省略，顶层首次/回归输出和执行索引保留。所有省略原件继续保留在完整包中；被省略逐条输出的哈希索引不能代替对应内容。

源码可由原包 `source_git_manifest.json` 所列固定Git提交重建。选入原件及用户粘贴报告保持原字节；`developer_archive_selection.json` 逐项列出选入原件及各自哈希，并记录精确选择规则、遗漏类别数量/大小及外部清单哈希，避免重新重复列出上万份Git源码。原 `artifact_manifest.json` 和 `verify_artifacts.py` 对应完整包，不能直接作为本选择性目录的完整性验证入口。完整目录和ZIP均有12475个文件，其中12474个文件登记在 `artifact_manifest.json`，清单自身是未自登记的第12475个文件；报告的12474是受清单校验文件数。

重新运行反例时，应把固定源码和所需独立脚本复制到新的临时工作区，按原 `formal_report.txt` 和原 `README.txt` 的布局运行；不要修改本目录原件，也不要把审核报告生成脚本重跑后覆盖原结论。原 `README.txt` 的编码显示问题保持原字节，不在归档时修写。

本目录新增的 `DEVELOPER_ARCHIVE_README.md`、`developer_archive.py`、`developer_archive_selection.json` 和 `.gitattributes` 是明确标注的开发者归档材料；原审核者没有审核这些新增材料。归档不包含新增市场调用、模型调用、部署、账本写入或独立金融测试。
