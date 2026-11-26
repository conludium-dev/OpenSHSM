"""Replay original SI against the actual inquiry-response objects."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/verify_di_burst_cache_si_regression.py')
body = parent.read_text().replace('mass-di-burst-cache-boot', 'mass-di-inquiry-boot').replace(
    'NEW_DI_BURST_CACHE_OBJECTS_SI16', 'NEW_DI_INQUIRY_OBJECTS_SI16')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
