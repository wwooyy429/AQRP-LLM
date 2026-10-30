# Phase 2修复011：完整开发与边界复审

固定软件源码：`dee26eec9481e8c75c09c2b97c680707d1814452`。请固定检出该提交审核代码，另从含本包的固定资料提交读取证据；不要把可变分支HEAD当最终审核身份。上一开发候选`5132ef0a1cb94b2070f02ba8e5a3f940da6a6e8e`保留了共享桥注册回归，不得倒改为通过。PR #2仍须保持草稿，不合并。

本次验收须涵盖以下全部开发、修复和既有边界的回归。开发方全量结果以`full_offline_validation_v3/result.json`和原始输出为准；它仍不是独立软件验收，更不是金融证据。

## 身份、测试和原件

先运行`python -B audit/review_packages/phase2_repair011/verify_packet.py`核对资料身份，再独立检出固定源码运行`python -B tools/stages.py verify`。232份受管源码使用既有source_manifest的UTF-8-sig/通用换行规范，保留EOF换行数量；原始输出、原件、台账及其他审计材料仍按原字节SHA核对，不能以文本规范化替代。旧工作区有4份受保护文件为CRLF而Git为LF，本轮不修改这些原文件；1dc317e首版包错用工作区原字节作为源码Git身份，已保留实际新检出首败及修正记录。使用完整Git克隆：旧缓存契约已知答案从固定5e09e63源码读取，测试阶段不能联网补对象。CI已改为完整历史检出，依赖和动作版本未变。

首轮1074项全量通过，但随后旧任务恢复探针失败；第二轮1084项有110个错误，均为共享基类对采集/认证子类误用工程计划schema；最终修复及全量v3结果必须单独核对。各定向测试与全量重叠，不相加。原始stdout/stderr以base64保留；代理早期仅有元数据的运行不能称原件齐全。财务早期15/13/1输出因文件名复用而覆盖，相关字节按先前记录的哈希重建，并明确标为重建，不作最终原件的替代。最终保留的17/13/1、全量v3和实际回归原件另列。

首轮暂存源保留了清单和实际输出，但其临时检出未保留，也没有单独的Git源码提交；不得称该暂存源完整可重放。第二轮失败源码固定在5132ef0，最终源码固定在dee26ee，可分别重放。请自行构造边界与已知答案，不仅重复开发者断言。报告每项实际命令、环境、首败与修复；若无法覆盖，明确写未验证。

## 预算、历史及真实MCP链

用户原话：“已授权重置额度，开始修复阶段2的所有任务”。该授权已经收到，但重置范围待用户选择，旧round009也仍未结算。不得清账、退款、伪造failed/close或放宽旧规则以绕过阻塞。当前仍是配置周期4/13、累计17、Research18/20、LEAN4/16、78条权威事件，本轮新增扣额为0。逐字节核对78事件SHA`5fa2c6fb5b94b7c76cb6b7458be3daec01c444057af0426a4aea9d2051f33e87`及预算投影，原71事件前缀仍保留。

实际生产UTC宿主已在原30分钟宽限后，先发出一次项目清单请求，再发出一页历史目录请求；工具结果原样通过correlation反馈。项目只取实际返回的38436695。目录摘要确认原回测`6347a33efc37e761f486f982e804dbac`为Runtime Error、progress1；这不是read_backtest原生回执，也没有错误栈。随后宿主因读取授权为空返回completed_read_not_authorized，没有请求结果、日志、订单或通过浏览器替代。原attempt `11147fc5a7ac4f6c951a86d021d069b2`仍pending，原因未臆造。

该链只证明实际宿主的项目发现及历史目录传输。新回执collector尚未装配生产receipt source，新47文件候选没有云端执行；旧5e09e63的44文件Research13/13不能授予新候选云端通过。

## 完整终态回执编排

审核`cloud/qresearch/terminal_receipt_tasks.py`、默认off的CLI及说明。可信Python工厂授予同attempt/project/backtest的真实送达/历史引用依据，stdin和LLM不能自授。目录状态或时间经过不构成read grant。每次出站请求先持久预留，晚到同原件幂等、冲突停止、未知响应不重发。

成功任务必须完整读取精确attempt的最多8页日志，全部chunk连续唯一且每块不超过500，再独立核对原生orders=[]且totalOrders整数0；不能从缺失统计或目录trades0推断零订单。重新取得原件后校验响应哈希，复用既有固定`backtest_observation`，只结算同attempt一次，不扣额、不退款、不自行关轮。

真正送达且固定parser确认的原生失败可直接settle failed，无需强求成功日志或订单查询；zero_order_evidence为null、成功链证明标志false。普通错误字符串、超时、运行状态及目录摘要均不能结算。原始行/订单留在QC Cloud，可信上游receipt source只能检索已取得原件，不能偷偷重新查询。

## 先扣额的认证诊断任务

审核`certification_tasks.py`共享库/CLI及Registry修改。新任务使用显式data_certification schema、Research-only、零重试，六类云内内容寻址引用；计划范围、来源、字段、部署及cell/input身份冻结。必须先有明确用户工程轮授权，再登记配置并预扣Research，不能借通用任务或不受限operation绕过。

原生单元源回读后一次性预留派发，native成功或绑定的notebook错误由固定parser解析，输出闭合聚合指标，无行值。执行completed允许数据诊断为insufficient_evidence；全部观测通过也不会认证供应商真实性或打开正式研究。

特别复验已发现的旁路：普通子类回调、显式调用基类回调、generic Registry.pending/complete/fail和重放不能制造没有原生证明的认证终态。原准入、dispatch、native响应、解析submission/completion和结果引用必须匹配不可变证明。LOCK内守卫不得递归进入Registry/Bridge造成死锁。可信宿主及文件写入者仍属操作信任边界；哈希不能认证远端发行者。

## 财务值、缓存闭包及旧任务恢复

仅新增`financial_statements.income_statement.total_revenue_as_reported.twelve_months`工程字段，角色as_reported_financial_value、单位reported_currency、期间twelve_months。指定期间必须先有字面SDK `has_period_value('12M')`返回精确True；缺失为None，真实零保留。拒绝默认值/标准化营收替代、任意路径和callable、布尔及无穷。币种身份、实际单位和版本尚未认证，因子字段权限仍false。

复验财务标量及期间对象__class__抛错、伪造异常__str__及可变reason均不能泄露原生异常；外围源诊断只输出固定词汇。原15字段与权限逐项不变，当前为16观测字段、1数值财务字段，不是0，也不是全财务覆盖。

当前缓存闭包含完整financial_fields.py，处理契约为0f01ca7f...；辅助代码单独变化必须改变指纹，缺少依赖不能伪装旧4源兼容。旧5e09e63的4源仍精确计算出5ef61ef7...。新执行/缓存不得复用旧契约，不能自动重新取数。

历史解析仅可信Python读取入口使用historical_decode；它不序列化，JSON不能开启。旧计划6a875...、配置64e7...、输入9cecf...保持原哈希；实际只读恢复145份台账原字节未变。新Bridge注册/claim、Registry授权/bind/扣额、worker和缓存仍须当前契约。尤其复验三类桥各走自己的闭合schema，避免再次误伤采集与认证继承入口。

## 仍缺的真实证据和审计边界

旧任务真实错误详情及原生失败结算、额度重置范围和合法应用、新47文件的真实SDK/云端执行、新collector生产装配与完整原生链、全历史US200/SID/日历/行情/行动覆盖、财务真实值/币种/版本/公开/实际送达/摄入、平台账单仍未认证。用户确认没有账单；内部quota和SDK容量不能代替计费凭证。官方文档与API目录不能代替历史行级来源。

不得为复审执行Research、提交回测、轮询刚提交未送达任务、修改预算、购买资源或打开最终测试。分别给软件、生产集成、数据认证与金融证据结论。正式研究、自动GPT、交易、最终测试均关闭；2024–2025已暴露，2026独立性未认证保留。WR29原范围关闭保持，开发修复点没有擅自取得新的独立WR通过结论。
