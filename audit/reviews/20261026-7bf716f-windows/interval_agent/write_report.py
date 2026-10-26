import hashlib
import json
from pathlib import Path

OUT=Path(__file__).resolve().parent
SOURCE=OUT.parent/'source'
STATIC=SOURCE/'audit/reviews/20261026-fbe2454-windows/source_agent/official_sdk_static'
def read(name): return json.loads((OUT/name).read_text(encoding='utf-8'))
candidate=read('candidate_summary.json'); baseline=read('baseline_summary.json')
start_candidate=read('candidate_start_only.json'); start_baseline=read('baseline_start_only.json')
exe=r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\venv\Scripts\python.exe'
def shell_command(argv):
    return "& '"+exe+"' -B "+' '.join("'"+str(x).replace("'","''")+"'" for x in argv)
commands=[]
for item,chunk,exitcode in [(candidate,'6b86aa',0),(baseline,'1b9e15',1),
                           (start_candidate,'7cc51f',0),(start_baseline,'1b8c61',1)]:
    commands.append({'kind':'synthetic execution','label':item['label'],
        'command':shell_command(item.get('command_argv',item.get('argv'))),
        'tool_chunk_id':chunk,'exit_code':exitcode})
commands += [
    {'kind':'read-only discovery error','tool_chunk_id':'609143','exit_code':1,
     'command':r"rg -n -C 8 'EndTime|StartTimeUtc|EndTimeUtc|SubscriptionDataReaderHistoryProvider|where|Where' 'C:\Users\11638\.codex\tmp\aqrp-review-7bf716f-20261026\source\audit\reviews\20261026-fbe2454-windows\source_agent\official_sdk_static\SubscriptionDataReaderHistoryProvider.cs'",
     'error':'系统找不到指定的文件。 (os error 2)',
     'resolution':'随后列目录发现归档以Engine__HistoricalData__前缀存储；改用完整文件名读取，chunk 014627。未据此修改源码或测试。'},
    {'kind':'read-only oversized inspection','tool_chunk_id':'12d2e1','exit_code':0,
     'command':r"Get-Content -LiteralPath 'C:\Users\11638\.codex\tmp\aqrp-review-7bf716f-20261026\change.diff'",
     'limitation':'宽范围diff含归档内容，输出被截断；后续以候选源码、合同文件及定向读取为结论依据。未导入任何开发者测试夹具。'},
]
(OUT/'command_log.json').write_text(json.dumps(commands,indent=2,ensure_ascii=False),encoding='utf-8')
specs=[
    (STATIC/'Engine__HistoricalData__SubscriptionDataReaderHistoryProvider.cs',['if (data.EndTime > EndTimeLocal) return false;','return data.EndTime > StartTimeLocal;']),
    (STATIC/'Common__Python__PandasData.cs',['var endTime = _isBaseData ? ((IBaseData)data).EndTime : default;','_rowTimes.Add(endTime);']),
    (STATIC/'Common__Data__Fundamental__FineFundamental.cs',['get { return Time + QuantConnect.Time.OneDay; }','set { Time = value - QuantConnect.Time.OneDay; }']),
    (STATIC/'Research__QuantBook.cs',['var filteredUniverseSelectionData = RunUniverseSelection(convertedUniverse, start, end, dateRule);','var history = History(universe, start, endDate);','if (dateRule == null)']),
    (SOURCE/'audit/reviews/20261026-fbe2454-windows/upstream_history_factory.cs',['startAlgoTz.ConvertToUtc(_algorithm.TimeZone),','endAlgoTz.ConvertToUtc(_algorithm.TimeZone))']),
]
contracts=[]
for path,needles in specs:
    lines=path.read_text(encoding='utf-8-sig').splitlines()
    excerpts=[]
    for needle in needles:
        hits=[{'line':i+1,'text':s.strip()} for i,s in enumerate(lines) if needle in s]
        assert hits,(path,needle)
        excerpts.extend(hits)
    contracts.append({'path':str(path),'raw_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'excerpts':excerpts})
(OUT/'static_contracts.json').write_text(json.dumps({'LEAN_commit':'f3d841e60dfd010ee5fc293ea893e56952484108','real_SDK_executed':False,'files':contracts},indent=2,ensure_ascii=False),encoding='utf-8')
after={p:hashlib.sha256((SOURCE/p).read_bytes()).hexdigest() for p in candidate['hashes_raw_sha256']}
assert after==candidate['hashes_raw_sha256'],'candidate source changed after tests'
matrix={}
for case in candidate['inputs']:
    name=case['method']; matrix[name]=matrix.get(name,0)+1
report={
    'reviewer':'independent interval_agent','date':'2026-10-26',
    'candidate_commit':'7bf716f45fd6183951a492f0201012af717070f0',
    'baseline_commit':'fbe2454e6ea10aa59211c01f236c54bb251527be',
    'finding_id':'WR-10','verdict':'修复在已核对的Daily基本面、Python datetime微秒网格及固定官方合同范围通过独立复验',
    'new_confirmed_defects':[],
    'candidate_results':{'methods':12,'passed_methods':12,'subcases':75,'failure_records':0,'error_records':0,'skipped':0,'additional_start_only_public_api_probes':2,'additional_probe_passed':2},
    'baseline_control':{'methods':2,'error_methods':2,'subcases':21,'error_records':21,'failure_records':0,'skipped':0,
        'first_failure':baseline['first_failure'],
        'start_only_public_api_probes':{'direct_expected':1,'direct_actual':0,'collector_expected':1,'collector_actual':0,'collector_empty_windows':1}},
    'method_subcases':matrix,'source_hashes_before_and_after_equal':True,'source_hashes':after,
    'static_contracts':'static_contracts.json','commands':'command_log.json',
    'regression_inputs':'candidate_summary.json:inputs','first_baseline_error':'baseline_summary.json:first_failure',
    'method':'独立FakeQB只实施(start,end] EndTime合同；使用标准库datetime/zoneinfo在UTC时间线上计算预期端点；不复用开发者夹具。公共QuantConnectSnapshotSource→HistoricalSnapshotCollector→MemoryArtifactStore→缓存复读全链；检查原冻结窗口与实际SDK请求分别保持其合同。',
    'equivalence':'在整数微秒网格上，A-1us < t <= B-1us 等价于 A <= t < B；UTC平移后转NY naive交给算法时区解释。',
    'evidence_limits':['只读核对固定官方源码，不执行真实SDK、Python.NET、Research或LEAN。',
        '不推广到任意100ns .NET tick/custom history；固定Daily午夜数据及Python datetime微秒网格是本结论范围。',
        '日历分窗不是交易所日历；合成通过不证明全市场SID、历史成员、字段值/修订、实际送达或财务证据。',
        '预算桥和真实部署/运行不在本次WR-10修复验收内；不将已声明缺证据项单独伪报为新缺陷。'],
    'actions':{'real_SDK':0,'market':0,'Research':0,'LEAN':0,'model_API':0,'deployment':0,'budget_changes':0,'candidate_source_edits':0,'baseline_source_edits':0,'actual_final_market_data_opened':0},
    'reviewer_process_notes':['首个定向静态文件路径缺少归档前缀导致rg失败，已按目录修正。',
        '早期宽范围diff输出截断，未用截断内容支撑结论。',
        '独立测试首次候选运行即12/75通过；无中途修生产源码或改测试掩盖候选失败。',
        '基线故障回放和候选输出分别保留，报告不覆盖旧正式失败结论。']
}
(OUT/'report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
markdown='''# WR-10 独立复验报告

固定候选 `7bf716f45fd6183951a492f0201012af717070f0`：WR-10 在已核对的 Daily 基本面路径、Python datetime 微秒网格与固定官方 LEAN 合同范围通过独立复验；未发现可证实新缺陷。结论不等于阶段2整体通过，也不等于真实SDK执行或金融证据。

独立脚本 `independent_intervals.py` 新造 FakeQB，原生侧仅按 `(start,end]` EndTime 过滤；预期值用标准库 datetime/zoneinfo 的UTC运算构造。未导入开发者测试夹具。候选首次运行 **12方法、75子例，0失败、0错误、0跳过**；另有 start-only 公共API直接源及collector两条探针，均得到预期1条。

覆盖：1/2/7日；2012/2018/2020/2023春秋DST；20日连续分窗（1/2/7日块）；UTC等价输入；aware秋季重复小时；末微秒；end=2024-01-01的合成边界；空窗；非午夜/8日/空/逆序/无时区/最终区间请求拒绝；源响应在start前、end上和end后拒绝；重复和混合股票池拒绝；失败intent保留且不重试。公共源→collector→内存存储→缓存复读检查了原冻结[start,end)窗口、实际平移请求、两SID记录、零值/缺失统计、认证标记false及不重取。

同一主脚本绑定旧 `fbe2454e6ea10aa59211c01f236c54bb251527be` 运行2核心方法/21子例，21个错误；首错为 `HistoricalSourceError: Duplicate or out-of-window native universe snapshot`。另一个独立start-only探针在旧源直接与collector都得到0条（应1条），collector错误完成为空窗；候选两条路径恢复1条。旧失败与候选输出分别留存。

固定官方源码核对：过滤 EndTime > start 且 EndTime <= end；Pandas行索引取EndTime；FineFundamental.EndTime为Time+1日；HistoryRequestFactory按算法时区将naive端点转UTC；QuantBook默认dateRule为空直接传递History结果。文件哈希与行号在 `static_contracts.json`。

在整数微秒网格，`A−1µs < t <= B−1µs` 等价于 `A <= t < B`。源码在UTC平移，collector继续验证原冻结边界，连续窗无间隙或重复，final合成边界没有进入原生请求。候选historical_source.py原字节SHA-256：`e979799f49ab66472c3c26467b8172608f9872645f7df6b86ec2919c13ed0556`；运行后四个所用生产文件哈希均未变化。

环境为固定Windows/Python3.10.11/numpy1.26.4/pandas2.3.3。实际可重放命令、工具chunk与退出码在 `command_log.json`；逐例回归输入及首次基线错误在各summary JSON；原始unittest输出完整保留。早期rg因归档文件名前缀缺失失败，后修正；一次宽diff读取被截断，后续改定向源码读取。这两项审核过程记录未被删掉。

本次真实SDK、市场、Research、LEAN、模型、部署、预算变更及最终行情读取均为0。未修改候选/基线源码。任意100ns自定义历史、交易所日历、市场覆盖/数值/版本/送达、预算任务桥与真实部署仍不由本报告证明。
'''
(OUT/'report.md').write_text(markdown,encoding='utf-8')
manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.iterdir() if p.is_file() and p.name!='manifest.json'}
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps({'report':str(OUT/'report.json'),'candidate_methods':12,'candidate_subcases':75,'candidate_success':True,'extra_public_api_probes':2,'new_defects':0,'files':len(manifest)},ensure_ascii=False))
