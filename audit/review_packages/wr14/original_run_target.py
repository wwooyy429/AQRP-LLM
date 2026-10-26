from pathlib import Path
import hashlib
import io
import json
import os
import platform
import sys
import time
import unittest

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / 'tests'))
stem = sys.argv[1]
output = root / '.git' / 'repair-work'
stream = io.StringIO()
class Counts(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.subcases = 0
        self.failed_subcases = 0
    def addSubTest(self, test, subtest, err):
        self.subcases += 1
        self.failed_subcases += int(err is not None)
        super().addSubTest(test, subtest, err)
start = time.monotonic()
suite = unittest.defaultTestLoader.loadTestsFromName('test_wr14_fractional_annotations')
result = unittest.TextTestRunner(stream=stream, verbosity=2, resultclass=Counts).run(suite)
(output / (stem + '.stdout')).write_bytes(b'')
(output / (stem + '.stderr')).write_bytes(stream.getvalue().encode('utf-8'))
summary = dict(python=sys.version, executable=sys.executable, methods=result.testsRun,
               subcases=result.subcases, failed_subcases=result.failed_subcases,
               failure_records=len(result.failures), error_records=len(result.errors),
               failed_methods=sorted({str(test.id()) for test, _ in result.failures + result.errors}),
               skipped=len(result.skipped), success=result.wasSuccessful(),
               seconds=time.monotonic() - start,
               test_sha256=hashlib.sha256((root / 'tests/test_wr14_fractional_annotations.py').read_bytes()).hexdigest(),
               source_sha256=hashlib.sha256((root / 'cloud/qresearch/engineering_receipts.py').read_bytes()).hexdigest(),
               actual_market_model_calls=0)
(output / (stem + '-summary.json')).write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
print(json.dumps(summary))
sys.exit(0 if result.wasSuccessful() else 1)
