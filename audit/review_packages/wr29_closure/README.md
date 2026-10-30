# WR-29独立复验关闭登记

本轮为已有精确源码的审核结果归档，没有修改宿主或计算实现，也没有新增云端执行或重新计算金融指标。

独立报告`AQRP-20261029-C2E63AC-WR29-27`固定源码`c2e63ac5f19901bd95e127069b5998452f7f9864`、受审资料`f698a38a99c3ed8388c9403f2eda723b579c5eaf`。源清单`9d0d6da95815ee77d993d823df616d575a3ec4f00f5e40e859a7858de02dad5f`和218份managed文件保持不变。WR-29/P1只在原标准脚本/module合法factory身份缺陷范围关闭，并保留本轮实际测试的本地CLI/stdio/API有限通过。

原审方最小脚本及成功预期没有改变：旧2d1d306的0/2/2及assertion exit1保留，新c2e63ac为0/0/0及exit0。独立实际重跑1012仓库、原19及新增6子集、原独立stdio/API及补充、新8方法/51入口场景、新3/28 append恢复和旧通知/锁/周期套件。所有计数有重叠，不合计独有总数。1012是本次独立复验的实际结果，本轮登记没有再次重跑代码。

独立首次append检查曾对Windows CRT字段有错误预期，保留首败与更正；实际Win32错误32通过Python表现为errno13/winerror=None，系统安全停止，释放句柄后同原响应可恢复且无重派/预算变化。旧开发79/84、89/90和未取trace异常未追认为历史全绿；原8/8恢复和10/10克隆没有被本次重新执行的等效故障测试替代。

原完整ZIP SHA为`aa3255bf18d19c397a3b50bcbdca7533c72d6ad4736776d970233e431fb332f6`；ZIP15416成员、原manifest15415条及对应Git映射已逐项核对。Git只选取196原件：84原UTF8 LF、112组明确LF镜像/原raw.base64。它不是完整原ZIP；省略source/materials及巨大映射/diff的原路径、bytes和SHA在import_index中。原正式JSON SHA为`3e8f605973c618ba9aa1761ade0a9901b9fb7003fb609492664621d99c517470`。

本地同步旁文件不属于声明的selected archive成员，也不进入Git。原ZIP完整集合校验并未放宽。348项旧开发守卫只声明worktree before/after字节相等；五个CRLF表示与Git blob差异分别保留，不能说全部原Git字节相同。

当前结果见`audit/review_results/wr29.json`。之前pending request固定f698a38、失败报告固定2d1d306及所有旧handoff保持历史事实。本轮新归档元数据不冒称独立通过；源码c2e63ac的有限通过与完整阶段2分开。

核对本轮登记：`python -B audit/review_packages/wr29_closure/verify_closure.py`，范围反例加`--self-test`。旧wr29/verify_review.py只在其原f698a38资料树重放，它对open/pending的断言不应倒改。本轮无需另建软件版本或重跑市场任务。

配置周期3/13、累计16、Research17/20、LEAN3/16、71事件及008closed保留。下一步是受限真实宿主/transport和完整回执收集的准备，再补US200/SID、财务数值及真实历史时点、计费认证；真实联调仍须明确授权。完整阶段2和阶段3–7未通过，金融证据false，最终测试等闸门关闭；2024–2025已暴露，2026未认证。
