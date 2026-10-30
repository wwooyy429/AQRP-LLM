from pathlib import Path
import subprocess,sys,json
R=Path(__file__).resolve().parent
cmd=[sys.executable,'-B',str(R/'minimal_wr29.py'),str(R/'source')]
r=subprocess.run(cmd,cwd=R,capture_output=True)
(R/'minimum.stdout').write_bytes(r.stdout);(R/'minimum.stderr').write_bytes(r.stderr)
observed=json.loads(r.stdout)
report={'command':cmd,'exit_code':r.returncode,'result':'confirmed_product_failure_NOT_a_pass','expected_entry_exits':0,'observed':observed,'overlaps_stdio_MRE_and_is_not_extra_unit_methods':True}
(R/'minimum_execution.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
assert r.returncode==1
assert observed['canonical_import_control']['actual_exit']==0
assert observed['documented_script']['actual_exit']==observed['documented_module']['actual_exit']==2
print(json.dumps({'minimum_assertion_exit':1,'canonical_control_exit':0,'script_exit':2,'module_exit':2,'classification':'WR29 actual failure preserved'}))
