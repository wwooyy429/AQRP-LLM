from pathlib import Path
OUT=Path(__file__).resolve().parent
text=(OUT/'independent_recovery.py').read_text(encoding='utf-8').split('class RecoveryTests(unittest.TestCase):',1)[0]
(OUT/'independent_recovery_support.py').write_text(text,encoding='utf-8')
print('Extracted only independently authored fixture/CLI helpers, no test runner')
