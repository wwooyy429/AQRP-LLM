from pathlib import Path
import json
R=Path(__file__).resolve().parent
p=R/'build_formal_report.py'
s=p.read_text(encoding='utf-8')
assert '10个公开函数/类AST原样保留' in s
s=s.replace('10个公开函数/类AST原样保留','10个顶层函数/类AST原样保留')
s=s.replace("'public_function_class_ASTs_unchanged':10","'top_level_function_class_ASTs_unchanged':10")
anchor="(R/'formal_report.json').write_text"
addition="report['reviewer_corrections']['formal_QA_wording']='10个顶层定义包含3个私有helper，不称10个公开接口；旧草稿formal_report_pre_QA.json及首QA问题保留。首次shell措辞编辑因引号失败未改报告，另存记录后用独立脚本更正。'\n"
assert anchor in s
s=s.replace(anchor,addition+anchor)
p.write_text(s,encoding='utf-8')
(R/'QA_wording_edit_first.json').write_text(json.dumps({'kind':'reviewer_report_helper_only','error':'PowerShell nested quotation attempted to interpret R/formal_report.json as command; no such command existed.','first_attempt_changed_formal_report':False,'first_attempt_changed_product':False,'original_formal_hash_remained':'45cf5e358d210d65945bfa56a6f0ab3568f7c28f9978ce5f13577dafa3add81a','correction':'Standalone Python helper, then regenerate only formal report.'},indent=2),encoding='utf-8')
