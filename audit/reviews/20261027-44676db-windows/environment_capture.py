from pathlib import Path
import hashlib,json,os,platform,sys,importlib.metadata as m
import numpy as np
R=Path(__file__).parent
deps={x:m.version(x)for x in ['numpy','pandas','python-dateutil','pytz','six','tzdata']}
d={'os':platform.platform(),'python':platform.python_version(),'python_full':sys.version,'executable':sys.executable,'dependencies':deps,'numpy_longdouble_mantissa_bits':np.finfo(np.longdouble).nmant,'native_Windows':True,'emulated_other_OS':False,'source_commit':'44676db609b3b7c2175fa7fa4f19c8ccf8165458','isolation':'raw Git archive; tests write derived copies or synthetic stores only','real_QC_Research_LEAN_model_deploy_trading_calls':0}
(R/'environment.json').write_bytes((json.dumps(d,indent=2)+'\n').encode());print(json.dumps(d))
