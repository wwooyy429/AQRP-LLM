import sys,runpy
from pathlib import Path
s=Path(sys.argv[1]);folder=Path(__file__).parent
sys.path[:0]=[str(s/'cloud'),str(s/'tools'),str(folder)]
import quick_joint_probes as h,independent_cli_gates as f
f.SOURCE=s;h.SOURCE=s
runpy.run_path(str(folder/'minimal_new_success_without_dispatch.py'),run_name='__main__')
