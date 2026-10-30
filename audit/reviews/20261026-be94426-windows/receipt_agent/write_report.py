import difflib
import hashlib
import json
from pathlib import Path

OUT=Path(__file__).resolve().parent;ROOT=OUT.parent/'source'
def read(name):return json.loads((OUT/name).read_text(encoding='utf-8'))
first=read('first_run_summary.json');corrected=read('corrected_run_summary.json');nested=read('nested_annotations_probe.json')
initial_script=OUT/'independent_carrier_boundaries.py';corrected_script=OUT/'independent_carrier_boundaries_corrected.py'
diff=''.join(difflib.unified_diff(initial_script.read_text(encoding='utf-8').splitlines(True),
    corrected_script.read_text(encoding='utf-8').splitlines(True),fromfile=initial_script.name,tofile=corrected_script.name))
(OUT/'reviewer_correction.diff').write_text(diff,encoding='utf-8')
assert hashlib.sha256(initial_script.read_bytes()).hexdigest()==first['script_sha256']
assert hashlib.sha256(corrected_script.read_bytes()).hexdigest()==corrected['script_sha256']
assert first['source_raw_sha256']==corrected['source_raw_sha256']
after={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in corrected['source_raw_sha256']}
assert after==corrected['source_raw_sha256']
exe=r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\venv\Scripts\python.exe'
def command(argv):return "& '"+exe+"' -B "+' '.join("'"+s.replace("'","''")+"'" for s in argv)
commands=[{'command':command(doc['command_argv']),'tool_chunk_id':chunk,'exit_code':code,'purpose':purpose}
    for doc,chunk,code,purpose in [(first,'f3dbc2',1,'首次新增独立15方法80子例，1审核器预期错误，原始输出保留'),
        (corrected,'66aee3',0,'另存修正审核器15方法80子例，0失败/错误/跳过'),
        (nested,'207d3e',1,'WR-13完整worker→双载体→parser→Bridge/Registry，5例中3误接受')]]
(OUT/'command_log.json').write_text(json.dumps(commands,indent=2,ensure_ascii=False),encoding='utf-8')
needle='''        if node.get("type") == "text" and set(node) <= {"type", "text", "annotations"}:
            visit(node.get("text"))
            return'''
inheritance=[]
for label,folder in [('7bf716f',r'C:\Users\11638\.codex\tmp\aqrp-review-7bf716f-20261026\source'),
    ('e513c66',r'C:\Users\11638\.codex\tmp\aqrp-review-e513c66-20261026\source'),
    ('be94426',str(ROOT))]:
    path=Path(folder)/'cloud/qresearch/engineering_receipts.py';text=path.read_text(encoding='utf-8')
    assert needle in text
    inheritance.append({'version':label,'file':str(path),'raw_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'same_ignored_annotations_branch_present':True,'branch_first_line':text[:text.index(needle)].count('\n')+1})
(OUT/'shared_branch_history.json').write_text(json.dumps(inheritance,indent=2,ensure_ascii=False),encoding='utf-8')
matrix={}
for case in corrected['inputs']:matrix[case['method']]=matrix.get(case['method'],0)+1
finding={'id':'WR-13','priority':'P2','title':'受支持的嵌套TextContent忽略未知annotations，带行侧载荷仍认证stdout-only并完成',
    'file':'cloud/qresearch/engineering_receipts.py','start_line':271,'end_line':273,
    'related_locations':[{'file':'cloud/qresearch/engineering_receipts.py','start_line':108,'end_line':111},
        {'file':'cloud/qresearch/engineering_receipts.py','start_line':301,'end_line':305},
        {'file':'cloud/qresearch/collection_execution.py','start_line':122,'end_line':140}],
    'trigger':'原生structuredContent中使用解析器明确支持的content/outputs包装text节点或直接text节点；text为合法固定marker，annotations带未知rows数组；外层content包含完全等价的JSON镜像。',
    'expected':'两个载体相同仍须递归验证所承载内容；未知annotations行/错误侧载荷应在stdout_only和终态前拒绝。若支持标准注解，应明确字段和类型。',
    'actual':'_native按完整JSON确认两载体相等；_research_stdout的text节点分支只visit(text)，不查看annotations。3个带合成rows的负例都得到Registry completed，raw.stdout_only=True、marker_count=1、report.market_values_exported=False。',
    'impact':'内容驻留与完成证据门槛遗漏了一条受支持输入路径。相同载体只能证明它们一致，不能证明annotations无额外数据。',
    'controls':'无注解及标准audience/priority/lastModified注解两正例都完成。不是主张所有annotations都应拒绝。外层MCP content块对非空annotations已有更严格检查，嵌套入口却忽略未知rows。',
    'limitations':'不声称真实QuantConnect SDK已发送这种注解，也不声称任意SDK封装均已认证。所有行均为新造合成sentinel；行字节未写入Registry，原生结果只以digest进入台账。',
    'reproduction':'nested_annotations_probe.py','evidence':'nested_annotations_probe.json','subcases':5,'false_acceptances':3,
    'fix_direction':'对所有解析器支持的text节点递归核验annotations。使用明确注解字段/类型白名单，拒绝未登记行/错误/其他侧载荷；保留合法标准注解与等价双表示的正向路径。',
    'root_cause_history':'7bf与e513中已存在同一忽略annotations分支，见shared_branch_history.json；不能归因本提交首次引入。'}
report={'reviewer':'receipt_agent independent repair review','commit':'be9442603a31481a9a71e51ca794df77650c7411','date':'2026-10-26',
    'verdict':'WR-11原双载体不一致路径在新增独立范围修复后通过；新增WR-13/P2旁路已复现，当前回执边界整体仍不通过。',
    'WR11_scope_result':'修复后通过：候选所有存在载体完整语义比较、等价键序/缩进、空可选载体、未知顶层/块元数据、类型差异、错误/隐藏输出、重复JSON键及新旧回执链。',
    'first_measurement':{'methods':15,'subcases':80,'failure_records':1,'error_records':0,'skipped':0,
        'classification':'审核器预期错误，不是产品缺陷','first_failure':first['first_failure']},
    'corrected_measurement':{'methods':15,'passed_methods':15,'subcases':80,'failure_records':0,'error_records':0,'skipped':0},
    'measurement_correction':'首跑把structuredContent=None当作实际存在载体，与空JSON字符串比较要求拒绝；源码与原合同明确None表示缺席。另存修正版将输入改为{x:null}与{x:""}，使两个载体实际存在，保留类型差异目标。只改该输入和输出文件名；未改候选源码，未覆盖首跑。diff在reviewer_correction.diff。',
    'additional_WR13_probe':{'programs':1,'subcases':5,'positive_controls':2,'positive_passed':2,'negative_cases':3,'incorrectly_completed':3,'exit_code':1},
    'counts_overlap_do_not_add':True,'method_subcases':matrix,'findings':[finding],
    'scope_details':['新采集合成worker经云store缓存、固定报告、原生direct/structured/content/dual四形状、Bridge/Registry完整成功终态；合成源行只存云store。',
        '旧Research使用独立EngineeringTaskPlan与实际固定_finish报告程序，原生四形状经parser/Bridge/Registry完成。未运行其真实SDK数据取得worker。',
        '旧LEAN在合成Research已完成后，原生create_backtest→read_backtest→分块logs三段解析及Bridge/Registry完成；四种支持包装正例通过。',
        '旧LEAN等价双载体Runtime Error可终结failed，合成error/stacktrace行sentinel不写入台账。',
        '各载体单侧冲突、两侧相同但各自有stdout/display/error/stderr、顶层/外层annotations隐藏行、重复键和错误JSON类型拒绝；拒绝路径不产生Registry新字节。',
        '严格封装兼容范围仅限本脚本列出的已支持包装及JSON等价镜像；不推广为任意MCP或SDK包装认证。'],
    'source_hashes_before_after_equal':True,'source_raw_sha256':after,'commands':'command_log.json','regression_inputs':'corrected_run_summary.json:inputs',
    'first_run_preserved':['first_run_summary.json','first_run_unittest.txt','independent_carrier_boundaries.py'],
    'correction_files':['independent_carrier_boundaries_corrected.py','corrected_run_summary.json','corrected_run_unittest.txt','reviewer_correction.diff'],
    'uncompleted_evidence':['真实新版成功运行与完整实际原生失败回执仍未执行。','真实SDK/Python.NET包装、云端部署/输入读回和金融/数据覆盖不由合成回执链证明。','原在途LEAN未查询、未重交、未替换输入；正式研究、最终测试和交易未开启。'],
    'actions':{'network':0,'real_SDK':0,'Research':0,'LEAN':0,'market':0,'models':0,'deployment':0,'actual_budget_changes':0,'candidate_source_edits':0,'actual_final_market_data_opened':0}}
(OUT/'report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
(OUT/'report.md').write_text('''# WR-11修复复验与WR-13新增旁路

固定 `be9442603a31481a9a71e51ca794df77650c7411`：WR-11原双载体不一致路径在本次独立范围修复后通过；**WR-13/P2已复现，当前回执边界整体仍不通过**。

新增独立矩阵修正版15方法80子例全过，0失败/错误/跳过，覆盖旧Research、旧LEAN提交/读回/日志、新采集worker到Registry完整回执链、等价双表示、冲突/错误/隐藏输出、顶层元数据、JSON类型与重复键、无行持久化。首跑15/80有1条审核器预期错误：误把structuredContent=None当作存在的载体；None实际表示缺席。首跑与原脚本保留，修正版和diff另存，不能把该测量错误归为生产缺陷。

WR-13根因在 `cloud/qresearch/engineering_receipts.py:271-273`：受支持嵌套TextContent分支只读取text，忽略annotations。把合法marker放入content包装、outputs包装或native text根节点，并在annotations中附带未知合成rows；两个外层载体完整JSON一致，仍会被认证stdout_only=True、marker_count=1、market_values_exported=False，并令Registry completed。独立完整worker→marker→native→parser→Bridge/Registry探针5例：无注解/标准注解2正例通过，带rows的3负例全部误接受。合成行字节未写入Registry；没有真实市场数据或真实QC执行。

建议递归核验所有受支持text节点的annotations，拒绝未登记行/错误等侧载荷；如支持标准audience/priority/lastModified注解，应明确字段和类型，保留合法标准注解及等价双表示正例。该忽略分支在7bf和e513已存在，不能声称本提交首次引入。见 `shared_branch_history.json`。

脚本、逐例原生形状、首次失败、修正diff、实际命令与源码SHA均已归档。所有所用源码前后哈希一致，未修改生产源码、预算或实际在途任务。真实SDK兼容、真实成功运行、完整实际失败回执、部署/输入读回及金融/覆盖证据仍未完成，不能由合成测试放行。
''',encoding='utf-8')
manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.iterdir() if p.is_file() and p.name!='manifest.json'}
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps({'report':str(OUT/'report.json'),'WR11':'fixed_in_tested_scope','WR13':'confirmed_P2','corrected_methods':15,'corrected_subcases':80,'nested_probe_subcases':5,'nested_false_completions':3,'source_hashes_unchanged':True},ensure_ascii=False))
