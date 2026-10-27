AQRP-LLM 独立验收 deb85d9f27441b275ab8b108f0232ecd2707a1e8，2026-10-27 Windows
结论：本轮软件验收失败WR21/P1、WR20/P2；阶段2整体未通过，financial_evidence=false。
先读formal_report.txt/.json及findings.json。聊天直接交付问题、最小复现核心及完整正式JSON，附件只作补充。
source为当前4270份固定Git原字节；baselines/66ff72f/source为前次基线；baselines/7fc5ef2/source为实际云端执行版本。三树逐字节核对Git，source_git_manifest.json记录所有文件。不可把当前deb后续解析修补当已上云运行。
只读封包核验：python -B verify_artifacts.py，无项目依赖或网络；不修改sealed文件。
离线环境见requirements-audit.txt，实际Python3.10.11/Windows。先复制source与要运行的审核scripts/support到新工作区，不在封包原件旁创建输出，避免破坏哈希。
仓库入口在固定source的临时完整副本执行python -B tools/stages.py verify，本轮612通过；独立反例仍表明不能接受新软件。
WR20：python -B cert_agent/minimal_wr20.py --output <新结果.json>，保持cert_fixture.py在同目录、其父目录含固定source。三合法控制通过，非法上市前记录当前观测误过，exit1。根再次独立运行结果见wr20_confirmation。
WR21：将entry_agent/minimal_new_success_without_dispatch.py、quick_joint_probes.py、independent_cli_gates.py、independent_wr16_boundaries.py复制到一个新目录，其父目录含固定source；运行python -B <新目录>/minimal_new_success_without_dispatch.py，当前exit1。创建的是隔离合成账本/报告/CLI，没有SDK/网络/Research/LEAN提交。原17CLI、根17CLI和另1次合成同父LEAN准入原始记录保留。合法已绑定/旧无marker控制成功，修复不得禁掉它们。
原WR21审核输出有字面反斜杠n后缀，保持原件；root strict_result是单独规范化副本，不冒充原生平台回执。原命令17，不是先前叙述14。
入口并发正控root entry_controls.py为3链/21CLI（含两个实际Windows进程只获1许可）全过；worker诊断6/51过；原生失败新6/91、旧9/90及8manual过；数据认证13方法12过1失败/43场景、2失败记录，不将场景加为方法。
历史16套件248方法2307子例过（含已认可adapted56及历史pending账本夹具）；Collection12/36、joint worker9/81、fraction10/803、恢复5/46、WR16 9/4、WR18 9/39过。原Collection首0方法/1setup错误因真实限额已满；原worker首8过1失败因写死旧预算；另稿只换历史预算/账本夹具，原脚本及断言不变。所有首结果保留，不声称原始套件无失败。
原生Research错误包为开发归档，审核者独立离线重解析：1错误/2载体、9traceback条目/43物理行，底层源原因未知。正常15→17→17，写故障15→16→18→18多审计pending非重复扣费；真实17事件从未由审核改写。
审核者实际QC只读先list_projects，再project38436695 open、32Python文件和cell1源；不读notebook输出/数据，不执行、不重交、不轮询。31实现+input均匹配7fc冻结身份，当前deb仅29/31相同，2不同；不认证全集或失败旧worker。
预算保持7/12、Research10/20、LEAN1/16，工程2/2/1已达停止门；审核新增真实执行/模型/部署/预算均0。开发本轮有1次已登记Research失败，未提交新LEAN。
完整脚本实际argv/cwd/stdout/stderr、反例、首次错误、源身份和QA均保存。可重构大case/source副本及source.tar不重复入包；固定source三树内部历史路径全部保存。旧C/B证据不删除。
有一项子审扩展被工具filter中止，未执行内容不计通过；根独立重放和另一代理QA补齐已交付结论。其余静态reader/矩阵准备错误另存原稿与trace，不作产品测试失败。
正式研究、自动GPT、交易、最终测试关闭，active factor/model/trading均null；2024–2025已暴露、2026独立性未知。阶段3–7未验收。
下一步仅修复WR21/WR20后提供新固定SHA复审；保持当前云端停止条件，真实成功联调、旧worker及数据认证缺口继续单列。
