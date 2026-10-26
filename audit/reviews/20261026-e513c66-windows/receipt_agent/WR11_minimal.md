# WR-11 / P2：双载体冲突被静默忽略

固定 `e513c66e5965133fbe83fb0ab987eae853f96260`。`cloud/qresearch/engineering_receipts.py:92-93` 在result含非空structuredContent时直接返回，未检查并存content。`collection_execution.py:140`随后把该观察标为stdout_only=True、marker_count=1。

运行同目录 `minimal_parallel_output.py`，传入 `--source <固定归档source> --out <输出json>`。脚本通过真正的 `prepare_task` 生成并核对惰性输入，在临时合成部署/云store上运行worker，生成固定marker，再用 `execute_metadata_command(research-result)` 完整走Bridge/Registry。CLI的current_bridge/export_usage仅在本进程绑定合成Registry/内存导出，未碰真实账本。

| 变体 | 预期 | 实际 |
| --- | --- | --- |
| 只有合法structuredContent | completed | completed |
| content与structuredContent完全等价 | completed | completed |
| structuredContent合法、content另含打印合成行 | 拒绝 | completed |
| structuredContent合法、content另含display_data合成行 | 拒绝 | completed |
| structuredContent合法、content另含error且status=error/success=false | 拒绝 | completed |

三个误接受均保存stdout_only=True、marker_count=1，报告market_values_exported=False。行sentinel未持久化到Registry，Registry保留原result的digest；缺陷是额外输出/错误被忽略并作出不实认证，不是本次发现了真实市场行外传。最小完整原生形状与结果在 `minimal_parallel_output.json`。

`engineering_receipts.py`与已归档7bf文件SHA-256同为 `69326601a5180487695a66e7dc5d7f858efdfac691c49f72b85958948680491d`。此问题在本固定候选新增采集路径中复现，根因来自继承共享函数，不能声称必由本提交引入。修复应检查所有载体的一致性，允许SDK的等价双表示、拒绝冲突或额外输出；不应一刀拒绝任何双表示。
