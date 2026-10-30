# host010离线候选与既往975f676验收登记

新宿主源码固定`2d1d3060dbc7eb136c1dee61f0647977528b8aad`，全源码清单`74bbefc270a6bd0d1385db9624eaa2bd600e38503f5932a88267a02a11c76a07`。资料提交以实际交接消息中的不可变Git版本为准。新宿主只有开发侧离线验证，尚无独审或真实宿主/云端认证。

本轮接收的独立审核固定旧源码975f676、资料a6a5a16。其987项仓库回归及通知18/106、Windows锁18/37等实际已测范围通过，无新增产品缺陷；阶段2整体未通过。实际执行任务为本地Codex聊天“更新 GPT 审核与验收状态”。旧ChatGPT聊天仅收到交接，不能据此声称它完成了本轮测试。

原报告、WR矩阵、原测试脚本、命令输出、首次失败/夹具适配及QA记录选取归档于`audit/reviews/20261029-975f676-recovery009`。205原件对应100份原LF文本及105组LF可读镜像/原raw.base64；镜像不是原字节。完整原ZIP另有SHA引用和完整集合核验记录，Git选取包不含source/materials导出及两份巨大原映射，不能称完整原包。新旧报告和研究历史均保留。

`tools/followup_host.py`提供默认关闭的Python API及stdio协议，使用固定next、独立前置发现许可、持久请求/关联ID、工具/参数白名单及连接器读取门禁。它不创建或重提任务。完成读取只交回`awaiting_native_receipt`，之后仍须原stage2固定parser、完整日志/零订单、Bridge/Registry结算与watch同步；本轮不宣称完整回执收集器或计费认证派发已完成。

开发首轮18宿主方法通过，补充字节边界反例后19方法首轮有1失败；修复后19通过。辅助边界复现的UTF8字节、直接API大小及未知发现状态问题已修复，10项重放通过；重复拒绝记录也作幂等。原始失败、修复后日志及脚本由`developer_records_manifest.json`绑定，不能当GPT独审。完整规定验证及准确计数见`full_offline_validation/result.json`，所有重叠数量不累加。

当前权威用量保持配置周期3/13、累计16，Research17/20、LEAN3/16，71事件，008关闭。新工程计划只准备、未授权/未准入/未冻结完整真实工具能力或派发，attempt/project/backtest均null。未创建production factory/automation；真实宿主和新44文件工程链、完整US200/SID、财务数值/版本/实际时点与计费认证仍是缺口。2024–2025暴露及2026未认证保留，最终测试等闸门关闭。

核验本轮：在固定资料Git检出执行`python -B audit/review_packages/host010/verify_review.py`，边界自测加`--self-test`。代码复验在独立私有副本运行`python -B tools/stages.py verify`。旧009的核对脚本仅在其固定a6a5a16资料树运行。本轮raw自洽清单不是远端签名或独立批准。
