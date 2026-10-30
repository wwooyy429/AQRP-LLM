AQRP-LLM be94426 独立复审包
正式结论：WR-11、WR-12在原问题及离线测试范围修复后通过；WR-13/P2阻断回执边界。阶段2及全系统未验收，无金融证据。
source为891份固定Git原件；基线e513的608份、fbe的313份原件另存。
Python3.10：pip install -r requirements-audit.txt
校验：python -B verify_artifacts.py
最小复现：python -B minimal_nested_annotations.py source（当前exit1）
完整有效报告链：python -B receipt_agent/nested_annotations_probe.py --source source --out <新JSON路径>（当前exit1，2正例完成/3误接受）
完整重现：python -B run_offline_review.py --out <不存在的新目录>
聚合脚本本轮仅检查语法和help；各底层验收命令均实际执行。不声称聚合脚本已整段重跑。该脚本会记录纯审核者解释器/基线/去重引用路径绑定diff。
聚合器核对预期结果后exit0不表示软件验收通过，WR13仍为失败。原始首跑、测量修正和差异全部保留。
recovery_agent/cases和runs/repository_source重复生成源码副本未装入包；所有独立测试、合成输入生成、61条CLI命令/输出和状态观察均保留，可由固定source重建。原临时目录未删除。
原run_main_checks最后一次原回执路径不存在而exit2，执行0方法；run_resolved_receipts按归档去重引用核对原字节后14/54通过。没有把它计为产品缺陷。
历史运行记录中绝对路径和脚本历史SHA字面量保持原样，以外层实际固定Git/源码hash绑定身份。
没有修改开发者源码或真实预算，没有新增Research、LEAN、模型、部署、交易或数据访问。
