"""Independent path compatibility check copied from official LEAN source."""
import json
from pathlib import Path
import re

# Official primary source retrieved 2026-10-29:
# https://raw.githubusercontent.com/QuantConnect/Lean/master/Engine/Storage/LocalObjectStore.cs
# _pathRegex line104, SaveBytes gate lines301-303. This is a source contract
# comparison, not proof of the exact binary used by a future QC cloud node.
native=re.compile(r'^\.?[a-zA-Z0-9\\/_#\-\$= ]+\.?[a-zA-Z0-9]*$')
prefix='aqrp/engineering/v2/engineering/pilot/received/'+'a'*32+'/'+'b'*64
cases=[]
for suffix,expected in (('.json.zlib',False),('.zlib',True),('.json',True)):
 actual=native.fullmatch(prefix+suffix) is not None
 assert actual is expected
 cases.append({'suffix':suffix,'accepted_by_current_official_native_regex':actual})
out={'kind':'independent_official_source_path_compatibility_probe','cases':cases,
 'source':'https://raw.githubusercontent.com/QuantConnect/Lean/master/Engine/Storage/LocalObjectStore.cs',
 'future_exact_cloud_binary_authenticated':False,'actual_cloud_calls':0,
 'finding':'Double-extension compressed key is rejected by current public native ObjectStore SaveBytes path gate.'}
Path(__file__).with_name('native_key_compatibility_probe_result.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
print(json.dumps(out))
