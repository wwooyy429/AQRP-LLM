from pathlib import Path
import sys
sys.dont_write_bytecode=True
D=Path(__file__).resolve().parent
target=D/'check_formal_final.py'
assert not target.exists()
text=(D/'check_formal.py').read_text(encoding='utf-8')
text=text.replace('45cf5e358d210d65945bfa56a6f0ab3568f7c28f9978ce5f13577dafa3add81a','3e8f605973c618ba9aa1761ade0a9901b9fb7003fb609492664621d99c517470')
text=text.replace('formal_QA.json','formal_QA_final.json')
target.write_text(text,encoding='utf-8')
