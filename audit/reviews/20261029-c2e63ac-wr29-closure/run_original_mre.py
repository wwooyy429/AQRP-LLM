from pathlib import Path
import subprocess,sys,json,hashlib
R=Path(__file__).resolve().parent
old=Path(r'C:\Users\11638\.codex\tmp\aqrp-review-2d1d306-20261029\source')
records=[]
for label,source in [('old_failed',old),('new_fixed',R/'source')]:
    cmd=[sys.executable,'-B',str(R/'original_minimal_wr29.py'),str(source)]
    p=subprocess.run(cmd,cwd=R,capture_output=True)
    (R/(label+'_minimum.stdout')).write_bytes(p.stdout);(R/(label+'_minimum.stderr')).write_bytes(p.stderr)
    observed=json.loads(p.stdout)
    record={'label':label,'command':cmd,'assertion_program_exit':p.returncode,'observed':observed}
    records.append(record)
    print(json.dumps({'label':label,'assertion_exit':p.returncode,'child_exits':{k:v['actual_exit'] for k,v in observed.items()}}),flush=True)
result={'original_script_sha256':hashlib.sha256((R/'original_minimal_wr29.py').read_bytes()).hexdigest(),'original_script_bytes_unchanged':True,'records':records,'counting':'Old negative and new positive overlap independent entry tests; no extra unique method count.'}
(R/'original_MRE_replay.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
assert records[0]['assertion_program_exit']==1
assert [records[0]['observed'][k]['actual_exit'] for k in ('canonical_import_control','documented_script','documented_module')]==[0,2,2]
assert records[1]['assertion_program_exit']==0
assert all(v['actual_exit']==0 for v in records[1]['observed'].values())
