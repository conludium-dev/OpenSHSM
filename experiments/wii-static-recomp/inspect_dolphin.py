"""Read existing Windows Dolphin capabilities through the established QA bridge."""
from pathlib import Path
import subprocess

result = subprocess.run(['C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                         '-File', 'experiments/wii-static-recomp/inspect_dolphin.ps1'], capture_output=True, text=True, timeout=30)
Path('work/private-game/static-recomp/dolphin-capabilities.log').write_text(result.stdout + result.stderr)
print(result.stdout, result.stderr)
assert result.returncode == 0
