"""Compare the integer-bit implementation with the entire original raw matrix."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/verify_single_arithmetic_native.py')
body = parent.read_text().replace('dolphin-single-arithmetic', 'dolphin-general-subtract').replace(
    'verify_single_arithmetic_capture.py', 'verify_general_subtract_capture.py').replace(
    'single_arithmetic_probe.cpp', 'general_subtract_probe.cpp').replace(
    'single_arithmetic_adapter.h', 'general_subtract_adapter.h').replace('2048', '1024').replace(
    "destination = 1 if record['operation'] == 0 else 0", 'destination = 0').replace(
    'single division/multiplication', 'general subtraction').replace('Exact two original opcodes', 'Exact EC020028 only')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
