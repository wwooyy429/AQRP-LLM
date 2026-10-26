# WR-11修复复验与WR-13新增旁路

固定 `be9442603a31481a9a71e51ca794df77650c7411`：WR-11原双载体不一致路径在本次独立范围修复后通过；**WR-13/P2已复现，当前回执边界整体仍不通过**。

新增独立矩阵修正版15方法80子例全过，0失败/错误/跳过，覆盖旧Research、旧LEAN提交/读回/日志、新采集worker到Registry完整回执链、等价双表示、冲突/错误/隐藏输出、顶层元数据、JSON类型与重复键、无行持久化。首跑15/80有1条审核器预期错误：误把structuredContent=None当作存在的载体；None实际表示缺席。首跑与原脚本保留，修正版和diff另存，不能把该测量错误归为生产缺陷。

WR-13根因在 `cloud/qresearch/engineering_receipts.py:271-273`：受支持嵌套TextContent分支只读取text，忽略annotations。把合法marker放入content包装、outputs包装或native text根节点，并在annotations中附带未知合成rows；两个外层载体完整JSON一致，仍会被认证stdout_only=True、marker_count=1、market_values_exported=False，并令Registry completed。独立完整worker→marker→native→parser→Bridge/Registry探针5例：无注解/标准注解2正例通过，带rows的3负例全部误接受。合成行字节未写入Registry；没有真实市场数据或真实QC执行。

建议递归核验所有受支持text节点的annotations，拒绝未登记行/错误等侧载荷；如支持标准audience/priority/lastModified注解，应明确字段和类型，保留合法标准注解及等价双表示正例。该忽略分支在7bf和e513已存在，不能声称本提交首次引入。见 `shared_branch_history.json`。

脚本、逐例原生形状、首次失败、修正diff、实际命令与源码SHA均已归档。所有所用源码前后哈希一致，未修改生产源码、预算或实际在途任务。真实SDK兼容、真实成功运行、完整实际失败回执、部署/输入读回及金融/覆盖证据仍未完成，不能由合成测试放行。
