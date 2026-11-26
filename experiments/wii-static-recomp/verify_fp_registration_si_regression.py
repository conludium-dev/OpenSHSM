"""Replay SI through the same module containing the second original constructor."""
from pathlib import Path

parent = Path('experiments/wii-static-recomp/verify_playrecord_dec_si_regression.py')
body = parent.read_text().replace('mass-playrecord-dec-boot','mass-fp-registration-boot').replace(
    'NEW_PLAYRECORD_DEC_OBJECTS_SI16','NEW_FP_REGISTRATION_OBJECTS_SI16')
exec(compile(body,str(parent),'exec'),{'__file__':__file__})
