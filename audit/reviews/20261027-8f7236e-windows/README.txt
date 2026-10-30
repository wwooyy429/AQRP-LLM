AQRP-LLM 8f7236e独立审核（2026-10-27，Windows）
软件结论：阶段2联合候选失败，WR-16/WR-17均P2；阶段0/1旧范围保留，阶段2整体及3–7未验收。终态无法确认，financial_evidence=false。
请先读formal_report.txt/.json及findings.json。正式JSON和短MRE亦直接在聊天交付；本包为补充原件。
固定源码source1563份、baseline dd094f3共1545份，已与git archive完整raw逐一核对；source_git_manifest.json保存所有原字节hash。
离线包校验：python -B verify_artifacts.py（只读，不需要网络或项目依赖）。
依赖：Python3.10.11，pip install -r requirements-audit.txt。本轮实际使用同版本Windows固定venv；其他环境未认证。
最小复现（只内存/新临时副本）：
 python -B minimal_boundaries.py source registry
 python -B minimal_boundaries.py source freeze
本候选均应exit1，分别显示禁止重试仍should_execute=True且用量2、v1freeze exit0且pointer_changed=True。默认临时副本保留，无原账本改动。
完整最小原件：admission_agent/minimal_joint_registry.py source；admission_agent/minimal_pending_freeze.py source <不存在的新输出目录>。
独立worker正链：python -B joint_worker_agent/independent_joint_worker.py --source source --out <不存在的新输出目录>。
该套件9方法/81子例首跑通过，另一次为原字节捕获重复，不能累计独有用例。
仓库验证：先把source复制至一个新目录，在新副本cwd执行python -B tools/stages.py verify，避免覆盖封包内受保护的stage_verification原件。
历史脚本按原断言重放，完整路径/命令/输出已保存；历史脚本输出中旧commit文字只是原literal，不冒充当前执行身份。run_main_checks.py及证据核对脚本保留本机固定路径；跨机器执行请用以上便携MRE/worker入口并自行设置解释器。完整旧日期负对照有本机旧源码路径依赖，未声称所有历史原脚本已跨机器验证。
两次注解重放各9pass/1审核器证据原件缺失error均保留，第三次补schema+helper原字节后10/803通过，未改测试断言或生产。原raw56不兼容记录和全部旧失败保留。
admission quick7方法为3pass/4fail，四负例归两问题；原MRE与短MRE主代理各复验一次均exit1，不算通过或新增方法。
证据63checks通过、两build/两preview无变化；只读QC26份Python=25实现+1输入，与旧75原字节相同；notebook、回测状态/结果/日志均未读。不能据pending归档断言平台当前仍运行。
市场/派发/部署/模型/真实预算变更均0；12事件重放配置6/12、Research9/20、LEAN1/16。最终测试继续关闭。
保留全部新脚本、实际命令、rawstdout/stderr、首轮错误、报告和哈希；重复完整源码测试副本/临时cases及source.tar不重复装包，均可由脚本重建。未删除任何原C/B证据。
