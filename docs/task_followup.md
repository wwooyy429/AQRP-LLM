# 已接受回测的通知恢复

这是阶段2的元数据任务控制，不生成因子、取行情或提交回测。`config/task_followup.json`是唯一政策来源：从原始已接受提交的Registry时间起等待30分钟，随后最多检查一次历史目录、最多3页。每页和完成结果读取都先持久预留，崩溃或未知响应不能重新派发。政策固定版本不允许随意改时间或分页上限。

`tools/stage2.py backtest-submission`成功入账后自动登记watch；若watch写入失败，明确返回`attention_required`，已接受的任务仍保留，不能降级为旧协议或重新提交。原生完成回执仍走既有`backtest-result`，成功后同步关闭已存在的watch。历史任务没有watch时不补造当年的登记记录。坏政策在freeze、register、claim的本地预检阶段即拒绝。

## 固定执行顺序

1. 调用`python -B tools/task_followup.py next --attempt <原attempt>`。生产时钟由程序取UTC，CLI没有改时钟入口。市场时间分区仍由既有美东配置定义。
2. `wait_for_delivery`表示仍在宽限期内，不查询任务状态。`list_projects`表示已到期但缺实际项目发现凭证；先调用QuantConnect原生list_projects，把完整tool_name/arguments/result存成元数据文件，再带`--projects-file`调用next。只使用实际返回且与已接受任务一致的编号。
3. 只有`should_execute=true`才能执行返回的`tool_request`，且只执行一次。第一个请求是list_backtests的固定项目和页码；把完整原生响应通过`history --attempt <id> --tool-file <原生封装>`交回程序。多个输出载体必须一致。仅保存响应hash与目标ID、状态、进度等观察，不保存收益或行值。
4. 再调用next。仅当前页没有目标且原生分页证明还有页时才可请求下一页，总计不超过3页。目标仍排队/运行、错误、缺页、未知响应或找不到任务时转为需处理状态，不循环查询、不退款、不重提。
5. 只有历史记录明确Completed.或Runtime Error，才可预留一次`read_completed_backtest`。随后读取该已完成任务的原生结果、同attempt的完整AQRP日志与零订单证据，通过原`tools/stage2.py backtest-result`解析、核对身份并结算。目录中的完成摘要本身不会写Registry成功。
6. 自动推送先到时可以直接走原完成回执链，再sync watch。工程轮仍由原关轮程序在所有工作已结算后关闭。编译、接受、平台终止、工程检查和独立验收是不同状态。

`status`只读；`register`用于恢复未成功写入的watch，沿用原pending时间，不重置截止点；`sync`只采用Registry真实终态。register/sync的非终态返回只确认登记/同步，无派发权限；未知响应的真实风险状态通过status或next查看，调度只依据next.should_execute。任何`attention_required`都应停止自动请求并报告一次明确问题，后续原生通知仍可结算同一attempt。不得把异常或缺通知认成任务失败。

## 调度端接入

原来的心跳只扫描聊天消息，可能永久等待；以后应调用上述固定next程序并执行它许可的请求。可使用`docs/task_followup_heartbeat.txt`作为任务跟进指令。该指令不自动授权Research、回测、资源购买或最终测试。

本轮只实现、离线测试并接入本地任务桥，没有部署新云端源码或创建新回测，也没有恢复已完成008的监控。实际MCP宿主调度器执行、自动推送传输以及超时对账的真实联调仍须在独审之后单独验证；不能用合成工具适配器冒充生产调度器。阶段5的无人值守GPT研究仍关闭。

## 本地锁释放

`FilesystemArtifactStore`对Windows WinError32增加独立的有限释放等待：最多6秒或lock_timeout中的较小者，最多120次，每次最多50毫秒。预期owner来自本次locked调用，不从磁盘重新建立。释放前检查当前PID、完整canonical owner、key、nonce和锁路径，每次重试再次核对全部字节。其他错误、替换、读失败和重试中的锁丢失均拒绝；不会猜测删除他人或未确定归属的锁。

该修复替代008结算时的操作包装器；包装器和失败记录留作历史证据。新源码未在QuantConnect运行，b1a的Research13/13和LEAN7/7不作为新源码的运行证明。
