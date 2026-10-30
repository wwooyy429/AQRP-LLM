AQRP-LLM独立复验44676db609b3b7c2175fa7fa4f19c8ccf8165458，Windows，2026-10-27。
先读formal_report.txt/.json、test_execution_summary.json；完整JSON和最小复现也直接在聊天交付，本包为补充。
本轮WR25/26/27原修复及注明相邻离线边界通过，未发现新增已复现软件问题；阶段2整体仍待真实成功联合链与数据认证，阶段3–7未验收，financial_evidence=false。通过仅限本次已测离线范围，不认证无缺陷、供应商或金融效果。
封包核验：python -B verify_artifacts.py，仅标准库、无网络。artifact_manifest.json为本包当前raw校验权威；source_git_manifest.json列三固定Git树全部hash。5433候选、4977失败ccad基线、4204实际cloud7fc均完整导出原字节，逐文件重比；固定source内部历史路径完全不裁剪。
重放先复制到新目录，Python3.10.11及requirements-audit.txt版本。正常入口python -B tools/stages.py verify在新完整可写副本运行，668通过；不向sealed包写输出。root另实际执行tools/research.py build，完整副本全部字节不变。
原7场景MRE字节不改：python -B minimal_wr25_wr26.py --source <固定source> --output <新JSON>。旧ccad exit1三误过，新446 exit0；明确stock/null/unknown/future/missing应不足，etf/unlisted仍可排除。原创fixture来自固定Git内历史独立审核，不导入开发者夹具。根独立再次确认在root_repair_confirmation。
WR27原MRE在旧ccad负控exit1。原字节直接跑新候选先因旧baseline断言停在产品CLI之前，首次保留，不记产品失败或通过；仅C/B两版本常量窄适配、原预期断言不改后新候选exit0。复现：python -B archive_agent/adapted_minimal_wr27.py --source <固定source> --git-repository <已有Git对象库> --output <新目录>。默认0、错误S哈希1、正确T哈希0；相对root及7目标拒绝也正确；root第二次独立确认在root_wr27_confirmation。
原WR20 13/43、WR22 9/23、上轮WR25/26边界9/29及新增资格套件、协议5/21、native9/90、manual8、recovery5/46、f5d6/91等实际结果详正式JSON。16历史248方法2307子例通过；方法/场景/子例/CLI/静态及重复复现有重叠，不计独有总数。67来源检查、WR27 9组/7拒绝为静态或只读CLI，非产品unit。
所有实际argv/cwd/exit/stdout/stderr/hash、首次失败及版本/夹具适配保留。原native/recovery合法绑定及WR21明确四字段前置为已认可适配；原脚本内旧literal SHA/静态目标标签保留，实际身份由外层绑定。协议并发在v1/v2每组4实际Windows进程只发1许可，不扩为OS kill/断电认证。
可重建cases、嵌套derived source、build_source、alternate_root和source.tar不重复入包；固定source树内部全部保留。开发省略binary Git index原件实际存在且rawhash吻合，仅临时工件未转码；原打包UTF8失败与纠正及61开发输出/381选择归档核验保留，不冒称完整上轮包。
权威17事件、7/12配置、10/20Research、1/16LEAN与ccad原字节一致；工程2/2/1停止，无退款。本轮真实QC/Research/LEAN/model/deploy/trading/账本写入0，生产源码/Git index不改，PR保持草稿未批准合并。
实际云端仍7fc归档Research CollectionError失败，底层原因未知；旧LEAN归档初始化源码不符失败，均非本轮live read。归档31云端参考对当前31为28同3异，不认证当前inventory/旧失败worker。正常原生失败恢复15→17→17；故障15→16→18→18的pending非新扣费。
新版真实Research→缓存→LEAN成功联合链、全历史US200、财务版本、真实送达/摄入仍证据不足；history API次数/接收行数/真实订单/金融统计null。正式研究、自动GPT、交易、最终测试关闭；2024–2025已暴露，2026独立性未知。
下一步是由有权执行者处理工程停止条件及真实联调/数据证据；本轮审核不授权新增执行、扩大额度或金融测试。
