"""Owned Dolphin process, accurate cache, private boot endpoint."""
from pathlib import Path
import subprocess
result = subprocess.run(['C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                         '-File', 'experiments/wii-static-recomp/run_dcache_probe.ps1'], capture_output=True, text=True, timeout=180)
Path('work/private-game/static-recomp/dolphin-dcache-probe/launch.log').write_text(result.stdout + result.stderr)
print(result.stdout, result.stderr, flush=True)
assert result.returncode == 0
