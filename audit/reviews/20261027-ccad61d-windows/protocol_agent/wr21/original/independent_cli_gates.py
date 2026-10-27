"""Actual production CLI entrypoints in disposable synthetic source/ledger copies."""
from pathlib import Path
from copy import deepcopy
from hashlib import sha256
from uuid import uuid4
import io,json,os,shutil,subprocess,sys,unittest
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parent;SOURCE=ROOT.parent/'source';RUN=ROOT/'cli_cases'/uuid4().hex[:8]
import quick_joint_probes as h
from qresearch.engineering_data import source_bytes_sha256
COMMANDS=[];OBS={}
def dump(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def inventory(case):return {p.relative_to(case).as_posix():sha256(p.read_bytes()).hexdigest() for p in case.rglob('*') if p.is_file()}
def case(version,tag):
    dest=RUN/(str(version)+'-'+tag+'-'+uuid4().hex[:6]);dest.mkdir(parents=True)
    for folder in ['cloud','tools','config','templates','tests','docs','.github']:
        if (SOURCE/folder).exists():shutil.copytree(SOURCE/folder,dest/folder,ignore=shutil.ignore_patterns('__pycache__'))
    for name in ['requirements-test.txt','AGENTS.md','.gitattributes','.gitignore']:
        if (SOURCE/name).exists():shutil.copy2(SOURCE/name,dest/name)
    (dest/'audit').mkdir();shutil.copy2(SOURCE/'audit/deployment.json',dest/'audit/deployment.json')
    b=json.loads((dest/'config/budget.json').read_text(encoding='utf-8-sig'));b['usage']={k:0 for k in b['usage']};dump(dest/'config/budget.json',b)
    qc=json.loads((dest/'config/quantconnect.json').read_text(encoding='utf-8-sig'));qc['active_project_id']=931001;dump(dest/'config/quantconnect.json',qc)
    raw=h.joint(name='independent-cli-'+str(version)).to_dict()
    if version==1:raw['schema_version']=1;raw.pop('collection_probe')
    else:raw['collection_probe']['field_catalog']=None
    dump(dest/'proposal.json',raw)
    dump(dest/'projects.json',{'success':True,'projects':[{'projectId':931001,'name':'independent-only','language':'Py'}]})
    return dest
def cli(dest,*args):
    cmd=[sys.executable,'-B',str(dest/'tools/stage2.py'),*map(str,args)]
    p=subprocess.run(cmd,cwd=dest,text=True,encoding='utf-8',capture_output=True,timeout=40,
        env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1'))
    COMMANDS.append({'command':cmd,'cwd':str(dest),'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
    return p
def freeze(dest,command='freeze'):return cli(dest,command,'--projects-file',dest/'projects.json','--plan-file',dest/'proposal.json')
def accepted(result):
    if result.returncode!=0:raise AssertionError('CLI prerequisite failed: '+result.stderr)
    return json.loads(result.stdout)
def prefix(dest,step):
    accepted(freeze(dest))
    if step=='register':return None
    accepted(cli(dest,'register'))
    if step=='claim':return None
    return accepted(cli(dest,'claim','--stage','research'))['attempt_id']
def mutate(dest,rebuild=False):
    target=dest/'cloud/main.py';target.write_bytes(target.read_bytes()+b'\n# independent physical drift\n')
    if rebuild:
        dep=json.loads((dest/'audit/deployment.json').read_text(encoding='utf-8-sig'))
        dep['source_files']['main.py']=source_bytes_sha256(target.read_bytes());dump(dest/'audit/deployment.json',dep)
def refuse_same(test,dest,callback):
    before=inventory(dest);p=callback();test.assertNotEqual(p.returncode,0,p.stdout);test.assertEqual(inventory(dest),before,'Rejected CLI wrote source/input/ledger/config metadata')
    return p

class CLIGates(unittest.TestCase):
    def test_v1_v2_legitimate_chain_and_original_input_recovery_after_drift(self):
        for version in [1,2]:
            with self.subTest(version=version):
                dest=case(version,'positive');before=inventory(dest)
                p=accepted(freeze(dest,'preview'));self.assertFalse(p['ready_to_dispatch']);self.assertEqual(inventory(dest),before)
                a=prefix(dest,'prepare');prepared=accepted(cli(dest,'prepare','--attempt',a))
                self.assertEqual(prepared['payload']['identity']['attempt_id'],a)
                mutate(dest,rebuild=True);(dest/'audit/engineering_current.json').unlink()
                dump(dest/'config/source_catalog.json',{'untrusted':'catalog drift'})
                before=inventory(dest);restored=accepted(cli(dest,'prepare','--attempt',a))
                self.assertEqual(restored,prepared);self.assertEqual(inventory(dest),before)
                OBS['positive_v'+str(version)]={'attempt':a,'original_input_recovered':True,'extra_charge_or_write':False}

    def test_unbuilt_physical_change_rejected_at_every_new_input_entrypoint(self):
        for version in [1,2]:
            for step in ['preview','freeze','register','claim','prepare']:
                with self.subTest(version=version,step=step):
                    dest=case(version,'unbuilt-'+step);a=None
                    if step not in ['preview','freeze']:a=prefix(dest,step)
                    mutate(dest)
                    if step in ['preview','freeze']:refuse_same(self,dest,lambda:freeze(dest,step))
                    elif step=='claim':refuse_same(self,dest,lambda:cli(dest,'claim','--stage','research'))
                    elif step=='prepare':refuse_same(self,dest,lambda:cli(dest,'prepare','--attempt',a))
                    else:refuse_same(self,dest,lambda:cli(dest,'register'))

    def test_self_consistent_new_source_and_manifest_cannot_reuse_old_plan(self):
        for version in [1,2]:
            for step in ['register','claim','prepare']:
                with self.subTest(version=version,step=step):
                    dest=case(version,'coherent-'+step);a=prefix(dest,step);mutate(dest,rebuild=True)
                    if step=='register':refuse_same(self,dest,lambda:cli(dest,'register'))
                    if step=='claim':refuse_same(self,dest,lambda:cli(dest,'claim','--stage','research'))
                    if step=='prepare':refuse_same(self,dest,lambda:cli(dest,'prepare','--attempt',a))

    def test_complete_managed_python_set_missing_extra_or_uppercase_blocks_freeze(self):
        for version in [1,2]:
            for mode in ['missing','extra','uppercase']:
                with self.subTest(version=version,mode=mode):
                    dest=case(version,'set-'+mode)
                    if mode=='missing':(dest/'cloud/main.py').unlink()
                    else:(dest/'cloud'/('orphan.PY' if mode=='uppercase' else 'orphan.py')).write_bytes(b'# independent extra\n')
                    refuse_same(self,dest,lambda:freeze(dest))

class Counted(unittest.TextTestResult):
    def __init__(self,*a,**k):super().__init__(*a,**k);self.subcases=0
    def addSubTest(self,test,sub,error):self.subcases+=1;super().addSubTest(test,sub,error)
def main():
    stream=io.StringIO();r=unittest.TextTestRunner(stream=stream,verbosity=2,resultclass=Counted).run(unittest.defaultTestLoader.loadTestsFromTestCase(CLIGates))
    ident=lambda t:getattr(t,'test_case',t).id()
    failed={ident(t) for t,_ in r.failures};errors={ident(t) for t,_ in r.errors}
    d={'source_commit':'66ff72ffaaff8c91c008898e6527c91131176c2a','methods':r.testsRun,'passed_methods':r.testsRun-len(failed|errors),'failed_methods':len(failed),'error_methods':len(errors),'subcases':r.subcases,'skips':len(r.skipped),
       'failures':[{'method':ident(t),'traceback':tb} for t,tb in r.failures],'errors':[{'method':ident(t),'traceback':tb} for t,tb in r.errors],
       'actual_CLI_processes':len(COMMANDS),'successful_CLI_commands':sum(c['exit_code']==0 for c in COMMANDS),'rejected_CLI_commands':sum(c['exit_code']!=0 for c in COMMANDS),
       'actual_worker_QC_market_model_calls':0,'actual_build_calls':0,'observations':OBS,'script_sha256':sha256(Path(__file__).read_bytes()).hexdigest(),'exit_code':0 if r.wasSuccessful() else 1}
    (ROOT/'cli_first_results.json').write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8');(ROOT/'cli_command_log.json').write_text(json.dumps(COMMANDS,indent=2)+'\n',encoding='utf-8')
    print(stream.getvalue());print(json.dumps({k:d[k] for k in ['methods','passed_methods','failed_methods','error_methods','subcases','actual_CLI_processes','exit_code']}));return d['exit_code']
if __name__=='__main__':raise SystemExit(main())
