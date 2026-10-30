本目录紧凑归档用户提交的独立复验 AQRP-20261028-4A42C18-EOFV2-23。

固定审核源码：4a42c18f0b78bea2068d589bc12f1615712354c6。
不可变比较基线：8d65c290773547c83549c098172f1eb8c3376cd7。
原资料提交：1cf26578da59eebd37e138ca5d6d076991386470。
审核结论：EOF-v2已测试核心/桥接功能范围通过；WR-28/P2阻断候选交付校验；阶段2整体未验收。
本目录只做归档和原始证据完整性核对，不重跑产品测试、不关闭WR、不产生新的独立批准或运行授权。

evidence/原样保留全部167份非源码证据，包括正式报告、首次失败、审查器helper/夹具修正、差异、复跑输出、执行记录和原错误checker日志。
user_delivery.txt为用户本轮原消息。原正式报告及失败记录不因后续修复而改写。
import_index.json记录原ZIP、两份完整大清单及每份复制原件的SHA256；archive_manifest.json封存本紧凑目录。

完整原始封存包保留在：
B:/BaiduSyncdisk/学习/投资/量化/量化交易比赛/LLM审核/review-4a42c18-20261028.zip
SHA256：e7f32eba7ccebcd6f833a9954b5ca13f50ec1a762497c59ae5f8a7a93fcc1910

三套Git导出共18,517份文件，不在本目录再次复制；原source_git_manifest.json、artifact_manifest.json也留在原封存ZIP中。
完整manifest有18,685项，另含manifest自身，ZIP共有18,686个文件条目。省略是存储去重，不删除或缩改独立审核范围。
原始树目录、commit、count及清单哈希见import_index.json；凭原封存包可还原完整索引和所有源码。

本目录自检（标准库、只读、无平台调用）：
python -B audit/reviews/20261028-4a42c18-eofv2/verify_import.py

重新校验原ZIP全部CRC、每项SHA和原始三树清单：
python -B audit/reviews/20261028-4a42c18-eofv2/verify_import.py --original-zip "B:/BaiduSyncdisk/学习/投资/量化/量化交易比赛/LLM审核/review-4a42c18-20261028.zip"

另从本地不可变Git对象核对三个导出树全部原字节（不checkout、不转换换行）：
python -B audit/reviews/20261028-4a42c18-eofv2/verify_import.py --original-zip "B:/BaiduSyncdisk/学习/投资/量化/量化交易比赛/LLM审核/review-4a42c18-20261028.zip" --git-repository .

evidence/verify_artifacts.py为审核者原脚本，原样保留；它要求完整原包，不适用于省略重复源码的本目录。
本归档自检通过只证明所保存原件及封存包一致，不改变正式报告中的WR-28失败。首次错误和审查器修正均保留，测试计数有重叠，不能相加为独立总数。

原失败LEAN仍为Runtime Error/failed；7项成功检查和实际订单数仍null。新EOF-v2候选未获云端成功证据。
预算为配置12/12、Research15/20、LEAN2/16，48事件及原46事件前缀保留；本次归档无QC、Research、LEAN、模型或供应商调用，无扣额、退款或上限变更。
完整历史US200、经济身份歧义、财务数值/版本和实际送达/摄入时点及计费认证派发仍有缺口。
阶段2和完整系统保持未验收；正式研究、自动GPT、交易及最终测试关闭。2024–2025暴露事实与2026独立性未认证事实保持。
