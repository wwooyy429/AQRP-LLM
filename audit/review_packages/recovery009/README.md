# 修复009的软件与交付证据

源码提交：`975f676d62b561689909744f9e7236290e3f5fcb`。审核资料提交以实际交接消息中固定的Git提交为准；从`audit/current_review_package.json`取得入口和测试绑定。源码提交保留当时的旧readiness，后续资料提交只更正当前候选状态，二者源码hash相同。

本轮实现通知漏送后的有限历史对账控制、stage2回执登记/关闭watch，以及本进程精确owner锁的WinError32有限释放重试。只有`next.should_execute`允许调度一次查询，未知响应不重派。实际MCP宿主调度和推送传输没有做新云端联调；旧008轮已关轮，不再创建任务或watch。原始自动推送的具体丢失环节尚无证据。

`full_offline_validation`记录规定的完整合成测试、source overlay及原文件守卫。首次前台进程中止的材料原样保留于`full_offline_validation_aborted_001`，不能使用其继承的旧825项报告。`development_repairs.json`还保留夹具修复与开发命令错误。`auxiliary_boundary_review.py`和结果只属于开发辅助独立合成检查，实际Windows共享占用测试须在Windows运行，不能冒充GPT Work外部验收。

`protected_history.json`分别核对不可变Git blob及既有工作区字节。budget、baseline和71事件账本原字节不变；data_exposure、research和data三份既有Windows工作区文件使用CRLF，而Git使用LF，明确记录两套raw hash及同一事实，不宣称它们原始字节相等。未规范化这些原文件。

当前用量仍为配置周期3/13、累计16，Research17/20、LEAN3/16。没有新配置登记、执行、计费、退款、额度变更或资源购买。2024–2025暴露和2026未认证事实保留。

统一历史与完整审核指令在`docs/review/current`。旧b1a运行源码的Research13/13、LEAN7/7及ca5终态资料仅为历史有限工程证据；新源码没有云端运行证据。阶段2整体、正式研究、自动GPT、交易及最终测试关闭。

资料检验：`python -B audit/review_packages/recovery009/verify_review.py`。软件复验：在独立临时固定Git检出中运行`python -B tools/stages.py verify`，再自行构造独立反例。raw清单自洽不等于远端签名或独立验收。
