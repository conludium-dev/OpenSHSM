"""Expand the existing read-only request observer to the complete64-byte startup packet."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/observe_ipc_message_boot.py')
body = parent.read_text().replace('mass-ipc-message-observer', 'mass-ipc-packet64-observer')
body = body.replace('index < 32;', 'index < 64;')
body = body.replace('len(lines[1].split()) == 33', 'len(lines[1].split()) == 65')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
