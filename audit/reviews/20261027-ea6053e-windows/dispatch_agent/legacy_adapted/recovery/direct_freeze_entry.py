"""Second entry point in a fresh process, still calling production freeze."""
from pathlib import Path
import json
import sys
root=Path(sys.argv[1]).resolve()
sys.dont_write_bytecode=True
sys.path[:0]=[str(root/'tools'),str(root/'cloud')]
import stage2
print(json.dumps(stage2.freeze(json.loads(Path(sys.argv[3]).read_text(encoding='utf-8')),plan_file=root/sys.argv[2])))
