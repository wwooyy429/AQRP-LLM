from pathlib import Path
import subprocess,json,hashlib,sys,tarfile,io,os
root=Path.cwd();scratch=root/'.git/repair-work/stage2-completion/certification';final_test=(root/'tests/test_data_certification.py').read_bytes();(scratch/'final_tests.py').write_bytes(final_test)
base=scratch/'baseline_a6_final';assert not base.exists();base.mkdir()
raw=subprocess.run(['git','archive','--format=tar','a6b14b05e913daa894c9049b428e953954b40e08','cloud','tools','tests','config'],capture_output=True,check=True,cwd=root).stdout
with tarfile.open(fileobj=io.BytesIO(raw)) as tf:
 for member in tf.getmembers():assert (base/member.name).resolve().is_relative_to(base.resolve()) and not member.issym() and not member.islnk()
 tf.extractall(base)
(base/'tests/test_data_certification.py').write_bytes(final_test)
runs=[]
for label,cwd,cmd in [('final_baseline',base,[sys.executable,'-B','-m','unittest','discover','-s','tests','-p','test_data_certification.py','-v']),('final_candidate',root,[sys.executable,'-B','-m','unittest','discover','-s','tests','-p','test_data_certification.py','-v']),('compatibility',root,[sys.executable,'-B','-m','unittest','tests.test_ingestion','tests.test_data_pipeline','tests.test_coverage','-v']),('capabilities',root,[sys.executable,'-B','tools/data_certification.py','capabilities'])]:
 env=dict(os.environ,PYTHONPATH=os.pathsep.join([str(cwd/'cloud'),str(cwd/'tests')]))
 p=subprocess.run(cmd,capture_output=True,cwd=cwd,env=env)
 (scratch/(label+'.stdout')).write_bytes(p.stdout);(scratch/(label+'.stderr')).write_bytes(p.stderr)
 item={'label':label,'command':cmd,'exit_code':p.returncode,'stdout_sha256':hashlib.sha256(p.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(p.stderr).hexdigest()};runs.append(item);print(json.dumps(item),flush=True)
 if label!='final_baseline' and p.returncode:print(p.stderr.decode(errors='replace'));raise SystemExit(p.returncode)
summary={'baseline_commit':'a6b14b05e913daa894c9049b428e953954b40e08','same_final_dedicated_tests':True,'dedicated_test_raw_sha256':hashlib.sha256(final_test).hexdigest(),'baseline_feature_absence':'New module absent; unittest discovery has one import-error, not22 executed failures','candidate_methods':22,'runs':runs,'source_raw_sha256':{name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in ('cloud/qresearch/data_certification.py','tools/data_certification.py','tests/test_data_certification.py')},'corrected_known_answer_expectations':['Jan31 unknown classification cannot contaminate earlier formation','shared validator rejects simultaneous financial vintages as whole batch'],'production_report_fix':'fixed zero counter keys; revalidate private partition inputs; reject incomplete eligible candidate histories','actual_provider_calls':0,'actual_research_executions':0,'actual_lean_submissions':0,'actual_budget_mutations':0,'active_configuration_changed':False,'research_certification_granted':False,'full_historical_US200_certified':False,'financial_evidence':False}
(scratch/'summary.json').write_bytes((json.dumps(summary,ensure_ascii=True,indent=2)+'\n').encode());print(json.dumps({'candidate_methods':22,'all_required_candidate_runs_passed':True,'scope':'declared observations only; vendor provenance remains unverified'}))
