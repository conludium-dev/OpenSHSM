"""Replay the original SI oracle using this actual OPEN profile's 125 objects."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/verify_di_burst_cache_si_regression.py')
body = parent.read_text().replace('mass-di-burst-cache-boot','mass-playrecord-open-boot').replace(
    'NEW_DI_BURST_CACHE_OBJECTS_SI16','NEW_PLAYRECORD_OPEN_OBJECTS_SI16')
exec(compile(body,str(parent),'exec'),{'__file__':__file__})
