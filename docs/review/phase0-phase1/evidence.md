# 证据索引、后续变更与未验证项

## 历史审核链

| 固定源码 | 实际记录 | 结论与范围 |
| --- | --- | --- |
| `113fdf7` | 仓库112/112；独立32项中30通过、2失败 | phase 0/1失败；WR-01无符号标签回绕，WR-02审计A可授权实际B |
| `dd77108` | 仓库133/133；原独立32/32及原最小复现2/2；新增16方法15通过、1失败（2失败子例） | phase 0修复后通过，phase 1因WR-03高精度数量窄化合并失败 |
| `ddca623` | 仓库138/138；独立32+2+16+14次执行全部通过 | phase 0/1修复后通过；合成软件范围，不含真实QC/金融效果或原生Windows独立认证 |
| `75f2462` | 仓库217/217；原独立64次回归通过；阶段2独立26项22通过4失败，WR-04最小复现失败 | phase 0/1离线回归通过；阶段2软件基础失败，总验收待定；不能声称整体准入均已原子 |

以上次数来自相应独立报告，包含重复复现，不是去重后的独有测试数。历史结论不因后续修复被覆盖。

报告路径：

- `audit/reviews/113fdf7cf7147d58a8b3125beceeaeee0f6aa962.json`
- `audit/reviews/dd7710854bca31135d2fc86f4f5625b8ded05d65.json`
- `audit/reviews/ddca623a879d7f051540b6a15a3fe29bc7b96441.json`
- `audit/reviews/75f24629d3b7f94ff3aa906c3ce8a2b8b9a8d3c4.json`

前3份报告已经随历史证据提交；第4份在本次资料整理中从既有GPT Work正式输出补归档，不代表本次新发起审核。

原始最小复现为`tests/test_work_p1_minimal.py`及`tests/test_work_wr03_minimal.py`。全部独立32/16/14脚本此前在Work工作区和附件中，不能假称仓库包含了完整独立脚本集。新审核者应自行构造独立案例；如需原完整脚本，应从原Work证据附件取得并核对版本。

## ddca623到75f2462的基础变更

| 位置 | 变更及复审意义 |
| --- | --- |
| `cloud/qresearch/artifacts.py` | Windows并发删除普通叶文件时不再resolve该叶；解析稳定parent、lstat叶，对symlink/reparse继续核对根内边界，保留真实IO错误 |
| `tests/test_persistence.py` | 新增3项确定性路径/IO边界回归，原phase 0/1关联14模块由138变为141个测试方法 |
| `cloud/main.py` | 加入受限、惰性工程任务输入与数据接收路由；无输入仍为Research宿主，不把立即退出计为有效回测 |
| `cloud/research_config.py` | 仅生成的IMPLEMENTATION_SHA更新；不能由此证明云端已部署或运行 |
| 新增阶段2模块及`tools/stage2.py` | 不算作phase 0/1的全部交付；其预算、身份、驻留和最终访问边界属于共享不变量，必须检查相互影响 |

以下核心文件在该diff中未变化：contracts、point_in_time、factors、labels、models、evaluation、pipeline、runtime、study、audits、registry、workflow。机器清单提供逐文件哈希及diff供核对；源码不因相同哈希而免除跨入口回归。

## WR-04：开放的P1

独立审核在内存和临时磁盘台账复现：两个请求都在已用1槽时通过阶段2停止检查，再分别登记或占用，最终达3。影响配置、Research和LEAN入口。全局Registry的12/20/16上限仍有效；额外2/2/2门槛失效仍是实际缺陷。

主要位置为`tools/stage2.py::_limits`及其调用点、`engineering_tasks.py`的登记/claim/submit路径。修复要求检查与扣费置于跨计划、跨项目共享的原子准入范围，并保留复用、失败计费和未知提交保护。

本次只整理资料，未修复该问题。不得以“只有一个AI”“没有在真实平台超支”或“文件属于phase 2”为理由将其隐藏。复审者应明确它对phase 0预算合同及阶段2准入结论的影响。

## 本次开发侧复核

本次报告为`audit/review_packages/phase0_phase1_developer_check.json`。检查对象应为固定75源码快照，使用本目录run_checks.py核对文件及原全仓源码清单，再运行manifest列出的14个关联模块。它覆盖原基础138方法加3个持久化回归；具体实际结果以报告为准。

本次报告不是GPT Work独立审核，不运行WR-04竞争修复，不重做真实数据或交易测试，不重写原审核结果。仓库测试可以使用作者夹具；审核者新增独立测试应自行构造输入。

主报告在临时venv按固定requirements-test安装后实际运行141/141，NumPy1.26.4、pandas2.3.3。首次本机NumPy2.2.6执行保留在`phase0_phase1_developer_check_unpinned.json`，只作额外兼容性证据；资料QA发现的环境说明及skip/expectedFailure通过门槛问题保存在`phase0_phase1_materials_qa.json`。复核脚本现要求固定依赖匹配、passed等于预期且所有非通过类别为0。

## 证据等级与当前状态

- 代码阅读、开发测试、独立合成复算、开发者归档平台证据、独立平台只读核验、金融独立测试分别标注，不能互换。
- 历史Work独立环境为Linux/Python3.12，依赖NumPy1.26.4、pandas2.3.3；未在原生Windows上独立运行。开发者Windows复核另列。
- 最近归档1f7c0c0重放预算为配置6、Research9、LEAN1。冻结75内budget usage较早，不能用它声称当前预算仍为5/8/0。
- 阶段2Research证据只有2018 AAPL/MSFT工程样例；完整历史US200、财务版本和实际送达均未认证。
- LEAN归档为pending。本资料不读取、轮询或改变该任务，不猜测其现时终态。
- 正式因子研究、最终测试、自动GPT API及交易保持关闭；2024–2025既往暴露保留。
- 缺失真实数据、交易和独立最终测试证据时，金融有效性结论必须为证据不足。
