"""Run sealed certification test methods in fresh local output storage."""
from pathlib import Path
import io
import json
import sys
import types
import unittest

ROOT = Path.cwd()
ORIGINAL = ROOT.parent / "LLM审核" / "review-deb85d9-20261027" / "cert_agent"
OUT = ROOT / ".git/repair-work/wr20_wr21/wr20/independent_suite"
OUT.mkdir(parents=True, exist_ok=True)
fixture = types.ModuleType("cert_fixture")
fixture.__file__ = str(ORIGINAL / "cert_fixture.py")
source = (ORIGINAL / "cert_fixture.py").read_text(encoding="utf-8-sig")
before = "ROOT=Path(__file__).resolve().parents[1];SOURCE=ROOT/'source';"
assert source.count(before) == 1
source = source.replace(before, "ROOT=Path(__file__).resolve().parents[1];SOURCE=Path.cwd();")
exec(compile(source, fixture.__file__, "exec"), fixture.__dict__)
sys.modules["cert_fixture"] = fixture
suite = types.ModuleType("independent_certification_replay")
suite.__file__ = str(ORIGINAL / "independent_certification.py")
source = (ORIGINAL / "independent_certification.py").read_text(encoding="utf-8-sig")
exec(compile(source, suite.__file__, "exec"), suite.__dict__)
suite.O = OUT
suite.PY = sys.executable
stream = io.StringIO()
result = unittest.TextTestRunner(stream=stream, verbosity=2, resultclass=suite.Result).run(
    unittest.defaultTestLoader.loadTestsFromTestCase(suite.Certification))
(OUT / "unittest.txt").write_text(stream.getvalue(), encoding="utf-8")
summary = {"methods": result.testsRun, "passed": len(result.successes),
    "failure_records": len(result.failures), "error_records": len(result.errors),
    "scenarios": len(suite.SCENARIOS), "cloud_or_market_calls": len(suite.NETWORK),
    "adaptations": ["fixture SOURCE points at current checkout", "CLI interpreter uses locked local venv",
        "output O points at fresh ignored folder; original modules loaded without __main__ archive sweep"],
    "failures": [{"test": str(t), "traceback": tb} for t, tb in result.failures],
    "errors": [{"test": str(t), "traceback": tb} for t, tb in result.errors],
    "independent_acceptance": False, "synthetic_replay_only": True}
(OUT / "results.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
print(stream.getvalue())
print(json.dumps(summary))
raise SystemExit(0 if result.wasSuccessful() else 1)
