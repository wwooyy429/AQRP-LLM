from pathlib import Path
O=Path(__file__).resolve().parent
qa_source=(O/'formal_QA.py').read_text(encoding='utf-8')
assert qa_source.count('aad0c66f970efe90f53e1877028ab4dbda07778651de66868f4774266b9e82ad')==1
qa_source=qa_source.replace('aad0c66f970efe90f53e1877028ab4dbda07778651de66868f4774266b9e82ad',
                          'ef0fa58a5e87d0930ed7b6c6ddbd11a1b96ecc0ea56678dd7989dbee2a890057')
qa_source=qa_source.replace("O/'formal_QA.json'","O/'formal_QA_final.json'")
exec(compile(qa_source,str(__file__),'exec'),globals())
