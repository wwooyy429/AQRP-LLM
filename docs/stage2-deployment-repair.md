# 阶段2：部署身份预检与逐文件故障诊断

本候选修补部署身份检查的诊断和执行前门禁，不宣称原云端初始化故障已消除。基线为 `f37340415ff080ae44310c912044f683e9986e96`；最终审核必须固定包含本文件的实际 Git 提交。阶段2整体仍待验收，原生拒绝和运行失败适配器也仍需固定版本独立审核。

## 实际观察与待证假设

原 attempt `bfd00f2611fd4496b9498d4597618a8e`、回测 `39cafa1e9b11f91b27e396b66d033a6d` 已按真实初始化异常结算为失败。不是提交失败或编译失败。此次只读排查先列项目，再读取列表返回的项目38436695；返回的25份已知实现逐项严格匹配原冻结清单，原输入的独立原字节哈希也匹配。记录在 `audit/stage2_deployment_root_cause.json`。

该记录来自实际 `read_project` 返回的 Python 源码投影；不是原生回执的替代品，也不是失败 worker 的文件快照。原始返回含 notebook，本轮未保存 notebook 内容，未把筛选后的对象冒充原生封装。旧回测列表给出的 snapshotId 38457775 不属于项目列表返回的 projectId，没有拿它调用项目接口。页面目前只提供失败详情，未取得可核对的 worker 文件。

QuantConnect [自动补全官方文档](https://www.quantconnect.com/docs/v2/lean-cli/projects/autocomplete)说明云端运行会自动添加部分导入。对未显式导入 AlgorithmImports 的旧模块进行本地插入模拟，可以复现严格哈希拒绝；这只是合成机制演示。旧源码包含函数内导入和 future import，不能据此断言平台实际修改了哪些文件、如何插入或造成了本次失败。实际 worker 的差异文件、字节及哈希仍缺证据。不能通过忽略导入、去除文件末尾换行或改用语法等价来消除错误。

## 修改及兼容边界

共享库 `cloud/qresearch/engineering_data.py` 保留原来的 UTF-8-sig 解码和通用换行身份合同：CRLF/CR转换为LF，文件末尾换行数量参与哈希。每个源文件只读取一次，拒绝时的实际哈希来自同一次读取。异常给出固定分类、安全相对路径或路径哈希、预期和实际SHA-256；不输出源代码、绝对路径或底层系统异常。整个清单的路径、哈希和目录约束先验证，再读取文件；Windows保留设备名、非法字符及DEL字符拒绝。

`tools/stage2.py` 在freeze/preview之前、register/claim扣费之前，以及首次prepare写输入之前，检查当前物理源码、完整受管Python文件集合和部署清单。后两处还必须匹配计划冻结的 `deployment_hash`。把源码和清单同时改成另一套自洽版本也不能通过原计划。v2同时保留稳定执行源码和字段目录校验。

v1的旧全量source身份含可变预算投影；本候选不在claim阶段新增该全量身份复查，否则首次登记本身会使旧计划失效。v1仍严格复查冻结的物理部署身份。该兼容选择不是给旧v1授予v2控制器身份保证。已经准入的旧输入恢复继续先返回原输入，不依赖当前源码、清单或可变指针，也不补写提交协议标记。

新 `tools/deployment_preflight.py` 是返回源码引用的纯只读核对器。它要求显式冻结清单/哈希、项目列表及 `read_project` 工具封装，校验工具参数、内部项目ID、所有MCP载体、重复/别名路径、缺失/新增/变化文件和可选原输入哈希。非Python内容不进入输出或源码摘要。返回只有许可的路径、哈希、计数和边界标志，`ready_to_dispatch`、`worker_source_verified`、`full_cloud_inventory_certified`始终为false。它不能替代预算准入、实际云端部署或worker认证。

其CLI只接受合成或获准本地保存的输入文件；不得为使用CLI把含真实notebook输出的原始返回落盘：

```powershell
python -B tools/deployment_preflight.py --project-tool-file <许可的工具封装.json> --projects-file <项目列表.json> --manifest-file <冻结部署清单.json> --deployment-hash <SHA256> --project-id <列表返回的ID> --input-sha256 <原输入SHA256>
```

退出码0仅表示返回引用匹配，1表示文件/输入不匹配，2表示输入元数据非法。不会自行调用平台、登记配置或提交任务。

## 验证与送审

离线命令仍为 `python -B tools/research.py build` 和 `python -B tools/stages.py verify`。新增测试、同字节基线重放、开发侧额外边界探针、发现的夹具错误及修正均保存在 `audit/review_packages/deployment_integrity/`；以清单和实际执行输出为准，重复执行不能累计成独有测试数。开发侧同伴复核不是GPT Work独立验收。

独立审核应在最终Git源码上自行构造：物理源码变化但未build、源码和清单同时变化却沿用旧计划、额外/缺失文件、Windows路径与Unicode、单次读取诊断、EOF变动、MCP镜像矛盾、notebook秘密不进入输出，以及v1/v2旧输入恢复和预算零变更。还应复核原任务和原始失败证据不变，避免把source引用匹配判成worker成功。

本轮没有新增配置、Research执行或LEAN提交，全局用量保持6/12、9/20、1/16；实际账本仍为13事件。未改变旧任务状态、原输入、预算、时间分区或暴露记录。最终测试、正式研究、自动GPT调用和交易继续关闭；2024–2025已暴露，2026独立性未知。新版本未部署到云端，未取得成功运行或市场数据认证，不能称原故障已修复或因子具有金融有效性。下一次真实运行必须先通过固定版本独立审核和原有准入；工程域最后一个名义槽不用于盲目诊断重试。
