"""Independent bounded diagnostic and archived-native probe; no provider calls.

Usage: python -B verify_phase2_scope.py <fixed-source-directory>
Dependencies: the fixed source's requirements-test.txt. Writes only temporary files.
"""
from pathlib import Path
import hashlib,json,sys,tempfile
from unittest.mock import patch
S=Path(sys.argv[1]).resolve();sys.dont_write_bytecode=True
sys.path.insert(0,str(S/'cloud'))
from qresearch.artifacts import content_hash
from qresearch.engineering_data import DeploymentVerificationError,source_bytes_sha256,verify_deployment
from qresearch.engineering_receipts import backtest_observation
checks=[]
with tempfile.TemporaryDirectory(prefix='aqrp-independent-')as directory:
    root=Path(directory);expected=b'VALUE = 1\n';observed=b'VALUE = 2\n'
    manifest={'main.py':hashlib.sha256(expected).hexdigest()}
    (root/'main.py').write_bytes(b'\xef\xbb\xbfVALUE = 1\r\n')
    assert verify_deployment(manifest,content_hash(manifest),source_root=root)==content_hash(manifest)
    assert source_bytes_sha256(expected)!=source_bytes_sha256(expected[:-1])
    checks.append('BOM/CRLF equivalent; EOF newline remains significant')
    (root/'main.py').write_bytes(observed)
    try:verify_deployment(manifest,content_hash(manifest),source_root=root)
    except DeploymentVerificationError as exc:
        assert exc.diagnostics=={'schema_version':1,'failure_kind':'source_hash_mismatch','path':'main.py',
            'expected_sha256':hashlib.sha256(expected).hexdigest(),'observed_sha256':hashlib.sha256(observed).hexdigest()}
        assert 'VALUE' not in str(exc) and str(root)not in str(exc)
    else:raise AssertionError('Changed source was accepted')
    checks.append('Changed source rejected with exact bounded file hashes')
    invalid={'main.py':manifest['main.py'],'../outside.py':'a'*64}
    with patch.object(Path,'read_bytes',side_effect=AssertionError('Source read before complete path validation')):
        try:verify_deployment(invalid,content_hash(invalid),source_root=root)
        except DeploymentVerificationError as exc:assert exc.diagnostics['failure_kind']=='invalid_path'
        else:raise AssertionError('Escaping path was accepted')
    checks.append('Whole manifest validated before any source read')
attempt='bfd00f2611fd4496b9498d4597618a8e'
admission=json.loads((S/('audit/runtime/engineering/admitted-inputs/'+attempt+'.json')).read_bytes())
envelope=json.loads((S/('audit/tool_observations/'+attempt+'-terminal-runtime-error.json')).read_bytes())
observed=backtest_observation(admission['payload'],admission['deployment'],'39cafa1e9b11f91b27e396b66d033a6d',envelope,[])
assert set(observed)=={'platform'} and observed['platform']['terminal']is True
assert observed['platform']['status']=='runtime_error'
assert observed['platform']['raw_receipt']['diagnostic_count']==2
checks.append('Archived native terminal is one runtime failure; no success report')
print(json.dumps({'source':str(S),'passed_probe_chains':len(checks),'checks':checks,'actual_provider_calls':0,
    'registry_writes':0,'financial_evidence':False},ensure_ascii=False))
