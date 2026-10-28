WR-28/P2 审计交付修复候选

原独立审核固定4a42c18f0b78bea2068d589bc12f1615712354c6。EOF-v2功能的已测范围通过；保护清单混入三个本地CRLF哈希，原干净Git交付检查失败，候选整体未通过。原正式报告与失败/审查器修正记录紧凑保存于audit/reviews/20261028-4a42c18-eofv2；原错误清单保持原字节，原checker及artifact_manifest另封存于originals。

修复仅在audit下进行：新保护清单从固定8d65c29原始Git blob生成，并核对4a42c18和1cf2657同122文件一致；同时固定SHA256、Git blob编号及字节数。校验不转换换行，原错误声明只作为来源保留。固定662ccd源码夹具只用于合成重放，使检查可以在无.git的原始Git导出执行，不代表worker文件实取。

主工作树原有CRLF文件不作改写。复验应使用固定Git原始导出或正常LF检出。原样运行以下标准库审计入口，可从不可变本地Git对象重建新清单，已有不同输出将拒绝覆盖：
python -B audit/review_packages/deployment-eof-v2/build_git_protection.py --repository . --output audit/review_packages/deployment-eof-v2/protected_git_baseline.json

单元边界（开发方测试，不是GPT Work独立批准）：
python -B audit/review_packages/wr28/test_git_protection.py -q

固定新交付提交完成后，运行两个独立raw Git导出、一份LF检出、13个正反端到端检查、两次幂等build及官方825仓库合成测试：
python -B audit/review_packages/wr28/verify_wr28_end_to_end.py --commit <固定40位新交付提交> --evidence-dir <新的空结果目录> --full-verify

结果目录不得覆盖已有证据。临时源码导出自动清理，Git仅保存小型结果/日志，不重复保存完整源码树。生产cloud/config/tools/tests/docs源码、原权威预算/任务/数据暴露记录不变。

当前仅11项开发方原始Git边界检查通过；完整新提交干净交付检查等待记录。WR-28仍待独立复验，阶段2整体未验收。预算12/12、15/20、2/16及48事件保持；无QC、Research、LEAN、模型、供应商调用或新增登记/扣费/退款。原LEAN仍Runtime Error/failed，七项成功检查及订单数null。正式研究、自动GPT、交易、最终测试继续关闭，2024–2025暴露及2026独立性未认证事实保留。
