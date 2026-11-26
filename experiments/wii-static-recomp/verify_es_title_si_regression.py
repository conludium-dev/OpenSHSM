"""Replay original SI on the actual first-title profile objects, IPC admission off."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/verify_es_open_si_regression.py')
body = parent.read_text().replace('mass-es-open-boot', 'mass-es-title-boot').replace('NEW_ES_OPEN_OBJECTS_SI16', 'NEW_ES_TITLE_OBJECTS_SI16')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
