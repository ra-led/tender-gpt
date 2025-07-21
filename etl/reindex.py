from pathlib import Path
from shutil import copy
root = Path('/Users/yuratomakov/zakupki-gov/tender-gpt')

files = list(root.glob('*/merged_*')) + list(root.glob('etl/archive/*/merged_*'))

     
for mf in files:
    copy(mf, root / 'etl' / mf.name)
    