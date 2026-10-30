# WR-22／23／24新固定版本独立复审入口

请固定本目录所在PR最终Git提交，记录 `git rev-parse HEAD`、全量source、稳定execution、implementation与deployment身份。原独立审核固定ea6053e；实际云端执行仍为7fc5ef2。本次候选未部署或真实运行，不能将旧编译、读回或失败回执视作新版本成功运行。

先读AGENTS.md、config/development.json、章程、预算、数据字典、时间分区、audit/review_tracking.json、audit/stage2_current_readiness.json、docs/review/wr22-wr24.md及ea原独立正式报告。保留原WR-20／21触发范围的局部通过；WR-23／P1、WR-22／P2和WR-24／P3的新修补待独立复验，不能由开发者关闭。

只在隔离源码和合成账本执行。规定入口为 `python -B tools/stages.py verify`，另运行只读 `python -B tools/review_metadata.py`；本地Git必须已有明确基线，不自动拉取远程。独立构造已知答案和边界，不修改预期迎合实现。不得执行可能改变真实账本的归档准入／结算脚本，不调用QC、Research、LEAN、模型或交易；保持工程停止门及最终测试关闭。

重点覆盖：

1. WR-23：保留原minimal_prepare_entry_crash.py及helper，先验证旧固定版本反例，再测试新准入的input、admission、entry发布前后同步异常。已落盘inline新协议身份不得因sidecar缺失被降级为legacy；prepare恢复不盲补协议，成功／失败结算都失败关闭且无额外写入或下游LEAN许可。测试inline／sidecar错配、合法绑定成功、明确旧四字段准入、原f5d失败15→17→17，以及实际并发首次prepare和仅一次派发许可。同步异常通过不能扩为断电持久性认证。
2. WR-22：原完整老master区间+新ticker或同ticker映射、liquidity全部缺失必须不足，不能被rank201补位掩盖；同SID完整、缺1session和全缺分别判断。完整历史资格独立于liquidity存在性；断档／重叠／未来才可知历史不能被假定连续。保留合法原listing证据和年轻IPO排除、19／20期、盘中／收盘／收盘后一微秒及WR-20原13方法／43场景。检查原refs／raw／count、summary私有重算和正式认证false。
3. WR-24：旧描述原文在带ea基线和7fc实际云端身份的historical对象中保留；当前新增计数、源码差异列表和平台读取说明一致。源码集合按明确基线到交付版本的cloud／tests／tools Python变化核对，不漏测试或夹带未改文件。当前0新增说明不得伴随未标历史的新配置／Research描述；预算和17事件与ea原字节相同。旧固定deb到ea反例不能直接重命名为新范围。
4. 回归所有受影响的阶段0／1、共享准入、WR-11至WR-21、原生双载体错误／未知注解、原attempt恢复、worker严格EOF哈希、采集缓存、PIT、数值、标签和幂等边界。首次失败、夹具适配和修正分别记载，开发者重放不等于独立批准。

开发证据见 developer_verification.json、developer_outputs_manifest.json。原独立审核为选择性归档，完整ZIP及省略项按归档校验记录引用；原件按局部.gitattributes保存原字节。不要累计有重叠的仓库／专用／原独立套件为独有总数。

输出正式JSON和可读报告：固定源码、环境、实际命令及次数、首次结果与修正、可复现新发现、覆盖与证据不足。分别判断原修复范围、模块整体、阶段2整体、数据与金融证据。即使三项修复通过，真实成功联合链、旧worker差异、完整US200／财务认证仍单列，阶段3–7不能据此通过。预算保持7/12、10/20、1/16，正式研究、自动GPT、交易和最终测试关闭。
