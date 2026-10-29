独立复审 AQRP-20261029-975F676-RECOVERY009-25
固定源码975f676、审核资料a6a5a16；全量987回归及已测局部软件范围通过，阶段2整体未通过。
本轮没有云端调用、真实行情行读取、真实预算/生产源码修改或PR批准合并。
source/与materials/是完整不可变Git原字节导出，分别7045/7076份文件；source_git_manifest.json逐文件校验。
root_execution_records.json保留两个幂等build、987测试及a6独立Git资料核对的真实命令/退出码。
notification_agent、windows_lock_agent及其supplement、history_agent保存首次失败、夹具适配、补充、stdout/stderr和全部QA（含旧hash不符及读取器错误）。
formal_report_pre_QA.*保留更正适配措辞前草稿。所有产品文件与断言未为获得通过而修改。
历史WR矩阵见history_agent/WR_current_matrix.json：原确认SHA与scope、当前987相关test IDs、额外独立重放及未重跑旧完整套件逐项区分。
旧b1a/ca5平台元数据只作离线重解析，不是新候选真实运行。旧PROJECT/Research43原字节与LEAN43 EOF归一化分开；当前部署44文件。
配置周期3/13、累计16，Research17/20、LEAN3/16，71事件和旧69原前缀保留。原人类新增额度对话本轮未独立获取，不授执行权限。
为去除重复，仅省略可重建的根work_source、materials_checkout Git工作树以及history_agent/replay_context/source重复树；原固定源码、历史脚本、首失败及适配diff/全部结果均已收入。非Git的百度同步临时旁文件不收入证据。
首个B同步目录封存因临时旁文件增删而被严格文件集合检查拒绝，记录见packaging_failure_001.json和原脚本；改为C盘严格封存后发布ZIP，未放宽校验或删除任何Git原件。B公开目录只提供报告/矩阵副本，完整封存与校验器在ZIP中。
部分Git来源重建/verify_review重跑要求实际固定Git检出（不是无.git导出）；原实际命令和版本已经记录。历史脚本需要按其runner建立合成上下文，不可将内嵌旧SHA当当前源码。
最小原生Windows检查：python -B minimal_windows.py source
新增根端已知答案：python -B independent_storage_identity.py
仓库回归：在临时source副本执行 python -B tools/stages.py verify，勿覆盖封存目录。
封存校验（只读）：python -B verify_artifacts.py
合成测试、进程请求、子场景、静态检查和重跑重叠，不能累加独有总数。金融证据为false。
