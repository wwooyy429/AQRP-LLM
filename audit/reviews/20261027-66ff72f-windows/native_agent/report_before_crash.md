固定源码 `66ff72ffaaff8c91c008898e6527c91131176c2a`：本代理覆盖的新失败封装、编译拒绝、协议/CLI与旧合同兼容在独立合成范围通过，未确认新增缺陷。

新增首跑 **6方法／62子例全部通过**，0 failure/error/skip，exit0，118.294秒。其中runtime解析20例、compile解析20例、v1/v2 started/ambiguous拒绝CLI4例、协议/已有接受/输入守卫14例、旧无marker runtime失败CLI2例及成功LEAN恢复CLI2例。每例及实际命令详见 `main/results.json` 和 `main/command_log.json`。

原3/28边界和原4个失败结算探针也原字节重放通过，三份原脚本/support SHA逐一相同，旧输出不覆盖。汇总为9个unittest方法／90子例，另1程序／4个参数化失败探针；实际CLI子进程102、synthetic metadata `_finish` 调用14、**实际worker和SDK均0**。原脚本旧81f/ae字面标签保留，实际argv与新源码哈希绑定66ff，不能据旧标签误认运行身份。

实际临时Filesystem链验证：原Research成功后才能准入LEAN；新prepare固定协议绑定identity和deployment/input_hash，恢复旧输入不补标记；编译拒绝只允许未接受任务，started/ambiguous失败不退款，同拒绝幂等、不同拒绝和失败后追加接受均拒绝。pending外部身份及单独接受指针的崩溃窗口都阻断拒绝覆盖。缺标记、foreign attempt/input标记、缺准入和输入字节篡改均拒绝且无文件/用量新增。

runtime严格封装、终态短语、诊断和原read参数绑定；transport、ID/project错配、矛盾载体、隐藏rows和非法诊断拒绝。旧无协议任务仍可按原接受提交结算synthetic runtime失败或成功，坏current/catalog、缺deployment/input和source漂移不妨碍原attempt恢复。runtime不补造completed/progress/订单观察；诊断/警告的合成敏感sentinel不进入Registry，只存hash/计数。这不是任意可信字符串隐编码的无泄漏证明。

上述回执全部自编合成：成功cell内的固定检查失败不是实际失败Research执行；Runtime Error对象和新isError失败封装也未调用平台。原真实13事件账本只读/哈希，不重新结算或重置；真实终态来源由其他证据代理审核。本代理不认证实际原生编译拒绝、新部署/输入读回、真实成功失败Research/LEAN、完整数据/金融或阶段2验收。

首跑脚本、逐CLI stdout/stderr、fixture原生输入和准入store、源码/权威预算/journal前后哈希完整保存。来源位置：`engineering_receipts.py:371-437,476-507`；`engineering_tasks.py:24-28,556-679`；`stage2.py:174-200,276-293`；`registry.py:606-629`。无生产源码/预算/真实账本改动，无QC/市场/模型/部署调用。
