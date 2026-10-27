AQRP-LLM独立复验 ccad61d03ccf17bf2bdc2d7ffc88dfd11b6d3ca6，Windows，2026-10-27。
正式结论、完整JSON和最小复现也直接在聊天提供，本包为补充。先读formal_report.txt/.json与findings.json。
原WR22/23/24在各原触发与注明范围修复后通过；新增WR25/P2未知分类、WR26/P2当前主表未知使全缺liquidity漏检，仍阻断观测审计；WR27/P3仅显式跨目录--root误用工具树hash，不影响当前默认源码身份正确。
仓库654通过，16历史套件248方法2307子例通过，其他已跑回归详test_execution_summary.json。新历史9方法7过2失败、29命名场景（不是unittest子例）、5失败记录对应2问题。方法/场景/子例/CLI/静态均有重叠，不合计独有总数。
原WR23 ea负控exit1、ccad同字节exit0；独立同步写入/身份5方法21场景全过，281只是custom chk调用，另6 assertRaises；180普通CLI和16实际并发CLI，27合成finish，无真实worker。v1/v2各4进程首次prepare/dispatch，均唯一许可；不扩成断电或OS kill认证。
原WR21旧夹具只删sidecar仍保留新inline协议，原字节先失败且保留；仅两行恢复明确历史四字段前置、所有assert AST一致后17CLI全链过。既有native/recovery使用原已认可合法绑定前置，全部首次/窄适配分开，未改生产或预期。
本包candidate4977、baseline ea4541、实际cloud7fc4204为完整固定Git原字节，逐文件重新比较；各固定树内所有历史路径保留。source_git_manifest.json记录全部hash。archive_agent65/65静态checks非unit；WR24专项11项9过2失败同WR27，12变异另计。开发manifest94条及历史325原件1833366bytes选择性归档已核对，不冒称完整旧包。
只读封包校验：python -B verify_artifacts.py，标准库即可、无网络、不得向sealed目录写结果。源源码在source。要重放先复制到新目录，依requirements-audit.txt准备Python3.10.11；正常入口python -B tools/stages.py verify须在可写完整副本运行。
直接反例：python -B minimal_wr25_wr26.py --source <固定source> --output <新JSON>，用固定Git内已归档原创201SID/21session/2formation夹具，全链Memory store。stock/null正确不足，etf/unlisted正确排除；unknown/future-current/missing-current误过，当前exit1。root独立重复及逐案原件在wr25_confirmation、wr26_confirmation。
WR27：python -B archive_agent/minimal_wr27_root_manifest.py --source <固定source> --git-repository <已有完整Git对象仓库> --output <新目录>；原始程序在新合成树自行构建目标与隔离index，默认0/错误外来hash0/正确目标hash1，反例exit1；root再次重复在wr27_confirmation。仅改合成目标，不改真实源码或Git index。
完整实际argv/cwd/exit/stdout/stderr/hash、外层版本绑定、适配说明及全部首次失败保留。可重建cases、嵌套derived source、alternate_root及source.tar不重复入包；原始固定source内部完全不裁剪。历史脚本literal旧SHA/目标标签保留，不当成本次实际观测。
预算与17事件原字节相同：配置7/12、Research10/20、LEAN1/16，工程2/2/1停止；本轮QC/真实Research/LEAN/model/deploy/trading/真实账本写入0，无退款。正式研究、GPT自动调用、交易及最终测试继续关闭。
实际云端仍7fc已归档Research CollectionError；解析正常15→17→17，故障15→16→18→18中pending非重复扣费。旧LEAN在归档中为初始化源码不符失败，非本轮live read。31部署对归档旧31为28同3异，只是历史参考，不认证当前inventory/失败worker；底层源迭代原因未知。
真实成功Research→缓存→LEAN联合链、完整历史US200/财务版本/实际送达认证仍缺；history API次数、接收行数、真实订单/金融统计null，不能冒充0。阶段3–7未验收；2024–2025已暴露，2026独立性未知；financial_evidence=false。
下一步仅离线修WR25/26及WR27，提交新固定SHA供复审。不能自动重交云端、扩大工程限额、批准或合并PR。
