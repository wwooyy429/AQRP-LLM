"""WR14 compatibility probe on the project's fixed Python3.10 environment."""
import sys
from pathlib import Path
from dateutil.parser import isoparse
sys.path.insert(0,str(Path(sys.argv[1])/'cloud'))
from qresearch.engineering_receipts import _annotations
short='2026-10-27T12:34:56.5Z'
padded='2026-10-27T12:34:56.500Z'
assert isoparse(short)==isoparse(padded)
_annotations({'lastModified':padded})
_annotations({'lastModified':'2026-10-27T12:34:56.500000Z'})
print('Equivalent 3/6-digit clocks accepted; validating 1-digit clock',flush=True)
_annotations({'lastModified':short})
print('Equivalent 1-digit clock accepted')
