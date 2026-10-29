# 现有任务的可执行宿主桥

`tools/followup_host.py`提供Python注入接口和JSON-lines stdio入口，消费既有`TaskFollowupController`。它只跟进已接受的工程LEAN attempt，不创建配置、Research、编译、回测或订单。当前没有生产factory、外部调度或新automation启用，默认不会打开真实Registry。

## 入口和权限

`python -B tools/followup_host.py plan --attempt <32位原attempt>`默认返回`dispatch_disabled`。`serve`默认也关闭。启用必须由可信宿主显式安装factory并选择`--enable-dispatch --host-factory module:function`；factory构建已有任务的controller及`TransportAuthority`。stdin不能供应权限、改时钟或自选工具。生产CLI覆盖factory中的测试时钟，使用真实UTC；市场时间分区仍为美东。

这不是LLM提案或FactorSpec的接口。可信factory本身必须由部署方固定、审核和授权，不能从模型输出、网页或原生工具文本导入任意模块。当前仓库不提供一个默认开通真实云端权限的factory。

Python程序可注入`FollowupHost`及具有`call_tool(name, arguments)`的可信client，运行`run_once`；stdio宿主则按请求帧执行真实MCP工具，再把原响应与原correlation ID、工具名、参数和attempt交回进程。外层MCP连接器仍保有自己的拒绝权。此代码已具备可执行协议，不等于Codex/MCP真实宿主已接好或已得到平台通知传输证明。

## 持久化和停止

host事件放在原store的`engineering/followup-host/<attempt>/events.jsonl`，宿主锁与Registry锁分开。原controller继续保存watch及最多三页对账预留；宿主在输出或调用工具前另外持久绑定请求和correlation ID。重复唤醒、崩溃或响应丢失不重新输出已预留的请求。项目发现单独授权、固定page1、一次预留；缺目标、错误或未知响应停止，不能循环查找。

只有固定next的`should_execute=true`可派发相应历史目录或完成读取；register、sync、status只处理元数据。30分钟从原pending起计，重启不重置。排队/运行、缺页、分页冲突、无目标、未知响应、拒绝读取或存储失败进入`attention_required`。停止自动跟进不等于把原任务判失败、退款或允许重提。晚到的真实回执仍可由原stage2入口核对和结算同一attempt。

## 协议与数据范围

输入命令是`wake`、`register`、`sync`、`status`及严格绑定的`response`。生产工具白名单限`list_projects`、`list_backtests`和`read_backtest`。工具名、参数集合、项目、页码、attempt与correlation都由固定程序约束；重复JSON键、非有限数、超大输入及不匹配响应拒绝。stdout只输出受限请求/状态，不输出原生结果行。事件记录hash、身份及封闭状态，不保存任意原生响应。

`read_backtest`有独立的连接器权限边界。聊天连接器禁止提前读取本聊天尚未收到真实结果的新提交任务；历史目录显示Completed和本地预留不能覆盖这项限制。可信宿主只能依据实际送达通知、合法历史用户引用或该transport明确允许的范围提供同任务读取凭证。没有凭证时停止，不能换工具绕过，也不能让stdin中的布尔值授予权限。

完成读取后返回`awaiting_native_receipt`。调用方须安全保留原生元数据，并补齐同attempt完整AQRP日志和原生零订单证据，调用既有`tools/stage2.py backtest-result`的固定parser→Bridge→Registry链，再同步watch。宿主桥不从目录摘要授予成功，不代替完整回执收集器、关轮器或独立验收；完整计费认证派发也不在本接口中。

## 当前验证和后续联调

本轮全部验证限私有合成store及本地进程。新代码的测试数量、源码和资料提交以当前审核包为准。975f676已测试范围通过结论保留在原精确版本；新宿主须独审。真实联调方案单列在`audit/review_packages/host010/next_engineering_preparation.json`，现在未授权/未登记/未执行该工程轮，不消耗新的研究额度。

一次未来真实任务可能只覆盖正常通知或超时恢复其中一个分支，未发生分支保留未验证，不能为补覆盖自动多提交。完整历史US200、财务真实时点及生产认证仍须独立证据。最终测试、金融研究、自动GPT及交易保持关闭。
