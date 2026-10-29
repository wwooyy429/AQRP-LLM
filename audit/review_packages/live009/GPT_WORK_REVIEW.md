# Phase 2 round009：真实联调和认证边界复审

本包可审核已发生的工程操作及其证据边界。LEAN原生终态尚未送达，完整阶段2验收条件未齐；不得把本包判作全阶段通过。

固定运行源码为 `5e09e63d87a42a07a448e27da6aedbe4e8210a6f`，稳定执行源码清单为 `fe3df524e360fef6d74dc06559b553bd0005b9350c9f425855a4ec26ec4360c5`。新增计划为 `config/engineering_host_round009_pilot.json`；计算、回执、缓存及宿主共享实现延续已审核c2e63ac，不能继承为本轮整体验收。全量预扣额前219文件清单为 `3ceea7654cbe7b6914eb7e3fcb0e33768eff47bcf9d39d80f12a9097f55db17f`，预算用量投影随后依法追加；执行清单排除可变用量，并保持不变。

资料和operator factory须从含本包的固定Git提交获取，不使用会变动的分支HEAD作最终审核身份。factory自身SHA见 `operator_binding.json`；它属于本轮操作者装配，未获独立验收，也不在运行源码5e09e63的managed source内。PR #2保留草稿、不合并。

## 先验证身份和历史

运行 `python -B audit/review_packages/live009/verify_packet.py`。这是纯本地完整性检查，不是独立验收。核对manifest中每份文件的原始SHA、1012项实际合成测试原输出base64、219文件清单和44文件云端读回。原生read_project含notebook，完整响应未导出；仅用固定JS程序在内存比较返回的Python源码，输出精确比较元数据。不得将它称完整平台库存或worker包认证。

核对71事件原始前缀SHA `cea800e0fe5a0facc5f2aed238d105a6f3d1c80db40c1dc4b674efd3026cd48a` 未改，只追加7事件到78。配置周期4/13、累计17、Research18/20、LEAN4/16；总上限不变，无重置、退款和购买。008保持关闭。用户原话、1/1/1授权、冻结和预扣额必须先于实际派发；失败同样消耗额度。

## 复核已发生的真实链

1. `project_listing.json`是实际QC清单，只使用返回的38436695；不得伪造项目编号。
2. 核对3份差异源码写入、44份严格读回、Research输入写入/精确读回、固定cell生成/源回读/dispatch绑定，再实际执行一次。
3. Research attempt为 `44eda8401c554e0b87bc01598169c919`。使用仓库固定parser重新解析 `research_native_execution.json`，独立比对13检查、报告引用、身份和原Registry结算；不得新增实际执行或扣额。
4. 实际统计为250形成日、2510字段记录，首次/二次History均0；40窗口复用、208223源投影、27重复、13空窗口、所选四字段冲突0。重复没有被悄悄删除；这些是工程计数，不是完整US200认证。
5. 核对真实Research worker44份源码原身份一致、EOF规范化0。不能继承旧LEAN43份worker的原始一致结论。
6. 核对LEAN attempt `11147fc5a7ac4f6c951a86d021d069b2`，backtest `6347a33efc37e761f486f982e804dbac`，输入9cecf347...、显式compile成功与原生submission。提交成功仅表示任务被接受，Registry仍pending。
7. 实际有5次`.py`保存调用（工具会自动编译）、1次显式create_compile和1次create_backtest（工具会编译），不能声称只有1次总编译。平台未返回独立compile job计数。
8. 真实Registry、UTC、canonical导入和唯一任务绑定的CLI/stdio register/wake均返回wait_for_delivery，退出0；未实际演示宿主发出MCP请求，不能判生产transport全面通过。读取授权为空、无假时钟、未将目录状态伪造成通知。

## 终态回执仍待补齐

本包没有实际终态通知、完成态read_backtest、日志页或原生零订单查询。不允许为复审轮询刚提交的任务。先等原生通知；通知未到时保持pending，不退款、不重提。生产UTC宽限截止为 `2026-10-29T15:15:59.738191+00:00`。超时只能按已审核的有界宿主机制预留至多3页历史对账；目录Completed不授予受限连接器的read权限。

实际通知送达并具备工具权限后：先列项目，读同一任务原生终态，取精确 `AQRP_ENGINEERING 11147fc5a7ac4f6c951a86d021d069b2` 日志的全部页/块，另取原生 `orders=[]/totalOrders=0`，再用固定stage2 parser结算同一attempt一次。`Total Orders`字段缺失不能当零订单。只有无歧义结算后才能关轮。任何新执行均不在本轮剩余额度内。

## 数据和计费认证不能被工程通过替代

阅读 `certification_gates.json`、`official_fundamental_documentation.json` 及既有 `audit/phase2_repair_data_evidence_requirements.json`。完整历史US200、历史候选分母、SID/交易日/20期暖启动、分类/上市/退市可用时间及完整行情行动覆盖仍不足。数值财务字段目录仍0；实际公开时间、报告版本、供应商历史送达及摄入凭证不足。

QC官方文档说明2026 Morningstar数据迁移重建历史，字段可用时间和股票池覆盖可能改变。复用的旧工程缓存不能认证新feed。Approximate FileDate、约6/7AM活跃配送日程和LEAN end_time不能当实际历史送达时间。现有认证CLI仅能力与计划验证，尚无完整认证任务原生派发/结算链。

SDK空间实际预检为52,325,933/52,428,800字节、483/1000文件，所设需求与保留扣减后20,947字节，status sufficient；它是该时点SDK观测，不能当锁定空间或账单凭证。内部quota可重放，但当前MCP无账单端点，UI工具无法确定URL而停止，用户确认没有账单/明细。平台实际计费认证为证据不足；不能用策略Fees或内部额度计数替代。

## 独立审核要求

另建边界/已知答案测试，报告实测命令、环境、首个失败和重跑原因。可对固定源码做离线 `python -B tools/stages.py verify`；不得为审核调用真实数据、执行Research、提交回测、买资源、改变预算或打开最终测试。对元数据、代码、数据覆盖、平台真实性及金融证据分别下结论。发现问题按WR继续编号，不把过去关闭的原范围倒改为失败。

正式研究、自动GPT、交易及最终测试均关闭。2024–2025既往暴露和2026独立性未认证必须保留。本轮没有收益、IC、费用收益或金融有效性发现。
