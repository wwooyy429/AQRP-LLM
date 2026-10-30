# 有界原生终态回执链

`qresearch.terminal_receipt_tasks.TerminalReceiptCollector` 将已经准入的唯一LEAN任务与原生完成结果、全部工程日志及成功任务的独立零订单证据关联。它不提交回测、不执行Research、不调整预算、不打开最终测试，也不证明数据或因子金融有效。

## 权限与宿主装配

默认CLI关闭，不打开Registry或加载工厂。开启只能由可信操作者安装零参数Python factory，再显式运行 `python -B tools/terminal_receipt_tasks.py serve --enable-dispatch --host-factory installed_module:create_collector`。工厂必须返回精确的、显式enabled的collector类型；stdin、LLM提案或目录Completed不能构造读取授权。

工厂先使用既有 `bridge_for_attempt` / `admitted_input` 恢复历史准入，不使用当前可变配置重新解释旧attempt。操作者核对实际送达的原生完成通知或用户对已完成历史任务的真实引用，再安装 `TerminalReadAuthority`。授权必须绑定该attempt、project、backtest以及实际凭证摘要。摘要只绑定字节，不能自行认证来源；工厂需另保留通知/引用的受信来源记录，并遵守实际连接器权限。

不可用“过了30分钟”“历史目录Completed”或LLM生成的描述替代真实送达通知。对本聊天刚提交而尚未送达结果的任务，本模块不增加任何提前读取许可。恢复目录机制与终态回执收集是不同的能力门槛。

## 调度及存储

每次 `wake` 只生成一个请求：先 `list_projects(page=1)`，确认目标项目在真实返回列表中；随后读取明确project/backtest的终态。成功任务最多请求8页精确 `AQRP_ENGINEERING <attempt>` 日志，验证每页和所有分块连续、唯一、齐全，再请求独立 `read_backtest_orders(page=1)`。原生订单数组必须为空且 `totalOrders` 为整数0；缺少统计字段不能充当零订单凭证。

每次调用在stdout发出之前，先向独立于预算Registry的元数据journal写入唯一correlation请求预留。未知响应、进程中断或丢失stdout不会重新派发；晚到的原始响应仍可按原correlation归档。相同响应重放幂等，冲突或非法响应停止这条收集链，不能自动重试或重建任务。

上游可信传输必须在云内保留真实原生响应，并提供 `receipt_source(envelope_sha256)`，仅检索已经观察过的原件，不能在这个回调里再次查询平台。本地journal仅保存身份、固定请求、响应哈希、分页与分块编号及其他闭合聚合元数据，不写财务面板、错误全文、订单行、行情行或base64工程日志块。原始响应不由CLI从本地文件读取。

`reconcile()` 重新检索并核对每一份原始响应哈希，再复用已有 `backtest_observation` 验证完整身份、报告引用和实际工程检查。`settle()` 还核对精确的既有EngineeringTaskBridge、原准入部署和输入哈希后结算同一个attempt；不新增扣额、不退款、不自行关轮。关闭工程轮仍需操作者检查结算无歧义后调用已有关轮入口。

## 失败与未知状态

真正送达且被既有固定parser确认的Runtime Error/失败终态，可直接结算为failed。初始化失败可能没有工程成功日志或可查询订单，本模块不为失败结算强求这些证据：`zero_order_evidence`为null，日志/独立零订单/成功链标志保持false。不得把失败任务称作零订单成功回测。

普通超时、错误字符串、排队/运行状态和目录摘要不能结算为失败或成功。它们停止自动动作，保留未知状态及已消耗额度，先对账后考虑新任务。

CLI支持的JSON命令只有 `wake`、`status`、`response`、`reconcile`、`settle`；响应只能绑定刚预留的tool_name、完整arguments和correlation。`reconcile`/`settle`需要工厂注入可信云内receipt source及历史bridge。没有这些装配，即使源码和合成测试通过，也不能宣称生产传输、平台通知、实际回执或阶段2整体验收通过。
