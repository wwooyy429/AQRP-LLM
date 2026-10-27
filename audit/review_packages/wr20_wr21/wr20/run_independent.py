"""Replay sealed independent WR20 fixture against this checkout, offline only."""
from pathlib import Path
import json
import runpy
import sys
import types

ROOT = Path.cwd()
ORIGINAL = ROOT.parent / "LLM审核" / "review-deb85d9-20261027" / "cert_agent"
module = types.ModuleType("cert_fixture")
module.__file__ = str(ORIGINAL / "cert_fixture.py")
source = (ORIGINAL / "cert_fixture.py").read_text(encoding="utf-8-sig")
before = "ROOT=Path(__file__).resolve().parents[1];SOURCE=ROOT/'source';"
after = "ROOT=Path(__file__).resolve().parents[1];SOURCE=Path.cwd();"
assert source.count(before) == 1
exec(compile(source.replace(before, after), module.__file__, "exec"), module.__dict__)
sys.modules["cert_fixture"] = module
runpy.run_path(str(ORIGINAL / "minimal_wr20.py"), run_name="__main__")
