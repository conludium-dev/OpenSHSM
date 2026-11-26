"""Separate protected COW original-disc/profile for DEC observations."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/prepare_playrecord_events_disc.py')
body = parent.read_text().replace('dolphin-playrecord-events','dolphin-playrecord-dec-events')
exec(compile(body,str(parent),'exec'),{'__file__':__file__})
