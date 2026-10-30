# WR-29开发修复与新SHA复验材料

修复源码固定`c2e63ac5f19901bd95e127069b5998452f7f9864`；source manifest为`9d0d6da95815ee77d993d823df616d575a3ec4f00f5e40e859a7858de02dad5f`。资料提交取实际交接消息的不可变Git版本。WR-29当前仅标记开发修复待独立复验，不能根据开发测试关闭。

原独审`AQRP-20261029-2D1D306-HOST010-26`固定2d1d306/fe08846，确认P1：合法factory正常导入`followup_host`，但脚本与module入口使用`__main__`的另一份类；严格类型检查把合法对象拒绝。原最小复现0/2/2，修复后重放0/0/0。新源码在定义类型/加载factory之前执行canonical薄入口；严格type/controller/authority/enabled、默认off、生产UTC和连接器权限不放宽。

原独审161原件以明确选择范围归档在`audit/reviews/20261029-2d1d306-host010`，77份原LF字节和84组LF可读镜像/raw.base64；Git选取包不是完整原ZIP。完整原包SHA为`feffb44a08485c0ac7dd87b46f47b53e810964c270ae41a9446ae6980aba4723`，原正式报告raw SHA为`224a7b8a0e7667b6759e685f71dae0fd54ba0eb6c914ced1c9c1332deb009e14`。报告及原失败/审核夹具更正保留，不改合法factory的成功预期。975f676原有限通过不变，2d1d306的API已测范围和CLI失败分开记录。

新增6项真实子进程回归涵盖canonical/脚本/module、合法空serve、默认off不导入、坏/disabled/duck/subclass拒绝、UTC、跨入口发现/响应/重启。原19项宿主回归也实际重跑。首个新增测试的未来submitted夹具非法，修正为合法pending，不改变产品时间规则；原失败和修正保留。完整规定验证及准确方法数见`full_offline_validation/result.json`，辅助检查不作为外部独审，也不累加重叠计数。

主守卫只声明本次worktree before/after原字节不变；它不能统称与Git原始blob相同。旧审核记录的五份CRLF差异见`protected_history.json`，保护预算/账本原字节及暴露事实分别核对。预算不变：配置周期3/13、累计16，Research17/20、LEAN3/16，71事件，008关闭；本轮QC/Research/LEAN/编译/模型/购买/准入均0。

核对当前固定资料：`python -B audit/review_packages/wr29/verify_review.py`，范围反例加`--self-test`；独立代码副本运行`python -B tools/stages.py verify`。旧host010核对脚本只能在原fe08846资料树运行。

新生产factory/transport未部署，真实通知/云端链和完整回执收集未认证，完整US200/SID、财务数值/版本/实际送达/摄入及计费认证仍缺。最终测试、正式研究、自动GPT、交易关闭，2024–2025已暴露及2026独立性未知保留。未来1/1/1仅待授权准备方案，不会因本修复触发执行。
