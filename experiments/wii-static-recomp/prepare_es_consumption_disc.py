"""Separate COW disc/profile for the original ES16 oracle; preserve prior captures."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/prepare_es_di_ticket_disc.py')
body = parent.read_text().replace('dolphin-es-di-ticket', 'dolphin-es-consumption')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
