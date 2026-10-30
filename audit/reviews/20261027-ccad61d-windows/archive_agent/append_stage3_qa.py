from pathlib import Path
import copy,hashlib,json
R=Path(__file__).resolve().parent;T=R.parent;qa=R/'qa.txt'
oldqa=qa.read_text(encoding='utf-8');before=json.loads(oldqa.split('本次读取文件SHA256：\n',1)[1])
raw=(T/'formal_report.json').read_bytes();current=json.loads(raw);previous=copy.deepcopy(current)
previous['stage_results'][3]['implementation']='部分计算与协议已实现；完整真实评价未完成'
previous['stage_results'][3]['gaps']=['登记固定模型与真实滚动报告','训练/验证及成熟标签完整运行证据']
sha=lambda b:hashlib.sha256(b).hexdigest()
previous_json=(json.dumps(previous,ensure_ascii=False,indent=2)+'\n').encode()
text=(T/'formal_report.txt').read_text(encoding='utf-8');prefix=text.split('完整机器报告：\n',1)[0]
s=previous['stage_results'][3]
old_line=f"阶段{s['stage']}｜{s['modules']}｜{s['implementation']}｜{s['evidence']}｜{s['status']}；缺口：{'、'.join(s['gaps'])}"
current_line=next(line for line in prefix.splitlines() if line.startswith('阶段3｜'))
previous_txt=(prefix.replace(current_line,old_line)+'完整机器报告：\n'+json.dumps(previous,ensure_ascii=False,indent=2)+'\n').encode()
after={p:sha((T/p).read_bytes()) for p in before}
record={'change_scope':'仅正式stage3 implementation增加分层收益未实现，gaps增加同一缺口；源码/发现/计数/预算/平台/结论不变。',
 'before_report_hashes':{p:before[p] for p in ('formal_report.json','formal_report.txt')},
 'after_report_hashes':{p:after[p] for p in ('formal_report.json','formal_report.txt')},
 'reverting_exactly_two_stage3_fields_reconstructs_before_JSON_hash':sha(previous_json)==before['formal_report.json'],
 'reverting_human_stage3_line_and_embedded_JSON_reconstructs_before_TXT_hash':sha(previous_txt)==before['formal_report.txt'],
 'other_prior_QA_file_hashes_unchanged':all(after[p]==h for p,h in before.items() if p not in ('formal_report.json','formal_report.txt')),
 'current_embedded_JSON_matches_current_formal_JSON':json.loads(text.split('完整机器报告：\n',1)[1])==current,
 'stage3_status_remains_not_accepted':current['stage_results'][3]['status']=='未验收',
 'new_product_tests_run':0,'root_files_modified_by_QA':0}
(R/'stage3_qa_appendix.json').write_bytes((json.dumps(record,ensure_ascii=False,indent=2)+'\n').encode())
append='\n\n阶段3说明补充后的QA追加（原哈希在上文保留，作为before）：\n'
append+='只读检查build_formal_report.py第22行及重新生成报告；恢复两个stage3字段即可重建原JSON的精确SHA256，恢复对应人读矩阵行及内嵌JSON即可重建原TXT的精确SHA256，证明其余内容未变。阶段3仍未验收，现明确分层收益未实现；既有来源/预算/平台/65与11-9-2计数/WR27/归档QA保持。没有运行新产品测试。\n'
append+=json.dumps(record,ensure_ascii=False,indent=2)+'\n'
with qa.open('ab') as f:f.write(append.encode())
print(json.dumps(record,ensure_ascii=True))
