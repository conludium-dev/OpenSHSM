"""Decode the entire next constructor independently; C is not an FP oracle."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/verify_fp_initializer_ghidra.py')
Path('work/private-game/static-recomp/fp-registration-source/ghidra').mkdir(parents=True,exist_ok=True)
body = parent.read_text().replace('fp-initializer-source','fp-registration-source').replace(
    'shsm-fp-initializer-','shsm-fp-registration-').replace('8000C2F4','80015234').replace(
    ',14,56)',',35,140)').replace('14_INSTRUCTIONS56','35_INSTRUCTIONS140')
exec(compile(body,str(parent),'exec'),{'__file__':__file__})
