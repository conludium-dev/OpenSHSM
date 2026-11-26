"""Check original word, private harness provenance and operand preservation."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/verify_single_arithmetic_capture.py')
body = parent.read_text().replace('dolphin-single-arithmetic', 'dolphin-general-subtract').replace(
    'build_single_arithmetic_dolphin.py', 'build_general_subtract_dolphin.py').replace(
    'run_single_arithmetic_dolphin.ps1', 'run_general_subtract_dolphin.ps1').replace(
    "['ec220824','ec000072']", "['ec020028']").replace('2048', '1024').replace('14336', '7168').replace(
    "destination = 1 if record['operation'] == 0 else 0", 'destination = 0').replace(
    'ORIGINAL_FDIVS_FMULS', 'ORIGINAL_GENERAL_SUBTRACT').replace('two adjacent observer exits', 'one adjacent observer exit')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
