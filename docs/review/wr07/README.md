# WR-07：Pearson数值稳定性修复与复审

最新独立审核绑定 `fe4374cee054fb8053706074be913ad7068c4484`：WR-04、WR-05原Spearman范围、WR-06均修复后通过，阶段0在实际覆盖范围通过；整体软件仍因新增WR-07不通过。原正式报告、失败输出、16项数值/时区套件及19项准入套件原件位于 `audit/reviews/20261026-fe4374c-windows/`，由 `archive_manifest.json` 记录原始字节哈希。

本页所在新修复提交仅有开发侧验证，等待GPT Work对明确的新固定SHA独立复审。原通过结论不自动覆盖新版本；不能称阶段1或整体系统已通过。

## 实现及边界

`cloud/qresearch/evaluation.py` 保留 `paired_factor_correlation` 的默认Pearson、符号和绝对值，以及矩阵的共同样本计数。没有改为默认Spearman，也没有把尺度极端但有限的分数作为缺失丢弃。

Pearson内核按以下步骤计算：对每列做2的整数次幂缩放，避免直接在原尺度平方；先减一个观察值作为锚点，再以 `math.fsum` 居中，保留大公共偏移下的微小差异；对居中差值再缩放后计算范数，最后用单位向量的稳定点积求相关系数。仅裁剪最终浮点舍入超出的[-1,1]边界，不引入相关性阈值。Spearman保留已经通过的平均秩相关路径及其输出行为。无需Windows不存在的额外longdouble精度。

共同索引、有限样本过滤、最小样本数和常数NaN规则保持；没有更改任何因子经济逻辑、方向、模型、股票池、日期、成本或交易参数。新配置、Research、LEAN及模型API的实际预算扣费均为0。

## 新回归与原失败保留

新增 `tests/test_work_wr07_regression.py` 共15个方法，使用精确Fraction表达实际二进制浮点输入的中心矩，再以90位Decimal平方根构造独立数值预期，不复用生产相关算法或 `np.corrcoef`。

覆盖1e-200／1／1e200的正反及非完美相关、双侧不同尺度、矩阵共同样本、索引对齐、常数／缺失／0、1、2个样本、float64最大值、subnormal和大偏移下ULP级差异，并保留Pearson与Spearman区别和平均秩行为。

原fe源码的负对照15项仅2项通过，13个不同方法非通过：8个方法含失败、9个方法含错误，两者重叠；22条失败和24条错误记录包含subTest，不能相加为方法数。修复后15项全部通过。首次子任务执行仅在工具记录中留有摘要，没有宣称存在未保存的日志；正式负对照另由固定旧源码重新执行并归档。

完整开发执行入口：`audit/review_packages/wr07/developer_verification.json`。仓库全测、原始数值16项、原始准入19项及此前认可适配的56项结果分别保存，包含重叠覆盖，不加总为独有案例。所有当前重放均是开发者执行，不是新增独立验收。

首次全仓验证运行265项，264通过、1失败：将稳定内核同时用于Spearman产生末位舍入差异，影响既有恒定IC的ICIR判断。失败报告及当时源码分别保存在 `first_full_verification.json`、`first_shared_core_evaluation.py`；修复仅在Pearson分支启用新内核，保留Spearman原有路径，没有更改原断言或ICIR统计规则。

## 复现与GPT Work审核指令

先固定交接消息中的新Git SHA，读取AGENTS.md、研究章程、预算、原正式报告、本页及源码差异，按requirements-test.txt建立隔离环境。以下输出目录必须为空；原脚本保持逐字节不变。

```powershell
python -m pip install -r requirements-test.txt
python -B tools/stages.py verify
python -B docs/review/wr07/replay.py --source-dir . --output-dir ../wr07-numeric --suite numeric
python -B docs/review/wr07/replay.py --source-dir . --output-dir ../wr07-atomic --suite atomic
python -B docs/review/wr04-wr06/replay.py --source-dir . --output-dir ../wr07-previous --mode adapted
```

数值原脚本输出里有写死的历史fe SHA；重放器不篡改该原件。实际执行源码以外层 `replay.json` 的文件哈希、候选清单和交接Git SHA为准，不能把脚本写死字段误作实际版本认证。

请独立验证默认Pearson及absolute_pearson矩阵的小／正常／大尺度、正反线性和非完美手算、共同样本、常数及样本边界，另检验大偏移／float64极值；不接受仅切换为Spearman或放弃合法有限输入。新增自己的数值边界，保留WR-04／05／06及原WR-01／02／03回归和合法完整链。不要仅复述开发者通过报告。

输出正式报告与JSON，明确实际版本、环境、方法数、失败／错误／跳过及subTest重叠，分别给出各阶段软件结论和仍缺证据。原样56项的六个历史异常处理不兼容及已认可的适配仍独立保留，不称原样套件全部通过。

当前预算仍为配置6/12、Research9/20、LEAN1/16。本次不授权新增市场／模型调用、资源购买、部署、PR合并或交易；不轮询既有LEAN任务。云端仍是旧75冻结部署，新本地构建不是部署证据。既有LEAN终态、完整历史US200、财务版本与实际送达仍缺证据，2024–2025暴露保留，2026独立性未认证；最终测试和生产执行保持关闭，`financial_evidence=false`。
