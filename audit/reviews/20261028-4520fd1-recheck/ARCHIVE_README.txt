本目录归档用户提交的独立审核 AQRP-20261028-4520FD1-RECHECK-22。

固定审核资料：4520fd1a4421a9b764d2bfd61e5fb5cf4b59a9c8。
实际云端修复源码：662ccd876b67ca0949f921a53c4c33df37cfbbf1。
结论：已测局部软件范围通过；Phase 2整体未验收；本轮无新增产品发现。
认证计算内核已有实现；财务数值字段目录0、计费认证派发桥未实现。
Research的13项检查获归档元数据级复验支持；LEAN的7项实际结果仍缺。
本次归档不产生新的运行授权，不执行QC/模型调用，不增加或退还预算。

evidence/保留本轮正式报告、首次失败、修正说明、独立测试与执行日志的原始字节。
user_delivery.txt为用户提供的消息原文。本目录没有重写审核者正式报告。
import_index.json是开发侧归档索引，不是新的独立批准。

原始完整封存ZIP保留在用户明确提供的位置：
B:/BaiduSyncdisk/学习/投资/量化/量化交易比赛/LLM审核/review-4520fd1-20261028-recheck.zip
SHA256: 3b2ab178256fff1ac49a049fb5a4659584cba57e1e2159368cfe5d0fd919189d

导入时已实际检查完整6139项manifest、5976份固定Git源码和ZIP全部条目/CRC。
Git中不重复复制完整source/树、prior_evidence/历史原件或两份完整清单。
它们仍在原封存ZIP中，原始清单及ZIP哈希记入import_index；这是存储去重，
并非删除证据、删掉失败记录或缩改正式审核范围。

本紧凑归档的自检入口（仓库根目录，离线、不修改账本）：
python -B audit/reviews/20261028-4520fd1-recheck/verify_import.py

如需重新检查完整原始封存ZIP：
python -B audit/reviews/20261028-4520fd1-recheck/verify_import.py --original-zip "B:/BaiduSyncdisk/学习/投资/量化/量化交易比赛/LLM审核/review-4520fd1-20261028-recheck.zip"

evidence/verify_artifacts.py是审核者原始脚本，原样保留；它必须在完整原包中执行，
不适用于省略重复source的本紧凑归档。其导入验证不被记作重跑765项产品测试。
最小合成测试可使用evidence/minimal_occurrence_known_answer.py --source 仓库根目录；
正式命令、首次输出及修正后的输出以原报告和各execution.json为准。

预算仍为配置12/12、Research15/20、LEAN2/16，原LEAN仍是未取得终态的pending快照。
不得把没有新WR解释为阶段2通过、已经无人值守运行、金融有效或最终样本独立。
2024–2025已暴露；2026独立性未认证；正式研究、自动GPT、交易及最终测试继续关闭。
