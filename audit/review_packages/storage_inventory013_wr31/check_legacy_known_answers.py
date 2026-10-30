"""Replay the original 20 literal fixtures with the repaired audit analyzer."""
import importlib.util
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

if __name__ == '__main__':
    tests = load('original_012_literal_cases', HERE.parent/'storage_inventory012/check_analyzer.py')
    tests.MODULE = load('fixed_013_analyzer', HERE/'analyze_inventory.py')
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(tests.InventoryKnownAnswers)
    assert suite.countTestCases() == 20
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
