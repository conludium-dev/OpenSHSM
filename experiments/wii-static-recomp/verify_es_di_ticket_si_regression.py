"""Replay original SI on actual ticket-response objects."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/verify_di_burst_cache_si_regression.py')
body = parent.read_text().replace('mass-di-burst-cache-boot', 'mass-es-di-ticket-boot').replace(
    'NEW_DI_BURST_CACHE_OBJECTS_SI16', 'NEW_ES_DI_TICKET_OBJECTS_SI16')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
