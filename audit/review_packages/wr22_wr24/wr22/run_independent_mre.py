from pathlib import Path
import contextlib
import hashlib
import io
import json
import runpy
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
REVIEW = Path('B:/BaiduSyncdisk/学习/投资/量化/量化交易比赛/LLM审核/review-ea6053e-20261027/cert_agent')
sys.dont_write_bytecode = True
sys.path[:0] = [str(ROOT / 'cloud'), str(REVIEW)]
import qresearch.data_certification
import cert_fixture
cert_fixture.SOURCE = ROOT
label = sys.argv[1]
sys.argv = [str(REVIEW / 'minimal_wr22.py'), '--output', str(HERE / (label + '_result.json'))]
out, err = io.StringIO(), io.StringIO()
start = time.monotonic()
code = 0
with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
    try:
        runpy.run_path(str(REVIEW / 'minimal_wr22.py'), run_name='__main__')
    except SystemExit as exc:
        code = exc.code
    except BaseException:
        code = 99
        traceback.print_exc()
(HERE / (label + '.stdout')).write_text(out.getvalue(), encoding='utf-8')
(HERE / (label + '.stderr')).write_text(err.getvalue(), encoding='utf-8')
report = {'exit_code':code,'elapsed_seconds':round(time.monotonic()-start,3),
    'source_root':str(ROOT),'actual_imported_production_module':qresearch.data_certification.__file__,
    'original_MRE_raw_sha256':hashlib.sha256((REVIEW/'minimal_wr22.py').read_bytes()).hexdigest(),
    'original_fixture_raw_sha256':hashlib.sha256((REVIEW/'cert_fixture.py').read_bytes()).hexdigest(),
    'current_production_raw_sha256':hashlib.sha256((ROOT/'cloud/qresearch/data_certification.py').read_bytes()).hexdigest(),
    'adaptations':['Preload current shared production module; set fixture SOURCE to current repository',
                   'Output redirected to fresh repair directory; original MRE and fixture bytes unchanged'],
    'new_QC_market_model_or_budget_calls':0,'independent_acceptance':False}
(HERE/(label+'_execution.json')).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report))
