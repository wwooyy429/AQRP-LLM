AQRP-LLM e513c66 独立审核包
正式结论：WR-11、WR-12阻断新增采集任务桥；全系统未验收；无金融证据。
source为608份固定Git原件，基线7bf/fbe也逐字节保存。
Python3.10，pip install -r requirements-audit.txt。
python -B run_offline_review.py --out <一个不存在的新目录>
预期：既有回归和准入通过；回执、CLI复现exit1，汇总器验证这些预期退出后exit0，不表示软件通过。
原始首次失败保留。cli_agent/case-*只保存原运行的状态/输入/变更配置，重复源码由source重建；临时绝对路径是历史执行记录。
portable复验输出另保存在本包portable_replay；不改固定source。只对审核者脚本的解释器/旧fbe路径建立显式diff。
没有新增平台、市场、模型、部署或真实预算调用。
