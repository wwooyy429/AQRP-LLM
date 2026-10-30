固定提交 `81fbe5294055423e88ee5aeae48ca6223e7971da`：本代理负责的旧恢复链及新共享 loader／完成合同边界通过，未确认新增缺陷。Registry 准入由主审和另一代理独立复验；完整系统、阶段2及真实平台执行仍未验收。

- 原 ae 独立脚本、support、direct 入口和两份 capture 共6文件原字节 SHA 一致，旧结果未覆盖。首跑 **5方法／46子例全过**，0 failure/error/skip，exit 0，91.088秒。涵盖 v1/v2、三个 open 状态、两种 freeze schema、CLI/函数进程及并发拒绝，以及原 attempt Research/LEAN 成功结算、current 计划切换、输入缺失／漂移／篡改拒绝。
- 原失败探针 **1程序／4子例全过**：v1/v2 Research 固定检查失败报告和 LEAN Runtime Error 合成信封在漂移后结算 failed，无新扣款，错误正文不持久化。成功合成 cell 内的 failed 报告不是真实失败 Research 执行；LEAN 信封也为合成。
- 新增首跑 **3方法／28子例全过**，0 failure/error/skip，exit 0，21.669秒。四种 v1/v2×Research/LEAN 路径分别验证：12例原提交缺失／哈希自洽空raw／accepted=false在完成回调前拒绝；12例 input_hash 冲突／空终态raw／未知rows在写入前拒绝；4例合法缺席或同步completed提交status、成功结算和completed幂等。坏current/catalog、缺deployment/local input、current source漂移均不阻断原冻结Bridge结算。幂等只读不赋予重新dispatch权限。

计数分别为8个unittest方法／74个子例，另1个程序／4个参数化失败探针；存在语义重叠，不作金融独立样本相加。实际生产CLI子进程116、direct freeze进程12、合成 metadata `_finish` 调用14，**实际worker／SDK／Research／LEAN执行均0**。本代理本轮无新增失败MRE，未重跑旧pending-freeze MRE；该问题由原5/46回归覆盖。

原脚本摘要保留硬编码 `commit=ae2b898…`，没有为新版本改写原件。实际 `--source` 命令及新 `engineering_tasks.py` SHA `c957b7ccc415e86a88f90b29bea63ee01f5ca657d1437340a890dad21b482a9e` 证明本轮目标为81f。见 `byte_identical_replay_inputs.json` 和三份 execution JSON。

源码核对：`engineering_tasks.py:436-479`共享原提交loader、`:662-690`完成合同、`:692-720`幂等和先验证后保存；`stage2.py:91-157`原attempt/准入恢复。首跑 stdout/stderr、每CLI原始输出、argv、输入和源码哈希完整保留，路径见 `report.json`；源文件、权威预算和原journal SHA前后相等。所有输入是独立合成受限元数据，不导入作者测试夹具、不访问网络/QC/市场/模型、不部署。
