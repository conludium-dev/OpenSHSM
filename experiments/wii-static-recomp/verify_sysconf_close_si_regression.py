"""Replay original SI endpoints with the actual first file CLOSE objects."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/verify_es_close_si_regression.py')
body = parent.read_text().replace('mass-es-close-boot', 'mass-sysconf-close-boot').replace(
    'NEW_ES_CLOSE_OBJECTS_SI16', 'NEW_SYSCONF_CLOSE_OBJECTS_SI16')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
