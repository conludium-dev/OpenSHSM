"""Replay original SI on actual ES OPEN profile objects, IPC admission off."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/verify_fs_open_si_regression.py')
body = parent.read_text().replace('mass-fs-open-boot', 'mass-es-open-boot').replace('NEW_FS_OPEN_OBJECTS_SI16', 'NEW_ES_OPEN_OBJECTS_SI16')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
