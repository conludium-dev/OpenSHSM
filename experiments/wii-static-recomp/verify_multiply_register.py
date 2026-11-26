"""Compare the new aliasing operand routing with original captures, not swapped host operands."""
from pathlib import Path
import subprocess

experiment = Path('experiments/wii-static-recomp')
subprocess.run(['python3',str(experiment / 'prepare_multiply_register_component.py')],check=True)
parent = experiment / 'verify_single_arithmetic_capture.py'
body = parent.read_text().replace('dolphin-single-arithmetic','dolphin-multiply-register').replace(
    'build_single_arithmetic_dolphin.py','build_multiply_register_dolphin.py').replace(
    'run_single_arithmetic_dolphin.ps1','run_multiply_register_dolphin.ps1').replace(
    'ec000072','ec010032').replace("record['a'] if record['operation'] == 0 else record['b']","record['a']")
exec(compile(body,str(parent),'exec'),{'__file__':__file__})
parent = experiment / 'verify_single_arithmetic_native.py'
body = parent.read_text().replace('dolphin-single-arithmetic','dolphin-multiply-register').replace(
    "subprocess.run(['python3',str(experiment / 'verify_single_arithmetic_capture.py')],check=True)",'').replace(
    "str(experiment / 'single_arithmetic_probe.cpp')","'work/private-game/static-recomp/multiply-register-component/multiply-register-probe.cpp'").replace(
    "'-I',str(experiment)","'-I','work/private-game/static-recomp/multiply-register-component','-I',str(experiment)")
exec(compile(body,str(parent),'exec'),{'__file__':__file__})
