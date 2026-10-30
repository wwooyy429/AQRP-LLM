from pathlib import Path
OUT=Path(__file__).resolve().parent
text=(OUT/'independent_annotations.py').read_text(encoding='utf-8').split('class IndependentAnnotationTests(unittest.TestCase):',1)[0]
# Reuse only our independent source/QB/Harness builders, not the test runner.
# Older be94426 lacks the two newly introduced private validators; the workers
# and public receipt parsers used by this helper are available on both versions.
text=text.replace('(_annotations,_text_node,_native,_research_stdout,ReceiptParseError,','(_native,_research_stdout,ReceiptParseError,')
(OUT/'independent_fractional_harness.py').write_text(text,encoding='utf-8')
print('independent_fractional_harness.py generated from independent reviewer code')
