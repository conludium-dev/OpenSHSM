"""Retest original SI contracts through the actual whole-function-verified module."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/verify_playrecord_dec_si_regression.py')
body = parent.read_text().replace('mass-playrecord-dec-boot', 'mass-divide-initializer-boot').replace(
    'NEW_PLAYRECORD_DEC_OBJECTS_SI16', 'NEW_DIVIDE_INITIALIZER_OBJECTS_SI16')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
