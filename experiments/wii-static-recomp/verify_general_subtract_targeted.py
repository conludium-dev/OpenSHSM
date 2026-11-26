"""Compare the entire expanded original matrix, including actual startup operands."""
from pathlib import Path

for name in ('verify_general_subtract_capture.py', 'verify_general_subtract_native.py'):
    parent = Path('experiments/wii-static-recomp') / name
    body = parent.read_text().replace('dolphin-general-subtract', 'dolphin-general-subtract-targeted').replace(
        'build_general_subtract_dolphin.py', 'build_general_subtract_targeted.py').replace(
        'run_general_subtract_dolphin.ps1', 'run_general_subtract_targeted.ps1')
    marker = "exec(compile(body, str(parent), 'exec'), {'__file__': __file__})"
    assert body.count(marker) == 1
    body = body.replace(marker, "body = body.replace('1024', '4096').replace('7168', '28672')\n" + marker)
    if name == 'verify_general_subtract_native.py':
        body = body.replace(marker, "body = body.replace(\"subprocess.run(['python3',str(experiment / 'verify_general_subtract_capture.py')],check=True)\", '')\n" + marker)
    exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
