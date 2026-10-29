from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import io,json,sys,unittest,copy,os
sys.dont_write_bytecode=True
import independent_stdio as base
product=base.product
D=Path(__file__).resolve().parent
CASES=[]
def mark(label):CASES.append(label)

class Supplemental(unittest.TestCase):
    def test_imported_main_factory_control_and_clock_override(self):
        with TemporaryDirectory(dir=D) as root:
            h,a=base.fixture(root,fresh=True)
            out=io.StringIO()
            with patch.dict(os.environ,{'SYNTHETIC_STDIO_STORE':root}):
                code=product.main(['serve','--enable-dispatch','--host-factory','independent_stdio:trusted_factory'],input_stream=io.StringIO(json.dumps({'command':'wake','attempt_id':a})+'\n'),output_stream=out)
            self.assertEqual(code,0);self.assertEqual(json.loads(out.getvalue())['action'],'wait_for_delivery')
            self.assertTrue((Path(root)/'factory_called.txt').exists());self.assertFalse(h.store.exists(h._stream(a)))
            mark('canonical_imported_main_accepts_same_valid_factory');mark('imported_main_overrides_factory_future_clock')
    def test_consistent_project_unknown_metadata_carriers_reject(self):
        for field,value in [('hidden_rows',[731.5]),('unknown',True),('transport_grant',{'read_mode':'completion_reads_permitted'})]:
            with TemporaryDirectory(dir=D) as root:
                h,a=base.fixture(root);req=h.prepare(a)
                native={'success':True,'projects':[{'projectId':base.PROJECT,'name':'synthetic','language':'Py'}],field:value}
                result=h.accept_response(base.response(req,base.native(native)))
                self.assertEqual(result['failure_code'],'invalid_native_response')
                self.assertNotIn(field.encode(),h.store.read_bytes(h._stream(a)));mark('consistent_unknown_'+field)
    def test_native_runtime_failure_receipt_handoff_only(self):
        with TemporaryDirectory(dir=D) as root:
            h,a=base.fixture(root,read=True);req=base.prime_read(h,a)
            before=h.store.read_bytes(h.controller.registry.JOURNAL)
            result=base.native({'success':False,'errors':['The backtest ended with a runtime error.','sensitive-native-error-detail']})|{'isError':True}
            status=h.accept_response(base.response(req,result))
            self.assertEqual(status['action'],'awaiting_native_receipt')
            self.assertEqual(h.store.read_bytes(h.controller.registry.JOURNAL),before)
            self.assertNotIn(b'sensitive-native-error-detail',h.store.read_bytes(h._stream(a)))
            mark('native_runtime_error_awaits_original_parser_not_fail_registry');mark('native_error_detail_hash_only')
    def test_inexact_runtime_failure_shapes_reject(self):
        cases=[('not_tool_error',False,['The backtest ended with a runtime error.','detail']),('missing_detail',True,['The backtest ended with a runtime error.']),('wrong_prefix',True,['different error','detail']),('blank_detail',True,['The backtest ended with a runtime error.',' ']),('nonstring_detail',True,['The backtest ended with a runtime error.',True])]
        for label,is_error,errors in cases:
            with TemporaryDirectory(dir=D) as root:
                h,a=base.fixture(root,read=True);req=base.prime_read(h,a)
                result=base.native({'success':False,'errors':errors})
                if is_error:result['isError']=True
                before=h.store.read_bytes(h.controller.registry.JOURNAL)
                status=h.accept_response(base.response(req,result));self.assertEqual(status['failure_code'],'invalid_native_response')
                self.assertEqual(h.store.read_bytes(h.controller.registry.JOURNAL),before);mark('runtime_reject_'+label)

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Supplemental))
    (D/'supplement_results.json').write_text(json.dumps({'methods':result.testsRun,'named_scenarios':len(CASES),'cases':CASES,'failures':[(str(t),s)for t,s in result.failures],'errors':[(str(t),s)for t,s in result.errors],'skips':[(str(t),s)for t,s in result.skipped],'actually_executed':True},indent=2),encoding='utf-8')
    sys.exit(not result.wasSuccessful())
