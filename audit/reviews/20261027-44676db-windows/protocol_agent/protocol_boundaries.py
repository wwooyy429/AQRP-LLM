"""Independent WR23 filesystem publication, compatibility and Windows process checks."""
import copy,hashlib,importlib.util,io,json,os,subprocess,sys,time,unittest,traceback
from pathlib import Path
from unittest.mock import patch
import independent_recovery_support as h
from qresearch.engineering_receipts import research_cell_source

OBS=[];PARALLEL=[];CHECKS=0
def chk(condition,message):
    global CHECKS
    CHECKS+=1
    if not condition:raise AssertionError(message)
def setup(tag,version=2,prepare=True):
    case,listing=h.fresh(tag)
    h.okay(h.invoke(case,['freeze','--plan-file',f'config/independent-v{version}.json','--projects-file',listing],tag+'-freeze'))
    h.okay(h.invoke(case,['register'],tag+'-register'))
    attempt=h.okay(h.invoke(case,['claim','--stage','research'],tag+'-claim'))['attempt_id']
    adm=h.okay(h.invoke(case,['prepare','--attempt',attempt],tag+'-prepare')) if prepare else None
    return {'case':case,'listing':listing,'attempt':attempt,'admission':adm,'version':version,'tag':tag}
def keys(ctx):
    a=ctx['attempt'];return ['engineering/admitted-inputs/'+a+'.json','engineering/research-entry-protocol/'+a+'.json','engineering/research-dispatch/'+a+'.json']
def stage_for(ctx):
    for name in ('research','stages','collection_task_cli','stage2_collection'):sys.modules.pop(name,None)
    sys.path.insert(0,str(ctx['case']/'tools'))
    spec=importlib.util.spec_from_file_location('independent_stage2_'+ctx['tag'],ctx['case']/'tools/stage2.py')
    stage=importlib.util.module_from_spec(spec);spec.loader.exec_module(stage)
    reg=h.registry(ctx['case']);return stage,stage.bridge_for_attempt(ctx['attempt'],registry=reg),reg
def success(ctx):return h.envelopes(ctx,ctx['admission'],'research')['result']
def failure(ctx):
    a=ctx['admission'];v={'tool_name':'mcp__quantconnect__jupyter_execute_cell','arguments':{'projectId':a['payload']['identity']['project_id'],'index':4},'result':{'isError':False,'content':[{'type':'text','text':json.dumps({'output_type':'error','ename':'IndependentSyntheticError','evalue':'WR23 bounded synthetic failure','traceback':['first','last']})}]}}
    p=ctx['case'].parent/'synthetic-error.json';h.dump(p,v);return p
def readcell(ctx):
    a=ctx['admission'];value={'tool_name':'mcp__quantconnect__jupyter_read_cell','arguments':{'projectId':a['payload']['identity']['project_id'],'index':4},'result':{'cellType':'code','source':research_cell_source(a['payload'],a['deployment']).splitlines(keepends=True)}}
    p=ctx['case'].parent/'read-fixed.json';h.dump(p,value);return p
def blocked(ctx):
    reg=h.registry(ctx['case']);before=reg.snapshot();saved=h.files(ctx['case'])
    for label,p in [('success',success(ctx)),('failure',failure(ctx))]:
        r=h.invoke(ctx['case'],['research-result','--attempt',ctx['attempt'],'--tool-file',p],ctx['tag']+'-reject-'+label)
        chk(r.returncode!=0,'unbound '+label+' accepted');chk(before==reg.snapshot(),'unbound '+label+' changed ledger');chk(saved==h.files(ctx['case']),'unbound '+label+' wrote files')
    r=h.invoke(ctx['case'],['claim','--stage','lean'],ctx['tag']+'-no-downstream')
    chk(r.returncode!=0,'downstream LEAN authorized');chk(before==reg.snapshot(),'rejected downstream claim changed ledger');chk(saved==h.files(ctx['case']),'rejected downstream claim wrote files')
def pin(ctx,label='pin'):
    return h.okay(h.invoke(ctx['case'],['research-dispatch','--attempt',ctx['attempt'],'--tool-file',readcell(ctx)],ctx['tag']+'-'+label))
def complete(ctx):
    p=success(ctx);reg=h.registry(ctx['case']);usage=reg.snapshot()['usage']
    r=h.okay(h.invoke(ctx['case'],['research-result','--attempt',ctx['attempt'],'--tool-file',p],ctx['tag']+'-complete'))
    chk(r['status']=='completed','legal success did not complete');saved=h.files(ctx['case'])
    chk(h.okay(h.invoke(ctx['case'],['research-result','--attempt',ctx['attempt'],'--tool-file',p],ctx['tag']+'-replay'))['status']=='completed','replay status changed')
    chk(saved==h.files(ctx['case']),'terminal replay wrote files');chk(reg.snapshot()['usage']==usage,'terminal replay charged')
def parallel(ctx,args,label,n=2):
    argv=[sys.executable,'-B',str(ctx['case']/'tools/stage2.py'),*map(str,args)];procs=[subprocess.Popen(argv,cwd=ctx['case'],env=h.ENV,stdout=subprocess.PIPE,stderr=subprocess.PIPE)for _ in range(n)];values=[]
    for i,p in enumerate(procs):
        stdout,stderr=p.communicate(timeout=60);folder=h.OUT/'parallel';folder.mkdir(exist_ok=True);stem=label+'-'+str(i);(folder/(stem+'.stdout')).write_bytes(stdout);(folder/(stem+'.stderr')).write_bytes(stderr)
        PARALLEL.append({'label':label,'index':i,'argv':argv,'cwd':str(ctx['case']),'exit_code':p.returncode,'stdout_sha256':hashlib.sha256(stdout).hexdigest(),'stderr_sha256':hashlib.sha256(stderr).hexdigest()})
        chk(p.returncode==0,'parallel child failed: '+stderr.decode(errors='replace'));values.append(json.loads(stdout))
    return values

class Boundaries(unittest.TestCase):
    def test_01_actual_publication_synchronous_exceptions(self):
        for boundary in ('input','admission','entry'):
            for after in (False,True):
                with self.subTest(boundary=boundary,after_write=after):
                    ctx=setup('publication-'+boundary+'-'+str(after),prepare=False);stage,bridge,reg=stage_for(ctx);admission,entry,_=keys(ctx);store_write=reg.store.write_once;input_write=stage.write_changed;order=[];before=reg.snapshot()
                    class Injected(RuntimeError):pass
                    def write(key,data):
                        order.append(key)
                        if boundary!='input' and key==(admission if boundary=='admission' else entry):
                            if after:store_write(key,data)
                            raise Injected('independent '+boundary+' '+str(after))
                        return store_write(key,data)
                    def local(path,text):
                        if boundary=='input':
                            if after:input_write(path,text)
                            raise Injected('independent input '+str(after))
                        return input_write(path,text)
                    with patch.object(reg.store,'write_once',side_effect=write),patch.object(stage,'write_changed',side_effect=local):
                        with self.assertRaises(Injected):stage.prepare(bridge,ctx['attempt'])
                    chk(reg.snapshot()==before,'prepare exception charged or settled')
                    persisted=reg.store.exists(admission)
                    if persisted:chk('research_entry_protocol' in json.loads(reg.store.read_bytes(admission)),'new persisted admission omitted inline version')
                    ctx['admission']=h.okay(h.invoke(ctx['case'],['prepare','--attempt',ctx['attempt']],ctx['tag']+'-restore'))
                    chk('research_entry_protocol' in ctx['admission'],'restore downgraded new admission');blocked(ctx)
                    has_entry=reg.store.exists(entry)
                    if has_entry:
                        chk(pin(ctx)['should_execute']is True,'legal dispatch missing permit');chk(pin(ctx,'pin-repeat')['should_execute']is False,'second permit issued');complete(ctx)
                    else:
                        saved=h.files(ctx['case']);chk(h.okay(h.invoke(ctx['case'],['prepare','--attempt',ctx['attempt']],ctx['tag']+'-restore-again'))==ctx['admission'],'restored admission changed');chk(saved==h.files(ctx['case']),'prepare backfilled sidecar')
                        chk(h.invoke(ctx['case'],['research-dispatch','--attempt',ctx['attempt'],'--tool-file',readcell(ctx)],ctx['tag']+'-no-permit').returncode!=0,'missing sidecar dispatched');chk(saved==h.files(ctx['case']),'failed dispatch wrote files')
                    OBS.append({'group':'publication','boundary':boundary,'after_write':after,'admission_at_exception':persisted,'entry_after_restore':has_entry,'writes':order,'passed':True})
    def test_02_inline_and_sidecar_disagreement_refuses_both_outcomes(self):
        for mode in ('inline-empty','inline-null','inline-bool','inline-foreign','sidecar-missing','sidecar-different','sidecar-missing-after-dispatch'):
            with self.subTest(mode=mode):
                ctx=setup(mode);adm,entry,_=keys(ctx);reg=h.registry(ctx['case'])
                if mode=='sidecar-missing-after-dispatch':chk(pin(ctx)['should_execute']is True,'prerequisite dispatch failed')
                if mode.startswith('inline'):
                    value=copy.deepcopy(ctx['admission']);protocol=value['research_entry_protocol']
                    if mode=='inline-empty':value['research_entry_protocol']={}
                    if mode=='inline-null':value['research_entry_protocol']=None
                    if mode=='inline-bool':protocol['schema_version']=True
                    if mode=='inline-foreign':protocol['identity']['attempt_id']='f'*32
                    reg.store._path(adm).write_bytes(h.canonical_json(value))
                    saved=h.files(ctx['case']);chk(h.invoke(ctx['case'],['prepare','--attempt',ctx['attempt']],ctx['tag']+'-reject-prepare').returncode!=0,'corrupt inline prepared');chk(saved==h.files(ctx['case']),'corrupt prepare wrote')
                elif mode=='sidecar-different':reg.store._path(entry).write_bytes(h.canonical_json({'synthetic_foreign_protocol':True}))
                else:reg.store._path(entry).unlink()
                blocked(ctx);OBS.append({'group':'identity','mode':mode,'passed':True})
    def test_03_explicit_four_field_legacy_and_pinned_sidecar_compatibility(self):
        for version in (1,2):
            for entry_present in (False,True):
                with self.subTest(version=version,entry_present=entry_present):
                    ctx=setup('legacy-v'+str(version)+'-entry-'+str(entry_present),version);adm,entry,_=keys(ctx);reg=h.registry(ctx['case']);ctx['admission'].pop('research_entry_protocol');reg.store._path(adm).write_bytes(h.canonical_json(ctx['admission']))
                    if not entry_present:reg.store._path(entry).unlink()
                    saved=h.files(ctx['case']);chk(h.okay(h.invoke(ctx['case'],['prepare','--attempt',ctx['attempt']],ctx['tag']+'-restore'))==ctx['admission'],'legacy shape changed');chk(saved==h.files(ctx['case']),'legacy restore backfilled')
                    if entry_present:blocked(ctx);chk(pin(ctx)['should_execute']is True,'old pinned sidecar dispatch rejected')
                    else:
                        chk(h.invoke(ctx['case'],['research-result','--attempt',ctx['attempt'],'--tool-file',failure(ctx)],ctx['tag']+'-legacy-error-reject').returncode!=0,'unbound legacy native failure accepted');chk(saved==h.files(ctx['case']),'legacy failure rejection wrote')
                    complete(ctx);chk(reg.store.exists(entry)==entry_present,'legacy protocol backfilled');OBS.append({'group':'legacy','version':version,'sidecar_present':entry_present,'passed':True})
    def test_04_first_prepare_and_dispatch_are_cross_process_serialized(self):
        for version in (1,2):
            with self.subTest(version=version):
                ctx=setup('process-v'+str(version),version,False);reg=h.registry(ctx['case']);before=reg.snapshot();values=parallel(ctx,['prepare','--attempt',ctx['attempt']],ctx['tag']+'-prepare',4);chk(all(v==values[0] for v in values),'first prepares published different inputs');ctx['admission']=values[0];chk('research_entry_protocol'in values[0],'parallel admission omitted inline');chk(reg.snapshot()==before,'parallel prepare charged');blocked(ctx)
                tool=readcell(ctx);values=parallel(ctx,['research-dispatch','--attempt',ctx['attempt'],'--tool-file',tool],ctx['tag']+'-dispatch',4);chk(sum(v['should_execute']is True for v in values)==1,'parallel dispatch permit was not exactly one');chk(reg.snapshot()==before,'parallel dispatch charged');complete(ctx);OBS.append({'group':'Windows_process_concurrency','version':version,'prepare_children':4,'dispatch_children':4,'permits':1,'passed':True})
    def test_05_unknown_prior_outcome_refuses_first_permission(self):
        for version in (1,2):
            with self.subTest(version=version):
                ctx=setup('unknown-v'+str(version),version);reg=h.registry(ctx['case']);reg.ambiguous(ctx['attempt'],reason='Independent synthetic unknown prior dispatch outcome');before=reg.snapshot();saved=h.files(ctx['case']);chk(h.invoke(ctx['case'],['research-dispatch','--attempt',ctx['attempt'],'--tool-file',readcell(ctx)],ctx['tag']+'-reject-dispatch').returncode!=0,'ambiguous attempt got permit');chk(reg.snapshot()==before and saved==h.files(ctx['case']),'ambiguous refusal changed ledger/files');OBS.append({'group':'unknown_outcome','version':version,'passed':True})

class Result(unittest.TextTestResult):
    def __init__(self,*a,**kw):super().__init__(*a,**kw);self.subcases=0;self.first_failure=None
    def addSubTest(self,test,subtest,err):
        self.subcases+=1
        if err and self.first_failure is None:self.first_failure={'method':str(test),'subtest':str(subtest),'traceback':self._exc_info_to_string(err,test)}
        super().addSubTest(test,subtest,err)
    def addError(self,test,err):
        if self.first_failure is None:self.first_failure={'method':str(test),'traceback':self._exc_info_to_string(err,test)}
        super().addError(test,err)
stream=io.StringIO();r=unittest.TextTestRunner(stream=stream,verbosity=2,resultclass=Result).run(unittest.defaultTestLoader.loadTestsFromTestCase(Boundaries));after={p:hashlib.sha256((h.ROOT/p).read_bytes()).hexdigest()for p in h.CHECK_FILES}
report={'fixed_commit':'ccad61d03ccf17bf2bdc2d7ffc88dfd11b6d3ca6','methods':r.testsRun,'subcases':r.subcases,'individual_checks':CHECKS,'failure_records':len(r.failures),'error_records':len(r.errors),'success':r.wasSuccessful(),'first_failure':r.first_failure,'observations':OBS,'ordinary_stats':h.STATS,'parallel_CLI_processes':len(PARALLEL),'source_before':h.BEFORE,'source_after':after,'source_and_authority_unchanged':h.BEFORE==after,'actual_provider_worker_model_calls':0,'authoritative_ledger_writes':0,'limits':'Synchronous exceptions at real production write boundary; no OS-kill, power-loss, disk persistence or actual platform execution certification.'}
(h.OUT/'results.json').write_bytes(json.dumps(report,indent=2).encode());(h.OUT/'command_log.json').write_bytes(json.dumps({'ordinary':h.LOG,'parallel':PARALLEL},indent=2).encode());(h.OUT/'unittest.txt').write_bytes(stream.getvalue().encode());print(stream.getvalue());print(json.dumps(report,indent=2));sys.exit(0 if r.wasSuccessful()and h.BEFORE==after else 1)
