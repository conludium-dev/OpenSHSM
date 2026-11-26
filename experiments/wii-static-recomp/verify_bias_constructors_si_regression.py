"""Retest original SI endpoints using the bulk-lowered125-object module."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/verify_playrecord_dec_si_regression.py')
body = parent.read_text().replace('mass-playrecord-dec-boot','mass-bias-constructors-boot').replace(
    'NEW_PLAYRECORD_DEC_OBJECTS_SI16','NEW_BIAS_CONSTRUCTORS_OBJECTS_SI16')
exec(compile(body,str(parent),'exec'),{'__file__':__file__})
