"""Replay original SI against the actual ES16 response objects."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/verify_di_burst_cache_si_regression.py')
body = parent.read_text().replace('mass-di-burst-cache-boot', 'mass-es-consumption-boot').replace(
    'NEW_DI_BURST_CACHE_OBJECTS_SI16', 'NEW_ES_CONSUMPTION_OBJECTS_SI16')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
