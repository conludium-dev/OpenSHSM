"""Retest original SI endpoints through the same module with the new multiplier routing."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/verify_playrecord_dec_si_regression.py')
body = parent.read_text().replace('mass-playrecord-dec-boot','mass-multiply-register-boot').replace(
    'NEW_PLAYRECORD_DEC_OBJECTS_SI16','NEW_MULTIPLY_REGISTER_OBJECTS_SI16')
exec(compile(body,str(parent),'exec'),{'__file__':__file__})
