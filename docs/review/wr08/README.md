# WR-08：稳定ICIR统计与复审交接

最新独立审核绑定 `7b0dccebef2d3582e1b07ada05211863c3cba0d8`：WR-07在本轮数值范围修复后通过，阶段0在实际覆盖范围通过；整体因新增继承缺陷WR-08仍不通过。本页所在新修复提交只有开发侧证据，等待新固定SHA独立复审，不能继承旧版本的通过结论。

原正式报告、兼容套件12项及其失败和首次11项通过记录、独立Pearson10项原件位于 `audit/reviews/20261026-7b0dcce-windows/`，原始字节哈希见 `archive_manifest.json`。更早报告与失败均保留。

## 修复及数学合同

仅修改 `cloud/qresearch/evaluation.py` 的IC摘要计算。ICIR仍为算术均值除以样本标准差，`ddof=1`，不年化；无效日过滤、有效日及共同观察计数保持原有规则。无有效日、单有效日的样本标准差/ICIR，以及零方差的ICIR仍未定义。

完全相同的有效IC以精确相等判为常数，返回原值均值与零标准差，不采用任意小方差阈值。非恒定序列先按2的幂缩放，去除锚点后以 `math.fsum` 居中，再用 `math.hypot` 计算样本标准差，保留相邻浮点值的真实差异。ICIR在同尺度的矩上直接求比值，避免先舍入均值/标准差再相除；极小值下对外float显示值可能舍入，不能靠显示值直接重构ICIR。无需额外longdouble精度。

Pearson、Spearman、标签、拟合、股票池及交易/风险协议没有改动，也没有改变研究时间分区、预算、最终测试门禁或云端在途任务。

## 回归及失败记录

新增 `tests/test_work_wr08_regression.py` 共15方法，覆盖正负非完美恒定IC、多种天数、全零、缺失/无限值、0/1个有效日、ddof=1手算、相邻float、微小尺度、subnormal、排列，以及daily→summary、六轮walk-forward和RegisteredStudy完整链。数值预期使用Fraction/Decimal；完整链借用作者模板，明确属于开发者测试，不冒充审核者新案例。

同一15项在固定旧7b源码负对照为4通过、11失败方法，包含26条失败子例记录；在修复实现15项通过。原审核12项兼容类负对照为11通过、1失败；各次结果分别保存，不以子例数当方法数，不加总重复覆盖。

首次局部修复15项中14通过、1项失败：subnormal输入的均值先舍入后再求比导致ICIR错误。该次仅有工具记录，没有虚构本地原始日志；开发记录保留真实摘要。随后在缩放尺度直接计算ICIR，未放宽断言。最终执行、旧源码负对照及源清单见 `audit/review_packages/wr08/developer_verification.json`。

## 重放与GPT Work审核指令

固定交接消息的新Git SHA并记录完整提交。读取AGENTS.md、研究章程、预算、历史正式报告、本页和源码差异，按requirements-test.txt建立隔离环境。所有输出目录必须为空，原件不得覆盖。

```powershell
python -m pip install -r requirements-test.txt
python -B tools/stages.py verify
python -B docs/review/wr08/replay.py --source-dir . --output-dir ../wr08-compatibility --suite compatibility
python -B docs/review/wr08/replay.py --source-dir . --output-dir ../wr08-pearson --suite pearson
python -B docs/review/wr07/replay.py --source-dir . --output-dir ../wr08-numeric --suite numeric
python -B docs/review/wr07/replay.py --source-dir . --output-dir ../wr08-atomic --suite atomic
python -B docs/review/wr04-wr06/replay.py --source-dir . --output-dir ../wr08-previous --mode adapted
```

新replay入口逐字节核对并导入原件，仅运行原 `PublicContracts` 的12项或 `ExactPearsonTests` 的10项。兼容原main中的机器专属静态差异和历史辅助入口本轮不重跑、不算作通过；源文件、计数、子例和日志由外层replay.json记录。未改任何测试方法、断言或预期，也未增加skip/expectedFailure。

请用独立输入复现恒定0.7及负常数，检验真实微小方差不被抹零，复核ddof=1、缺失/计数和未定义规则，再检查日IC到完整公开评价链。保留原WR-01～WR-07的已验范围及合法正向路径，单独记录新边界和实际证据，不直接沿用开发侧通过结论。

请输出正式报告和机器可读JSON，明确新固定SHA、环境、方法/子例、失败/错误/跳过及重叠，分别给出阶段状态和未验证范围。原样56项的历史六个异常处理不兼容及已认可适配继续分列，不称原样56全部通过。

预算仍为配置6/12、Research9/20、LEAN1/16。本轮不授权新增市场/模型API、资源购买、部署、PR合并或交易；既有LEAN只保留pending记录，不轮询或重交。完整历史US200、财务版本及实际送达未认证，2024–2025暴露保留，2026独立性未知，最终及生产执行关闭，`financial_evidence=false`。
