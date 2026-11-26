"""Replay original SI against the exact first-DI-OPEN native objects."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/verify_sysconf_complete_si_regression.py')
body = parent.read_text().replace('mass-sysconf-complete-boot', 'mass-di-open-boot').replace(
    'NEW_SYSCONF_COMPLETE_OBJECTS_SI16', 'NEW_DI_OPEN_OBJECTS_SI16')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
