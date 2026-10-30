# Joint v2 worker 独立审核

固定 `8f7236ecbafcb514f07a6af4150a5afdbc1fd474`：本代理实际worker/collector/cache/receipt/Bridge完成链在所测合成范围通过，未新增确认缺陷。此结论不覆盖其他代理的Registry准入/CLI问题，也不代表阶段2或完整系统通过。

首跑9方法81子例，0失败/错误/跳过。为保存原字节stdout/stderr，另目录做1次明确捕获重放，仍9/81全过；首跑未覆盖，相同案例不累计成162个独有子例。原字节stdout3202B、stderr0B及完整argv/cwd/SHA在 `captured_execution.json`。

每次测试实际调用纯Python Research worker 11次（包含失败/intent重入）、receiver initialize 6次、finish 5次、receive_slice 15次，child helper重放3次。两次合计22/12/10/30/6；这些都是本地假SDK，不是实际Research/LEAN执行。三种成功回执模式用同一worker产物的独立Registry克隆，不冒称三次新Research。

成功链真实调用run_research_task：全2018假OHLCV缓存→40日真实Source/Collector→只读缓存→固定summary→原生形状Research parser→Registry完成→Research已验SID/refs→真实initialize/receive/finish_receiver→LEAN提交/读回/分块日志→Registry完成。direct/content/等价双表示均通过；假receiver仅观察3个发明weekday与1个合成dividend。

已知答案：40窗、80行、DollarVolume缺失40、另外3字段缺失0；False的HasFundamentalData成员40行保留。原生库存实现(start,end]；40个请求分别是原[A,B)端点各减1µs，保留Jan1、排除Feb10。父History一次、child原生40次，cache-only replay零新增；receipt/report原字节SHA、父identity/子plan hash/窗口refs一致。

跨父/attempt引用、summary计数/认证/行旁载荷、冲突载体、隐藏display/注解行、错误项目、LEAN挟带Research summary和改变SID/refs均拒绝。空child使Research报告failed并阻止LEAN；异常/越界/重复/混合响应保留intent、重入不重取；损坏receipt/payload不修复或重取。受信假adapter观察到先扣后执行，失败ambiguous且不免费派发重试。合成行sentinel不进入台账。

所用7份生产源码前后SHA一致，未导入作者fixture。FakeQB、ObjectStore、weekday日历、常量数值与dividend全部新造；无实际SDK/Research/LEAN/市场/模型/部署/网络/预算变更或最终行情读取。真实平台回执/输入读回、旧LEAN终态、市场覆盖与金融证据仍未验证。
