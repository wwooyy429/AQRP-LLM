AQRP-20261029-2D1D306-HOST010-26 独立复审
结论：新宿主启用CLI/stdio不通过，WR-29/P1；阶段2整体未通过。
1006仓库、19宿主子集、7元数据自测通过；API18/89通过；stdio19方法17过2失败、69成功完成场景。计数重叠不合计独有总数。
source2d1d306与materials fe08846完整原Git字节保留，7080/7445文件；216份身份中原213未变、新增3，原44份云端部署未因本轮改变或重新运行。
root_execution_records.json、各agent/execution_records及archive replay保存实际命令/退出码。所有首跑失败、夹具/审核helper修正、stdio产品失败和原始日志均保留。
WR29：标准factory导入followup_host.FollowupHost，官方脚本/-m定义__main__.FollowupHost，第469行精确同一性比较拒绝合法对象。canonical import控制exit0，两个可执行入口exit2（应0）。不修改产品或失败预期。
最小复现：python -B minimal_wr29.py source
注意：当前最小复现的合法路径断言应失败、程序exit1，这是真实产品失败，不是通过或expectedFailure；minimum_execution.json保留控制0/脚本2/模块2。
材料verify_review.py需实际固定Git检出；本次已在独立Git副本运行成功。tools/stages.py verify需在另建临时source副本运行，会生成audit/stage_verification.json，不得写封存目录。
原975 Windows18/37、通知12/79+6/27、周期7/28原脚本在当前source全部首跑通过；内嵌旧SHA只作历史标签，实际source明确为2d。
旧975完整ZIP hash c4437f...14330项及CRC、旧7045+7076 Git blobs核对。205原件恢复，100直接原字节+105LF镜像/raw.base64；selected不是完整原包。
346开发守卫前后相等，其中5项是已重建核对的工作树CRLF表示，不能称全部与Git原字节一致。71账本/原69前缀不变，配置周期3/13累计16、Research17/20LEAN3/16、008关轮。
本轮QC/Research/LEAN/compile/市场/模型/生产automation调用和真实预算/生产源码写入均0。旧b1a云端证据不继承新宿主。未来1/1/1无授权/准入/真实任务ID。
为去重，只省略根work_source、materials_checkout及archive_agent/replay_context/source重复树；原完整source/materials、原脚本、结果和首次失败均保留。不收入非Git的同步临时旁文件。
严格封存在C临时区完成，ZIP逐项hash/CRC通过后复制B盘；B目录只提供报告和最小复现副本，完整包与校验器在ZIP。
封存校验：python -B verify_artifacts.py（校验文件，不表示软件验收通过）。
正式研究、自动GPT、交易及最终测试保持关闭，financial_evidence=false。
