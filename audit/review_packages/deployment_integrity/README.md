# 部署预检与诊断修补送审包

固定源码身份以本包所在Git提交为准，本轮程序修补基线为f37340415ff080ae44310c912044f683e9986e96。开发侧530项仓库合成测试和额外16方法边界探针通过；两者有重叠，不累计为546项独有检查。本包不是GPT Work审核结论。首次发布796ed92后，逐文件核对发现仓库README传输编码损坏；后续提交更正该文档及本说明，程序、配置、测试和源码身份不变，失败核对保留在Git历史。

`developer_outputs_manifest.json`登记78份原字节输出/脚本及SHA-256。`.gitattributes`关闭本目录的换行转换。`diagnostics/final_replay.json`是最终15方法诊断测试的同字节基线/候选重放；`preflight/summary.json`是最终22方法预检测试及66方法兼容执行；`peer/final-report.json`是额外16方法开发侧边界复核。失败子例和方法计数分开，缺少新增接口导致的异常也不是云端运行故障。

保留的早期修正包括：诊断测试的None/default合成夹具错误；设备路径探针最初漏mock旧read_text（OS拒绝，没有内容读出），随后同时隔离两种读取；两个旧夹具原本只给虚构源码哈希，现创建真实合成stub且不改原断言；同伴LEAN探针先因缺Research前置证据被正确门禁拒绝；同伴发现返回源码预检接受DEL路径，生产代码修后通过。不得删除前失败或把夹具错误登记成金融发现/云端失败。

从最终Git检出执行 `python -B tools/stages.py verify`；这只运行合成数据，不应触发任何市场或云端任务。最终专用测试已在tests/中。额外peer探针的原路径是`.git/repair-work/deployment-repair-peer/`，其ROOT采用parents[3]；复现时把peer/probe.py复制到这个原路径再用Python -B执行，不要直接从归档路径运行导致ROOT错误。root_cause及diagnostics重放脚本同样按清单origin还原到临时目录，保留原字节；它们需要本地可读取的旧Git提交。不得对真实账本执行归档中的结算脚本，本包没有要求新增真实提交。

root_cause目录只有源码哈希、AST导入清单和合成插入机制演示。旧75冻结清单、实际当前返回参考与原输入均一致；尚无实际worker逐文件证据。官方参考为[QuantConnect Autocomplete / Imports](https://www.quantconnect.com/docs/v2/lean-cli/projects/autocomplete#07-Imports)。该文档只支持可能机制，不能证明具体worker转换。旧AST初版ImportFrom清单只识别两文件；all_forms版还包括两处函数内import，完整结果为四文件存在导入、21文件没有。旧future import使盲目前缀插入还可能产生语法问题，因此不能把21文件模拟当成真实平台实现。

verification/compare_current.py的输入投影只留在本地临时区；含notebook的原生封装和Python源码投影均未收入此包，不能仅凭本包独立重放那次平台读取。实际计算结果明确记录在audit/stage2_deployment_root_cause.json，属于投影元数据，不冒充原生回执或worker快照。

最终源码、执行清单及部署身份分别为：

- source: be03e60b842695537192d78c33af0246009382d67528574a43bf541e06f08d1e
- execution source: 1b8339b34322f2a1a26176fe7cf339fe7f796b23696148154e11ca4ea82ab13e
- implementation: 6f28b7f280d5c94b7ce73edf50db0005dff4128c224100dcd1b945058e7ddb8e
- deployment: e96729c6fa3617f37f25eec71969a7824bd019ea6990f9df956c5c41ae030431

源码目录/docs/config等进入source清单，审计输出不进入该清单，以免自引用。实际账本、预算投影、旧输入、原生失败回执及暴露记录均逐字节未变。预算6/12、9/20、1/16，最终测试和正式研究关闭。原云端故障尚未确认消除，阶段2整体未通过，新版本未部署。详见docs/stage2-deployment-repair.md。
