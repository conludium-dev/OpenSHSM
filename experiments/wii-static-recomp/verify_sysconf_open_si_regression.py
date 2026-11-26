"""Replay SI endpoints on the actual async file OPEN profile objects."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/verify_es_close_si_regression.py')
body = parent.read_text().replace('mass-es-close-boot', 'mass-sysconf-open-boot').replace(
    'NEW_ES_CLOSE_OBJECTS_SI16', 'NEW_SYSCONF_OPEN_OBJECTS_SI16')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
