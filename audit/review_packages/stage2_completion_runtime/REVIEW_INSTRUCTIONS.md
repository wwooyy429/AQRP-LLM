# GPT Work统一审核指令

请审核本文件所在PR最终固定Git提交，先记录git rev-parse HEAD、全量source清单、稳定execution清单、部署及实现哈希。实际云端执行版本固定7fc5ef2e9d2379d29f48d05a1f3cc760000884d6，当前交付包含真实失败之后的本地解析器修补；必须分开这两个身份。现有独立批准仍只对应66ff72f的旧已测范围，不授予新增功能通过。

先阅读AGENTS.md、config/development.json、研究章程/预算/数据字典/时间分区、audit/review_tracking.json、audit/stage2_current_readiness.json、audit/stage2_completion_round_report.json、本目录README及两个开发包的原字节清单。确认正式研究、自动GPT、交易和最终测试关闭，2024–2025暴露/2026未知未被覆盖或删除。

只运行离线检查和隔离数据测试。规定入口为python -B tools/stages.py verify；额外构造自己的已知答案与边界，不能仅重复开发者测试或把预期断言改成产品现状。原失败、夹具适配及所有首次结果须保留，计数分开方法/子例/重叠套件。不要执行本包的实际准入或结算脚本去改变真实账本，不提交新Research/LEAN；工程配置/Research已达本轮停止条件。若只读核对QC，必须先列项目，仅用列表返回的ID，不能把snapshotId当projectId；不读取/导出notebook市场数据输出。

审核所有新增及受影响组件：

1. worker_identity与engineering_data：默认schema1、严格EOF/hash保持；同一次read的schema2格式/AST/路径指纹；消息长度、非法路径/设备名/未知字段/转义/重复诊断边界；提取不授予远端来源、完整worker或旧根因认证。
2. engineering_receipts及stage2 CLI：固定cell按唯一部署位置找input，异CWD/多位置拒绝、单读原字节、惰性AST、identity核对、清长驻旧模块；首次entry-protocol与实际read_cell全载体绑定；跨进程只一次许可、旧输入不补标记、未知结果不重跑。
3. Research真实错误：逐字节保留f5d原件、admitted-input、entry/dispatch；2个MCP载体应为一次错误而不是2次任务。每个载体及注解都验证、完整original result hash保留，不能信内部投影为原件。测试不同JSON/附加输出/structured矛盾/typed bool别名/网络错误/成功打印错误字典/一个JSON中两个error拒绝；全局_native与既有成功及WR11/13/14边界不扩大。
4. 失败恢复：在隔离15事件副本重放15→17→17；验证原attempt/input/cell/项目/部署/response hash错配拒绝、写故障恢复不多扣、不生成成功结果。旧13事件前缀、旧LEAN失败和所有原件不可变，真实17事件及7/10/1预算不退款。注意traceback数组9条目与43物理行的区别及旧字段含义。
5. data_certification：真实值只留QC Cloud、固定范围/预热/calendar/SID/200/20和原refs哈希；所有已知老eligible候选历史缺失不能靠rank201补位掩盖，未知分类和IPO必须正确处理；财务版本/实际可用时间、date-only next close、RAW价格及行动边界。汇总需重新核对私有原始输入，拒空counts/refs加自由true、缺报告、重叠、扩全史或哈希自洽伪造；观测符合不得授予供应商真实性、完整数据或生产批准。
6. 原有阶段0/1及受影响模块回归：Registry预算原子性/旧任务恢复、采集/caching/PIT/数值/标签等，保持固定源码及实际覆盖范围，不将组件测试扩展为阶段3–7通过。

请独立核实实际云端失败事实：源取数迭代抛CollectionError，底层cause未提供；没有Research成功工程报告、没有新LEAN提交、没有新版云端成功。31文件读回及编译成功不能代替运行成功；当前本地版本29份与已部署7fc参考相同、2份不同不是当前完整平台inventory认证。不要根据两股/40日观察认证2010–2023 US200、财务版本或实际送达。

输出正式JSON及可读报告，逐项写明固定提交、环境、实际命令/次数/首次失败/修正、发现和可复现案例；无新缺陷也要列证据不足。G1实际失败，G2旧worker证据不足，G3有真实原生失败和恢复但新软件待独立验收，G4正式数据认证不足。最终分别判断软件、阶段2整体、数据和金融证据；不能为方便通过而放宽预算、数据可用时间、原件/身份或最终日期。
