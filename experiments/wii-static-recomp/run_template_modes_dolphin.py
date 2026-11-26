"""Run owned Dolphin NI-mode template-copy measurements without touching retail data."""
from pathlib import Path
import subprocess

result = subprocess.run(['C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                         '-File', 'experiments/wii-static-recomp/run_template_modes_dolphin.ps1'], capture_output=True, text=True, timeout=180)
Path('work/private-game/static-recomp/dolphin-template-modes/launch.log').write_text(result.stdout + result.stderr)
print(result.stdout, result.stderr, flush=True)
assert result.returncode == 0
