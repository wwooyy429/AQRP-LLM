# WR-17独立修复复验

固定 `ae2b8985f3799c246e90341370f86d80483f63ed`：**WR-17原冻结/按attempt恢复问题在本次离线范围修复后通过，未新增确认缺陷。** 不覆盖其他代理确认的WR-18，也不代表阶段2或完整系统通过。

首跑5方法46子例全过，0失败/错误/跳过，无重跑覆盖。实际72个隔离CLI子进程、12个直接freeze函数子进程，4次受限metadata `_finish`，实际worker次数0。另4个失败结算探针全过（28 CLI、6次metadata `_finish`），不计为4个单元方法；它们仅使用自建受限回执。

v1/v2原计划×started/pending/ambiguous×v1/v2目标×CLI/函数子进程24例及2个双进程混合freeze例全部拒绝，明确核对策略错误，前后持久文件SHA完全相同，未写新计划/listing、current指针、journal或预算。

两版本均从实际CLI freeze→register→claim→prepare开始。原admission保存后，删除current/deployment/catalog/本地input、改动当前源码，旧Research和LEAN仍能按原attempt prepare/status/settle；不重建缺失input文件、不新增费用。Research终结后合法零费freeze到B，仍可读取A原准入。篡改/foreign/missing admission、输入hash/字节或目标路径、额外字段、未知attempt均拒绝；finalized无admission不能创建新input。原本已存在的admission幂等读取仍允许，未当作新执行许可。

补充v1/v2各测固定check失败的Research报告及LEAN Runtime Error形状，在同样漂移后都进入failed，usage不变，错误文本不入账。成功cell中的失败check不是实际Research执行失败；LEAN错误封装也完全合成，不能替代真实原生失败证据。

原 `minimal_pending_freeze.py` 原字节SHA `c2771ab9fdf7b90f971b988491ab95d1d1eb35da69da058c2cba9d45e1aead8c` 已单独重放exit0：v1/v2 freeze都拒绝、旧指针/journal不变、原pending attempt prepare成功。原件和原始stdout/stderr均保留。

源码主范围：stage2.py:70–74统一冻结锁/检查，91–117从不可变config恢复Bridge，120–149校验admission/hash/本地字节，152–157幂等读取/终结新输入拒绝，224–247按attempt路由。所用原源码及权威budget/journal前后SHA相同；只在隔离副本写合成账本和输入。

全部原始命令、stdout/stderr、首跑与补充输出及精确计数均归档。未导入作者测试fixture，未运行真实SDK/worker/Research/LEAN/QC/模型或市场任务。真实平台运行、旧任务终态、数据/金融证据及其他共享准入问题仍单独待验。
