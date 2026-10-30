import difflib
import hashlib
import json
from pathlib import Path

OUT=Path(__file__).resolve().parent;ROOT=OUT.parent/'source'
def read(name):return json.loads((OUT/name).read_text(encoding='utf-8'))
first=read('first_run_summary.json');corrected=read('role_corrected_summary.json')
candidate=read('candidate_fractional_clock.json');baseline=read('baseline_be94426_fractional_clock.json')
adapted=read('adapted_nested_annotations_probe.json')
def make_diff(old,new,out):
    a=(OUT/old).read_text(encoding='utf-8').splitlines(True);b=(OUT/new).read_text(encoding='utf-8').splitlines(True)
    (OUT/out).write_text(''.join(difflib.unified_diff(a,b,fromfile=old,tofile=new)),encoding='utf-8')
make_diff('independent_annotations.py','independent_annotations_role_corrected.py','reviewer_role_correction.diff')
make_diff('original_nested_annotations_probe.py','adapted_nested_annotations_probe.py','adapted_nested_annotations.diff')
original=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-be94426-20261026\receipt_agent\nested_annotations_probe.py')
assert (OUT/'original_nested_annotations_probe.py').read_bytes()==original.read_bytes()
assert hashlib.sha256((OUT/'independent_annotations.py').read_bytes()).hexdigest()==first['script_sha256']
assert hashlib.sha256((OUT/'independent_annotations_role_corrected.py').read_bytes()).hexdigest()==corrected['script_sha256']
after={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in first['source_raw_sha256']}
assert after==first['source_raw_sha256']==corrected['source_raw_sha256']
schema_path=OUT/'official_mcp_schema_2025-11-25.json';schema=json.loads(schema_path.read_text(encoding='utf-8'))['$defs']
official={'repository':'modelcontextprotocol/modelcontextprotocol','file_commit':'c4c367f9f58296a7053f5c78a52fd02bfbb56a49',
    'schema_version':'2025-11-25','fetch_date':'2026-10-27',
    'source_url':'https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/c4c367f9f58296a7053f5c78a52fd02bfbb56a49/schema/2025-11-25/schema.json',
    'discovery_url':'https://api.github.com/repos/modelcontextprotocol/modelcontextprotocol/commits?path=schema/2025-11-25/schema.json&per_page=1',
    'raw_sha256':hashlib.sha256(schema_path.read_bytes()).hexdigest(),
    'Annotations':schema['Annotations'],'Role':schema['Role'],'TextContent':schema['TextContent'],
    'interpretation':'官方Annotations登记三字段：audience为Role数组，priority为0–1数值，lastModified为ISO提示字符串；schema并未封闭全部扩展或机器校验全部ISO。本项目明确采用更窄白名单/时钟子集，未知扩展拒绝与None兼容是本适配器合同，不冒称所有MCP封装兼容。'}
(OUT/'official_schema_contract.json').write_text(json.dumps(official,indent=2,ensure_ascii=False),encoding='utf-8')
exe=r'C:\Users\11638\.codex\tmp\aqrp-review-20261026\venv\Scripts\python.exe'
def command(argv):return "& '"+exe+"' -B "+' '.join("'"+s.replace("'","''")+"'" for s in argv)
commands=[{'command':command(doc['command_argv']),'tool_chunk_id':chunk,'exit_code':code,'purpose':purpose}
    for doc,chunk,code,purpose in [(first,'291b61',1,'首次12/160：Role顺序测量失败1，时间验证产品错误记录2；原件保留'),
        (corrected,'4a2ccb',1,'只改Role集合比较：12/160，0失败记录，2时间错误记录保持'),
        (candidate,'d30da1',1,'普通微秒内fraction完整新旧worker14例，候选8误拒绝'),
        (baseline,'d7143d',0,'同一14例同一脚本旧be94426全完成；仅嵌套注解排除旧outer拒绝'),
        (adapted,'a2a187',0,'原5变体另存适配：2正例完成，3负例捕获预期拒绝')]]
commands.extend([
    {'purpose':'发现官方schema文件最后变更commit','tool_chunk_id':'10d034','exit_code':0,
        'command':"Invoke-RestMethod -Uri '"+official['discovery_url']+"' -Headers @{ 'User-Agent' = 'AQRP-Independent-Review' }"},
    {'purpose':'只读固定官方schema原字节','tool_chunk_id':'328f4e','exit_code':0,
        'command':"Invoke-WebRequest -Uri '"+official['source_url']+"' -OutFile '"+str(schema_path)+"'"},
    {'purpose':'为分版本探针抽出审核者自建worker/QB/Harness定义，不导入开发fixture','tool_chunk_id':'c5fefc','exit_code':0,
        'command':"& '"+exe+"' -B '"+str(OUT/'prepare_fractional_harness.py')+"'"},
    {'purpose':'官方primary页面读取','tool':'web.run','references':['turn18view0','turn19view0'],
        'urls':['https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/schema/2025-11-25/schema.json',official['source_url']]}
])
(OUT/'command_log.json').write_text(json.dumps(commands,indent=2,ensure_ascii=False),encoding='utf-8')
matrix={}
for case in corrected['inputs']:matrix[case['method']]=matrix.get(case['method'],0)+1
finding={'id':'WR-14','priority':'P2','title':'新注解校验器在固定Python3.10误拒绝普通小数秒，合法完成回执无法结算',
    'file':'cloud/qresearch/engineering_receipts.py','start_line':73,'end_line':78,
    'related_locations':[{'file':'cloud/qresearch/engineering_receipts.py','start_line':69,'end_line':70},
        {'file':'docs/review/wr13.md','start_line':11,'end_line':11}],
    'trigger':'lastModified为普通ISO提示时钟2018-01-03T00:00:00.5Z、.12Z、.1234Z或.12345Z；均在普通秒级/微秒内fraction形式，文档声明支持且前置正则接受。',
    'actual':'固定Python3.10.11的datetime.fromisoformat在此调用下只接受0/3/6位fraction；1/2/4/5位被报“not a valid calendar clock”。合法worker报告已completed，新采集和旧Research共8个完整链例被拒绝，Registry保持started。',
    'expected':'已登记的普通fraction提示应与其等值的毫秒/微秒拼写同样通过日历校验并结算；未知旁载荷和非法时钟仍拒绝。',
    'proof':'同脚本14例（2家族×全秒及1–6位）：候选仅6完成、8误拒绝；旧be94426同14例全完成。外层annotations为空，只有受支持嵌套标准lastModified，避免旧outer行为混淆。',
    'impact':'这是提示注解兼容回归，阻止已完成合法回执结算；不是金融日期计算错误，也不证明真实QC发生此事件。拒绝不新增扣费、不退款、无行写入Registry。',
    'introduced_by_current_validator':True,
    'fix_direction':'保持原hint字符串/marker身份，只对日历验证副本规范化普通fraction（例如在微秒内补齐），或显式逐分量校验；保持offset/日历/未知字段拒绝。不能把这些合法正例改成预期拒绝以使测试变绿。',
    'not_basis':'首矩阵9位fraction观察单独留存，不作为本问题唯一或核心依据；不要求全部ISO异体。',
    'reproduction':'fractional_clock_probe.py','candidate_evidence':'candidate_fractional_clock.json','baseline_evidence':'baseline_be94426_fractional_clock.json'}
report={'reviewer':'receipt_agent independent WR-13 repair review','commit':'dc49f0f3037918f3ce4413665c59b164a8d6e2b7','date':'2026-10-27',
    'verdict':'WR-13原未知注解/非字符串text旁路在本范围修复后通过；新增WR-14/P2普通fraction兼容回归，回执边界整体仍不通过。',
    'WR13_result':{'status':'修复后通过（原旁路和本次已测试范围）','adapted_original_variants':5,'positive_completed':2,'negative_correctly_rejected':3,
        'negative_registry_state':'started','negative_no_new_registry_bytes':True,'negative_no_budget_change':True},
    'first_run':{'methods':12,'passed_methods':10,'failed_methods':1,'error_methods':1,'subcases':160,'failure_records':1,'error_records':2,'skipped':0,'first_failure':first['first_failure']},
    'role_corrected_run':{'methods':12,'passed_methods':11,'failed_methods':0,'error_methods':1,'subcases':160,'failure_records':0,'error_records':2,'skipped':0},
    'reviewer_measurement_correction':'官方Role enum顺序与我首跑预期数组相反；角色允许集合相同，只有该比较改为集合。Role错误不是产品缺陷；两条时间ReceiptParseError原样保持，未吞掉。首跑和修正代码/输出均分别保留，diff另存。',
    'time_error_scope':'首矩阵含9位小数秒和1位comma/offset两个错误记录。前者单列兼容观察，不作为主判断；14例后续用dot/Z、1/2/4/5位微秒内格式独立证实WR14。',
    'additional_fractional_probe':{'programs':1,'variants_each_source':14,'candidate_completed':6,'candidate_false_rejections':8,'baseline_completed':14,'baseline_false_rejections':0},
    'counts_overlap_do_not_add':True,'method_subcases':matrix,'findings':[finding],
    'coverage':['共用_annotations/_text_node覆盖outer、text根、content/outputs、嵌套wrapper与四层JSON文本。未知rows/errors/outputs/_meta、非字符串text、错误audience、非有限/布尔/越界priority及无效日历/offset拒绝。',
        '新采集真实纯Pythonworker用独立SyntheticSource；旧run_research_task真实纯Pythonworker用新造FakeQB/ObjectStore、发明的weekday日历和常量数值，实际调用共享cache/coverage/报告。均不是真SDK执行或市场证据。',
        '有效6位fraction标准注解及合法outer/nested路径保留；新旧worker→marker→parser→Bridge/Registry完成，无合成行sentinel进入台账。',
        '新旧完整worker未知rows/errors负例拒绝且保持未终结、usage/字节不变。旧LEAN的提交/读回/logs带合法外层标准注解路径保持，未知外层注解三阶段均拒绝。'],
    'official_contract':'official_schema_contract.json','official_schema_file_sha256':official['raw_sha256'],
    'source_hashes_before_after_equal':True,'source_raw_sha256':after,'commands':'command_log.json',
    'original_adaptation':{'original_file':'original_nested_annotations_probe.py','original_byte_equal_to_be_probe':True,
        'original_sha256':hashlib.sha256(original.read_bytes()).hexdigest(),'adapted_file':'adapted_nested_annotations_probe.py','diff':'adapted_nested_annotations.diff',
        'explanation':'原脚本负例直接执行故障路径。适配只捕获预期ReceiptParseError并测量拒绝状态/字节/usage，改当前身份元数据；原5个输入及源行为未改，原件不覆盖。'},
    'regression_inputs':'role_corrected_summary.json:inputs','first_run_preserved':['first_run_summary.json','first_run_unittest.txt','independent_annotations.py'],
    'limits':['官方schema静态合同与声明子集，不认证任意MCP扩展或真实QC包装。','真实云端部署/输入读回、真实成功/完整失败回执、旧LEAN终态及市场数据覆盖仍未完成。','全部调用SDK形状均为本地新造对象，原在途任务未读/轮询/重交。'],
    'actions':{'official_primary_readonly_fetch':'仅官方GitHub schema/API/raw静态取证','real_SDK':0,'Research':0,'LEAN':0,'market':0,'models':0,'deployment':0,'real_budget_changes':0,'candidate_source_edits':0,'actual_final_market_data_opened':0}}
(OUT/'report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
(OUT/'report.md').write_text('''# WR-13修复复验与WR-14新增回归

固定 `dc49f0f3037918f3ce4413665c59b164a8d6e2b7`：WR-13原未知annotations/非字符串text旁路在本次独立范围修复后通过；**新增WR-14/P2，回执边界整体仍不通过**。

原5变体另存适配后，2正例完成、3未知rows负例捕获预期拒绝，保持started、Registry字节及usage不变；原件和适配diff均保留。新增独立12方法160子例首跑有1失败记录（Role enum顺序测量错误）及2时间错误；只纠正Role集合比较后，11方法通过、1方法产生2错误记录，0失败/跳过，时间错误没有被消掉。

WR-14位于 `engineering_receipts.py:73–78`：文档 `docs/review/wr13.md:11` 声明普通小数秒，前置正则也接受；固定Python3.10.11的fromisoformat却拒绝1/2/4/5位fraction，报invalid calendar。`2018-01-03T00:00:00.5Z`即为最小普通格式。后续完整worker→marker→parser→Bridge/Registry脚本，对新采集与旧run_research_task各测全秒及1–6位：候选14例只完成6、8误拒绝，旧be94426同14例全完成。外层注解为空，排除了旧outer标准注解另因拒绝。所有worker报告在校验前已completed，被拒后Registry仍started；没有新增扣费或行入台账。9位fraction仅保留为首矩阵观察，不支撑主判定。

建议保持原hint字符串/marker身份，仅对日历校验副本规范化普通fraction或按分量校验，并保留非法日期/offset/未知字段拒绝；不能把合法正例改成拒绝来消绿。本问题是提示注解兼容回归，不是金融日期计算错误，也不证明真实QC发生过。

官方MCP 2025-11-25 schema已按文件commit `c4c367f9f58296a7053f5c78a52fd02bfbb56a49`固定，SHA256 `268a5f82ba70fd7e4b6dc4aa1e64f116f74b4d0edcb69dc046829c79dd4e97e7`。注解字段/Role/priority/text类型合同见 `official_schema_contract.json`；本适配器的白名单与时钟子集不等于任意MCP扩展或全部ISO认证。[官方固定schema](https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/c4c367f9f58296a7053f5c78a52fd02bfbb56a49/schema/2025-11-25/schema.json)

新旧完整worker、旧LEAN三段回执、深层JSON、标准注解、未知行/错误、非字符串text、finite priority及无效offset均有独立新造输入。旧worker使用发明weekday日历/常量数值，合成通过不是交易所或数据覆盖证据。所有源文件前后SHA不变；真实SDK/Research/LEAN/市场/模型/部署/预算变更/最终行情读取均为0，只有官方primary静态schema取证。真实运行与完整原生失败回执仍未验证。
''',encoding='utf-8')
manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.iterdir() if p.is_file() and p.name!='manifest.json'}
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps({'report':str(OUT/'report.json'),'WR13':'fixed_in_tested_scope','WR14':'confirmed_P2','methods':12,'subcases':160,
    'role_corrected_failures':0,'role_corrected_errors':2,'fractional_candidate_false_rejects':8,'fractional_baseline_completed':14,
    'original_adapted_controls':2,'original_adapted_rejects':3,'source_hashes_unchanged':True},ensure_ascii=False))
