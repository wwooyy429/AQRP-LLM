# 阶段2新增：历史快照采集与只读复用

> 历史fbe2454复审发现WR-09／WR-10；后续GPT Work固定7bf716f独立确认两项在已测离线范围修复后通过。当前结论及剩余工作见[WR-09／WR-10](review/wr09-wr10.md)；阶段2整体仍待验收，未部署／运行新版。

本次在已验收d0离线内核之上增加数据准备模块，尚未部署或执行新的QuantConnect任务。阶段2仍待验收；开发侧合成测试不能替代GPT Work对本次固定Git提交的独立复验，也不能证明历史股票池、财务版本或实际送达时间已认证。

## 本次实现

| 文件 | 职责与边界 |
| --- | --- |
| `config/source_catalog.json` | 唯一默认源字段目录，15项已明确路径、类型、单位和用途；不是因子字段白名单。这里只开放工程观察，不启用经济特征。 |
| `templates/historical_collection.json` | 未启用的采集计划模板。日期、计划名、数据版本及源码清单哈希必须显式冻结，空值不能执行。没有自动填入整个2010–2023或最终日期。 |
| `cloud/qresearch/collection.py` | 冻结计划、按NY日历分窗、流式分批、云端内容寻址、失败意图、完成缓存复用及完整读取校验。 |
| `cloud/qresearch/historical_source.py` | Research专用`universe_history`来源、永久SID及精确字段投影；保留无基本面覆盖的名字。提供保守的流动性观察接入函数。 |
| `tools/stage2_collection.py` | 仅检查元数据和源码清单绑定；不调用平台、不登记配置、不扣预算、不提交任务。 |

默认每次请求1个日历日，允许1–7日；这是内存及API请求分区，不是交易所日历。每批最多1000行、每窗最多50000行是未启用模板值。完整计划可在硬上限内明确调整；实际采集配置仍须冻结、登记并计预算。每窗一次批量API调用，不逐股票或逐因子取数。

数据路径为：原生历史Universe快照 → 显式字段投影 → 云端不可变批次 → 完成窗口引用 → 只读消费者。完成同一计划再次读取新增源调用为0；只读消费者缺缓存就拒绝，因子代码没有此源对象。不会为每次评价自动生成同内容副本。新计划、字段语义、数据版本或实现身份产生新命名空间；不承诺任意变更计划都实现跨计划零下载。

## 时点、分类和版本

`snapshot_at`来自历史Universe索引，含义是**模型中的选股发生时间**。QC的naive索引按显式设置的America/New_York解释；原生`time`、`end_time`作为原精度ISO观察保留。三者均不填充`vendor_available_at`或`historical_ingested_at`。财务日期保留日期精度，不虚构盘中时间。

无`has_fundamental_data`过滤、不用当前成分表、不按市值或价格缩小来源。SDK原生`symbol.id`是唯一身份；没有SID就失败，不退回ticker。缺失字段和NaN存为null，零值保留；未识别分类保留未知，禁止用其他股票替换。

`observed_liquidity_record`只使用供应商`dollar_volume`，不以close×volume重建。调用者必须从独立核对的交易所日历及数据日期关系提供前一收盘时点；函数不自行推断节假日或快照属于哪一交易日。它只转换观察，无法认证这个日期映射。生成的`observed_snapshot:<hash>`是观察内容指纹，**不是供应商修订号**。分类、上市生效/送达、供应商送达/摄入证据仍为空，因此既有ingestor允许存档但PIT读取拒绝，不会进入US200排名或正式因子。

默认目录包含市值和财务报告的期末、文件日期、申报编号、表格类型元数据；不猜测未核对的资产负债表字段，不把元数据称为完整财务数值接入。后续新增报表数值路径、单位和周期须核实并重新冻结目录/计划。

QC文档说明：Morningstar基本面并不覆盖所有ADR等股票，旧报告文件日期可能使用近似值，部分数据会前向携带。2026年9月供应商迁移也涉及历史数据；仅填写`data_version`不能证明上游历史版本未变。当前模块固定实际取得快照的内容，不授予上游修订或历史可得性认证。依据见[基本面数据说明](https://www.quantconnect.com/docs/v2/writing-algorithms/datasets/morningstar/us-fundamental-data)和[迁移说明](https://www.quantconnect.com/docs/v2/writing-algorithms/universes/equity/morningstar-migration)。

## 失败、并发和预算

采集器先写入窗口意图，再调用来源。失败、超限、重复SID/时点、异常字段、数据损坏均保留意图及已存批次。相同窗口不会自动重试；应核对未知/失败状态，显式形成新版本或新计划并保留旧证据，实际重跑仍须计预算。源异常不会原样输出可能含有许可行值的消息。

真实行只允许进入`residency=quantconnect_cloud`存储；本地Memory/Filesystem仅用于显式synthetic测试。Object Store仍要求一个明确生产者，其余只读；进程锁不是跨节点锁或原子比较交换。哈希能检测内容不一致，不是外部不可篡改认证。保存引用或计数也不意味着数据覆盖通过。每个结果的完整US200、实际送达和研究认证标记固定为false。

本模块不新增第二套预算账。新远端Research任务必须由可信调度器先列项目、使用返回ID，冻结完整范围、登记新配置并从现有Registry预扣调用；函数本身不能约束绕过调度器的手工SDK调用。**本次未把新采集协议接入自动远端任务桥**：旧工程桥仍只接受固定2018两股计划；不能将新计划塞入旧计划或复用旧的扣款回执。

旧LEAN `39cafa1e9b11f91b27e396b66d033a6d`尚无自动交付终态。旧75源码及任务输入不改、不轮询、不重交。收尾后才能安排新计划的实际平台验收。本轮只读官方接口文档及本地开发，不新增配置登记、Research、LEAN或模型API调用；权威用量仍为6/12、9/20、1/16。

## 离线检查与独立复审

在固定测试依赖下执行：

```powershell
python -B tools/stage2_collection.py template
python -B tools/research.py build
python -B tools/stages.py verify
```

`validate --plan <已填写的元数据计划.json>`只验证元数据。计划的`source_manifest_hash`必须匹配`tools/stages.py manifest`当前源码清单，字段目录定义也参与计划哈希。该命令不授予实际执行许可；模板本身含空值，不能通过验证。不要在本地CLI文件中放入真实行情或财务行。

新合成测试覆盖DST、NaN/零值、非数值、缺SID、非历史窗口、异常形状、财务缺失不筛选、缓存复用、失败不自动重试、跨计划引用、损坏批次和PIT拒绝。GPT Work应另造边界，特别检查数据是否能通过不可信标记升级为真实覆盖、是否存在最终日期访问或隐式重新下载。对新增模块的结论和已验收d0的原结论分别记录。

剩余验收包括：旧LEAN终态入账；新源码部署/读回/编译及完整运行；新采集远端协议和预算原子准入；全市场SID/分类/上市映射及实际预期交易日；财务数值/修订/公开与实际送达证据；公司行动覆盖。完整历史研究仍关闭，2024–2025既往暴露保留，最终测试和交易仍关闭。

接口依据：[Research Universe History](https://www.quantconnect.com/docs/v2/research-environment/universes)、[Coarse Universe数据](https://www.quantconnect.com/docs/v2/writing-algorithms/datasets/quantconnect/us-equity-coarse-universe)。SDK真实响应和资源占用尚待实际平台验收；合成形状测试不代替此项。
