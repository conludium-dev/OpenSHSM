"""Keep the callback observer in its own protected COW disc and LAB profile."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/prepare_playrecord_start_disc.py')
body = parent.read_text().replace('dolphin-playrecord-start', 'dolphin-playrecord-events')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
