"""Retest original SI endpoint contracts through the current initializer module."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/verify_playrecord_dec_si_regression.py')
body = parent.read_text().replace('mass-playrecord-dec-boot', 'mass-bias-alias-initializer-boot').replace(
    'NEW_PLAYRECORD_DEC_OBJECTS_SI16', 'NEW_BIAS_ALIAS_INITIALIZER_OBJECTS_SI16')
exec(compile(body, str(parent), 'exec'), {'__file__': __file__})
