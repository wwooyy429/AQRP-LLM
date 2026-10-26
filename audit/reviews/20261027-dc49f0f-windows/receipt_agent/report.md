# WR-13修复复验与WR-14新增回归

固定 `dc49f0f3037918f3ce4413665c59b164a8d6e2b7`：WR-13原未知annotations/非字符串text旁路在本次独立范围修复后通过；**新增WR-14/P2，回执边界整体仍不通过**。

原5变体另存适配后，2正例完成、3未知rows负例捕获预期拒绝，保持started、Registry字节及usage不变；原件和适配diff均保留。新增独立12方法160子例首跑有1失败记录（Role enum顺序测量错误）及2时间错误；只纠正Role集合比较后，11方法通过、1方法产生2错误记录，0失败/跳过，时间错误没有被消掉。

WR-14位于 `engineering_receipts.py:73–78`：文档 `docs/review/wr13.md:11` 声明普通小数秒，前置正则也接受；固定Python3.10.11的fromisoformat却拒绝1/2/4/5位fraction，报invalid calendar。`2018-01-03T00:00:00.5Z`即为最小普通格式。后续完整worker→marker→parser→Bridge/Registry脚本，对新采集与旧run_research_task各测全秒及1–6位：候选14例只完成6、8误拒绝，旧be94426同14例全完成。外层注解为空，排除了旧outer标准注解另因拒绝。所有worker报告在校验前已completed，被拒后Registry仍started；没有新增扣费或行入台账。9位fraction仅保留为首矩阵观察，不支撑主判定。

建议保持原hint字符串/marker身份，仅对日历校验副本规范化普通fraction或按分量校验，并保留非法日期/offset/未知字段拒绝；不能把合法正例改成拒绝来消绿。本问题是提示注解兼容回归，不是金融日期计算错误，也不证明真实QC发生过。

官方MCP 2025-11-25 schema已按文件commit `c4c367f9f58296a7053f5c78a52fd02bfbb56a49`固定，SHA256 `268a5f82ba70fd7e4b6dc4aa1e64f116f74b4d0edcb69dc046829c79dd4e97e7`。注解字段/Role/priority/text类型合同见 `official_schema_contract.json`；本适配器的白名单与时钟子集不等于任意MCP扩展或全部ISO认证。[官方固定schema](https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/c4c367f9f58296a7053f5c78a52fd02bfbb56a49/schema/2025-11-25/schema.json)

新旧完整worker、旧LEAN三段回执、深层JSON、标准注解、未知行/错误、非字符串text、finite priority及无效offset均有独立新造输入。旧worker使用发明weekday日历/常量数值，合成通过不是交易所或数据覆盖证据。所有源文件前后SHA不变；真实SDK/Research/LEAN/市场/模型/部署/预算变更/最终行情读取均为0，只有官方primary静态schema取证。真实运行与完整原生失败回执仍未验证。
