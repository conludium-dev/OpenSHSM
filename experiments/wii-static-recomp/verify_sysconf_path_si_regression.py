"""Replay existing SI oracle using the actual SYSCONF path profile objects."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/verify_es_close_si_regression.py')
body = parent.read_text().replace('mass-es-close-boot', 'mass-sysconf-path-boot').replace(
    'NEW_ES_CLOSE_OBJECTS_SI16', 'NEW_SYSCONF_PATH_OBJECTS_SI16')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
