"""Replay original SI on actual native CLOSE objects, IPC admission off."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/verify_es_datadir_si_regression.py')
body = parent.read_text().replace('mass-es-datadir-boot', 'mass-es-close-boot').replace('NEW_ES_DATADIR_OBJECTS_SI16', 'NEW_ES_CLOSE_OBJECTS_SI16')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
