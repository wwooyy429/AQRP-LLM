# WR-14 独立修复复验

固定 `4a94430144cd3d9e4b5469bd2b6e4a48d80d5fc7`：**WR-14在本次独立覆盖范围修复后通过，未发现可证实新缺陷。** 不等于阶段2或完整系统验收。

新增独立首跑10方法、803子例，0失败、0错误、0跳过，无审核器修正或重跑覆盖。已知答案覆盖0–6位点/逗号、T/t/空格、Z/z、有效偏移/naive提示、世纪闰年与有效年/月/日，注解和text原字符串不变。9–4096位数字fraction仅测试已登记数字串语法，不强加其他ISO形式。

新采集及旧run_research_task各实际执行一次纯Python合成worker；后者用审核者自建FakeQB、ObjectStore、发明weekday日历和常量数值。对同一预扣attempt的独立MemoryRegistry克隆，234个合法原生观察分支完成，36个非法日历/offset/旁载荷分支拒绝且台账字节/usage不变。2个同attempt先拒绝再纠正的恢复例完成，无重取/再扣费；行sentinel不进入台账。上述是2次worker加独立回执/ledger分支，不冒称234次独立worker执行。

旧LEAN提交/读回/logs三段外层短fraction正例及完整receipt→Bridge/Registry完成保留。WR-13未知rows/errors/outputs/_meta、非字符串text、非法priority/角色/时钟及深层JSON旁载荷拒绝继续有效。

源码 `engineering_receipts.py:77` 改为只构造年/月/日；严格regex经AST核对与dc49相同。小数不再交给运行时ISO解析，也没有补零、截断、舍入或改写原hint字符串。外层157行、递归316行仍经过共用text校验器。只读差异见 `production_change_readonly.diff`。

官方schema沿用固定c4c367f9f58296a7053f5c78a52fd02bfbb56a49，原字节SHA `268a5f82ba70fd7e4b6dc4aa1e64f116f74b4d0edcb69dc046829c79dd4e97e7`；审核者自建helper原hash一致，未导入作者测试夹具。七份所用生产文件运行前后hash一致。

真实SDK、Research、LEAN、市场、模型、部署、网络、实际预算变更和最终行情读取均为0。新版真实运行、完整实际失败回执、云端输入读回、旧LEAN终态、历史覆盖和金融证据仍缺证据；正式研究、最终测试和交易保持关闭。
