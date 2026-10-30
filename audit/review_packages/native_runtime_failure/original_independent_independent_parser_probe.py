from copy import deepcopy
from pathlib import Path
import hashlib
import json
import sys
import unittest

ROOT=Path(__file__).resolve().parents[3]
WORK=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'cloud'))
from qresearch.artifacts import canonical_json, content_hash
import qresearch.engineering_receipts as parser

ORIGINAL=json.loads((WORK/'native_original.json').read_text(encoding='utf-8'))
ADMISSION=json.loads((WORK/'fixed81/audit/runtime/engineering/admitted-inputs/bfd00f2611fd4496b9498d4597618a8e.json').read_text(encoding='utf-8'))
EXTERNAL='39cafa1e9b11f91b27e396b66d033a6d'
MARKER='The backtest ended with a runtime error.'

def packet(native):
    value=deepcopy(ORIGINAL)
    value['result']['structuredContent']=native
    value['result']['content'][0]['text']=json.dumps(native)
    return value

class IndependentNativeRuntimeFailure(unittest.TestCase):
    def parse(self,value=None,payload=None,deployment=None,external=EXTERNAL):
        method=getattr(parser,'backtest_runtime_failure',None)
        self.assertTrue(callable(method),'Missing strict native runtime failure adapter')
        return method(deepcopy(ADMISSION['payload'] if payload is None else payload),
            deepcopy(ADMISSION['deployment'] if deployment is None else deployment),external,
            deepcopy(ORIGINAL if value is None else value))

    def test_actual_original_projects_failure_only_and_does_not_mutate(self):
        before=canonical_json(ORIGINAL)
        observed=self.parse()
        self.assertEqual(set(observed),{'platform'})
        value=observed['platform']
        self.assertEqual(value['status'],'runtime_error')
        self.assertIs(value['terminal'],True)
        self.assertEqual(value['deployment'],ADMISSION['deployment'])
        self.assertEqual(value['identity'],dict(ADMISSION['payload']['identity'],external_id=EXTERNAL))
        self.assertEqual(value['raw_receipt']['response_sha256'],content_hash(ORIGINAL['result']))
        self.assertEqual(canonical_json(ORIGINAL),before)
        encoded=json.dumps(observed)
        for forbidden in ('Cloud implementation differs','1998-01-01','orders_count','completed','progress','stacktrace'):
            self.assertNotIn(forbidden,encoded)

    def test_default_native_remains_strict_and_public_router_matches(self):
        with self.assertRaises(parser.ReceiptParseError):parser._native(deepcopy(ORIGINAL['result']))
        self.assertEqual(parser.backtest_observation(ADMISSION['payload'],ADMISSION['deployment'],EXTERNAL,
            deepcopy(ORIGINAL),[]),self.parse())

    def test_only_exact_runtime_marker_plus_nonempty_diagnostic_is_supported(self):
        for errors in ([],[MARKER],[MARKER,''],[MARKER,'   '],[MARKER,' '+MARKER+' '],
                ['request timed out'],['internal server error','diagnostic'],
                [MARKER,None],[MARKER,{}],['Runtime Error','diagnostic']):
            with self.subTest(errors=errors),self.assertRaises(parser.ReceiptParseError):
                self.parse(packet({'success':False,'errors':errors}))

    def test_transport_success_and_ambiguous_error_flags_do_not_establish_terminal(self):
        for flag in (False,None,1,'true'):
            value=deepcopy(ORIGINAL); value['result']['isError']=flag
            with self.subTest(flag=flag),self.assertRaises(parser.ReceiptParseError):self.parse(value)
        value=deepcopy(ORIGINAL); del value['result']['isError']
        with self.assertRaises(parser.ReceiptParseError):self.parse(value)
        for success in (True,None,0,'false'):
            value=deepcopy(ORIGINAL['result']['structuredContent']); value['success']=success
            with self.subTest(success=success),self.assertRaises(parser.ReceiptParseError):self.parse(packet(value))

    def test_wrong_project_backtest_tool_or_extra_arguments_are_rejected(self):
        variants=[]
        for name,value in (('projectId',38436696),('projectId',True),('backtestId','different'),('page',1)):
            entry=deepcopy(ORIGINAL);entry['arguments'][name]=value;variants.append(entry)
        entry=deepcopy(ORIGINAL);entry['tool_name']='mcp__quantconnect__create_backtest';variants.append(entry)
        for entry in variants:
            with self.subTest(args=entry['arguments']),self.assertRaises(parser.ReceiptParseError):self.parse(entry)
        with self.assertRaises(parser.ReceiptParseError):self.parse(external='different')

    def test_inconsistent_mirrors_or_extra_output_are_not_terminal_evidence(self):
        entries=[]
        entry=deepcopy(ORIGINAL);entry['result']['content'][0]['text']=json.dumps({'success':False,'errors':['request timed out']});entries.append(entry)
        entry=deepcopy(ORIGINAL);entry['result']['content'].append({'type':'text','text':'extra output'});entries.append(entry)
        entry=deepcopy(ORIGINAL);entry['result']['content'].append({'type':'image','data':'AAAA','mimeType':'image/png'});entries.append(entry)
        entry=deepcopy(ORIGINAL);entry['result']['_meta']={'hidden_rows':[[123]]};entries.append(entry)
        entry=deepcopy(ORIGINAL);entry['result']['content'][0]['annotations']={'rows':[[123]]};entries.append(entry)
        for entry in entries:
            with self.subTest(keys=set(entry['result'])),self.assertRaises(parser.ReceiptParseError):self.parse(entry)

    def test_unknown_native_fields_and_duplicate_text_keys_are_rejected(self):
        for name,value in (('rows',[[123]]),('backtestId',EXTERNAL),('backtest',{}),('status','Runtime Error')):
            native=deepcopy(ORIGINAL['result']['structuredContent']);native[name]=value
            with self.subTest(name=name),self.assertRaises(parser.ReceiptParseError):self.parse(packet(native))
        entry=deepcopy(ORIGINAL);entry['result']['content'][0]['text']='{"success":false,"success":false,"errors":["'+MARKER+'","diagnostic"]}'
        with self.assertRaises(parser.ReceiptParseError):self.parse(entry)

    def test_original_context_input_hash_and_stage_remain_bound(self):
        for key in ('source_manifest_hash','deployment_hash','input_hash'):
            deployment=deepcopy(ADMISSION['deployment']);deployment[key]='wrong'
            with self.subTest(key=key),self.assertRaises(parser.ReceiptParseError):self.parse(deployment=deployment)
        payload=deepcopy(ADMISSION['payload']);payload['identity']['stage']='research'
        with self.assertRaises(parser.ReceiptParseError):self.parse(payload=payload)

if __name__=='__main__':unittest.main(verbosity=2)
