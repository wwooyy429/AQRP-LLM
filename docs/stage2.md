# 阶段2：数据接入与任务桥

> 历史时点说明：本页保留原开发版本的参数和状态，不是当前调度指令。新的统一复审与现状见[全部开发与修复入口](review/current/README.md)，通知恢复见[固定跟进程序](task_followup.md)。原限额与原结论不据此改写。

> 当前状态、版本与终态入账顺序见[阶段2继续工作](stage2-continuation.md)。原audit/stage2_readiness.json是早期历史诊断，当前差距见audit/stage2_current_readiness.json。

> 新增[历史快照采集模块](stage2-snapshot-collection.md)已完成离线实现，尚未接入本页固定两股任务桥或开展新云端运行。其模板不构成已登记的全市场采集计划。

本阶段使用固定两只样例股和2018年数据验证工程路径，不登记经济因子或生产模型。完整历史US200、财务版本和实际供应商送达证明仍是后续独立门槛。阶段2的实际验收结果记录在audit中，不能由本说明或自由布尔值授予。

## 唯一流程

1. 重新调用QuantConnect的list_projects，保存实际返回的项目元数据；只使用该结果中的项目编号。
2. 在Git固定共享源码，构建cloud部署清单并通过离线检查；上传后逐文件读回，核对清单并编译。编译不等于运行完成。
3. 用tools/stage2.py freeze冻结config/engineering.json的工程计划。实现源码清单和部署清单分别绑定；任务输入是另行核对哈希的惰性JSON字符串，不参与源码自引用。
4. register登记完整计划并扣配置预算。每个真正的Research或LEAN调用前先claim扣次数，重复已完成或状态不明的任务不能重新提交。
5. prepare生成固定任务输入。每个项目同时只有一个未终结工程任务；未知提交或旧锁须先核对。直到收到终态不更换该任务输入或运行源码。
6. Research一次执行先解析永久SID、保存解析注册表，再按2018全年分区批量获取RAW OHLCV。第二遍预取和只读消费者不能发出新的History请求。只返回计数、哈希和缺口；记录值留云端。
7. LEAN继承已核验的Research解析引用，实际接收行情和公司行动；核对完整预期交易日、同一永久SID和零订单。必须收到实际完成通知后才读取完成结果和元数据日志，不轮询等待中的任务。
8. 固定解析器核对原生工具名、项目、任务、输入哈希、实际终态及云端报告，再由任务桥入账。只有编译编号、自由completed字典或缺失日志均不能完成任务。

## 实现边界

- engineering_tasks.py负责完整计划、预算与状态；engineering_receipts.py只解析可信调度器实际取得的工具回执，不伪称能密码学认证任意本地JSON文件的远端来源。
- engineering_data.py是明确不下单的数据接收器。无任务输入时main.py保留Research宿主用途；它立即退出的结果不能冒充数据接收测试。
- coverage.py从缓存内容和实际记录计算工程覆盖；工程passed不授权真实因子计算。现有生产覆盖入口会生成带失败检查的未认证记录。
- ingestion.py接收历史批次和显式源字段投影，保留修订、缺失、分类和映射证据；它不是已经完成的全市场采集或财务认证。
- end_time和算法事件时钟只证明建模的LEAN交付路径，不能替代历史vendor_available_at或ingested_at。未知时间保持未知。
- 原始行情、公司行动值、财务行和历史成员面板只存QuantConnect Object Store。日志仅含工程计数、状态及不可逆内容哈希；原生回测收益面板不进入本地台账。
- 原始快照data_version与控制器源码版本分离，修改回执或报告代码不会自动重新下载行情。损坏、失败或需要修订的数据快照必须显式更换data_version并保留旧证据，不能覆盖旧缓存。
- 本阶段额外停止门槛为最多2个工程配置、2次Research及2次LEAN（含失败和修复），仍受用户全局12/20/16上限约束，不购买额外资源。软件单元测试不占市场执行次数。
- 自动GPT API、生产Research调度、最终样本和交易保持关闭。2024–2025既往暴露事实不变。

## 官方接口依据

- [Research历史股票池](https://www.quantconnect.com/docs/v2/research-environment/universes)
- [历史Universe数据](https://www.quantconnect.com/docs/v2/writing-algorithms/historical-data/universe-data)
- [证券映射与公司行动](https://www.quantconnect.com/docs/v2/writing-algorithms/datasets/quantconnect/us-equity-security-master)
- [日志规则](https://www.quantconnect.com/docs/v2/writing-algorithms/logging)：常规记录使用log，debug有200字符及频率限制，不能日志导出数据集值。
