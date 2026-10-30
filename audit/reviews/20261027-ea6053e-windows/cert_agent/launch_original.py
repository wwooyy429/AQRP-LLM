"""Bind an unchanged historical audit script to an explicit fixed source tree."""
from pathlib import Path
import argparse, runpy, sys
sys.dont_write_bytecode=True
p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('script',type=Path);p.add_argument('args',nargs=argparse.REMAINDER);a=p.parse_args()
sys.path.insert(0,str(a.source/'cloud'));sys.path.insert(0,str(a.script.parent))
import cert_fixture
cert_fixture.SOURCE=a.source.resolve();cert_fixture.ROOT=a.source.resolve().parent
sys.argv=[str(a.script)]+a.args
runpy.run_path(str(a.script),run_name='__main__')
