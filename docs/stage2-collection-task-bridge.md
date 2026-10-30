# 阶段2：历史采集任务的预算与调度接入

> 后续固定e513独立审核确认共享准入在已测范围通过，但发现WR-11／12，新增任务桥不通过。当前修复和复审边界见[WR-11／12入口](review/wr11-wr12.md)，本页原开发说明不授予当前候选验收。

本轮在已独立验收7bf离线实现之上增加采集任务协议，继续使用唯一Registry。新候选尚未独立验收、部署或真实运行；7bf的WR-09／10通过结论不自动覆盖新增代码，阶段2仍待整体验收。

## 实现

| 模块 | 职责 |
| --- | --- |
| `collection_tasks.py` | 冻结采集任务、受信项目发现和字段目录、固定Research操作、继承已有回执／终态流水线；只接受元数据。 |
| `registry.py` | 新旧任务共享全局12/20/16和工程2/2/2；注册／执行在同一事务锁下检查。拒绝修改任务类型、任意操作、额外阶段或超限重试。 |
| `collection_execution.py` | 核对部署清单，调用共享采集库、只读重放，原始行及全部窗口引用留云端；只输出固定报告、计数、字段缺失数和内容引用；解析实际Research单元回执。 |
| `tools/stage2_collection.py`及`collection_task_cli.py` | 冻结、登记、预扣、准备惰性输入和原生完成回执入账。CLI本身不连接QC、提交或轮询任务。 |
| `templates/collection_task.json` | 未启用模板；计划名、返回的项目ID、完整采集计划等必须显式填写。不会自动扩展为全市场多年采集。 |

`CollectionTaskPlan`固定项目、源码／部署身份、字段定义、采集计划、结果命名空间和重试上限。它使用原`engineering_task_schema_version=1`包络，`task_kind=historical_collection`区分任务；不另建工程域或计数器。新注册仍扣完整配置，实际Research调用仍提前扣次数。旧两股任务的扣款不能拿来执行新采集计划。

执行源码身份与独立复审清单分开：`execution_source_manifest()`覆盖完整源码／配置，将`config/budget.json`中的用量投影`usage`排除后绑定其余预算政策。正常登记／预扣更新usage不会使自身计划失效；上限、分配或其他规则变化仍使冻结失效。权威用量始终来自Registry事件，而非这个源码哈希。`tools/stages.py manifest`仍生成完整独立复审清单，不因此省略任何文件。

## 准入和恢复

1. 先通过实际`list_projects`结果冻结计划，只使用返回ID；字段语义来自`config/source_catalog.json`。CLI检查当前源码和部署与冻结身份一致，才允许新增登记／预扣。
2. 同项目存在任意新旧工程`started/pending/ambiguous`任务时，在新执行扣款前拒绝；新采集注册也受保护。检查位于Registry全局事务内，跨Bridge、CLI、直接Registry、不同store实例以及进程竞争不能重置额度。
3. 采集只允许固定Research操作，不接受LEAN或随机operation来另起调用。正常、修复、失败、跨项目及重启共用工程2/2/2。重试须指定最后失败attempt、原因并满足冻结上限；失败不退款。已完成／未终结任务复用原身份，不重新执行。
4. 提交回执只能进入pending；实际完成单元的固定stdout标记须经原生解析器核对工具、项目、attempt、源码、部署、输入哈希及云端报告，之后才能终结。编译或自由`completed`字典均不能完成任务。受信adapter／completion reader是程序I/O边界，不是LLM批准。
5. 未知提交保留ambiguous，不自动重试；收到真实终态后由受信完成读取器核对。当前CLI解析成功完成单元；无完整标记的执行错误／传输异常不被擅自归为可重试失败，仍需实际终态及显式核对，不能换名重交。

新输入独立保存为`audit/collection_task_inputs/<attempt>.py`，云端目标`_collection_task_input.py`；不改旧`_engineering_task_input.py`。输入是惰性JSON字符串，不能执行附带代码。生成输入前必须已有预扣attempt，完成任务不能再准备新远端输入。准备文件不表示已部署或实际执行。

云端采集器按冻结窗口预取、再以无source的只读消费者完整校验。保存窗口意图后来源失败，仍由原采集库阻止自动重取。完整元数据收据已保存后的重入只核对缓存并恢复同一报告，保留首次取数计数；不是新的执行许可。损坏、旧最小日期错误缓存和未知窗口继续拒绝，不能静默覆盖。

报告中的`collection_receipt_ref`严格绑定本attempt路径；大列表和市场行不进入本地台账。Object Store仍要求一个明确生产者，进程锁不提供云端跨节点CAS。哈希检测一致性，不证明上游供应商修订或历史可得性。云端任务输入也是受信调度器的绑定，不是签名预算凭证；任意Python代码仍能绕开接口手工调用SDK，本系统不将这当作可自动批准的研究入口。

## 操作入口和验收

离线开发验证：

```powershell
python -B tools/research.py build
python -B tools/stages.py verify
```

实际调度就绪后才使用以下元数据命令。此次未对真实账本运行这些变更命令，未创建实际采集配置或任务输入。

| 命令 | 结果与扣款 |
| --- | --- |
| `template`、`validate --plan ...` | 检查原采集计划，零扣款，不授予执行许可。 |
| `freeze-task --task-file ... --projects-file ...` | 冻结源码和实际项目发现，零扣款；字段目录不能由候选覆盖。 |
| `register-task` | 新完整任务配置预扣；同内容复用不重复扣。 |
| `claim-task [--retry-of ... --reason ...]` | Research执行预扣；仅`should_execute=true`可由受信调度器实际调用平台。 |
| `prepare-task --attempt ...` | 生成不可变惰性输入，不发送云端。 |
| `research-result --attempt ... --tool-file ...` | 核对实际完成回执，再pending／终态入账，不新增调用。 |
| `task-status` | 查看已存身份／计数；旧源码任务的结果仍按原身份核对。 |

新增测试验证混合任务的全局／工程额度、注册和执行竞争、Windows跨进程事务、直接Registry绕行、固定操作和重试、实际模拟worker→原生形状解析→终态链、行数据拒绝、未知提交、源版本变更和输入不可覆盖。它们全部使用合成来源、临时存储或原账本的只读内存副本，不发出市场／模型调用。

GPT Work应对新固定SHA独立构造同项目混合并发、旧事件重放、跨attempt证据、伪造标记、损坏缓存、失败后重启和预扣顺序边界；开发侧测试不代替独立验收。

旧LEAN `39cafa1e9b11f91b27e396b66d033a6d`仍无交付终态，本次不轮询、不重交、不换在途云端源码／输入。预算仍为配置6/12、Research9/20、LEAN1/16，工程域各已用1/2；不购买新资源。正式研究、GPT自动调用、最终测试和交易继续关闭，2024–2025既往暴露保留。实际新版部署、完整运行、历史US200／财务／公司行动数据认证仍是后续门槛。
