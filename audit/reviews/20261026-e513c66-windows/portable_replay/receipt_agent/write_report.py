import hashlib
import json
from pathlib import Path

OUT=Path(__file__).resolve().parent; ROOT=OUT.parent/'source'
first=json.loads((OUT/'first_run_summary.json').read_text(encoding='utf-8'))
minimal=json.loads((OUT/'minimal_parallel_output.json').read_text(encoding='utf-8'))
recovery=json.loads((OUT/'adapter_recovery.json').read_text(encoding='utf-8'))
exe=r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\venv\Scripts\python.exe'
def command(argv):return "& '"+exe+"' -B "+' '.join("'"+x.replace("'","''")+"'" for x in argv)
commands=[{'command':command(item['command_argv']),'tool_chunk_id':chunk,'exit_code':code,'purpose':purpose}
    for item,chunk,code,purpose in [(first,'f22ecb',1,'首次独立14方法54子例；保留2个回归失败'),
        (minimal,'bddb39',1,'公共prepare-task→worker→原生形状→CLI research-result→Registry最小复现；3个误接受'),
        (recovery,'e11f78',0,'实际合成adapter回调未知/拒绝/worker异常3个恢复探针')]]
commands.append({'purpose':'只读发现路径错误','tool_chunk_id':'b6f55d','exit_code':1,
    'command':r"Get-Content -LiteralPath 'C:\Users\11638\.codex\tmp\aqrp-review-e513c66-20261026\source\cloud\qresearch\collection_task_cli.py'",
    'error':'Cannot find path ... because it does not exist.','resolution':'rg --files定位到source/tools/collection_task_cli.py后读取；未修改源文件。'})
commands.append({'purpose':'只读预期研究入口路径不存在','tool_chunk_id':'33b016','exit_code':1,
    'command':r"rg -n -C 3 'collection|run_collection' 'C:\Users\11638\.codex\tmp\aqrp-review-e513c66-20261026\source\cloud\research.py' 'C:\Users\11638\.codex\tmp\aqrp-review-e513c66-20261026\source\cloud\research.ipynb' 'C:\Users\11638\.codex\tmp\aqrp-review-e513c66-20261026\source\cloud\research_config.py'",
    'error':'cloud/research.py与cloud/research.ipynb不存在','resolution':'改读实际worker和tools/collection_task_cli.py；不将路径发现错误报告为产品缺陷。'})
(OUT/'command_log.json').write_text(json.dumps(commands,indent=2,ensure_ascii=False),encoding='utf-8')
after={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in first['source_raw_sha256']}
assert after==first['source_raw_sha256']
old=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-7bf716f-20261026\source\cloud\qresearch\engineering_receipts.py')
inherited=hashlib.sha256(old.read_bytes()).hexdigest()==after['cloud/qresearch/engineering_receipts.py']
matrix={}
for case in first['inputs']: matrix[case['method']]=matrix.get(case['method'],0)+1
finding={
    'id':'WR-11','priority':'P2','title':'双输出载体冲突被忽略，带额外行或错误的原生形状回执被认作stdout-only并完成',
    'primary_file':'cloud/qresearch/engineering_receipts.py','start_line':92,'end_line':93,
    'downstream':[{'file':'cloud/qresearch/collection_execution.py','start_line':122,'end_line':140},
        {'file':'tools/collection_task_cli.py','start_line':123,'end_line':125}],
    'trigger':'同一result含合法structuredContent marker，同时content含额外text行、display_data行或执行error。',
    'actual':'_native只返回structuredContent；另一输出载体完全未检查。collection_research_observation写stdout_only=True与marker_count=1；CLI research-result完整Bridge/Registry链把3个负例都终结为completed，报告market_values_exported=False。',
    'expected':'等价双表示可通过；冲突的额外输出、行展示或错误必须在终态认证前拒绝，不能宣称stdout-only。',
    'effect':'本地台账的元数据完整性与数据外传门槛失真。另一个载体真实含什么不能由被忽略的载体哈希证明；携带执行错误亦被完成。',
    'non_claim':'没有发现行字节被该parser写入Registry；Registry只保存原native结果digest和固定元数据。复现所有行与错误都是合成，无真实数据外传或真实Research执行。',
    'controls':'单载体及content/structuredContent完全等价的双载体两个正例均completed。单个有效载体内部的额外stdout、display_data、stderr、error、重复marker均被现有检查拒绝。',
    'line_cause':'engineering_receipts._native在92-93行提前return；collection_execution.py:140无条件标记stdout_only，tools/collection_task_cli.py:123-125随后入账。',
    'inherited_from_7bf':inherited,'inherited_file_sha256':after['cloud/qresearch/engineering_receipts.py'],
    'introduced_by_current_commit_claimed':False,
    'reproduction':'minimal_parallel_output.py','regression':'independent_receipts.py:test_native_parallel_content_row_leak_must_be_rejected',
    'fix_direction':'解析/正规化全部存在的输出载体；容许等价重复表示，拒绝冲突或额外行/显示/错误后才设置stdout_only。不要一律拒绝SDK规范的等价双表示。'
}
report={
    'reviewer':'receipt_agent independent review','fixed_commit':'e513c66e5965133fbe83fb0ab987eae853f96260',
    'date':'2026-10-26','verdict':'不通过：WR-11/P2已复现；真实新版运行和完整失败回执验证另有未完成门槛。',
    'first_run':{'methods':14,'passed_methods':13,'failed_methods':1,'subcases':54,'failure_records':2,'error_records':0,'skipped':0,'first_failure':first['first_failure']},
    'additional_minimal_probes':{'variants':5,'positive_controls':2,'positive_passed':2,'negative_variants':3,'incorrectly_accepted':3},
    'additional_adapter_recovery_probes':{'probes':3,'passed':3},
    'counts_are_overlapping_not_unique':True,'method_subcases':matrix,'findings':[finding],
    'source_hashes_before_after_equal':True,'source_hashes':after,
    'coverage':['独立采集源→缓存→固定报告→structured/content/direct三种原生形状→pending→Registry completed。',
        '跨attempt/plan_hash/config_id/project/source/deployment/request/stage/report_path/external_identity_kind篡改拒绝；completion input_hash与已存submission不同拒绝。',
        '部署源码变更在source.fetch前拒绝；惰性输入只接受单字符串赋值，额外语句/调用/错误变量名拒绝。',
        '固定报告flags、字段白名单、missing计数、count bool、receipt路径与check/status不一致均拒绝。',
        '完整重入不fetch且恢复同报告；receipt identity/window/payload损坏及payload缺失不fetch。',
        '真正调用合成adapter：未知提交只扣一次保持ambiguous，晚到成功可核对终结；明确拒绝不回款，显式retry再扣后成功；worker异常保持ambiguous且不自动重取。',
        '源异常带合成行sentinel不会进入错误消息或Registry；合法报告和台账无合成行SID/数值。'],
    'uncompleted_evidence_separate_from_findings':[
        '未执行真实SDK/Python.NET/Research/LEAN；原生形状成功链不是实际平台成功执行证据。',
        '未验证真实执行失败的交付回执及失败终态完整链。worker源异常仅观察到抛出、intent保留和ambiguous阻止自动重试；现有CLI成功marker路径不把无marker错误直接当可重试失败，符合文档声明但不满足完整运行门槛。',
        '手动将固定check置false的失败marker探针仅验证元数据形状→Registry failed，不能冒充实际worker异常/平台失败回执。',
        'CLI research-result使用admission中已准备的deployment/input_hash，native参数只有projectId/index；本次只证明准备字节自洽和submission/completion一致，未证明真实云端上传/执行输入的独立读回。该点由受信调度器I/O边界承担，未单独另报缺陷。',
        '未证明历史US200成员、SID/分类/交易日、财务数值/修订/实际送达；未授权正式研究、最终测试或交易。'],
    'commands':'command_log.json','regression_inputs':'first_run_summary.json:inputs',
    'first_failure_preserved':'first_run_summary.json:first_failure / first_run_unittest.txt',
    'minimal_full_output':'minimal_parallel_output.json','adapter_full_output':'adapter_recovery.json',
    'actions':{'real_SDK':0,'market':0,'Research':0,'LEAN':0,'model_API':0,'deployment':0,'real_budget_changes':0,'source_edits':0,'actual_final_market_data_opened':0},
    'reviewer_process_notes':['不导入作者测试/fixture；所有输入、store、源行及异常均新造。',
        '首次运行14/54原始失败完整留存，未修生产源码，也未改首次测试后重跑覆盖失败。',
        '仅在receipt_agent目录写脚本/报告/临时合成部署和输入；临时目录由其TemporaryDirectory正常清理。',
        '发现错误路径均为只读探索，见命令日志；不混作产品失败。']
}
(OUT/'report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
(OUT/'WR11_minimal.md').write_text('''# WR-11 / P2：双载体冲突被静默忽略

固定 `e513c66e5965133fbe83fb0ab987eae853f96260`。`cloud/qresearch/engineering_receipts.py:92-93` 在result含非空structuredContent时直接返回，未检查并存content。`collection_execution.py:140`随后把该观察标为stdout_only=True、marker_count=1。

运行同目录 `minimal_parallel_output.py`，传入 `--source <固定归档source> --out <输出json>`。脚本通过真正的 `prepare_task` 生成并核对惰性输入，在临时合成部署/云store上运行worker，生成固定marker，再用 `execute_metadata_command(research-result)` 完整走Bridge/Registry。CLI的current_bridge/export_usage仅在本进程绑定合成Registry/内存导出，未碰真实账本。

| 变体 | 预期 | 实际 |
| --- | --- | --- |
| 只有合法structuredContent | completed | completed |
| content与structuredContent完全等价 | completed | completed |
| structuredContent合法、content另含打印合成行 | 拒绝 | completed |
| structuredContent合法、content另含display_data合成行 | 拒绝 | completed |
| structuredContent合法、content另含error且status=error/success=false | 拒绝 | completed |

三个误接受均保存stdout_only=True、marker_count=1，报告market_values_exported=False。行sentinel未持久化到Registry，Registry保留原result的digest；缺陷是额外输出/错误被忽略并作出不实认证，不是本次发现了真实市场行外传。最小完整原生形状与结果在 `minimal_parallel_output.json`。

`engineering_receipts.py`与已归档7bf文件SHA-256同为 `69326601a5180487695a66e7dc5d7f858efdfac691c49f72b85958948680491d`。此问题在本固定候选新增采集路径中复现，根因来自继承共享函数，不能声称必由本提交引入。修复应检查所有载体的一致性，允许SDK的等价双表示、拒绝冲突或额外输出；不应一刀拒绝任何双表示。
''',encoding='utf-8')
(OUT/'report.md').write_text('''# 采集worker / 回执独立审核

固定 `e513c66e5965133fbe83fb0ab987eae853f96260`：**本范围不通过**。确认WR-11/P2：并存MCP输出载体被忽略，额外行/显示或执行错误可通过stdout-only门槛并令Registry完成。详见 `WR11_minimal.md`、机器报告 `report.json` 和最小复现。

首次独立测试14方法54子例：13方法通过、1方法失败；2条失败记录、0错误、0跳过。首次失败未覆盖。额外完整CLI链5变体中2正例通过、3负例误接受；另有实际合成adapter回调的3条未知/失败/恢复探针全部通过。各组有重叠，不能相加宣称独立测试总数。

已验合法worker→缓存→固定marker→原生形状Research回执→pending→Registry completed；跨身份/部署/输入绑定、固定元数据白名单、缺失统计、无行台账、缓存重入、损坏不重取、未知/拒绝不退款及显式重试预扣均有独立合成检查。实际命令、哈希、逐例输入及首次错误完整保留，所用7份源码前后哈希一致。

本次没有真实SDK、市场、Research、LEAN、模型、部署、预算变更、最终行情读取或候选源码修改。真实新版成功运行、真实失败交付回执完整链及真实上传/执行输入读回仍未完成；成功合成链和手造失败marker均不能代替这些证据。历史覆盖/财务/修订/送达认证也未由本报告证明。完整系统、正式研究、最终测试和交易不得据此放行。
''',encoding='utf-8')
manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.iterdir() if p.is_file() and p.name!='manifest.json'}
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps({'report':str(OUT/'report.json'),'findings':['WR-11/P2'],'first_methods':14,'first_subcases':54,'first_failures':2,'minimal_false_acceptances':3,'adapter_probes_passed':3,'source_hashes_unchanged':True},ensure_ascii=False))
