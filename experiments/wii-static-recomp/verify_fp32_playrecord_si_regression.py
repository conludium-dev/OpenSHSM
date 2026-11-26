"""Replay original SI using the actual FP32 continuation module."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/verify_di_burst_cache_si_regression.py')
body = parent.read_text().replace('mass-di-burst-cache-boot','mass-fp32-playrecord-boot').replace(
    'NEW_DI_BURST_CACHE_OBJECTS_SI16','NEW_FP32_PLAYRECORD_OBJECTS_SI16')
exec(compile(body,str(parent),'exec'),{'__file__':__file__})
