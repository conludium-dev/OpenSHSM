"""Retest SI endpoints using the module containing the register-variant operation."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/verify_playrecord_dec_si_regression.py')
body = parent.read_text().replace('mass-playrecord-dec-boot','mass-bias-register-boot').replace(
    'NEW_PLAYRECORD_DEC_OBJECTS_SI16','NEW_BIAS_REGISTER_OBJECTS_SI16')
exec(compile(body,str(parent),'exec'),{'__file__':__file__})
