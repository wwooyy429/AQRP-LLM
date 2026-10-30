AQRP-LLM 独立复验 ea6053e3e9ef4be17db246daf18a4cf9b2e5be58，2026-10-27 Windows
结论：原WR20/21触发场景修复后通过；新WR23/P1和WR22/P2阻断本轮模块整体验收；WR24/P3非阻断。阶段2整体未通过，financial_evidence=false。
先读formal_report.txt/.json、findings.json、test_execution_summary.json；完整正式JSON和反例核心直接在聊天交付，附件非唯一证据。
source4541、failed baseline deb4270、actual cloud7fc4204均为完整固定Git原字节并逐字节核对；source_git_manifest.json记录全部hash。新修补未上云；旧云端读回仅历史离线重解析。
只读封包核验：python -B verify_artifacts.py，无需项目依赖或网络。本包artifact_manifest.json为当前封包校验权威；历史首checksum或日志若记录旧LF测量，保留不作当前raw校验。
实际依赖：Python3.10.11、requirements-audit.txt版本。先复制需要的固定source和独立审核scripts/support到新目录再运行，不往sealed目录写输出。生产入口python -B tools/stages.py verify在独立完整副本630通过。
WR20原byte-identical minimal与13方法/43场景：deb退出1，ea退出0；candidate13全过。原脚本中fixed_commit=deb和SID200_ranked_first目标标签保持原字节，不当当前实际身份/排名。
WR21原byte-identical17CLI反例：deb退出1，ea退出0；显式entry存在/dispatch缺失已拒，合法绑定和明确旧兼容保留。不能把此原例通过推成自然写失败后协议识别也正确。
WR23：python -B dispatch_agent/minimal_prepare_entry_crash.py --source <固定source> --out <新输出目录>，同目录放independent_recovery_support.py；当前exit1。首次entry写点同步异常使admission已落而协议无，恢复后成功结算并同父LEAN可准入；6CLI+1合成metadata_finish、0worker/provider，无手动删除已存在marker。根独立原件重复见wr23_confirmation。
WR22：python -B cert_agent/minimal_wr22.py --output <新结果.json>，相邻cert_fixture.py，父目录放source；当前exit1。完整老SID历史+近期映射、流动性齐全/单缺正控正确；全缺却被201补位，12checks误全true。根再次重复见wr22_confirmation。完整原批次、refs/count/raw及7个认证false均保留。
WR24：python -B archive_agent/minimal_wr24_metadata.py，当前exit1；current字段残留旧轮收费/文件列表/平台读取描述，仅P3不影响真实用量。
新数据9方法8过1失败/23场景（2失败记录同WR22），原630与历史16套件248方法2307子例通过；Collection12/36、worker9/81、fraction10/803、WR16 9/4、WR18 9/39、诊断6/51、预检12/70、原生失败6/91等通过。方法/子例/场景/CLI/手工/静态有重叠，不累计为独有总数。
旧native6/62、完成合同3/28、manual8、恢复5/46在独立合法index4绑定前置适配后过；类/断言AST不变。原先缺绑定被新guard拒绝、setup未完成及依赖template缺失的原始结果完整保留，不计通过。适配不改生产或放宽断言。
根另执行3入口正控链/21CLI，2个实际Windows进程只发1许可；未知执行不重跑、恢复不盲补旧marker。native原正常15→17→17、写故障15→16→18→18多审计pending非重复扣费。
静态主55/55+补充44/44不计软件方法。审查器首schema54/55和root else0语法错误、矩阵LF/CRLF侧校验误差等原件不改，另存正确raw校验及QA。子审中断未执行扩展不计；根已独立核对完成输出及反例。
原17事件和deb逐字节相等，旧13前缀；预算7/12、Research10/20、LEAN1/16，工程2/2/1仍停止，无退款或本轮实际扣费。本轮QC/Research/LEAN/model/deploy/trading/最终数据读取全部0，未改生产或批准合并PR。
旧完整deb审核ZIP33811222 bytes、SHA19d2614008caf209c18b79e16220826de0394ee9a86f585f32ccce5a9bfd6b49，含12474清单项+自身12475文件；本次Git选择216原件3361243bytes、省略12259。4047旧Git归档不变是另一历史总体，不冒称完整旧包。
完整actualargv/cwd/stdout/stderr、首次失败和版本/夹具差异均在。可重构的大case/source副本及source.tar不重复入包，三固定Git树内部所有历史路径保留；旧C/B证据不删。
本地31部署与归档7fc旧31仅28同3异，不是本轮平台inventory认证。f5d原Research归档CollectionError仍failed，底层cause未知；无成功报告、新LEAN或金融指标。旧worker差异、真实成功联合链、全历史US200/财务版本/实际送达仍不足。
下一步只离线修WR23协议身份/发布顺序、WR22历史连续资格，以及WR24当前元数据，提供新固定SHA；保持工程停止门，不自动重交或扩大额度。
正式研究、自动GPT、交易、最终测试关闭；2024–2025暴露/2026独立性未知保留，阶段3–7未验收，软件不代表金融有效。
