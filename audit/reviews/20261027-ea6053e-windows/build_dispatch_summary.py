from pathlib import Path
import importlib.metadata,json,platform,sys
R=Path(__file__).parent;D=R/'dispatch_agent'
records=json.loads((D/'legacy_adapted/executions.json').read_bytes());assert len(records)==5 and all(x['exit_code']==0 for x in records)
a=json.loads((D/'fixture_adapters.json').read_bytes());assert next(x for x in a if x['file']=='independent_recovery.py')['all_class_AST_unchanged']is True
stats=[]
for folder,file in [('main','results.json'),('compat_boundaries','result.json'),('compat_failure','failure_settlement_result.json'),('crash_addendum','results.json'),('recovery','first_run_summary.json')]:
    data=json.loads((D/'legacy_adapted'/folder/file).read_bytes())
    stats.append({'suite':folder,'methods':data.get('methods',0),'subcases':data.get('subcases'),'manual':data.get('manual_probes',data.get('subcases') if folder=='compat_failure' else 0),'passed':data.get('passed'),'failure_records':data.get('failure_records',data.get('failures',data.get('failed',0))),'error_records':data.get('error_records',0),'stats':data.get('stats'),'actually_executed':True})
research=json.loads((D/'legacy_original/research/results.json').read_bytes());assert research['methods']==6 and research['subcases']==91 and research['failure_records']==research['error_records']==0
summary={'actual_commit':'ea6053e3e9ef4be17db246daf18a4cf9b2e5be58','adapted_suites':stats,'new_native_research_original_bytes':{'methods':6,'subcases':91,'failure_records':0,'error_records':0,'stats':research['stats'],'actually_executed':True},'original_mre':json.loads((D/'original_mre_execution.json').read_bytes()),'fixture_adaptation':'Only reviewer setup_case pins matching fixed source/index4 after actualprepare; original test classes/assertion AST unchanged. First original lack-binding rejects/setup errors and dependent missing-template failures retained.','child_interruption':'Child turn ended at tool filter after background adapter executions were launched. Root inspected completed successful outputs and independently repeated WR23; no unexecuted extension is claimed.'}
(D/'root_verified_summary.json').write_bytes((json.dumps(summary,ensure_ascii=False,indent=2)+'\n').encode())
import numpy
E={'platform':platform.platform(),'python':platform.python_version(),'executable':sys.executable,'dependencies':{n:importlib.metadata.version(n)for n in ['numpy','pandas','python-dateutil','pytz','six','tzdata']},'native_Windows':True,'numpy_longdouble_mantissa_bits':numpy.finfo(numpy.longdouble).nmant}
(R/'environment.json').write_bytes((json.dumps(E,indent=2)+'\n').encode());print(json.dumps({'adapted_suites':stats,'research':summary['new_native_research_original_bytes']},ensure_ascii=False))
