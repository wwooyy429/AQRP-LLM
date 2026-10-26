# WR-10 独立复验报告

固定候选 `7bf716f45fd6183951a492f0201012af717070f0`：WR-10 在已核对的 Daily 基本面路径、Python datetime 微秒网格与固定官方 LEAN 合同范围通过独立复验；未发现可证实新缺陷。结论不等于阶段2整体通过，也不等于真实SDK执行或金融证据。

独立脚本 `independent_intervals.py` 新造 FakeQB，原生侧仅按 `(start,end]` EndTime 过滤；预期值用标准库 datetime/zoneinfo 的UTC运算构造。未导入开发者测试夹具。候选首次运行 **12方法、75子例，0失败、0错误、0跳过**；另有 start-only 公共API直接源及collector两条探针，均得到预期1条。

覆盖：1/2/7日；2012/2018/2020/2023春秋DST；20日连续分窗（1/2/7日块）；UTC等价输入；aware秋季重复小时；末微秒；end=2024-01-01的合成边界；空窗；非午夜/8日/空/逆序/无时区/最终区间请求拒绝；源响应在start前、end上和end后拒绝；重复和混合股票池拒绝；失败intent保留且不重试。公共源→collector→内存存储→缓存复读检查了原冻结[start,end)窗口、实际平移请求、两SID记录、零值/缺失统计、认证标记false及不重取。

同一主脚本绑定旧 `fbe2454e6ea10aa59211c01f236c54bb251527be` 运行2核心方法/21子例，21个错误；首错为 `HistoricalSourceError: Duplicate or out-of-window native universe snapshot`。另一个独立start-only探针在旧源直接与collector都得到0条（应1条），collector错误完成为空窗；候选两条路径恢复1条。旧失败与候选输出分别留存。

固定官方源码核对：过滤 EndTime > start 且 EndTime <= end；Pandas行索引取EndTime；FineFundamental.EndTime为Time+1日；HistoryRequestFactory按算法时区将naive端点转UTC；QuantBook默认dateRule为空直接传递History结果。文件哈希与行号在 `static_contracts.json`。

在整数微秒网格，`A−1µs < t <= B−1µs` 等价于 `A <= t < B`。源码在UTC平移，collector继续验证原冻结边界，连续窗无间隙或重复，final合成边界没有进入原生请求。候选historical_source.py原字节SHA-256：`e979799f49ab66472c3c26467b8172608f9872645f7df6b86ec2919c13ed0556`；运行后四个所用生产文件哈希均未变化。

环境为固定Windows/Python3.10.11/numpy1.26.4/pandas2.3.3。实际可重放命令、工具chunk与退出码在 `command_log.json`；逐例回归输入及首次基线错误在各summary JSON；原始unittest输出完整保留。早期rg因归档文件名前缀缺失失败，后修正；一次宽diff读取被截断，后续改定向源码读取。这两项审核过程记录未被删掉。

本次真实SDK、市场、Research、LEAN、模型、部署、预算变更及最终行情读取均为0。未修改候选/基线源码。任意100ns自定义历史、交易所日历、市场覆盖/数值/版本/送达、预算任务桥与真实部署仍不由本报告证明。
