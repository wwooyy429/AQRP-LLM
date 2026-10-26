AQRP-LLM 4a94430 独立复审包，2026-10-27 Asia/Shanghai
WR14在已测离线范围修复后通过，无新的阻断性软件发现；WR15/P3为开发输出清单raw声明对应CRLF而Git为LF，非阻断。阶段2及全系统仍未验收，无金融证据。
固定source1331份、baseline dc1088份、baseline fbe313份Git原字节均独立一致。
Python3.10：pip install -r requirements-audit.txt
校验：python -B verify_artifacts.py
原WR14最小：python -B minimal_fractional_clock.py source（当前0，旧dc1）
原14链脚本在source/audit/reviews/20261027-dc49f0f-windows/receipt_agent/fractional_clock_probe.py，--source source --out <新目录>当前14完成exit0；source改baselines/dc49f0f/source则6完成8误拒绝exit1。同脚本/helper未改。路径推断child label不是实际版本身份，外层full_chain_bindings记录实际路径/哈希。
WR15最小：python -B minimal_manifest_hash.py source（当前exit1，仅声明raw不符，48底层输出原字节都通过）。本包审核者重算manifest可以校验全部文件。
完整离线重现：python -B run_offline_review.py --out <不存在的新目录>
聚合入口本轮仅校验语法/help，各底层验收命令已实际执行，不声称聚合整段重跑。聚合器核对预期结果exit0也不表示完整系统验收；保留WR15非阻断差异。
原注解套件首重放OUT缺schema：12/156有1个环境错误。首输出保留，另建OUT复制同raw官方fixture后原脚本/断言不变12/160通过。聚合复制fixture时有显式diff。
审计首465检查461过4不符，3个是选择嵌套历史报告的ZIP测量错误，1个是实际清单raw差异；首报告/修正保留，最终466=465过1不符，未吞差异。
恢复cases/parser_cases和runs/repository_source重复完整源码副本不入包；测试、合成生成器、命令及输出完整可重建，原临时目录不删除。new_parser_recovery需先生成同目录recovery状态，聚合已排序。
历史脚本be/dc字面量、旧归档和首次失败保持原样，以当前外层命令/source路径/raw哈希绑定真实4a身份。
无生产/真实预算改动、无新增Research/LEAN/模型/市场/部署/购买/交易，未轮询或读取待终态LEAN日志。
