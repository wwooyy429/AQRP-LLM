# Phase 0 开发说明与验收矩阵

目标是建立可检查的合同、身份和审计骨架，防止LLM用自由配置或说明文字替代固定程序的批准。本文描述固定75f2462的实现，不等于新的审核通过结论。

## 模块与接口

| 模块 | 已实现接口或职责 | 对应测试 |
| --- | --- | --- |
| `cloud/qresearch/contracts.py` | `DataRequest`、`PITWindow`、`validate_records`；NY时区、开发边界、字段/SID和历史成员合同 | test_data_pipeline、test_factors |
| `study.py` | `StudySpec.from_dict`、`validate_trading_spec`；因子/模型/标签/交易/数据/代码和六轮设计绑定 | test_study |
| `study.py` | `AuditEvidence`；subject/source、issuer、scope、check和原始证据引用 | test_study、test_audit_bridge |
| `audits.py` | `audit_formula`、`verify_evidence`；持久化检查报告，复核原报告与声明一致 | test_audit_bridge、test_runtime_binding |
| `artifacts.py` | 规范化序列化、内容哈希、不可变对象、文件/内存存储、链式事件和协作锁 | test_persistence |
| `registry.py` | 配置登记；执行前计费；started/pending/completed/failed/ambiguous生命周期；结果复用 | test_persistence |
| `workflow.py` | 提前交付的持久化状态机；规范/身份/审计绑定，失败和显式重试边界 | test_workflow |
| `tools/research.py` | 通用配置构建及唯一Registry的元数据命令，不自行发起QC调用 | 结合上列测试和源码检查 |
| `tools/stages.py` | 全仓离线验证与源码清单；其输出是开发侧证据，不是独立批准 | 原仓库验收入口 |
| `config/`、`templates/` | 研究章程、数据、股票池、预算、阶段及Factor/Model/Trading规范来源 | 配置解析及StudySpec测试 |
| `.github/workflows/offline-tests.yml` | Python3.10/3.11执行离线检查 | 独立核对实际CI运行 |

表中未写完整路径的模块均位于`cloud/qresearch/`；测试均位于`tests/`，以`.py`结尾。

## 验收矩阵

| 编号 | 必须验证的行为 | 不能接受的替代证据 |
| --- | --- | --- |
| P0-C01 | 缺失/非法合同被拒绝；工程fixture与真实research身份不可互换 | 只存在JSON模板或注释 |
| P0-C02 | 经济语义、模型、标签、交易、数据和实现绑定正确；篡改被拒绝 | 仅比较调用方自由字典 |
| P0-C03 | 引用的原始审计报告存在、内容哈希正确、subject/source/scope和所有检查一致 | `passed=True`、删掉失败检查或换issuer |
| P0-C04 | 原始市场数据及逐行结果不进入本地Registry或Git | 只写`market_values_exported=False` |
| P0-C05 | 配置及执行预算原子占用，正常/预留/总额度一致，失败不退款 | 日志声称已扣费或只在执行后计数 |
| P0-C06 | 同一完成任务复用；未知提交不重交；修复有原因、身份与新扣费 | 改任务名重新发起或自动清除旧锁 |
| P0-C07 | 文件写入幂等、事件链可核对、重启可恢复；真实IO错误和根外链接被拒绝 | 仅单线程内存成功 |
| P0-C08 | 最终数据与正式交易访问仍关闭；历史暴露和预算不随删除归零 | 删除旧文件后声明研究从未发生 |
| P0-C09 | 研究章程、代码、配置、文档和提交版本一致；历史结论只适用于其固定版本 | 把最新HEAD、编译或开发测试视为独立通过 |

P0-C05必须结合WR-04判定：Registry全局上限与阶段2额外停止门槛是两层约束。前者有效不能抵消后者的并发缺口。审阅者应说明通过的具体范围或保留阻断，不能仅凭本矩阵判定通过。

## 数据与时间合同

`DataRequest`限定源、字段、永久SID、区间、版本、股票池、复权和时区。开发请求结束不得超过2024-01-01；这不是独立最终执行器的实现。

`PITWindow`要求排序且唯一的带时区形成时点、固定SID列和可选历史成员布尔矩阵。它验证窗口形式；真实供应商可用性仍依赖数据接入与覆盖证据。

`validate_records`保留事件时间、可用时间和revision，拒绝歧义的同时版本和越界记录。真实公开、供应商送达、摄入时间及财务版本不能由报告期或LEAN end_time推断。

全局因子字段白名单当前未填充。真实研究需可信调度方提供并冻结精确字段/算子目录，候选自身声明不构成授权。

## 存储与并发边界

文件存储对合作进程使用锁；进程崩溃可能留下需核对的锁，不自动删除。75版本已修改Windows普通删除叶文件的路径解析，仍检查父目录及实际symlink/reparse边界并保留真实IO异常。

事件哈希链用于发现不一致，不是外部不可篡改认证。工具原始JSON由可信调度器获得，离线重解析不等于独立访问平台。

QuantConnect Object Store没有已实现的跨节点CAS保证，当前生产操作须遵守明确单写者约束。该限制不能被写成“已验证分布式并发”。

## 未完成或未认证

- 生产经济研究、实际完整US200及财务时点覆盖。
- 独立金融最终执行器、生产交易与模型API。
- 所有入口的阶段2原子停止门槛：WR-04开放。
- 原生Windows行为的GPT Work独立复验：历史Work报告在Linux运行，开发侧Windows检查应单列。
- 不能仅因提前存在workflow状态机，授予phase 5无人值守闭环通过。
