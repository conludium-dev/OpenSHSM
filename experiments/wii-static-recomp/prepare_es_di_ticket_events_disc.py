"""Separate COW original disc/profile for four-request ticket-view observations."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/prepare_di_initialized_disc.py')
body = parent.read_text().replace('dolphin-di-initialized', 'dolphin-es-di-ticket-events')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
