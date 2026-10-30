"""Independent synthetic developer probes; no provider or real ledger access."""
from contextlib import ExitStack, redirect_stdout
from copy import deepcopy
import ast
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'cloud'), str(ROOT/'tools'), str(ROOT/'tests')]
from qresearch.artifacts import MemoryArtifactStore, canonical_json, content_hash
from qresearch.engineering_data import DeploymentVerificationError, source_bytes_sha256, verify_deployment
from qresearch.engineering_tasks import EngineeringTaskPlan, EngineeringTaskBridge
from qresearch.registry import Registry
from test_engineering_receipts import context, report, research_tool
from test_phase2_joint_boundaries import joint_document, CATALOG, wrapper
from qresearch.engineering_receipts import research_observation
import stage2
import stage2_collection
import collection_task_cli
import deployment_preflight

RAW=b'answer = 7\n'
MANIFEST={'worker.py': hashlib.sha256(RAW).hexdigest()}
SECRET='NEVER_REPORT_SYNTHETIC_NOTEBOOK_OUTPUT'

def native(value):
    return {'structuredContent':deepcopy(value),'content':[{'type':'text','text':json.dumps(value)}],'isError':False}

def listing():
    return {'tool_name':'mcp__quantconnect__list_projects','arguments':{},'result':native({'success':True,'projects':[{'projectId':17,'name':'sample','language':'Py'}]})}

def source_tool(files=None):
    return {'tool_name':'mcp__quantconnect__read_project','arguments':{'projectId':17},'result':native({'success':True,'project':{'projectId':17,'name':'sample','language':'Py','files': files if files is not None else [{'filePath':'worker.py','content':RAW.decode()},{'filePath':'research.ipynb','content':SECRET}]}})}

def check(tool=None, projects=None, manifest=None, digest=None, **kwargs):
    return deployment_preflight.read_project_preflight(source_tool() if tool is None else tool,
        listing() if projects is None else projects,MANIFEST if manifest is None else manifest,
        content_hash(MANIFEST) if digest is None else digest,project_id=17,**kwargs)

def sync(tool):
    tool['result']['content'][0]['text']=json.dumps(tool['result']['structuredContent'])
    return tool

class Sandbox:
    def __init__(self, version):
        self.version=version
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        for part in ('cloud','config','audit'): (self.root/part).mkdir()
        (self.root/'cloud/worker.py').write_bytes(RAW)
        self.dump('audit/deployment.json',{'source_files':MANIFEST})
        self.dump('config/quantconnect.json',{'active_project_id':17})
        raw=joint_document() if version==2 else deepcopy(context('research')[0]['plan'])
        raw.update(project_id=17,source_manifest_hash='a'*64,deployment_hash=content_hash(MANIFEST))
        self.plan=EngineeringTaskPlan.from_dict(raw,discovered_project_ids=[17])
        self.dump('plan.json',raw)
        self.store=MemoryArtifactStore();self.registry=Registry(self.store,{k:{'normal':8,'reserve':2,'total':10} for k in ('configurations','research','lean')})
        self.bridge=EngineeringTaskBridge(self.registry,self.plan)
        projects={'success':True,'projects':[{'projectId':17}]}
        plan_key='engineering/frozen-plans/'+self.plan.hash+'.json'
        proof_key='engineering/project-listings/'+content_hash(projects)+'.json'
        self.store.write_once(plan_key,canonical_json(self.plan.to_dict()))
        self.store.write_once(proof_key,canonical_json(projects))
        self.dump('audit/engineering_current.json',{'plan_key':plan_key,'plan_hash':self.plan.hash,'project_listing_ref':{'key':proof_key,'sha256':content_hash(projects)}})
        self.stack=ExitStack()
        for p in (patch.object(stage2,'ROOT',self.root),patch.object(stage2,'open_registry',return_value=self.registry),patch.object(stage2,'export_usage',return_value=None),patch.object(stage2,'source_manifest',return_value={'source_hash':'a'*64}),patch.object(collection_task_cli,'execution_source_manifest',return_value={'source_hash':'a'*64}),patch.object(stage2_collection,'catalog',return_value=deepcopy(CATALOG))): self.stack.enter_context(p)
    def dump(self,name,document):
        path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(canonical_json(document));return path
    def command(self,name,stage=None):
        args=['stage2.py',name]+(['--stage',stage] if stage else [])
        with patch.object(sys,'argv',args),redirect_stdout(io.StringIO()): stage2.main()
    def snapshot(self):
        return dict(self.store._data),{p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
    def complete_research(self):
        attempt=self.bridge.claim('research').attempt_id
        admission=stage2.prepare(self.bridge,attempt);payload=admission['payload']
        doc=wrapper(payload) if self.version==2 else report(payload)
        observed=research_observation(payload,admission['deployment'],research_tool(payload,doc))
        self.bridge.record_submission(attempt,observed['submission'])
        self.bridge.consume_completion(attempt,completion_source=lambda _:observed['completion'])
    def __enter__(self):return self
    def __exit__(self,*a):self.stack.close();self.tmp.cleanup()

class StrictSourceProbes(unittest.TestCase):
    def test_original_contract_BOM_and_universal_newlines(self):
        for raw in (RAW,b'\xef\xbb\xbf'+RAW,RAW.replace(b'\n',b'\r\n'),RAW.replace(b'\n',b'\r')):
            with self.subTest(raw_hash=hashlib.sha256(raw).hexdigest()):self.assertEqual(source_bytes_sha256(raw),MANIFEST['worker.py'])
        self.assertNotEqual(source_bytes_sha256(b'\xef\xbb\xbf\xef\xbb\xbf'+RAW),MANIFEST['worker.py'])

    def test_EOF_content_and_import_changes_are_still_rejected(self):
        for changed in (RAW.rstrip(b'\n'),RAW+b'\n',b'from AlgorithmImports import *\n'+RAW,RAW.replace(b'7',b'8')):
            with self.subTest(hash=hashlib.sha256(changed).hexdigest()),tempfile.TemporaryDirectory() as d:
                root=Path(d);(root/'worker.py').write_bytes(changed)
                with self.assertRaises(DeploymentVerificationError) as c:verify_deployment(MANIFEST,content_hash(MANIFEST),source_root=root)
                self.assertEqual(c.exception.diagnostics['failure_kind'],'source_hash_mismatch')
                self.assertEqual(c.exception.diagnostics['observed_sha256'],source_bytes_sha256(changed))

    def test_rejection_uses_one_read_and_no_source_disclosure(self):
        raw=b'PRIVATE_SOURCE_CONTENT = 13\n'
        with tempfile.TemporaryDirectory() as d,patch.object(Path,'read_bytes',return_value=raw) as read:
            with self.assertRaises(DeploymentVerificationError) as c:verify_deployment(MANIFEST,content_hash(MANIFEST),source_root=d)
            self.assertEqual(read.call_count,1)
            self.assertEqual(c.exception.diagnostics['observed_sha256'],source_bytes_sha256(raw))
            self.assertNotIn('PRIVATE_SOURCE_CONTENT',str(c.exception))
            self.assertNotIn(d,str(c.exception))
            copied=c.exception.diagnostics;copied['path']='altered';self.assertEqual(c.exception.diagnostics['path'],'worker.py')

    def test_invalid_and_device_paths_reject_before_any_read(self):
        names=['../a.py','/a.py','C:/a.py','a\\b.py','CON.py','AUX.py','LPT1.py','COM9.py','dir/NUL.py','a?.py','a*.py','a<.py','a|.py','a\".py','a\x00.py','a\x7f.py','a. /b.py']
        for name in names:
            manifest={'worker.py':MANIFEST['worker.py'],name:'1'*64}
            with self.subTest(name=repr(name)),patch.object(Path,'read_bytes',side_effect=AssertionError('I/O forbidden')) as read:
                with self.assertRaises(DeploymentVerificationError):verify_deployment(manifest,content_hash(manifest),source_root=ROOT)
                self.assertFalse(read.called)

    def test_invalid_UTF8_and_OS_errors_are_bounded(self):
        for result,error in ((b'\xffSECRET',None),(None,OSError('C:/PRIVATE/SECRET source = 1'))):
            with self.subTest(error=bool(error)),patch.object(Path,'read_bytes',return_value=result,side_effect=error):
                with self.assertRaises(DeploymentVerificationError) as c:verify_deployment(MANIFEST,content_hash(MANIFEST),source_root=ROOT)
                self.assertNotIn('SECRET',str(c.exception));self.assertNotIn('PRIVATE',str(c.exception))

    def test_original75_manifest25_remains_accepted(self):
        tree=ast.parse((ROOT/'audit/task_inputs/bfd00f2611fd4496b9498d4597618a8e.py').read_text(encoding='utf-8-sig'))
        payload=json.loads(ast.literal_eval(tree.body[0].value));manifest=payload['deployment_manifest']
        self.assertEqual(len(manifest),25)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for name in manifest:
                raw=subprocess.run(['git','show','75f24629d3b7f94ff3aa906c3ce8a2b8b9a8d3c4:cloud/'+name],cwd=ROOT,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE).stdout
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
            self.assertEqual(verify_deployment(manifest,payload['identity']['deployment_hash'],source_root=root),'dad57a0513899dc5ed89cef637d648229dd1c5c1b31bb70583ff95962c1c5bc6')

class LifecycleProbes(unittest.TestCase):
    def test_stale_physical_source_blocks_freeze_and_preview_without_writes(self):
        for version in (1,2):
            for preview in (False,True):
                with self.subTest(version=version,preview=preview),Sandbox(version) as s:
                    (s.root/'cloud/worker.py').write_bytes(RAW+b'\n');before=s.snapshot()
                    with self.assertRaises(ValueError):stage2.freeze({'success':True,'projects':[{'projectId':17}]},plan_file=s.root/'plan.json',preview=preview)
                    self.assertEqual(s.snapshot(),before)

    def test_new_self_consistent_manifest_cannot_retarget_frozen_plan(self):
        for version in (1,2):
            for operation in ('register','claim','prepare'):
                with self.subTest(version=version,operation=operation),Sandbox(version) as s:
                    if operation in ('claim','prepare'):s.bridge.register()
                    attempt=s.bridge.claim('research').attempt_id if operation=='prepare' else None
                    raw=RAW+b'\n';(s.root/'cloud/worker.py').write_bytes(raw)
                    s.dump('audit/deployment.json',{'source_files':{'worker.py':source_bytes_sha256(raw)}})
                    before=s.snapshot()
                    with self.assertRaises(ValueError):
                        if operation=='prepare':stage2.prepare(s.bridge,attempt)
                        else:s.command(operation,'lean' if operation=='claim' else None)
                    self.assertEqual(s.snapshot(),before)

    def test_complete_local_set_is_enforced_before_register_claim_and_prepare(self):
        for version in (1,2):
            for operation in ('freeze','preview','register','claim','prepare'):
                for mutation in ('extra','missing'):
                    with self.subTest(version=version,operation=operation,mutation=mutation),Sandbox(version) as s:
                        if operation in ('claim','prepare'):s.bridge.register()
                        attempt=s.bridge.claim('research').attempt_id if operation=='prepare' else None
                        if mutation=='extra':(s.root/'cloud/hidden.py').write_bytes(b'hidden = 1\n')
                        else:(s.root/'cloud/worker.py').unlink()
                        before=s.snapshot()
                        with self.assertRaises(ValueError):
                            if operation=='prepare':stage2.prepare(s.bridge,attempt)
                            elif operation in ('freeze','preview'):stage2.freeze({'success':True,'projects':[{'projectId':17}]},plan_file=s.root/'plan.json',preview=operation=='preview')
                            else:s.command(operation,'research' if operation=='claim' else None)
                        self.assertEqual(s.snapshot(),before)

    def test_old_lean_admission_recovers_without_current_source_or_protocol_backfill(self):
        for version in (1,2):
            with self.subTest(version=version),Sandbox(version) as s:
                s.bridge.register();s.complete_research();attempt=s.bridge.claim('lean').attempt_id
                original=stage2.prepare(s.bridge,attempt)
                s.store._data.pop('engineering/submission-protocol/'+attempt+'.json')
                (s.root/'cloud/worker.py').unlink();(s.root/'audit/deployment.json').unlink()
                s.dump('audit/engineering_current.json',{'foreign':'pointer'})
                before=s.snapshot()
                with patch.object(stage2,'joint_preflight',side_effect=AssertionError('No current-source access')):
                    self.assertEqual(stage2.prepare(s.bridge,attempt),original)
                self.assertEqual(s.snapshot(),before)

class NativeReadbackProbes(unittest.TestCase):
    def test_CLI_reports_source_hashes_without_printing_notebook_and_uses_result_exitcodes(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            files={'project.json':source_tool(),'listing.json':listing(),'manifest.json':MANIFEST}
            for name,value in files.items():(root/name).write_bytes(canonical_json(value))
            args=[sys.executable,'-B',str(ROOT/'tools/deployment_preflight.py'),'--project-tool-file',str(root/'project.json'),'--projects-file',str(root/'listing.json'),'--manifest-file',str(root/'manifest.json'),'--deployment-hash',content_hash(MANIFEST),'--project-id','17']
            for state,code in (('valid',0),('changed',1),('invalid',2)):
                if state=='changed':(root/'project.json').write_bytes(canonical_json(source_tool([{'filePath':'worker.py','content':RAW.decode()+'\n'},{'filePath':'research.ipynb','content':SECRET}])))
                elif state=='invalid':(root/'project.json').write_text('{"source":"'+SECRET+'",bad}',encoding='utf-8')
                before={p.name:p.read_bytes() for p in root.iterdir()}
                result=subprocess.run(args,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
                with self.subTest(state=state):
                    self.assertEqual(result.returncode,code)
                    self.assertNotIn(SECRET.encode(),result.stdout+result.stderr)
                    self.assertEqual({p.name:p.read_bytes() for p in root.iterdir()},before)
                    decoded=json.loads(result.stdout);self.assertIs(decoded['ready_to_dispatch'],False)

    def test_source_only_match_does_not_certify_worker_or_leak_notebook(self):
        report=check();encoded=json.dumps(report)
        self.assertTrue(report['preflight_passed'])
        for key in ('ready_to_dispatch','budget_admission_performed','worker_source_verified','full_cloud_inventory_certified','financial_evidence'):self.assertIs(report[key],False)
        self.assertNotIn(SECRET,encoded);self.assertNotIn(RAW.decode().strip(),encoded)
        tool=source_tool();tool['result']['structuredContent']['project']['files'][1]['content']='DIFFERENT_NOTEBOOK';sync(tool)
        self.assertEqual(check(tool),report)

    def test_mirror_and_annotation_disagreement_are_rejected(self):
        for target in ('source','listing'):
            for mutation in ('mirror','extra_text','annotation','isError','meta'):
                tool=source_tool();projects=listing();envelope=tool if target=='source' else projects
                if mutation=='mirror':envelope['result']['content'][0]['text']='{"success":false}'
                elif mutation=='extra_text':envelope['result']['content'].append({'type':'text','text':SECRET})
                elif mutation=='annotation':envelope['result']['content'][0]['annotations']={'rows':[SECRET]}
                elif mutation=='isError':envelope['result']['isError']=True
                else:envelope['result']['_meta']={'output':SECRET}
                with self.subTest(target=target,mutation=mutation),self.assertRaises(ValueError):check(tool,projects)

    def test_true_bool_ids_duplicate_ids_and_duplicate_paths_are_rejected(self):
        for mutation in ('source_arg_bool','source_internal_bool','listing_bool','duplicate_ids','duplicate_path','case_alias'):
            tool=source_tool();projects=listing()
            if mutation=='source_arg_bool':tool['arguments']['projectId']=True
            elif mutation=='source_internal_bool':tool['result']['structuredContent']['project']['projectId']=True;sync(tool)
            elif mutation=='listing_bool':projects['result']['structuredContent']['projects'][0]['projectId']=True;sync(projects)
            elif mutation=='duplicate_ids':projects['result']['structuredContent']['projects']*=2;sync(projects)
            else:tool['result']['structuredContent']['project']['files'].append({'filePath':'worker.py' if mutation=='duplicate_path' else 'WORKER.py','content':'irrelevant'});sync(tool)
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):check(tool,projects)

    def test_raw_input_identity_does_not_adopt_source_normalization(self):
        text='TASK_INPUT_JSON = "synthetic"\n';digest=hashlib.sha256(text.encode()).hexdigest()
        for variant,expected in ((text,True),(text.replace('\n','\r\n'),False),('\ufeff'+text,False),(text+'\n',False)):
            tool=source_tool([{'filePath':'worker.py','content':RAW.decode()},{'filePath':'_engineering_task_input.py','content':variant}]);report=check(tool,input_sha256=digest)
            self.assertIs(report['preflight_passed'],expected);self.assertIs(report['input_binding_verified'],expected)
            self.assertEqual(report['input_observed_sha256'],hashlib.sha256(variant.encode()).hexdigest())

    def test_extra_missing_changed_sources_and_reserved_names_reject(self):
        for files in ([],[{'filePath':'worker.py','content':RAW.decode()+'\n'}],[{'filePath':'worker.py','content':RAW.decode()},{'filePath':'extra.py','content':'x=1'}]):self.assertFalse(check(source_tool(files))['preflight_passed'])
        for name in ('CON.py','dir/COM1.py','../worker.py','worker?.py','C:/worker.py','bad\x7f.py'):
            with self.subTest(name=name),self.assertRaises(ValueError):check(source_tool([{'filePath':name,'content':'x=1'}]))
        name='bad\x7f.py';manifest={name:source_bytes_sha256(RAW)}
        with self.assertRaises(ValueError):check(source_tool([{'filePath':name,'content':RAW.decode()}]),manifest=manifest,digest=content_hash(manifest))

if __name__=='__main__':
    unittest.main(verbosity=2)
