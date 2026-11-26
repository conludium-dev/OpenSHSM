"""Retest original SI endpoints on the module with verified arithmetic operations."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/verify_playrecord_dec_si_regression.py')
body = parent.read_text().replace('mass-playrecord-dec-boot','mass-single-arithmetic-boot').replace(
    'NEW_PLAYRECORD_DEC_OBJECTS_SI16','NEW_SINGLE_ARITHMETIC_OBJECTS_SI16')
exec(compile(body,str(parent),'exec'),{'__file__':__file__})
