AQRP-LLM dc49f0f 独立复审包，2026-10-27 Asia/Shanghai
WR13原未知注解旁路修复后通过；新增WR14/P2普通小数秒兼容失败，阶段2及全系统未验收。financial_evidence=false。
source1088份、baselinebe891份、baselinefbe313份均固定Git原字节。
Python3.10：pip install -r requirements-audit.txt
校验：python -B verify_artifacts.py
最小复现：python -B minimal_fractional_clock.py source（当前exit1，等价.500/.500000通过、.5拒绝）
完整新旧worker链：python -B receipt_agent/fractional_clock_probe.py --source source --out <新目录>（当前6完成8误拒绝，exit1）；--source baselines/be94426/source时14完成exit0。
WR13原最小：python -B minimal_nested_annotations.py source（当前0，旧be1）
完整离线重现：python -B run_offline_review.py --out <不存在的新目录>
聚合入口本轮仅检查语法/help；各底层验收命令均实际执行，不声称聚合整段重跑。聚合返回0只表示预期结果重现，WR14仍为软件错误。纯审核者解释器/基线路径绑定有diff。
原脚本的历史commit或按路径推断label不作为实际版本证明；看外层命令、实际source目录和raw源码hash。完整fraction探针相同脚本/helper在新旧source运行，输出目录分开保留。
恢复cases/parser_cases和runs/repository_source重复完整源码副本不入包；原临时目录保留，所有测试、合成fixture生成、命令、输出与状态观察保存，可从source重建。new_parser_recovery需先执行同目录原recovery脚本生成本轮case状态，聚合已排序。
首12/160的Role排序测量失败及合法clock错误都保留；另存Role-only修正版仍保留两条产品错误，不吞异常或改合法clock预期。原5变体适配只增加修复后拒绝处理/状态测量，原件/diff也保存。
无生产源码/真实预算改动，无新增Research/LEAN/模型/市场/部署/购买/交易，未轮询待终态LEAN或读日志。
