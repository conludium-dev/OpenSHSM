"""Independently check the whole original five-instruction function span."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/verify_fp_initializer_ghidra.py')
Path('work/private-game/static-recomp/divide-initializer-source/ghidra').mkdir(parents=True, exist_ok=True)
body = parent.read_text().replace('fp-initializer-source/ghidra', 'divide-initializer-source/ghidra').replace(
    'shsm-fp-initializer-', 'shsm-divide-initializer-').replace('fn_8000C2F4', 'fn_8013B0C0').replace(
    'auto_fn_8000C2F4_text.o', 'auto_fn_8013B0C0_text.o').replace(',14,56)', ',5,20)').replace(
    'GHIDRA14_INSTRUCTIONS56_BYTES', 'GHIDRA5_INSTRUCTIONS20_BYTES')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
