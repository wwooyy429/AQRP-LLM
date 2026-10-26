"""Byte-level static check supplemental to the dynamic compatibility run."""
from pathlib import Path
import ast, hashlib, json

ROOT = Path(__file__).resolve().parent
OLD = Path(r'C:\Users\11638\.codex\tmp\aqrp-review-7b0dcce-20261026\source')
NEW = ROOT.parent / 'source'

def files(root, dirs):
    return {p.relative_to(root).as_posix(): p for d in dirs for p in (root/d).rglob('*')
            if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}

a, b = files(OLD, ['cloud','config','templates','tools']), files(NEW, ['cloud','config','templates','tools'])
changes = [{'path': r, 'kind': 'added' if r not in a else 'removed' if r not in b else 'changed'}
           for r in sorted(a.keys() | b.keys())
           if r not in a or r not in b or a[r].read_bytes() != b[r].read_bytes()]
dynamic = json.loads((ROOT/'results.json').read_text(encoding='utf-8'))
protected = {r: (OLD/r).read_bytes() == (NEW/r).read_bytes()
             for r in dynamic['static_checks']['protected_hashes_equal']}
tests_a, tests_b = files(OLD, ['tests']), files(NEW, ['tests'])
test_differences = [{'path':r, 'kind':'added' if r not in tests_a else 'removed' if r not in tests_b else 'changed'}
                    for r in sorted(tests_a.keys() | tests_b.keys())
                    if r not in tests_a or r not in tests_b or tests_a[r].read_bytes() != tests_b[r].read_bytes()]
locations = {}
for rel in ['cloud/qresearch/evaluation.py','cloud/qresearch/pipeline.py','cloud/qresearch/models.py']:
    for n in ast.walk(ast.parse((NEW/rel).read_text(encoding='utf-8-sig'))):
        if isinstance(n,(ast.FunctionDef,ast.ClassDef)):
            locations[f'{rel}:{n.name}'] = {'start':n.lineno,'end':n.end_lineno}
out = {'comparison':'7b0dccebef2d3582e1b07ada05211863c3cba0d8..d0b9c98ae9490b977d62f3e9742d854146d298b4',
       'comparison_method':'SHA256/raw bytes; union of paths catches additions/deletions',
       'production_changes':changes,'protected_count':len(protected),'protected_byte_equal':protected,
       'test_differences':test_differences,'source_locations':locations,
       'checked_file_sha256':{r:hashlib.sha256((NEW/r).read_bytes()).hexdigest() for r in protected}}
(ROOT/'static_byte_results.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
assert changes == [{'path':'cloud/qresearch/evaluation.py','kind':'changed'},
                   {'path':'cloud/research_config.py','kind':'changed'}], changes
assert all(protected.values()), protected
assert all(d['kind']=='added' for d in test_differences), test_differences
print(json.dumps({'production_changes':changes,'protected_byte_equal_count':sum(protected.values()),
                  'existing_tests_byte_equal':True,'test_differences':test_differences},ensure_ascii=False))
