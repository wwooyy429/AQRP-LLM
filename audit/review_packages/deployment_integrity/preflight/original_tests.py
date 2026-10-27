"""Strict deployment prerequisites with synthetic files and native-shaped tools."""
from contextlib import ExitStack
from copy import deepcopy
import hashlib
import importlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'cloud'),str(ROOT/'tools'),str(ROOT/'tests')]
import stage2 as cli
import collection_task_cli
import stage2_collection
from qresearch.artifacts import MemoryArtifactStore, canonical_json, content_hash
from qresearch.engineering_tasks import EngineeringTaskBridge, EngineeringTaskPlan
from qresearch.registry import Registry
from test_engineering_receipts import context
from test_phase2_joint_boundaries import joint_document, CATALOG

SOURCE=b'value = 1\n'
HASH=hashlib.sha256(SOURCE).hexdigest()
MANIFEST={'stub.py':HASH}
SECRET='SYNTHETIC_MARKET_OUTPUT_MUST_NOT_LEAVE_NOTEBOOK'

def envelope(name,args,native):
    return {'tool_name':'mcp__quantconnect__'+name,'arguments':args,
        'result':{'structuredContent':native,'content':[{'type':'text','text':json.dumps(native)}],'isError':False}}

def project_tool(files=None,project=17):
    return envelope('read_project',{'projectId':project},{'success':True,'project':{
        'projectId':project,'name':'synthetic','language':'Py','files':files if files is not None else [
            {'filePath':'stub.py','content':SOURCE.decode()},
            {'filePath':'research.ipynb','content':SECRET}]}})

def projects():return envelope('list_projects',{}, {'success':True,'projects':[{'projectId':17,'name':'synthetic','language':'Py'}]})

class LocalFixture:
    def __init__(self,version):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
        (self.root/'cloud').mkdir(); (self.root/'audit').mkdir(); (self.root/'config').mkdir()
        (self.root/'cloud/stub.py').write_bytes(SOURCE)
        self.dump('audit/deployment.json',{'source_files':MANIFEST})
        self.dump('config/quantconnect.json',{'active_project_id':17})
        raw=joint_document() if version==2 else deepcopy(context('research')[0]['plan'])
        raw.update(project_id=17,source_manifest_hash='a'*64,deployment_hash=content_hash(MANIFEST))
        self.plan=EngineeringTaskPlan.from_dict(raw,discovered_project_ids=[17])
        self.dump('plan.json',raw)
        self.store=MemoryArtifactStore(); self.registry=Registry(self.store,
            {name:{'normal':8,'reserve':2,'total':10} for name in ('configurations','research','lean')})
        self.bridge=EngineeringTaskBridge(self.registry,self.plan)
        listing={'success':True,'projects':[{'projectId':17}]}
        key='engineering/frozen-plans/'+self.plan.hash+'.json'
        listing_key='engineering/project-listings/'+content_hash(listing)+'.json'
        self.store.write_once(key,canonical_json(self.plan.to_dict()))
        self.store.write_once(listing_key,canonical_json(listing))
        self.dump('audit/engineering_current.json',{'plan_key':key,'plan_hash':self.plan.hash,
            'project_listing_ref':{'key':listing_key,'sha256':content_hash(listing)}})
        self.stack=ExitStack()
        for p in [patch.object(cli,'ROOT',self.root),patch.object(cli,'open_registry',return_value=self.registry),
                patch.object(cli,'export_usage',return_value=None),
                patch.object(cli,'source_manifest',return_value={'source_hash':'a'*64}),
                patch.object(collection_task_cli,'execution_source_manifest',return_value={'source_hash':'a'*64}),
                patch.object(stage2_collection,'catalog',return_value=deepcopy(CATALOG))]:self.stack.enter_context(p)
    def dump(self,name,value):
        p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(json.dumps(value).encode());return p
    def command(self,command,stage=None):
        argv=['stage2.py',command]+(['--stage',stage] if stage else [])
        with patch.object(sys,'argv',argv),patch('sys.stdout',io.StringIO()):cli.main()
    def __enter__(self):return self
    def __exit__(self,*_):self.stack.close();self.tmp.cleanup()

class LocalPreflightTests(unittest.TestCase):
    def test_valid_local_freeze_preview_is_readonly_for_both_versions(self):
        for version in (1,2):
            with self.subTest(version=version),LocalFixture(version) as f:
                before=dict(f.store._data); pointer=(f.root/'audit/engineering_current.json').read_bytes()
                result=cli.freeze({'success':True,'projects':[{'projectId':17}]},plan_file=f.root/'plan.json',preview=True)
                self.assertFalse(result['ready_to_dispatch']);self.assertEqual(f.store._data,before)
                self.assertEqual((f.root/'audit/engineering_current.json').read_bytes(),pointer)

    def test_stale_local_source_blocks_freeze_and_preview_before_any_writes(self):
        for version in (1,2):
            for preview in (True,False):
                with self.subTest(version=version,preview=preview),LocalFixture(version) as f:
                    (f.root/'cloud/stub.py').write_bytes(b'value=2\n')
                    before=dict(f.store._data);pointer=(f.root/'audit/engineering_current.json').read_bytes()
                    with self.assertRaises(ValueError):cli.freeze({'success':True,'projects':[{'projectId':17}]},plan_file=f.root/'plan.json',preview=preview)
                    self.assertEqual(f.store._data,before);self.assertEqual((f.root/'audit/engineering_current.json').read_bytes(),pointer)

    def test_missing_or_extra_local_python_blocks_freeze(self):
        for mutate in ('missing','extra'):
            with self.subTest(mutate=mutate),LocalFixture(1) as f:
                if mutate=='missing':(f.root/'cloud/stub.py').unlink()
                else:(f.root/'cloud/extra.py').write_bytes(b'extra=1\n')
                before=dict(f.store._data)
                with self.assertRaises(ValueError):cli.freeze({'success':True,'projects':[{'projectId':17}]},plan_file=f.root/'plan.json',preview=True)
                self.assertEqual(f.store._data,before)

    def test_generated_fixed_input_is_not_implementation(self):
        with LocalFixture(1) as f:
            (f.root/'cloud/_engineering_task_input.py').write_bytes(b'TASK_INPUT_JSON = "synthetic"\n')
            result=cli.freeze({'success':True,'projects':[{'projectId':17}]},plan_file=f.root/'plan.json',preview=True)
            self.assertEqual(result['plan']['deployment_hash'],content_hash(MANIFEST))

    def test_register_and_claim_reject_stale_source_without_debit(self):
        for version in (1,2):
            for command in ('register','claim'):
                with self.subTest(version=version,command=command),LocalFixture(version) as f:
                    if command=='claim':f.bridge.register()
                    (f.root/'cloud/stub.py').write_bytes(b'value=2\n')
                    before=f.registry.snapshot();saved=dict(f.store._data)
                    with self.assertRaises(ValueError):f.command(command,'research' if command=='claim' else None)
                    self.assertEqual(f.registry.snapshot(),before);self.assertEqual(f.store._data,saved)

    def test_first_prepare_rejects_stale_source_before_input_or_admission(self):
        for version in (1,2):
            with self.subTest(version=version),LocalFixture(version) as f:
                f.bridge.register();attempt=f.bridge.claim('research').attempt_id
                (f.root/'cloud/stub.py').write_bytes(b'value=2\n')
                before=f.registry.snapshot();saved=dict(f.store._data)
                with self.assertRaises(ValueError):cli.prepare(f.bridge,attempt)
                self.assertFalse((f.root/'audit/task_inputs'/f'{attempt}.py').exists())
                self.assertEqual(f.registry.snapshot(),before);self.assertEqual(f.store._data,saved)

    def test_existing_admission_recovery_does_not_read_current_sources(self):
        for version in (1,2):
            with self.subTest(version=version),LocalFixture(version) as f:
                f.bridge.register();attempt=f.bridge.claim('research').attempt_id
                original=cli.prepare(f.bridge,attempt);before=dict(f.store._data)
                (f.root/'cloud/stub.py').unlink();(f.root/'audit/deployment.json').unlink()
                with patch.object(cli,'joint_preflight',side_effect=AssertionError('Current source forbidden')):
                    self.assertEqual(cli.prepare(f.bridge,attempt),original)
                self.assertEqual(f.store._data,before)

    def test_v2_current_source_catalog_identity_still_blocks_new_claim(self):
        with LocalFixture(2) as f:
            f.bridge.register();before=f.registry.snapshot();saved=dict(f.store._data)
            with patch.object(collection_task_cli,'execution_source_manifest',return_value={'source_hash':'f'*64}):
                with self.assertRaises(ValueError):f.command('claim','research')
            self.assertEqual(f.registry.snapshot(),before);self.assertEqual(f.store._data,saved)

class NativeSourceReferenceTests(unittest.TestCase):
    def verifier(self):
        try:module=importlib.import_module('deployment_preflight')
        except ImportError:self.fail('Missing pure native deployment preflight')
        return module.read_project_preflight
    def check(self,tool=None,listing=None,manifest=None,digest=None,input_hash=None):
        return self.verifier()(project_tool() if tool is None else tool,projects() if listing is None else listing,
            MANIFEST if manifest is None else manifest,content_hash(MANIFEST) if digest is None else digest,
            project_id=17,input_sha256=input_hash)
    def test_native_match_outputs_only_metadata_and_never_dispatches(self):
        r=self.check();self.assertTrue(r['source_reference_matches']);self.assertTrue(r['preflight_passed'])
        self.assertFalse(r['ready_to_dispatch']);self.assertFalse(r['worker_source_verified'])
        self.assertFalse(r['full_cloud_inventory_certified']);self.assertNotIn(SECRET,json.dumps(r))
        self.assertNotIn(SOURCE.decode().strip(),json.dumps(r))
    def test_notebook_content_is_not_part_of_source_comparison_or_output(self):
        first=self.check();tool=project_tool();tool['result']['structuredContent']['project']['files'][1]['content']='OTHER_NOTEBOOK_DATA'
        tool['result']['content'][0]['text']=json.dumps(tool['result']['structuredContent'])
        self.assertEqual(self.check(tool),first)
    def test_exact_implementation_hash_normalizes_only_BOM_and_line_endings(self):
        good=project_tool([{'filePath':'stub.py','content':'\ufeffvalue = 1\r\n'}])
        self.assertTrue(self.check(good)['source_reference_matches'])
        for text in ('value = 1','value = 1\n\n','from AlgorithmImports import *\nvalue = 1\n'):
            r=self.check(project_tool([{'filePath':'stub.py','content':text}]))
            self.assertFalse(r['preflight_passed']);self.assertEqual(r['different_paths'],['stub.py'])
    def test_missing_extra_and_changed_reference_never_ready(self):
        for files,field,paths in (([], 'missing_from_returned_reference',['stub.py']),
                ([{'filePath':'stub.py','content':SOURCE.decode()},{'filePath':'extra.py','content':'x=1\n'}],'unexpected_in_returned_reference',['extra.py']),
                ([{'filePath':'stub.py','content':'x=2\n'}],'different_paths',['stub.py'])):
            with self.subTest(field=field):
                r=self.check(project_tool(files));self.assertFalse(r['preflight_passed']);self.assertEqual(r[field],paths)
    def test_explicit_input_binding_uses_exact_UTF8_bytes(self):
        text='TASK_INPUT_JSON = "synthetic"\n';digest=hashlib.sha256(text.encode()).hexdigest()
        files=[{'filePath':'stub.py','content':SOURCE.decode()},{'filePath':'_engineering_task_input.py','content':text}]
        self.assertTrue(self.check(project_tool(files),input_hash=digest)['input_binding_verified'])
        for data in (text.replace('\n','\r\n'),text+'\n'):
            files[1]['content']=data;r=self.check(project_tool(files),input_hash=digest)
            self.assertFalse(r['preflight_passed']);self.assertFalse(r['input_binding_verified'])
        self.assertFalse(self.check(input_hash=digest)['preflight_passed'])
    def test_tool_project_listing_and_internal_identity_are_bound(self):
        for change in ('tool','argument','internal','listing','bool'):
            tool=project_tool();listing=projects()
            if change=='tool':tool['tool_name']='mcp__quantconnect__read_file'
            elif change=='argument':tool['arguments']['projectId']=18
            elif change=='internal':tool['result']['structuredContent']['project']['projectId']=18
            elif change=='listing':listing['result']['structuredContent']['projects']=[]
            else:tool['arguments']['projectId']=True
            with self.subTest(change=change),self.assertRaises(ValueError):self.check(tool,listing)
    def test_duplicate_and_unsafe_paths_are_rejected(self):
        for name in ('../stub.py','/stub.py','a\\stub.py','stub.py\n','C:/stub.py'):
            with self.subTest(name=name),self.assertRaises(ValueError):self.check(project_tool([{'filePath':name,'content':'x'}]))
        for files in ([{'filePath':'stub.py','content':'x'},{'filePath':'stub.py','content':'x'}],
                [{'filePath':'stub.py','content':'x'},{'filePath':'STUB.py','content':'x'}]):
            with self.assertRaises(ValueError):self.check(project_tool(files))
    def test_manifest_and_native_unknown_fields_are_not_silently_ignored(self):
        for manifest,digest in ((MANIFEST,'f'*64),({'stub.py':'bad'},content_hash({'stub.py':'bad'})),
                ({'_engineering_task_input.py':HASH},content_hash({'_engineering_task_input.py':HASH}))):
            with self.subTest(manifest=manifest),self.assertRaises(ValueError):self.check(manifest=manifest,digest=digest)
        tool=project_tool();tool['result']['structuredContent']['project']['rows']=[SECRET]
        with self.assertRaises(ValueError):self.check(tool)
    def test_content_only_structured_only_and_direct_successful_record(self):
        tool=project_tool();forms=[deepcopy(tool),deepcopy(tool),deepcopy(tool)]
        forms[0]['result'].pop('content');forms[1]['result'].pop('structuredContent')
        forms[2]['result']=forms[2]['result']['structuredContent']
        for form in forms:self.assertTrue(self.check(form)['preflight_passed'])
    def test_all_mirrors_errors_and_unregistered_annotations_are_checked(self):
        for change in ('mirror','extra_text','isError','annotations'):
            tool=project_tool()
            if change=='mirror':tool['result']['content'][0]['text']=json.dumps({'success':False})
            elif change=='extra_text':tool['result']['content'].append({'type':'text','text':SECRET})
            elif change=='isError':tool['result']['isError']=True
            else:tool['result']['content'][0]['annotations']={'rows':[SECRET]}
            with self.subTest(change=change),self.assertRaises(ValueError):self.check(tool)

if __name__=='__main__':unittest.main()
