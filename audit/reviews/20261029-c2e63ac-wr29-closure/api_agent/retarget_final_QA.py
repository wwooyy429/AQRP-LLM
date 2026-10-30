from pathlib import Path
ROOT=Path(__file__).resolve().parent
source=(ROOT/'check_formal.py').read_text(encoding='utf-8')
source=source.replace('45cf5e358d210d65945bfa56a6f0ab3568f7c28f9978ce5f13577dafa3add81a','3e8f605973c618ba9aa1761ade0a9901b9fb7003fb609492664621d99c517470')
source=source.replace('formal_QA.json','formal_QA_final.json')
target=ROOT/'check_formal_final.py'
assert not target.exists()
target.write_text(source,encoding='utf-8')
